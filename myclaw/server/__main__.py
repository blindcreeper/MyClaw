"""
MyClaw Server - 启动入口

用法:
    python -m myclaw.server              # 默认 9910 端口
    python -m myclaw.server --port 8080  # 自定义端口
    python -m myclaw.server --reload     # 开发模式热重载
"""
import sys
import uvicorn

# Windows 下强制 stdout 使用 UTF-8，避免 emoji 编码崩溃
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    # 解析命令行参数（简单版，不需要 argparse）
    kwargs = {
        "app": "myclaw.server.app:app",
        "host": "0.0.0.0",
        "port": 9910,
        "log_level": "info",
    }

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            kwargs["port"] = int(args[i + 1])
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            kwargs["host"] = args[i + 1]
            i += 2
        elif args[i] == "--reload":
            kwargs["reload"] = True
            i += 1
        elif args[i] in ("--help", "-h"):
            print("MyClaw Server - QQ Bot 后端")
            print()
            print("用法: python -m myclaw.server [选项]")
            print()
            print("选项:")
            print("  --port PORT    监听端口 (默认 9910)")
            print("  --host HOST    监听地址 (默认 0.0.0.0)")
            print("  --reload       开发模式，代码变更自动重启")
            print("  --help, -h     显示帮助")
            return
        else:
            print(f"未知参数: {args[i]}")
            print("使用 --help 查看帮助")
            return

    print(f"🚀 MyClaw Server 启动中...")
    print(f"   监听: http://{kwargs['host']}:{kwargs['port']}")
    print(f"   OneBot WS: ws://127.0.0.1:{kwargs['port']}/ws/onebot")
    if kwargs.get("reload"):
        print(f"   🔄 热重载已启用")
    print()

    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()