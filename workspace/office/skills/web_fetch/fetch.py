"""
MyClaw Web Fetch — AI 优化网页抓取器
纯标准库实现，智能提取正文，自动过滤广告/导航/侧边栏/评论区。

用法:
  python fetch.py <url>
  python fetch.py <url> --max-chars 3000
  python fetch.py <url> --json
"""
import sys, os, re, json, html
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── 内容提取器 ─────────────────────────────────────────

# 非正文标签集合（会被跳过）
SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg", "canvas",
             "nav", "footer", "header", "aside", "form", "button",
             "select", "textarea", "option", "input", "label"}
# 块级标签（会在其后插入换行）
BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3",
              "h4", "h5", "h6", "section", "article", "pre", "blockquote",
              "table", "ul", "ol", "dl", "hr", "figure"}

# 正文区域的关键 class/id 模式
CONTENT_PATTERNS = [
    r'(?:article|post|content|main|body|entry|text|story|document)',
]
# 非正文区域的关键 class/id 模式（权重扣分）
BOILERPLATE_PATTERNS = [
    r'(?:nav|menu|sidebar|footer|header|comment|ad|advertisement|'
    r'banner|popup|modal|cookie|social|share|related|recommend|'
    r'sponsor|widget|pagination|breadcrumb|search)',
]

# 无意义文本模式（会被移除的行）
NOISE_PATTERNS = [
    r'^(Cookie|隐私|隐私政策|Accept|接受|同意|Subscribe|订阅|Sign\s*up'
    r'|注册|登录|Log\s*in|Share|分享|Follow|关注)',
    r'^(首页|Home|返回顶部|Back to top|上一篇|下一篇|相关文章)',
    r'^(\s*|\d+\s*)$',  # 纯数字或空行
]


class SmartExtractor(HTMLParser):
    """智能正文提取器 — 基于文本密度和语义标签"""

    def __init__(self):
        super().__init__()
        self.blocks: list[dict] = []      # 文本块列表
        self.current_block: list[str] = []
        self.current_tag = ""
        self.skip_level = 0
        self.in_block_tag = False
        self.title = ""
        self.in_title = False

    def _attr_str(self, attrs: list[tuple]) -> str:
        return " ".join(f'{k}="{v}"' for k, v in attrs).lower()

    def handle_starttag(self, tag: str, attrs: list[tuple]):
        tag_lower = tag.lower()
        attr_str = self._attr_str(attrs)

        # 标题追踪
        if tag_lower == "title":
            self.in_title = True
            return

        # 跳过非正文标签
        if tag_lower in SKIP_TAGS:
            self.skip_level += 1
            return

        # 检查 boilerplate 标识
        if re.search("|".join(BOILERPLATE_PATTERNS), attr_str):
            self.skip_level += 1
            return

        # 检查正文标识（加分项）
        if re.search("class=[\"']?(?:article|content|post-body|entry-content)[\"' ]", attr_str):
            self.skip_level = max(0, self.skip_level - 1)

        # 块级标签 — 刷新当前块
        if tag_lower in BLOCK_TAGS:
            if self.current_block:
                text = " ".join(self.current_block).strip()
                if text:
                    self.blocks.append({"tag": self.current_tag, "text": text})
                self.current_block = []
            self.current_tag = tag_lower
            self.in_block_tag = True

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if tag_lower == "title":
            self.in_title = False
            return

        if tag_lower in SKIP_TAGS:
            self.skip_level = max(0, self.skip_level - 1)
            return

        if tag_lower in BLOCK_TAGS:
            if self.current_block:
                text = " ".join(self.current_block).strip()
                if text:
                    self.blocks.append({"tag": self.current_tag, "text": text})
                self.current_block = []
            self.in_block_tag = False

    def handle_data(self, data: str):
        if self.skip_level > 0:
            return

        if self.in_title:
            self.title += data
            return

        stripped = data.strip()
        if stripped:
            self.current_block.append(stripped)

    def get_text(self) -> str:
        # 刷新最后一块
        if self.current_block:
            text = " ".join(self.current_block).strip()
            if text:
                self.blocks.append({"tag": self.current_tag, "text": text})

        return self._assemble()

    def _assemble(self) -> str:
        """将文本块组装为格式化输出"""
        lines = []
        prev_tag = ""

        for block in self.blocks:
            text = block["text"]
            tag = block["tag"]

            # 过滤噪声行
            if any(re.match(p, text) for p in NOISE_PATTERNS):
                continue

            # 过滤过短的非标题文本（很可能是按钮文字、标签等）
            if len(text) < 20 and tag not in ("h1", "h2", "h3", "h4"):
                continue

            # 标题加前缀
            if tag in ("h1", "h2", "h3"):
                level = int(tag[1])
                prefix = "#" * level + " "
                lines.append("")
                lines.append(prefix + text)
                lines.append("")
            elif tag == "li":
                lines.append(f"• {text}")
            elif tag == "pre":
                lines.append(f"```\n{text}\n```")
            elif tag == "blockquote":
                for line in text.split("\n"):
                    lines.append(f"> {line}")
            else:
                if prev_tag in ("h1", "h2", "h3") and tag == "p":
                    lines.append(text)
                elif tag != prev_tag:
                    lines.append("")
                    lines.append(text)
                else:
                    lines.append(text)

            prev_tag = tag

        return "\n".join(lines)


