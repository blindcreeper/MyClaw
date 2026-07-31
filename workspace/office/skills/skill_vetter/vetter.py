"""
MyClaw Skill Vetter — 技能安全静态扫描器
用法: python vetter.py <技能目录路径>
示例: python vetter.py ../web_fetch
"""
import sys, os, re, ast
from pathlib import Path

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ─── 检查引擎 ───────────────────────────────────────────

class SkillVetter:
    def __init__(self, skill_dir: str):
        self.skill_dir = Path(skill_dir).resolve()
        self.skill_name = self.skill_dir.name
        self.findings = {"fatal": [], "high": [], "suggestion": []}

    def add(self, severity: str, title: str, location: str, risk: str, fix: str):
        self.findings[severity].append({
            "title": title, "location": location, "risk": risk, "fix": fix
        })

    # ─── skill.md 检查 ────────────────────────────────

    def check_skill_md(self):
        md_path = self.skill_dir / "skill.md"
        if not md_path.exists():
            self.add("fatal", "skill.md 缺失",
                     str(self.skill_dir),
                     "技能缺少说明书，skill_loader 无法注册此技能",
                     "创建 skill.md，确保第一行为 name:，第二行为 description:")
            return

        with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.split("\n")

        # name 字段
        first_line = lines[0].strip() if lines else ""
        if not first_line.startswith("name:"):
            self.add("fatal", "skill.md 第一行不是 name:",
                     f"{md_path}:1", "skill_loader 无法提取技能名",
                     "将第一行改为: name: <技能中文名>")

        # description 字段
        second_line = lines[1].strip() if len(lines) > 1 else ""
        if not second_line.startswith("description:"):
            self.add("fatal", "skill.md 第二行不是 description:",
                     f"{md_path}:2", "skill_loader 无法提取技能描述",
                     '将第二行改为: description: "<一句话描述>"')

        # {baseDir} 占位符
        if "{baseDir}" not in content:
            self.add("high", "skill.md 未使用 {baseDir} 占位符",
                     str(md_path),
                     "命令模板中缺少 {baseDir}，技能可能无法正确执行",
                     "在命令中使用 {baseDir} 代指技能目录，如 python {baseDir}/main.py")

    # ─── 实用工具 ──────────────────────────────────────

    @staticmethod
    def _strip_strings_and_comments(source: str) -> str:
        """剥离所有字符串字面量和注释，避免扫描到示例文字/正则表达式"""
        # 1. 多行文档字符串
        source = re.sub(r'""".*?"""', '""', source, flags=re.DOTALL)
        source = re.sub(r"'''.*?'''", "''", source, flags=re.DOTALL)
        # 2. 单行字符串（包括 r'' f'' b'' 前缀，以及正则字符串）
        source = re.sub(r"[rfbu]*'[^']*'", "''", source)
        source = re.sub(r'[rfbu]*"[^"]*"', '""', source)
        # 3. 单行注释
        source = re.sub(r'#.*$', '', source, flags=re.MULTILINE)
        return source

    # ─── Python 文件检查 ──────────────────────────────

    def check_python_files(self):
        py_files = list(self.skill_dir.glob("*.py"))
        if not py_files:
            self.add("suggestion", "缺少 Python 脚本",
                     str(self.skill_dir), "技能没有任何可执行代码", "至少创建一个 .py 入口脚本")
            return

        for py_path in py_files:
            self._scan_python(py_path)

    def _scan_python(self, py_path: Path):
        rel_path = str(py_path.relative_to(self.skill_dir.parent.parent))

        with open(py_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        # 先清理注释和 docstring，避免扫描到示例代码/说明文字
        clean = self._strip_strings_and_comments(source)

        # ─── 🔴 致命：路径穿越 ───
        path_danger = re.findall(
            r'(?:\.\./|\.\.\\|/[a-z]+/|C:\\|D:\\|[A-Z]:\\|~/)', clean
        )
        if path_danger:
            unique = list(set(path_danger))
            self.add("fatal", "检测到路径穿越尝试",
                     f"{rel_path}",
                     f"代码中包含可疑路径: {', '.join(unique)}",
                     "所有路径必须限制在 office/ 和 skills/ 范围内，使用相对路径")

        # ─── 🔴 致命：eval / exec ───
        eval_matches = re.findall(r'\b(eval|exec|compile|__import__)\s*\(', clean)
        if eval_matches:
            self.add("fatal", "检测到动态代码执行",
                     f"{rel_path}",
                     f"使用了 {' / '.join(set(eval_matches))}，可能执行任意代码",
                     "移除 eval/exec，用安全解析替代（如 ast.literal_eval 或自定义解析器）")

        # ─── 🔴 致命：os.system / subshell ───
        shell_matches = re.findall(
            r'(os\.system|subprocess\.(?:call|Popen|run|check_output))\s*\(', clean
        )
        if shell_matches:
            has_shell_true = "shell=True" in clean or "shell = True" in clean
            severity = "fatal" if has_shell_true else "high"
            self.add(severity, "检测到 Shell 执行",
                     f"{rel_path}",
                     f"使用了 {' / '.join(set(shell_matches))}" +
                     ("（含 shell=True，极其危险）" if has_shell_true else ""),
                     "改用 subprocess.run([...], shell=False) 并限制在 office 目录内")

        # ─── 🟡 高风险：无限制网络请求 ───
        net_patterns = re.findall(
            r'(urllib\.request|requests\.(?:get|post)|socket\.socket)\s*\(',
            clean
        )
        if net_patterns:
            has_timeout = "timeout=" in clean
            if not has_timeout:
                self.add("high", "网络请求缺少超时设置",
                         f"{rel_path}",
                         "请求可能无限挂起，阻塞 Agent 流程",
                         "添加 timeout=15 参数")

        # ─── 🟡 高风险：文件写入 ───
        write_patterns = re.findall(
            r'(open\([^)]*,\s*["\'][wa]["\']|\.write\()', clean
        )
        if write_patterns:
            self.add("high", "脚本可写入文件",
                     f"{rel_path}",
                     f"发现 {len(write_patterns)} 处文件写入操作",
                     "确保写入路径限制在 office/ 内，不可由用户输入直接拼接")

        # ─── 🟢 建议：错误处理 ───
        if "try:" not in source and ("urllib" in source or "request" in source or "subprocess" in source):
            self.add("suggestion", "缺少异常处理",
                     f"{rel_path}",
                     "网络或外部调用没有 try/except 包裹",
                     "对外部调用添加 try/except，避免一个错误导致整个 Agent 崩溃")

        # ─── 🟢 建议：输出截断 ───
        if "print(" in source and "[:5000]" not in source and "[:10000]" not in source:
            self.add("suggestion", "输出可能未截断",
                     f"{rel_path}",
                     "脚本输出没有长度限制，可能撑爆 LLM token 窗口",
                     "在 print 前对长内容做截断，如 content[:5000]")

        # ─── 🟢 建议：docstring ───
        if not re.search(r'""".*?"""', source, re.DOTALL):
            self.add("suggestion", "缺少模块 docstring",
                     f"{rel_path}",
                     "没有用法说明，LLM 难以理解脚本功能",
                     '在文件开头添加 """...""" 说明用法和参数')

        # ─── 🟢 建议：第三方依赖 ───
        non_stdlib = re.findall(
            r'^(?:from|import)\s+(?!sys|os|re|json|time|datetime|math|random|'
            r'collections|itertools|functools|pathlib|typing|abc|hashlib|'
            r'base64|html|xml|urllib|http|subprocess|shutil|tempfile|io|'
            r'csv|string|textwrap|argparse|logging|unittest|asyncio|threading|'
            r'queue|socket|struct|enum|dataclasses|contextlib|copy|traceback|'
            r'inspect|warnings|ast|platform|stat|uuid)(\S+)',
            source, re.MULTILINE
        )
        if non_stdlib:
            self.add("suggestion", "使用了非标准库依赖",
                     f"{rel_path}",
                     f"依赖: {', '.join(non_stdlib)}。用户需要手动 pip install",
                     "优先使用标准库实现，如果必须用第三方库，在 skill.md 中注明安装方式")

    # ─── 报告生成 ─────────────────────────────────────

    def report(self) -> str:
        total = sum(len(v) for v in self.findings.values())
        fatal_n = len(self.findings["fatal"])
        high_n = len(self.findings["high"])
        sugg_n = len(self.findings["suggestion"])

        lines = [
            f"## 🔒 安全审查报告：{self.skill_name}",
            "",
            "### 📊 总览",
            f"| 类别 | 数量 |",
            f"|------|------|",
            f"| 🔴 致命风险 | {fatal_n} |",
            f"| 🟡 高风险 | {high_n} |",
            f"| 🟢 建议改进 | {sugg_n} |",
            f"| **总计** | **{total}** |",
            "",
        ]

        # 综合判定
        if fatal_n > 0:
            verdict = "🚫 禁止使用 — 存在致命安全风险，必须修复后才能使用"
        elif high_n > 0:
            verdict = "⚠️ 需修复 — 存在高风险项，建议修复后再使用"
        elif sugg_n > 0:
            verdict = "✅ 基本安全 — 有改进空间，可正常使用"
        else:
            verdict = "✅ 安全 — 未发现安全风险"
        lines.append(f"**综合判定**：{verdict}")
        lines.append("")

        # 逐项输出
        for severity, label, icon in [
            ("fatal", "🔴 致命风险", "🔴"),
            ("high", "🟡 高风险", "🟡"),
            ("suggestion", "🟢 建议改进", "🟢"),
        ]:
            items = self.findings[severity]
            if not items:
                lines.append(f"### {label}")
                lines.append("")
                lines.append("✅ 未发现此类问题。")
                lines.append("")
                continue

            lines.append(f"### {label}")
            lines.append("")
            for i, f in enumerate(items, 1):
                lines.append(f"**{i}. {f['title']}**")
                lines.append(f"- 位置：`{f['location']}`")
                lines.append(f"- 风险：{f['risk']}")
                lines.append(f"- 修复：{f['fix']}")
                lines.append("")

        # 致命风险额外警告
        if fatal_n > 0:
            lines.append("---")
            lines.append("")
            lines.append("## 🚫 此技能存在致命安全风险，在修复前不应使用！")
            lines.append("")
            lines.append("请根据上方的修复建议逐项处理后，重新运行本审查。")

        return "\n".join(lines)


# ─── CLI 入口 ───────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python vetter.py <技能目录路径>")
        print("示例: python vetter.py ../web_fetch")
        print("      python vetter.py /path/to/skills/my_skill")
        sys.exit(1)

    raw = Path(sys.argv[1])
    # 优先按原始路径找（支持绝对路径、相对CWD的路径）
    if raw.exists():
        target = raw.resolve()
    else:
        # 回退：相对于本脚本所在 skills 目录
        target = (Path(__file__).parent.parent / raw).resolve()

    if not target.exists():
        print(f"❌ 技能目录不存在: {target}")
        print(f"   提示: 可用相对路径(如 web_fetch)或绝对路径")
        sys.exit(1)

    if not target.is_dir():
        print(f"❌ 路径不是目录: {target}")
        sys.exit(1)

    vetter = SkillVetter(str(target))
    vetter.check_skill_md()
    vetter.check_python_files()
    print(vetter.report())

    # 退出码：致命风险 → 1
    if vetter.findings["fatal"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
