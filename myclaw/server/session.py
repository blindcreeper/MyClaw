"""
MyClaw Server - 多用户 Session 管理

一个 AsyncSqliteSaver + 一个 LangGraph App 被所有用户共享。
通过 thread_id 区分不同用户的对话上下文。
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from myclaw.core.agent import create_agent_app
from myclaw.core.config import DB_PATH

# ====== 用户 Session 数据结构 ======

@dataclass
class UserSession:
    """单个用户的会话状态

    注意：app 和 memory 是所有 session 共享的，不放在这里。
    这里只放每个用户独有、且轻量的信息。
    """
    user_id: int
    thread_id: str            # LangGraph thread_id，如 "qq_12345" 或 "qq_12345_g67890"
    config: dict              # {"configurable": {"thread_id": "qq_12345"}}
    last_active: float        # 最后活跃时间戳，用于过期清理
    is_group: bool
    group_id: Optional[int] = None

# ====== Session 管理器 ======

class SessionManager:
    """
    管理所有 QQ 用户的 Agent 会话

    职责：
    1. 懒加载创建共享的 AsyncSqliteSaver + LangGraph App
    2. 为每个用户分配独立的 thread_id 和 config
    3. 定期清理长时间不活跃的 session
    """

    def __init__(self, provider: str = "aliyun", model: str = "deepseek-v4-flash"):
        self.provider = provider
        self.model = model

        # 共享资源（懒加载，第一次 get_or_create 时才创建）
        self._memory: Optional[AsyncSqliteSaver] = None
        self._memory_ctx: Optional[AsyncSqliteSaver] = None  # 保留引用用于 __aexit__
        self._app = None  # 编译好的 LangGraph StateGraph

        # 用户 session 表：key → UserSession
        self._sessions: Dict[str, UserSession] = {}
        self._lock = asyncio.Lock()

    # ====== 内部辅助 ======

    def _make_key(self, user_id: int, group_id: Optional[int] = None) -> str:
        """
        生成 session 的唯一 key

        隔离策略：
        - 私聊：同一用户的私聊共享上下文 → key = "qq_123:private"
        - 群聊：同一用户在不同群的上下文隔离  → key = "qq_123:group_456"

        这样你在群里聊技术、私聊聊生活，Bot 不会搞混。
        """
        if group_id:
            return f"qq_{user_id}:group_{group_id}"
        return f"qq_{user_id}:private"

    def _make_thread_id(self, user_id: int, group_id: Optional[int] = None) -> str:
        """
        生成 LangGraph 使用的 thread_id

        这个 ID 会出现在：
        - SQLite checkpoint 表（对话历史持久化）
        - 审计日志文件名 logs/{thread_id}.jsonl
        """
        if group_id:
            return f"qq_{user_id}_g{group_id}"
        return f"qq_{user_id}"

    # ====== 核心方法 ======

    async def _ensure_app(self):
        """
        懒加载：第一次有人发消息时，才创建 Agent App

        为什么懒加载？
        - 服务器启动时可能 QQ 还没上线，不急着建 DB 连接
        - import app.py 时不会触发 DB 连接（因为 lifespan 里才调用 SessionManager 构造，
          但构造里也不建连接，只有第一个用户发消息时才建）

        实际上 lifespan 里就构造了 SessionManager，但 _ensure_app 在
        get_or_create 时才调，所以 DB 连接发生在第一个 QQ 消息到达时。
        """
        if self._app is not None:
            return  # 已经初始化过了

        # 创建 AsyncSqliteSaver 并手动进入 async context
        # from_conn_string 返回实例，__aenter__ 创建数据表
        self._memory_ctx = AsyncSqliteSaver.from_conn_string(DB_PATH)
        self._memory = await self._memory_ctx.__aenter__()

        # 编译 LangGraph App（全局共享一个实例）
        self._app = create_agent_app(
            provider_name=self.provider,
            model_name=self.model,
            checkpointer=self._memory,
        )

        print(f"📦 Agent App 已初始化 (DB: {DB_PATH})")

    async def get_or_create(self, user_id: int, group_id: Optional[int] = None) -> UserSession:
        """
        获取或创建用户 session

        Args:
            user_id: QQ 号
            group_id: 群号（私聊时为 None）

        Returns:
            UserSession，包含 thread_id 和 config
        """
        await self._ensure_app()
        key = self._make_key(user_id, group_id)

        async with self._lock:
            if key in self._sessions:
                session = self._sessions[key]
                session.last_active = time.time()
                return session

            # 新用户 → 创建 session
            thread_id = self._make_thread_id(user_id, group_id)
            config = {"configurable": {"thread_id": thread_id}}

            session = UserSession(
                user_id=user_id,
                thread_id=thread_id,
                config=config,
                last_active=time.time(),
                is_group=group_id is not None,
                group_id=group_id,
            )

            self._sessions[key] = session
            print(f"📝 新会话: {key} (thread_id={thread_id})")
            return session

    # ====== 清理方法 ======

    async def cleanup_expired(self, max_idle_seconds: int = 3600):
        """
        清理长时间不活跃的 session

        清理只是从内存字典中移除 UserSession 对象。
        对话历史仍然在 SQLite 里，用户下次发消息时会自动恢复。

        Args:
            max_idle_seconds: 超过这个秒数未活动就清理（默认 1 小时）
        """
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, s in self._sessions.items()
                if now - s.last_active > max_idle_seconds
            ]
            for key in expired_keys:
                s = self._sessions.pop(key)
                print(f"🧹 清理过期会话: {key} (空闲 {now - s.last_active:.0f}s)")

    async def close_all(self):
        """关闭共享的 AsyncSqliteSaver（服务关闭时调用）"""
        if self._memory_ctx:
            await self._memory_ctx.__aexit__(None, None, None)
            print("📦 DB 连接已关闭")

        # ====== 查询方法 ======

    @property
    def active_count(self) -> int:
        """当前活跃 session 数（管理面板用）"""
        return len(self._sessions)

    def get_app(self):
        """获取共享的 LangGraph App（ws_handler 调用时用）"""
        return self._app
