name: 网页抓取
description: "抓取网页并提取AI优化的纯净正文。智能去除广告/导航/侧边栏，输出结构化文本。"

## 🧠 智能体使用说明

### 适用场景
- 用户发了一个链接让你看内容
- 需要获取网页的纯文本进行分析、总结、翻译
- 阅读技术文档、新闻、博客文章
- 批量抓取搜索结果中的多个页面

### run 模式命令格式
```
python {baseDir}/fetch.py <url>
python {baseDir}/fetch.py <url> --max-chars 3000
python {baseDir}/fetch.py <url> --json
```

### 参数说明
- `<url>`: 要抓取的完整网址（必含 http:// 或 https://）
- `--max-chars N`: 输出最大字符数，默认 5000
- `--json`: 以 JSON 格式输出（含标题、来源、正文、长度等信息）

### 示例
```
python {baseDir}/fetch.py https://news.ycombinator.com
python {baseDir}/fetch.py https://docs.python.org/3/library/urllib.html --max-chars 8000
python {baseDir}/fetch.py https://blog.example.com/post --json
```

### 输出格式

普通模式:
```
📄 大模型开启AI应用新纪元 —— 技术博客
  来源: blog.example.com
  ─────────────────────────────────
  [纯净正文内容...]
  ─────────────────────────────────
  📊 原文 18432 字符 → 提取 4521 字符
```

JSON 模式 (--json):
```json
{
  "title": "大模型开启AI应用新纪元",
  "source": "blog.example.com",
  "chars_original": 18432,
  "chars_extracted": 4521,
  "text": "纯净正文内容..."
}
```

### 注意事项
1. 必须传入完整 URL（含协议），短链接会自动跟随重定向
2. 智能提取正文会自动过滤导航栏、广告、侧边栏、评论区、cookie 提示
3. JS 渲染的页面（SPA）正文可能不完整，建议用原文链接而非前端路由链接
4. 遇到 403/404 等错误返回状态码和原因，不要重复尝试
5. 每次只抓一个 URL。如需批量抓取，多次调用本工具
6. 抓取结果会被截断到 --max-chars，超长页面需要时可以提高限制
