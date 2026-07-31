"""
MyClaw Server - SSE 审计日志实时推送

GET /api/monitor/stream  → SSE 流，实时推送最新日志行

类似 tail -f logs/*.jsonl，通过 Server-Sent Events 推送到浏览器。
管理面板的 MonitorView 连接这个端点，实时看到 Agent 的各项活动。
"""
import os
import asyncio
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api", tags=["监控"])

# 计算日志目录的绝对路径
# monitor.py 位置: myclaw/server/routes/monitor.py
# 向上三级: routes → server → myclaw → project_root
ROUTES_DIR = os.path.dirname(os.path.abspath(__file__))   # routes/
SERVER_DIR = os.path.dirname(ROUTES_DIR)                    # server/
MYCLAW_DIR = os.path.dirname(SERVER_DIR)                    # myclaw/
PROJECT_ROOT = os.path.dirname(MYCLAW_DIR)                  # D:\sxxm\MyClaw\

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

async def log_streamer():
    """
    SSE 日志流生成器

    每隔 1 秒检查所有 .jsonl 日志文件的新增行，推送给客户端。

    设计要点：
    - last_positions 字典记录每个文件的已读位置，重启客户端也能从新行开始
    - 新建的日志文件会自动被发现和追踪
    - 使用 asyncio.sleep 而非文件系统的 inotify（Windows 兼容）
    """
    last_positions: dict[str, int] = {}

    while True:
        try:
            log_files = list(Path(LOG_DIR).glob("*.jsonl"))

            for fpath in log_files:
                fkey = str(fpath)

                if fkey not in last_positions:
                  try:
                    last_positions[fkey] = fpath.stat().st_size
                  except FileNotFoundError:
                    continue

                # 文件被截断（轮转）：重新从开头读
                try:
                    current_size = fpath.stat().st_size
                except FileNotFoundError:
                    last_positions.pop(fkey, None)
                    continue

                if current_size < last_positions[fkey]:
                    last_positions[fkey] = 0  # 文件被清空或轮转

                # 有新内容
                if current_size > last_positions[fkey]:
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            f.seek(last_positions[fkey])
                            for line in f:
                                line = line.strip()
                                if line:
                                    yield f"data: {line}\n\n"
                    except (FileNotFoundError, PermissionError):
                        pass  # 文件被删除或无权限，跳过

                    # 更新位置（即使读取失败也更新，避免死循环）
                    try:
                        last_positions[fkey] = fpath.stat().st_size
                    except FileNotFoundError:
                        last_positions.pop(fkey, None)

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            break  # 客户端断开连接
        except Exception as e:
            # 发送错误事件而不是中断流
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
            await asyncio.sleep(2.0)


@router.get("/monitor/stream")
async def monitor_stream():
    """
    SSE 实时日志流端点

    连接后持续推送 JSONL 日志行，格式为 SSE 标准：
        data: {"ts":"...","thread_id":"...","event":"...","content":"..."}
        <空行>

    前端使用 EventSource 接收：
        const source = new EventSource('/api/monitor/stream');
        source.onmessage = (e) => {
            const log = JSON.parse(e.data);
            // 渲染日志行
        };

    注意：此端点目前无认证。本地局域网使用场景下风险可控。
    如需外网部署，建议加上 Token 认证参数。
    """
    return StreamingResponse(
        log_streamer(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",           # 禁止浏览器缓存
            "Connection": "keep-alive",             # 保持连接
            "X-Accel-Buffering": "no",             # Nginx 禁用缓冲（部署时有用）
            "Access-Control-Allow-Origin": "*",     # CORS
        },
    )
