"""
MyClaw Server - 管理 API

GET /api/health  → 服务状态（无需认证）
GET /api/skills  → 技能列表（需 Token 认证）
"""
import time
from fastapi import APIRouter, Depends
from myclaw.core.skill_loader import load_dynamic_skills
from myclaw.server.auth import verify_admin_token
from myclaw.server.models import HealthResponse, SkillInfo

# 注意：这里 import 模块而非变量名，
# 因为 lifespan 会更新 app.py 的全局变量，
# 用模块属性访问才能读到最新值
import myclaw.server.app as server_app

router = APIRouter(prefix="/api", tags=["管理"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    服务健康检查

    返回服务运行状态、运行时长、活跃 session 数、QQ 在线状态。
    无需认证——监控面板、探活脚本都可以直接调。

    示例响应:
    {
        "status": "ok",
        "uptime": 1234.5,
        "active_sessions": 3,
        "qq_online": true
    }
    """
    sm = server_app.session_manager
    oh = server_app.onebot_handler
    return HealthResponse(
        status="ok",
        uptime=round(time.time() - server_app.start_time, 1),
        active_sessions=sm.active_count if sm else 0,
        qq_online=oh._bot_self_id is not None if oh else False,
    )


@router.get("/skills", response_model=list[SkillInfo])
async def list_skills(_auth=Depends(verify_admin_token)):
    """
    获取所有已加载的技能列表

    需要 Bearer Token 认证: Authorization: Bearer <MYCLAW_ADMIN_TOKEN>

    调用 load_dynamic_skills() 扫描 workspace/office/skills/ 目录下的技能，
    返回每个技能的 name、description、所属文件夹。

    示例响应:
    [
        {"name": "weather", "description": "查询天气信息", "folder": "weather"},
        {"name": "translate", "description": "多语言翻译", "folder": "translate"}
    ]
    """
    try:
        tools = load_dynamic_skills()
    except Exception as e:
        tools = []
        print(f"⚠️ 加载技能列表失败: {e}")

    return [
        SkillInfo(
            name=tool.name,
            description=tool.description[:200],  # 描述可能很长，截断
            folder=getattr(tool, "name", ""),
        )
        for tool in tools
    ]