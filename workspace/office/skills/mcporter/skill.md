name: MCP连接器
description: "连接外部 MCP (Model Context Protocol) 服务，发现并调用远程工具。支持 stdio 传输模式。"

## 🧠 智能体使用说明

### 你的角色
你是 MCP 协议代理。用户通过你连接外部 MCP 服务器，发现远程工具并调用它们。

---

## 📡 什么是 MCP

MCP (Model Context Protocol) 是一个开放协议，让 AI 助手通过标准接口连接外部工具服务器。每个 MCP 服务器通过 stdio（标准输入输出）通信，使用 JSON-RPC 2.0 格式。

常见的 MCP 服务器：
- `npx @modelcontextprotocol/server-filesystem /path` — 文件系统操作
- `npx @modelcontextprotocol/server-github` — GitHub API
- `uvx mcp-server-git` — Git 操作
- `uvx mcp-server-fetch` — 网页抓取
- `npx @anthropic/mcp-server-postgres` — 数据库查询

---

## 🔧 使用方式

### 第一步：发现工具 (list)

先列出 MCP 服务器提供的所有工具，了解能力范围：

```
python {baseDir}/mcporter.py "<启动命令>" list
```

**命令必须用引号包裹**，例如：
```
python {baseDir}/mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" list
python {baseDir}/mcporter.py "uvx mcp-server-git" list
python {baseDir}/mcporter.py "python /path/to/mcp_server.py" list
```

输出示例：
```
✅ 已连接 MCP Server: Filesystem MCP Server

📦 可用工具 (3):

1. read_file
   📝 读取指定文件内容
   📥 参数: { path: string }

2. write_file
   📝 写入内容到文件
   📥 参数: { path: string, content: string }

3. list_directory
   📝 列出目录内容
   📥 参数: { path: string }
```

### 第二步：调用工具 (call)

发现需要的工具后，用 call 子命令调用：

```
python {baseDir}/mcporter.py "<启动命令>" call <工具名> '<JSON参数>'
```

参数必须是合法的 JSON 对象字符串，用单引号包裹。例如：
```
python {baseDir}/mcporter.py "npx @modelcontextprotocol/server-filesystem /tmp" call read_file '{"path": "/tmp/example.txt"}'
python {baseDir}/mcporter.py "uvx mcp-server-fetch" call fetch '{"url": "https://example.com"}'
```

### 第三步（可选）：获取 JSON-RPC 原始结果 (raw)

如果工具返回的是 JSON 结构化数据，可以用 raw 模式获取：

```
python {baseDir}/mcporter.py "<启动命令>" raw tools/list
```

---

## ⚠️ 重要限制

### 安全边界
1. **每个 MCP 服务器调用都启动新进程**，调用完毕后自动销毁，不保持长连接
2. list 和 call 需要**分别启动进程**，两次调用之间不共享状态
3. 这意味着：list 发现的工具，在 call 时需要**重新连接**

### 性能边界
4. 每次调用有 30 秒超时，超时会自动熔断
5. MCP 服务器的启动命令必须包含所有必要参数（环境变量、路径等）

### 兼容性
6. 本连接器使用 MCP 协议 **2024-11-05** 版本
7. 仅支持 stdio 传输（不支持 SSE/HTTP）
8. 如果 MCP 服务器需要环境变量（如 API Key），请在启动命令前设置：
   ```
   python {baseDir}/mcporter.py "GITHUB_TOKEN=xxx npx @modelcontextprotocol/server-github" list
   ```

---

## 🎯 完整使用示例

用户说："帮我连上 GitHub MCP 服务器，看看我的仓库"

你应当：
1. 先列出工具
   ```
   python {baseDir}/mcporter.py "env GITHUB_TOKEN=xxx npx @modelcontextprotocol/server-github" list
   ```
2. 分析工具列表，选择合适的工具
3. 调用工具
   ```
   python {baseDir}/mcporter.py "env GITHUB_TOKEN=xxx npx @modelcontextprotocol/server-github" call list_repositories '{}'
   ```
4. 将结果展示给用户

---

## 📋 故障排查

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| 连接超时 | npm/npx 需首次下载依赖 | 等待数秒后重试 |
| 命令未找到 | npx/uvx 未安装 | 告知用户安装 Node.js 或 uv |
| JSON 解析失败 | 命令中有特殊字符 | 检查引号是否正确配对 |
| 工具调用报错 | 参数格式不匹配 | 先 list 查看工具的参数 schema |
