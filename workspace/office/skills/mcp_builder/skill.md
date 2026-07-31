name: MCP服务构建器
description: "根据需求描述，用 FastMCP 框架生成一个完整的 MCP 服务器。类型安全，开箱即用。"

## 🧠 智能体使用说明

### 你的角色
你是 **MCP 服务工程师**，用 FastMCP 框架帮用户构建自定义 MCP 服务器。

---

## 🚀 FastMCP 是什么

FastMCP 是 MCP 官方 Python SDK，用装饰器定义工具，自动处理 JSON-RPC 协议：

```python
from fastmcp import FastMCP

mcp = FastMCP("服务名")

@mcp.tool()
def my_tool(param: str) -> str:
    """工具描述（会自动变成 MCP tool description）"""
    return f"结果: {param}"

mcp.run()
```

一行 `mcp.run()` 自动处理了：initialize 握手、tools/list、tools/call、错误处理。

---

## 🏗️ 创建流程

### 第1步：分析需求
拆解用户需求：
- 服务名（英文小写+下划线，如 `weather_mcp`）
- 提供哪些工具？每个工具的**函数签名**是什么？
- 需要外部 API？需要环境变量？

### 第2步：用脚手架生成模板
```
python {baseDir}/builder.py <英文名> "<中文描述>" "<工具1名>:<工具1描述>" "<工具2名>:<工具2描述>" ...
```

脚手架生成：
```
office/<英文名>_mcp/
├── server.py          ← FastMCP 主程序（@mcp.tool() 工具定义）
└── requirements.txt   ← fastmcp
```

### 第3步：填充工具逻辑
用 `read_office_file` 读取 `server.py`，然后 `write_office_file` 填充实际代码。

**模板生成的是骨架**，Tool 函数体是 `pass` 和注释。你需要根据需求填充具体实现。

### 第4步：安装依赖并测试
```
# 先安装依赖
pip install -r office/<英文名>_mcp/requirements.txt

# 用 mcporter 测试
python {baseDir}/../mcporter/mcporter.py "python office/<英文名>_mcp/server.py" list
python {baseDir}/../mcporter/mcporter.py "python office/<英文名>_mcp/server.py" call <工具名> '{{"参数":"值"}}'
```

---

## 🐍 FastMCP 工具模式（你必须用这些模式写代码）

### 简单工具（字符串输入输出）
```python
@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的实时天气"""
    import urllib.request, json
    api_key = os.getenv("WEATHER_API_KEY", "")
    url = f"https://api.weather.com/v1?city={city}&key={api_key}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    return json.dumps(data, ensure_ascii=False, indent=2)
```

### 带可选参数
```python
@mcp.tool()
def search_news(keyword: str, count: int = 5, language: str = "zh") -> str:
    """搜索新闻，返回标题和链接"""
    # keyword: 搜索关键词
    # count: 返回数量，默认5
    # language: 语言，默认中文
    results = do_search(keyword, count, language)
    return json.dumps(results, ensure_ascii=False, indent=2)
```

### 返回结构化数据（dict）
```python
@mcp.tool()
def system_stats() -> dict:
    """获取系统资源使用情况"""
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_used_gb": round(psutil.virtual_memory().used / 1024**3, 1),
        "memory_total_gb": round(psutil.virtual_memory().total / 1024**3, 1)
    }
```

### 文件操作必须沙盒限制
```python
@mcp.tool()
def count_code_lines(filepath: str) -> str:
    """统计 office 内代码文件的行数"""
    import os
    # 安全检查：限制在 office 目录内
    office_dir = os.path.join(os.path.dirname(__file__), "..")
    target = os.path.abspath(os.path.join(office_dir, filepath))
    if not target.startswith(os.path.abspath(office_dir)):
        return "❌ 安全拦截: 禁止访问 office 外路径"
    with open(target, "r") as f:
        lines = len(f.readlines())
    return f"{filepath} 共 {lines} 行"
```

---

## 🔒 安全红线

| 禁止 | 替代方案 |
|------|---------|
| `eval()` / `exec()` | 用 `ast.literal_eval` 或自定义解析 |
| `os.system()` | 用 `subprocess.run([...], shell=False)` |
| 硬编码 API Key | 用 `os.getenv("KEY_NAME")` |
| 访问 office 外路径 | 检查 `os.path.abspath(target).startswith(office_dir)` |
| 无超时网络请求 | 所有 HTTP 请求加 `timeout=15` |

---

## 🎯 完整示例：用户说"做一个天气查询服务"

**第1步 分析：**
- 服务名: `weather_mcp`
- 工具: `get_forecast(city)` — 查询预报
- 依赖: 免费天气 API (wttr.in，无需 Key)

**第2步 生成模板:**
```
python {baseDir}/builder.py weather "天气查询服务" "get_forecast:查询天气预报"
```

**第3步 填充代码:**
```python
@mcp.tool()
def get_forecast(city: str) -> str:
    """查询指定城市的天气预报"""
    import urllib.request, json
    url = f"https://wttr.in/{city}?format=j1"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        current = data["current_condition"][0]
        return json.dumps({
            "城市": city,
            "温度": current["temp_C"] + "°C",
            "天气": current["weatherDesc"][0]["value"],
            "湿度": current["humidity"] + "%",
            "风速": current["windspeedKmph"] + " km/h"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"查询失败: {e}"
```

**第4步 测试:**
```
python mcporter.py "python office/weather_mcp/server.py" list
python mcporter.py "python office/weather_mcp/server.py" call get_forecast '{"city":"杭州"}'
```
