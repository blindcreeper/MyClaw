"""
MyClaw Server - 管理面板 Token 认证
"""
import os
from fastapi import Header, HTTPException

# 从 .env 读取，默认值仅用于本地开发
ADMIN_TOKEN = os.getenv("MYCLAW_ADMIN_TOKEN", "myclaw-admin-2026")

def verify_admin_token(authorization: str = Header(...)) -> bool:
    """
    管理面板 API 认证依赖

    用法（在路由里）：
        @router.get("/api/skills")
        async def list_skills(_auth=Depends(verify_admin_token)):
            ...

    前端请求时带上 Header:
        Authorization: Bearer myclaw-admin-2026
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证信息")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证格式错误，应为 Bearer <token>")

    token = authorization.removeprefix("Bearer ")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token 无效")

    return True 