"""
MyClaw MCP (Model Context Protocol) 连接器
纯标准库实现，通过 stdio 连接外部 MCP 服务器，发现并调用远程工具。

用法:
  python mcporter.py "<server_command>" list
  python mcporter.py "<server_command>" call <tool_name> '<json_args>'
  python mcporter.py "<server_command>" raw <method> ['<json_params>']

示例:
  python mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" list
  python mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" call read_file '{"path":"/tmp/example.txt"}'
  python mcporter.py "uvx mcp-server-git" raw tools/list
"""
import sys, os, json, shlex, subprocess, uuid, time

# ── Windows 编码兼容 ──────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── JSON-RPC 消息构造 ─────────────────────────────────

MCP_VERSION = "2024-11-05"
MCP_TIMEOUT = 30


def make_request(method: str, params: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4())[:8],
        "method": method,
        "params": params or {}
    }


def make_notification(method: str, params: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {}
    }


def log_debug(msg: str):
    """调试信息写入 stderr，不污染 stdout（mcp 协议走 stdout）"""
    print(f"[mcporter] {msg}", file=sys.stderr, flush=True)


# ── MCP 传输层 ─────────────────────────────────────────

class MCPSession:
    """MCP 会话管理器，封装子进程 + JSON-RPC 通信"""

    def __init__(self, server_cmd: str):
        self.server_cmd = server_cmd
        self.proc: subprocess.Popen | None = None
        self.server_name = "Unknown"

    def start(self):
        """启动 MCP 服务器子进程"""
        log_debug(f"启动 MCP 服务器: {self.server_cmd}")

        try:
            if sys.platform == "win32":
                self.proc = subprocess.Popen(
                    self.server_cmd,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                args = shlex.split(self.server_cmd)
                self.proc = subprocess.Popen(
                    args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    errors="replace",
                )
        except FileNotFoundError:
            raise RuntimeError(
                f"命令未找到: {self.server_cmd}\n"
                f"提示: 请确认 npx/uvx/python 已安装并在 PATH 中"
            )
        except Exception as e:
            raise RuntimeError(f"启动 MCP 服务器失败: {e}")

    def send(self, message: dict):
        """发送 JSON-RPC 消息到服务器"""
        line = json.dumps(message, ensure_ascii=False)
        log_debug(f">> {line[:200]}")
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout: int = MCP_TIMEOUT) -> dict:
        """从服务器接收一行 JSON-RPC 响应"""
        import threading

        result: dict | None = None
        error: Exception | None = None

        def _read():
            nonlocal result, error
            try:
                line = self.proc.stdout.readline()
                log_debug(f"<< {line[:200] if line else '<EOF>'}")
                if not line:
                    error = RuntimeError("MCP 服务器意外关闭了连接")
                    return
                result = json.loads(line)
            except json.JSONDecodeError as e:
                error = RuntimeError(f"JSON 解析失败: {e}")
            except Exception as e:
                error = e

        thread = threading.Thread(target=_read, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            self.kill()
            raise TimeoutError(f"MCP 服务器响应超时 ({timeout}s)")

        if error:
            raise error

        return result

    def initialize(self) -> str:
        """MCP 握手：initialize → initialized notification"""
        init_req = make_request("initialize", {
            "protocolVersion": MCP_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "MyClaw-mcporter", "version": "0.1.0"}
        })
        self.send(init_req)
        init_resp = self.recv()

        if "error" in init_resp:
            raise RuntimeError(f"初始化被拒绝: {init_resp['error']}")

        caps = init_resp.get("result", {}).get("capabilities", {})
        if "tools" not in caps:
            raise RuntimeError("此 MCP 服务器不支持工具调用 (tools capability)")

        self.server_name = init_resp.get("result", {}).get("serverInfo", {}).get("name", "Unknown")

        # 发送 initialized 通知
        self.send(make_notification("notifications/initialized"))

        return self.server_name

    def list_tools(self) -> list[dict]:
        """获取工具列表"""
        req = make_request("tools/list")
        self.send(req)
        resp = self.recv()

        if "error" in resp:
            raise RuntimeError(f"获取工具列表失败: {resp['error']}")

        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """调用指定工具"""
        req = make_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        self.send(req)
        resp = self.recv()

        if "error" in resp:
            raise RuntimeError(f"工具调用失败: {resp['error']}")

        return resp.get("result", {})

    def raw_call(self, method: str, params: dict | None = None) -> dict:
        """发送任意 JSON-RPC 请求，返回原始响应"""
        req = make_request(method, params)
        self.send(req)
        resp = self.recv()
        return resp

    def kill(self):
        """终止子进程"""
        if self.proc:
            try:
                self.proc.kill()
                self.proc.wait(timeout=3)
            except Exception:
                pass

    def close(self):
        self.kill()


