name: 技能创建器
description: "用自然语言描述需求，让 MyClaw 自动创建新技能。这是一个元技能，用于生成其他技能。"

## 🧠 智能体使用说明

### 你的角色
你正在扮演 **MyClaw 技能工程师**。用户想让你创建一个新的自动化技能。
请严格按照以下规范，使用现有工具完成技能创建。

---

## 📐 技能目录规范

每个技能是一个独立文件夹，放在 `skills/` 下：

```
skills/<英文名>/
├── skill.md          ← 必需：说明书（name + description + 使用指南）
└── <script>.py       ← 必需：可执行的功能代码
```

### 命名规则
- 文件夹名：英文小写 + 下划线（如 `web_fetch`、`data_analysis`、`dingtalk_notify`）
- 工具名：`skill.md` 的 `name:` 字段用中文简短描述
- 脚本名：能描述功能的英文名（如 `fetch.py`、`analyze.py`、`send.py`）

---

## 📝 skill.md 格式规范（必须严格遵守）

```markdown
name: <中文技能名，10字以内>
description: "<一句话功能描述，会被用作工具 description>"

## 🧠 智能体使用说明

### 适用场景
- 场景1
- 场景2

### run 模式命令格式
\`\`\`
<命令模板，用 {baseDir} 代指技能目录>
\`\`\`

### 参数说明
- `<参数名>`: 说明
- `<参数名>`: 说明

### 示例
\`\`\`
python {baseDir}/xxx.py <具体示例>
\`\`\`

### 注意事项
1. 注意事项1
2. 注意事项2
```

**关键要求**：
- 第一行必须是 `name:`，第二行必须是 `description:`，否则 skill_loader 扫不到
- description 用双引号包裹，60字以内
- 命令中路径用 `{baseDir}` 占位符，系统会自动替换为 `skills/<技能名>`

---

## 🐍 Python 脚本规范

### 基础模板
```python
"""
MyClaw <技能名> Skill
用法: python <script>.py <参数1> <参数2> ...
"""
import sys
import ...

def main(arg1, arg2):
    # 核心逻辑
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python <script>.py <参数说明>")
        sys.exit(1)
    result = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(result)
```

### 规范要求
1. **纯标准库优先**：避免让用户装额外依赖。如果必须用第三方库（如 requests），在 skill.md 注意事项里说明
2. **错误处理**：每个外部调用（网络、文件）必须有 try/except
3. **输出格式**：用 print 输出结果给 LLM 看，简洁清晰，关键信息优先
4. **防爆截断**：如果输出可能很长（如网页正文），限制在 5000 字符内
5. **沙盒约束**：所有读写操作只能访问 `{baseDir}`（即 `skills/<技能名>/`）和 office 目录内的文件
6. **禁止危险操作**：不能访问外部路径、不能执行系统敏感命令

---

## 🔧 创建流程（你每一步应该做什么）

### 第1步：理解需求
仔细阅读用户描述，拆解：
- 这个技能要解决什么问题？
- 输入是什么？输出是什么？
- 需要外部 API 还是纯 Python 能搞定？

### 第2步：确定技能名和脚本名
- 技能文件夹名（英文）：如 `dingtalk_notify`
- 中文名：如 `钉钉消息推送`
- 脚本名：如 `send.py`

### 第3步：编写 skill.md
用 `write_office_file` 工具创建：
```
filepath = "skills/<技能名>/skill.md"
content = <按模板编写的完整说明书>
```

### 第4步：编写 Python 脚本
用 `write_office_file` 工具创建：
```
filepath = "skills/<技能名>/<script>.py"
content = <功能代码>
```

### 第5步：验证
用 `execute_office_shell` 工具运行脚本测试：
```
command = "python skills/<技能名>/<script>.py <测试参数>"
```
如果报错，根据错误信息修正脚本。

### 第6步：告知用户
总结你创建了什么技能，功能是什么，如何使用。

---

## 📋 创建前检查清单

- [ ] skill.md 第一行是 `name: ...`
- [ ] skill.md 第二行是 `description: "..."`（带双引号）
- [ ] 命令模板中路径使用 `{baseDir}` 占位符
- [ ] Python 脚本有 shebang/用法说明
- [ ] Python 脚本有错误处理
- [ ] 没有违反沙盒限制
- [ ] 已用 `execute_office_shell` 做过基础测试

---

## 🎯 示例：用户说"帮我创建一个翻译技能"

你应该：

1. 创建 `skills/translator/skill.md`
2. 创建 `skills/translator/translate.py`（调用免费翻译API或无依赖实现）
3. 测试 `python skills/translator/translate.py "hello" en zh`
4. 告知用户结果
