"""
MyClaw Server - 数据模型
OneBot v11 事件模型 + 内部消息模型 + API 响应模型
"""
from pydantic import BaseModel
from typing import Optional, Any


# ====== OneBot v11 事件模型 ======
# 参考: https://docs.onebot.dev/v11/event/

class OneBotSender(BaseModel):
    """消息发送者信息"""
    user_id: int
    nickname: str = ""
    card: str = ""          # 群名片（仅群聊时有值）
    sex: str = "unknown"    # male/female/unknown
    age: int = 0
    role: str = "member"    # owner/admin/member

class OneBotMessageEvent(BaseModel):
    """
    OneBot v11 message.private / message.group 事件

    NapCat WebSocket 推送的原始 JSON 结构。
    私聊: message_type="private", 有 user_id，无 group_id
    群聊: message_type="group", 有 user_id + group_id
    """
    time: int
    self_id: int            # Bot 自己的 QQ 号
    post_type: str          # "message" / "notice" / "meta_event" / "request"
    message_type: str       # "private" / "group"
    sub_type: str           # "friend" / "normal" / "anonymous" / "group"
    message_id: int
    user_id: int            # 发送者 QQ 号
    group_id: Optional[int] = None
    message: Any            # 消息内容: str (纯文本) 或 list[dict] (CQ 码数组)
    raw_message: str        # 纯文本消息
    sender: OneBotSender

class OneBotRequestEvent(BaseModel):
    """OneBot v11 好友请求 / 群邀请事件"""
    time: int
    self_id: int
    post_type: str          # "request"
    request_type: str       # "friend" / "group"
    user_id: int
    comment: str = ""       # 验证消息
    flag: str               # 处理请求用的标识符

class OneBotNoticeEvent(BaseModel):
    """OneBot v11 通知事件（好友添加等）"""
    time: int
    self_id: int
    post_type: str          # "notice"
    notice_type: str        # "friend_add" / "group_increase" / ...
    user_id: int

class OneBotHeartbeatEvent(BaseModel):
    """OneBot v11 心跳事件"""
    time: int
    self_id: int
    post_type: str          # "meta_event"
    meta_event_type: str    # "heartbeat"
    status: dict = {}

# ====== 内部消息模型 ======

class QQMessage:
    """
    标准化 QQ 消息，屏蔽 OneBot 协议细节

    不管原始 JSON 长什么样，ws_handler 统一转成这个对象，
    后续 Agent 处理只跟这个对象打交道。
    """
    user_id: int = 0
    message_id: int = 0
    raw_text: str = ""           # 纯文本（已去除 @Bot、CQ 码）
    is_group: bool = False
    group_id: Optional[int] = None
    sender_name: str = ""        # 昵称或群名片
    image_urls: list = []        # 图片 URL 列表（从 CQ 码提取）

    def __repr__(self):
        scope = f"群{self.group_id}" if self.is_group else "私聊"
        return f"<QQMessage {self.user_id}({self.sender_name}) [{scope}]: {self.raw_text[:50]}>"

# ====== API 响应模型 ======

class HealthResponse(BaseModel):
    """GET /api/health 响应"""
    status: str             # "ok" 或 "degraded"
    uptime: float           # 运行秒数
    active_sessions: int    # 当前活跃 session 数
    qq_online: bool         # QQ Bot 是否在线

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "uptime": 1234.5,
                "active_sessions": 3,
                "qq_online": True
            }
        }

class SkillInfo(BaseModel):
    """GET /api/skills 响应中的单个技能"""
    name: str
    description: str
    folder: str = ""        # 技能文件夹名（如 "weather"）

class ErrorResponse(BaseModel):
    """通用错误响应"""
    detail: str
