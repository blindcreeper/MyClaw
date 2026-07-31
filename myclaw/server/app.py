"""
MyClaw Server - FastAPI 主应用
启动: python -m myclaw.server
"""
import os
import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 确保项目根目录在 path 中（从 myclaw/server/ 向上两级）
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))       # myclaw/server/
PACKAGE_DIR = os.path.dirname(SERVER_DIR)                      # myclaw/
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)                    # D:\sxxm\MyClaw\

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -------- 全局单例（lifespan 里初始化）--------
session_manager = None       # SessionManager 实例
onebot_handler = None        # OneBotHandler 实例
start_time: float = 0.0      # 服务启动时间戳

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    - 启动时: 加载配置 → 初始化 SessionManager → 打印启动信息
    - 关闭时: 清理所有 session → 关闭 HTTP 客户端
    """
    global session_manager, onebot_handler, start_time

    # 加载 .env（server 子包也能读到的路径）
    from dotenv import load_dotenv
    env_path = os.path.join(PROJECT_ROOT, ".env")
    load_dotenv(env_path)

    provider = os.getenv("DEFAULT_PROVIDER", "aliyun")
    model = os.getenv("DEFAULT_MODEL", "deepseek-v4-flash")

    # 初始化session管理器
    from .session import SessionManager
    session_manager = SessionManager(provider, model)

    # 初始化OneBotHandler
    from .ws_handler import OneBotHandler
    onebot_handler = OneBotHandler(session_manager)

    start_time = time.time()

    print()
    print(f"🚀 MyClaw Server 已启动")
    print(f"   Provider: {provider}  |  Model: {model}")
    print(f"   OneBot WS:   ws://127.0.0.1:9910/ws/onebot")
    print(f"   管理面板:    http://localhost:9910")
    print(f"   健康检查:    http://localhost:9910/api/health")
    print()

    yield

    # ====== 关闭清理 ======
    await session_manager.close_all()
    if onebot_handler and onebot_handler._http_client:
        await onebot_handler._http_client.aclose()
    print("👋 MyClaw Server 已关闭")

# -------- 创建 FastAPI 应用 --------
app = FastAPI(
    title="MyClaw Server",
    version="0.1.0",
    description="MyClaw QQ Bot 后端 — OneBot v11 + LangGraph Agent",
    lifespan=lifespan,
)

# -------- CORS --------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 本地开发宽松，部署时收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- WebSocket: OneBot v11 --------
@app.websocket("/ws/onebot")
async def ws_onebot(websocket: WebSocket):
    """
    NapCat 通过 WebSocket 连接此端点，发送 OneBot v11 事件

    流程: NapCat 连接 → 循环 receive JSON → dispatch → Agent → HTTP API 回复 QQ
    """
    await onebot_handler.handle(websocket)

# -------- 管理 API 路由 --------
from .routes.admin import router as admin_router
from .routes.monitor import router as monitor_router

app.include_router(admin_router)
app.include_router(monitor_router)

# -------- 管理面板静态文件（可选）--------
WEB_DIR = os.path.join(PROJECT_ROOT, "web-admin", "dist")
if os.path.exists(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web-admin")
    print(f"📦 管理面板已挂载: {WEB_DIR}")