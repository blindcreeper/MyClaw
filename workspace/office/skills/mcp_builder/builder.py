"""
MyClaw MCP 服务构建器 — 基于 FastMCP 一键生成 MCP 服务器
用法: python builder.py <英文名> "<描述>" "<工具1>:<说明>" "<工具2>:<说明>" ...

示例:
  python builder.py weather "天气查询服务" "get_forecast:查询天气预报" "get_alerts:获取预警信息"
  python builder.py todo "待办管理" "add_task:添加任务" "list_tasks:列出所有任务" "complete_task:完成任务"
"""
import sys, os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── 模板 ────────────────────────────────────────────────

SERVER_TEMPLATE = '''"""
{display_name} — MCP Server
基于 FastMCP 构建。{description}

启动:   python server.py
测试:   python ../mcporter/mcporter.py "python server.py" list
依赖:   pip install -r requirements.txt
"""
import sys, os, json
from fastmcp import FastMCP

# 加载 .env（如果需要在 tools 中使用环境变量）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
except ImportError:
    pass

mcp = FastMCP("{server_name}")
{tool_functions}

if __name__ == "__main__":
    mcp.run()
'''


TOOL_TEMPLATE = '''
@mcp.tool()
def {func_name}({params}) -> {return_type}:
    """{description}"""
    # TODO: 实现核心逻辑{param_comment}
    {skeleton}
'''


REQUIREMENTS_TEMPLATE = '''# {display_name} — MCP Server 依赖
# pip install -r requirements.txt

fastmcp>=2.0.0
python-dotenv>=1.0.0
'''


# ── 代码生成 ────────────────────────────────────────────

def camel_to_snake(name: str) -> str:
    """CamelCase → snake_case"""
    result = []
    for ch in name:
        if ch.isupper() and result:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


def generate_tool(name: str, desc: str) -> str:
    """根据工具名智能推断函数签名和骨架"""
    func_name = camel_to_snake(name) if any(c.isupper() for c in name) else name

    # 根据名称推断参数
    params = ""
    param_comment = ""
    skeleton = "pass"
    return_type = "str"

    # 模式匹配：猜工具类型
    if any(kw in name.lower() for kw in ["get", "fetch", "query", "search", "list", "find"]):
        params = "keyword: str"
        param_comment = "\n    # keyword: 查询关键词"
        skeleton = 'result = f"查询 {keyword} 的结果（待实现）"\n    return result'
        return_type = "str"

    elif any(kw in name.lower() for kw in ["add", "create", "insert", "save", "register"]):
        params = "name: str"
        param_comment = "\n    # name: 创建的名称"
        skeleton = 'result = f"✓ {name} 创建成功（待实现）"\n    return result'

    elif any(kw in name.lower() for kw in ["delete", "remove", "clear", "destroy"]):
        params = "target_id: str"
        param_comment = "\n    # target_id: 要删除的目标 ID"
        skeleton = 'result = f"✓ {target_id} 已删除（待实现）"\n    return result'

    elif any(kw in name.lower() for kw in ["update", "modify", "edit", "change", "set"]):
        params = "target_id: str, new_value: str"
        param_comment = "\n    # target_id: 目标 ID\n    # new_value: 新值"
        skeleton = 'result = f"✓ {target_id} 更新为 {new_value}（待实现）"\n    return result'

    elif any(kw in name.lower() for kw in ["stats", "status", "info", "summary", "count"]):
        params = ""
        skeleton = 'result = json.dumps({"status": "ok", "message": "待实现"}, ensure_ascii=False, indent=2)\n    return result'

    # 确保有 return 语句
    if "return" not in skeleton:
        skeleton += '\n    return "TODO: 待实现"'

    return TOOL_TEMPLATE.format(
        func_name=func_name,
        params=params,
        return_type=return_type,
        description=desc,
        param_comment=param_comment,
        skeleton=skeleton
    ).strip()


# ── CLI 入口 ────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("用法: python builder.py <英文名> \"<描述>\" \"<工具1>:<描述>\" \"<工具2>:<描述>\" ...")
        print()
        print("示例:")
        print('  python builder.py weather "天气查询" "get_forecast:查询天气预报" "get_alerts:获取预警"')
        print('  python builder.py todo "待办管理" "add_task:添加任务" "list_tasks:列出任务"')
        print()
        sys.exit(1)

    server_name = sys.argv[1]
    description = sys.argv[2]
    tool_raw = sys.argv[3:]

    # 解析工具定义（name:description 格式）
    tools = []
    seen = set()
    for raw in tool_raw:
        if ":" in raw:
            name, _, desc = raw.partition(":")
            name = name.strip()
            desc = desc.strip()
        else:
            name = raw.strip()
            desc = "待补充"
        if name and name not in seen:
            tools.append({"name": name, "desc": desc})
            seen.add(name)

    if not tools:
        tools.append({"name": "example_tool", "desc": "示例工具，替换为你自己的功能"})

    # 生成工具函数
    tool_funcs = []
    for t in tools:
        code = generate_tool(t["name"], t["desc"])
        tool_funcs.append(code)

    # 渲染模板
    server_code = SERVER_TEMPLATE.format(
        display_name=description,
        description=description,
        server_name=server_name,
        tool_functions="\n".join(tool_funcs)
    )

    reqs_code = REQUIREMENTS_TEMPLATE.format(display_name=description)

    # 写入文件
    target_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        f"{server_name}_mcp"
    )

    if os.path.exists(target_dir):
        print(f"⚠️ 目录已存在: {target_dir}")
        print("   换个名字或先删除。")
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)

    files = {
        "server.py": server_code,
        "requirements.txt": reqs_code,
    }

    for filename, content in files.items():
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # 输出
    print(f"✅ FastMCP 服务器已生成!")
    print(f"   目录: {target_dir}/")
    for f in files:
        print(f"   ├── {f}")
    print()
    print(f"📦 已注册 {len(tools)} 个工具:")
    for t in tools:
        func_name = camel_to_snake(t["name"]) if any(c.isupper() for c in t["name"]) else t["name"]
        print(f"   • {func_name}() — {t['desc']}")
    print()
    print("📝 下一步:")
    print(f"   1. pip install -r {target_dir}/requirements.txt")
    print(f"   2. 编辑 {target_dir}/server.py，替换 TODO")
    print(f"   3. 用 mcporter 测试:")
    print(f'      python ../mcporter/mcporter.py "python {target_dir}/server.py" list')
    print()


if __name__ == "__main__":
    main()