# ── HTTP 抓取 ──────────────────────────────────────────

def fetch_url(url: str, timeout: int = 15) -> tuple[str, str]:
    """抓取网页，返回 (final_url, html_content)"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        html_bytes = resp.read()

    # 尝试解码
    for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            return final_url, html_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    raise RuntimeError("无法解码网页内容")


# ── 主逻辑 ─────────────────────────────────────────────

def extract(url: str, max_chars: int = 5000) -> dict:
    """抓取并提取网页正文"""
    final_url, html_str = fetch_url(url)
    parsed = urlparse(final_url)
    source = parsed.netloc

    # 提取标题
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_str,
                            re.IGNORECASE | re.DOTALL)
    meta_title = title_match.group(1).strip() if title_match else ""

    # 尝试提取 og:title（通常更准）
    og_match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html_str, re.IGNORECASE
    )
    og_title = og_match.group(1) if og_match else ""

    # 智能提取正文
    extractor = SmartExtractor()
    try:
        extractor.feed(html_str)
    except Exception:
        pass

    body_text = extractor.get_text()
    page_title = extractor.title or og_title or meta_title or "（无标题）"

    # 清理正文
    body_text = re.sub(r"\n{4,}", "\n\n\n", body_text)   # 合并超多空行
    body_text = re.sub(r"[ \t]{2,}", " ", body_text)      # 合并多余空格
    body_text = body_text.strip()

    # 如果没有提取到正文，回退到纯文本提取
    if len(body_text) < 50:
        body_text = _fallback_extract(html_str)

    original_len = len(body_text)

    # 截断
    if len(body_text) > max_chars:
        body_text = body_text[:max_chars] + (
            f"\n\n…[截断] 原文共 {original_len:,} 字符"
        )

    return {
        "title": page_title.strip(),
        "source": source,
        "url": final_url,
        "chars_original": original_len,
        "chars_extracted": min(original_len, max_chars),
        "text": body_text,
    }


def _fallback_extract(html_str: str) -> str:
    """回退方案：简单去除所有标签"""
    # 去除 script/style
    html_str = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>",
                      "", html_str, flags=re.DOTALL | re.IGNORECASE)
    # 去除 HTML 标签
    text = re.sub(r"<[^>]+>", " ", html_str)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 清理空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


# ── CLI ────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python fetch.py <url> [--max-chars N] [--json]")
        print("示例: python fetch.py https://example.com")
        print("      python fetch.py https://example.com --json --max-chars 3000")
        sys.exit(1)

    url = args[0]
    if not url.startswith(("http://", "https://")):
        print("❌ URL 必须以 http:// 或 https:// 开头")
        sys.exit(1)

    max_chars = 5000
    output_json = False

    i = 1
    while i < len(args):
        if args[i] == "--max-chars" and i + 1 < len(args):
            max_chars = int(args[i + 1])
            i += 2
        elif args[i] == "--json":
            output_json = True
            i += 1
        else:
            i += 1

    try:
        result = extract(url, max_chars=max_chars)
    except HTTPError as e:
        print(f"❌ HTTP 错误 {e.code}: {e.reason}")
        sys.exit(1)
    except URLError as e:
        print(f"❌ 网络错误: {e.reason}")
        sys.exit(1)
    except TimeoutError:
        print("❌ 请求超时")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        sys.exit(1)

    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"📄 {result['title']}")
        print(f"   来源: {result['source']}")
        print(f"   " + "─" * 50)
        print(result["text"])
        print(f"   " + "─" * 50)
        print(f"📊 原文 {result['chars_original']:,} 字符 → "
              f"提取 {result['chars_extracted']:,} 字符")


if __name__ == "__main__":
    main()
