"""
MyClaw Server - OneBot v11 协议处理器

职责：
1. 接收 NapCat WebSocket 连接，解析 OneBot v11 JSON 事件
2. 私聊消息 → 直接调用 Agent
3. 群聊消息 → 仅 @Bot 时调用 Agent
4. 好友请求 → 自动通过 + 发欢迎消息
5. Agent 流式输出 → 分片发送回 QQ（模拟打字效果）
"""
import os
import re
import json
import time
import asyncio
import base64
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
import httpx
from langchain_core.messages import HumanMessage

from .models import (
    OneBotMessageEvent,
    OneBotRequestEvent,
    OneBotNoticeEvent,
    OneBotHeartbeatEvent,
    QQMessage,
)
from .session import SessionManager
from myclaw.core.tools.builtins import current_user_id


# ====== 配置常量 ======
NAPCAT_HTTP_URL = os.getenv("NAPCAT_HTTP_URL", "http://127.0.0.1:3000")

# 分片发送参数
CHUNK_SIZE = 50          # 每 50 字发一次
CHUNK_INTERVAL = 0.5     # 分片间隔（秒）
MAX_REPLY_LENGTH = 2000  # QQ 单条消息上限

class OneBotHandler:
    """OneBot v11 协议处理器"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

        # 运行时状态（handle() 被调用时初始化）
        self._http_client: Optional[httpx.AsyncClient] = None
        self._bot_self_id: Optional[int] = None  # Bot 自己的 QQ 号
        self._napcat_url: str = NAPCAT_HTTP_URL

    # ==================================================================
    # 主入口
    # ==================================================================

    async def handle(self, websocket: WebSocket):
        """
        WebSocket 主循环

        NapCat 连接后，这里会一直循环，接收 JSON 事件 → 分发处理。
        如果 WebSocket 断开（QQ 关闭或 NapCat 崩溃），循环退出。
        """
        await websocket.accept()
        print("🔌 NapCat WebSocket 已连接")

        # WebSocket 连上说明 NapCat 在线，此时创建 HTTP 客户端
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"⚠️ 无效 JSON: {raw[:100]}")
                    continue

                # 快速分发，不让其他事件阻塞消息处理
                asyncio.create_task(self._dispatch(event))

        except WebSocketDisconnect:
            print("🔌 NapCat WebSocket 断开")
        except Exception as e:
            print(f"⚠️ WebSocket 异常: {e}")
        finally:
            if self._http_client:
                await self._http_client.aclose()
                self._http_client = None

    async def _dispatch(self, event: dict):
        """根据 post_type 路由到对应处理函数"""
        post_type = event.get("post_type", "")

        if post_type == "message":
            await self._handle_message(event)
        elif post_type == "notice":
            await self._handle_notice(event)
        elif post_type == "meta_event":
            await self._handle_meta(event)
        elif post_type == "request":
            await self._handle_request(event)
        # 其他类型静默忽略

    # ==================================================================
    # 消息处理（核心）
    # ==================================================================
    async def _handle_message(self, event: dict):
        """处理私聊/群聊消息"""
        msg = OneBotMessageEvent(**event)
        self._bot_self_id = msg.self_id  # 更新 Bot QQ 号

        # -------- 第 1 步：提取纯文本 --------
        raw_text = self._extract_text(msg)
        if not raw_text:
            return

        # -------- 第 2 步：群聊 @ 过滤 --------
        if msg.message_type == "group":
            if not self._is_at_me(msg):
                return  # 没 @Bot，不回复
            raw_text = self._remove_at(raw_text, msg.self_id)
            if not raw_text.strip():
                return  # @了但没说话

        # -------- 第 3 步：标准化为 QQMessage --------
        qq_msg = QQMessage()
        qq_msg.user_id = msg.user_id
        qq_msg.message_id = msg.message_id
        qq_msg.raw_text = raw_text.strip()
        qq_msg.is_group = (msg.message_type == "group")
        qq_msg.group_id = msg.group_id
        qq_msg.sender_name = msg.sender.card or msg.sender.nickname
        qq_msg.image_urls = self._extract_images(msg)

        # -------- 第 4 步：调用 Agent --------
        if qq_msg.image_urls:
            print(f"📩 [{qq_msg.sender_name}] {qq_msg.raw_text[:40] or '(图片消息)'} + {len(qq_msg.image_urls)}张图")
        else:
            print(f"📩 [{qq_msg.sender_name}] {qq_msg.raw_text[:80]}")
        await self._process_with_agent(qq_msg)

    # -------- 文本提取 --------

    def _extract_text(self, msg: OneBotMessageEvent) -> str:
        """
        从 OneBot message 字段提取纯文本

        OneBot 的 message 字段有两种格式：
        - 纯文本:  "你好"  (message_type=str)
        - CQ 码数组: [{"type":"text","data":{"text":"你好"}},
                       {"type":"at","data":{"qq":"123456"}}]

        CQ 码数组是更常见的情况，因为 QQ 消息经常包含图片、表情、
        @ 等富媒体。这里只提取 text 片段，忽略图片、表情等。
        """
        if isinstance(msg.message, str):
            return msg.message
        if isinstance(msg.message, list):
            parts = []
            for seg in msg.message:
                if seg.get("type") == "text":
                    parts.append(seg.get("data", {}).get("text", ""))
            return "".join(parts)
        # 兜底：用 raw_message
        return msg.raw_message or ""

    # -------- @ 检测 --------

    def _is_at_me(self, msg: OneBotMessageEvent) -> bool:
        """
        检查消息是否 @了 Bot

        两种检测方式（任一种匹配即可）：
        1. CQ 码数组中有 type="at" 且 qq=self_id
        2. raw_message 中包含 [CQ:at,qq=self_id]
        """
        # 方式 1: 遍历 CQ 码数组
        if isinstance(msg.message, list):
            for seg in msg.message:
                if seg.get("type") == "at":
                    at_qq = str(seg.get("data", {}).get("qq", ""))
                    if at_qq == str(msg.self_id):
                        return True

        # 方式 2: 检查文本形式的 @
        target_at = f"[CQ:at,qq={msg.self_id}]"
        if target_at in msg.raw_message:
            return True

        return False

    def _remove_at(self, text: str, self_id: int) -> str:
        """去除消息中的 @Bot CQ 码，保留用户真正说的话"""
        # 移除 [CQ:at,qq=xxx] 及其前后的空格
        text = re.sub(rf'\s*\[CQ:at,qq={self_id}\]\s*', '', text)
        # 也处理结尾的 @（有些客户端会把 @ 放最后）
        text = re.sub(rf'\s*@.*?\s*$', '', text)
        return text.strip()

    # -------- 图片提取 --------

    def _extract_images(self, msg: OneBotMessageEvent) -> list[str]:
        """
        从 OneBot CQ 码数组中提取图片 URL

        QQ 图片 CQ 码格式:
        {"type":"image", "data":{"file":"xxx.jpg", "url":"http://gchat.qpic.cn/..."}}

        返回所有图片的原始 URL 列表。
        """
        urls = []
        if isinstance(msg.message, list):
            for seg in msg.message:
                if seg.get("type") == "image":
                    url = seg.get("data", {}).get("url", "")
                    if url:
                        urls.append(url)
        # raw_message 中的 [CQ:image,...] 格式也检查
        if not urls and msg.raw_message:
            for match in re.finditer(r'\[CQ:image,.*?url=([^\],]+)', msg.raw_message):
                urls.append(match.group(1))
        return urls

    async def _download_and_encode_images(self, urls: list[str]) -> list[dict]:
        """
        下载图片并编码为 base64 data URL

        Args:
            urls: 图片 URL 列表

        Returns:
            [{"mime_type": "image/jpeg", "data_url": "data:image/jpeg;base64,..."}, ...]
            下载失败的图片会被跳过
        """
        results = []
        if not self._http_client:
            return results

        for i, url in enumerate(urls):
            try:
                resp = await self._http_client.get(url, follow_redirects=True,
                    timeout=httpx.Timeout(15.0))
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    # 清理 content-type（可能带 charset）
                    mime_type = content_type.split(";")[0].strip()
                    b64_data = base64.b64encode(resp.content).decode("ascii")
                    data_url = f"data:{mime_type};base64,{b64_data}"
                    results.append({
                        "mime_type": mime_type,
                        "data_url": data_url,
                    })
                    kb = len(resp.content) / 1024
                    print(f"  🖼️ 图片 {i+1}/{len(urls)} 已下载: {kb:.0f} KB ({mime_type})")
                else:
                    print(f"  ⚠️ 下载图片 {i+1} 失败: HTTP {resp.status_code}")
            except httpx.TimeoutException:
                print(f"  ⚠️ 下载图片 {i+1} 超时")
            except Exception as e:
                print(f"  ⚠️ 下载图片 {i+1} 异常: {e}")

        return results

    # ==================================================================
    # Agent 调用 + 分片回复（最核心）
    # ==================================================================

    async def _process_with_agent(self, qq_msg: QQMessage):
        """
        调用 LangGraph Agent 处理消息，并流式发送回复到 QQ

        流程：
        SessionManager 按 QQ 号分配 thread_id → Agent astream
        → 文本进入缓冲区 → 分片发送回 QQ

        关于 astream 的 stream_mode="updates":
        - agent 节点吐出 AIMessage 时触发
        - tools 节点吐出 ToolMessage 时触发
        - 每次 agent 输出可能是 纯文本 或 tool_calls，不同时出现
        """
        # 1. 获取 Session
        session = await self.session_manager.get_or_create(qq_msg.user_id, qq_msg.group_id if qq_msg.is_group else None)
        app = self.session_manager.get_app()

        # 设置当前用户上下文（builtins 工具用）
        t = current_user_id.set(qq_msg.user_id)


        # 2. 构建输入（多模态：文本 + 图片）
        if qq_msg.image_urls:
            encoded_images = await self._download_and_encode_images(qq_msg.image_urls)
            content: list = [{"type": "text", "text": qq_msg.raw_text or "请描述这张图片的内容"}]
            for img in encoded_images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img["data_url"]}
                })
            human_msg = HumanMessage(content=content)
        else:
            human_msg = HumanMessage(content=qq_msg.raw_text)

        inputs = {"messages": [human_msg]}

        # 3. 流式处理
        full_text = ""
        buffer = ""
        last_send = 0.0

        try:
            async for chunk in app.astream(inputs, config=session.config, stream_mode="updates"):
                for node_name, node_data in chunk.items():
                    if node_name == "agent":
                        last_msg = node_data["messages"][-1]
                        # ----- 情况 A: 纯AI 文本回复 -----
                        if(hasattr(last_msg, "content") and last_msg.content and 
                           not last_msg.tool_calls):
                            buffer += last_msg.content
                            now = time.time()

                            # 判断是否需要发送
                            should_send =(
                                len(buffer) >= CHUNK_SIZE or
                                "\n" in buffer or 
                                (buffer and now - last_send >= 1.5)
                            )

                            if should_send:
                                full_text += buffer
                                await self._send_qq_message(qq_msg, buffer)
                                buffer = ""
                                last_send = now

                        # ----- 情况 B: 工具调用 -----
                        elif (
                            hasattr(last_msg, "tool_calls")
                            and last_msg.tool_calls
                        ):
                            # 先清空文本缓冲区
                            if buffer:
                                full_text += buffer
                                await self._send_qq_message(qq_msg, buffer)
                                buffer = ""

                            for tc in last_msg.tool_calls:
                                tool_name = tc.get("name", "unknown")
                                print(f"  🔧 Tool: {tool_name}")
                                await self._send_qq_message(
                                    qq_msg, f"🔧 正在执行: {tool_name}..."
                                ) 
            # 4. 发送剩余文本
            if buffer:
                full_text += buffer
                await self._send_qq_message(qq_msg, buffer)

            # 5. 兜底：如果全程无输出（纯工具调用后 LLM 没说话）
            if not full_text.strip():
                await self._send_qq_message(qq_msg, "✅ 处理完成")

        except Exception as e:
            import traceback
            traceback.print_exc()
            await self._send_qq_message(
                qq_msg, f"⚠️ 发生错误: {str(e)[:150]}"
            )

    # ==================================================================
    # QQ 消息发送
    # ==================================================================

    async def _send_qq_message(self, qq_msg: QQMessage, content: str):
        """
        通过 NapCat HTTP API 发送 QQ 消息

        NapCat HTTP API:
        - POST /send_private_msg  → {"user_id": ..., "message": ...}
        - POST /send_group_msg    → {"group_id": ..., "message": ...}

        auto_escape=False 表示不转义 CQ 码，让 QQ 正常渲染文本。
        """
        if not content or not self._http_client:
            return

        # 截断超长消息
        if len(content) > MAX_REPLY_LENGTH:
            content = content[:MAX_REPLY_LENGTH - 15] + "…\n(消息过长已截断)"

        
        try:
            if qq_msg.is_group:
                endpoint = f"{self._napcat_url}/send_group_msg"
                payload = {
                    "group_id": qq_msg.group_id,
                    "message": content,
                    "auto_escape": False,
                }
            else:
                endpoint = f"{self._napcat_url}/send_private_msg"
                payload = {
                    "user_id": qq_msg.user_id,
                    "message": content,
                    "auto_escape": False,
                }

            
            resp = await self._http_client.post(endpoint, json=payload)
            if resp.status_code != 200:
                print(f"  ⚠️ NapCat API 返回 {resp.status_code}: {resp.text[:100]}")

        except httpx.TimeoutException:
            print(f"  ⚠️ NapCat API 超时 (>{15}s)")
        except Exception as e:
            print(f"  ⚠️ 发送 QQ 消息失败: {e}")

    async def _send_private_message(self, user_id: int, content: str):
        """
        发送私聊消息（不依赖 QQMessage 对象）

        用于系统通知场景：新好友欢迎、错误提示等。
        """
        if not self._http_client:
            return
        try:
            await self._http_client.post(
                f"{self._napcat_url}/send_private_msg",
                json={"user_id": user_id, "message": content, "auto_escape": False},
            )
        except Exception as e:
            print(f"  ⚠️ 发送系统消息失败: {e}")

    # ==================================================================
    # 通知事件
    # ==================================================================

    async def _handle_notice(self, event: dict):
        """处理通知事件"""
        notice_type = event.get("notice_type", "")

        if notice_type == "friend_add":
            user_id = event.get("user_id", 0)
            print(f"👤 新好友: {user_id}")
            await self._send_private_message(
                user_id,
                "👋 你好！我是 MyClaw，你的 AI 助手。\n直接发消息就能跟我聊天，试试问我一个问题吧~",
            )

        # 群成员增加等其他通知可以在这里扩展

    # ==================================================================
    # 元事件（心跳）
    # ==================================================================

    async def _handle_meta(self, event: dict):
        """处理元事件"""
        meta_type = event.get("meta_event_type", "")

        if meta_type == "heartbeat":
            self._bot_self_id = event.get("self_id")
            # 首次心跳时打印
            if not hasattr(self, "_heartbeat_printed"):
                self._heartbeat_printed = True
                print(f"💓 心跳正常 | Bot QQ: {self._bot_self_id}")

    # ==================================================================
    # 请求事件（好友申请）
    # ==================================================================

    async def _handle_request(self, event: dict):
        """处理好友请求——自动通过"""
        if event.get("request_type") == "friend":
            req = OneBotRequestEvent(**event)
            print(f"📩 好友请求: {req.user_id} (备注: {req.comment})")

            if self._http_client:
                try:
                    resp = await self._http_client.post(
                        f"{self._napcat_url}/set_friend_add_request",
                        json={
                            "flag": req.flag,
                            "approve": True,
                            "remark": "",
                        },
                    )
                    if resp.status_code == 200:
                        print(f"✅ 已通过好友请求: {req.user_id}")
                    else:
                        print(f"⚠️ 通过好友请求失败: {resp.text[:100]}")
                except Exception as e:
                    print(f"⚠️ 处理好友请求异常: {e}")