# ── 输出格式化 ─────────────────────────────────────────

def format_tool_list(tools: list[dict]) -> str:
    """格式化工具列表供 LLM 阅读"""
    if not tools:
        return "📦 此服务器没有暴露任何工具。"

    lines = [f"📦 可用工具 ({len(tools)}):", ""]
    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        desc = tool.get("description", "（无描述）")
        schema = tool.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])

        lines.append(f"  {i}. {name}")
        lines.append(f"     📝 {desc}")

        if props:
            lines.append(f"     📥 参数:")
            for pname, pinfo in props.items():
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                req_mark = " [必需]" if pname in required else " [可选]"
                lines.append(f"       - {pname}: {ptype}{req_mark}")
                if pdesc:
                    lines.append(f"         {pdesc}")
        lines.append("")

    return "\n".join(lines)


def format_tool_result(result: dict) -> str:
    """格式化工具调用结果"""
    content = result.get("content", [])

    if not content:
        return "（空结果）"

    output_parts = []
    for item in content:
        item_type = item.get("type", "text")

        if item_type == "text":
            text = item.get("text", "")
            # 截断
            if len(text) > 5000:
                text = text[:5000] + "\n\n... [内容过长，已截断]"
            output_parts.append(text)

        elif item_type == "image":
            mime = item.get("mimeType", "image/png")
            data_len = len(item.get("data", ""))
            output_parts.append(f"[图片: {mime}, {data_len} 字节 base64]")

        elif item_type == "resource":
            uri = item.get("resource", {}).get("uri", "unknown")
            text = item.get("resource", {}).get("text", "")
            if len(text) > 3000:
                text = text[:3000] + "\n\n..."
            output_parts.append(f"--- 资源: {uri} ---\n{text}")

        else:
            output_parts.append(json.dumps(item, ensure_ascii=False, indent=2))

    return "\n\n".join(output_parts)


# ── CLI 入口 ───────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("用法:")
        print('  python mcporter.py "<server_cmd>" list')
        print('  python mcporter.py "<server_cmd>" call <tool_name> \'<json_args>\'')
        print('  python mcporter.py "<server_cmd>" raw <method> \'[<json_params>]\'')
        print()
        print("示例:")
        print('  python mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" list')
        print('  python mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" call read_file \'{"path":"/tmp/test.txt"}\'')
        sys.exit(1)

    server_cmd = sys.argv[1]
    action = sys.argv[2]

    session = MCPSession(server_cmd)

    try:
        session.start()

        # 握手
        server_name = session.initialize()

        if action == "list":
            tools = session.list_tools()
            print(f"✅ 已连接 MCP Server: {server_name}")
            print()
            print(format_tool_list(tools))

        elif action == "call":
            if len(sys.argv) < 5:
                print("❌ 缺少参数: call 需要 tool_name 和 json_args")
                print('用法: python mcporter.py "<cmd>" call <tool_name> \'{"key":"val"}\'')
                sys.exit(1)

            tool_name = sys.argv[3]
            try:
                args = json.loads(sys.argv[4])
            except json.JSONDecodeError as e:
                print(f"❌ JSON 参数解析失败: {e}")
                print(f"   你传入的是: {sys.argv[4]}")
                print(f"   提示: 参数必须是合法 JSON，用单引号包裹")
                sys.exit(1)

            result = session.call_tool(tool_name, args)
            print(format_tool_result(result))

        elif action == "raw":
            if len(sys.argv) < 4:
                print("❌ 缺少参数: raw 需要 method")
                sys.exit(1)

            method = sys.argv[3]
            params = None
            if len(sys.argv) >= 5:
                try:
                    params = json.loads(sys.argv[4])
                except json.JSONDecodeError:
                    print(f"❌ JSON 参数解析失败: {sys.argv[4]}")
                    sys.exit(1)

            result = session.raw_call(method, params)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        else:
            print(f"❌ 未知操作: {action}")
            print("支持: list / call / raw")
            sys.exit(1)

        session.close()

    except TimeoutError as e:
        print(f"❌ 超时: {e}")
        print(f"   提示: MCP 服务器可能正在下载依赖或遇到问题")
        session.kill()
        sys.exit(1)

    except RuntimeError as e:
        print(f"❌ {e}")
        session.kill()
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        session.kill()
        sys.exit(1)

    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        session.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
