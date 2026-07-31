"""
MyClaw 技能脚手架
用法: python scaffold.py <英文技能名> <中文技能名> "<一句话描述>"
示例: python scaffold.py web_fetch "网页抓取" "抓取网页提取纯文本正文"
"""
import sys, os

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


SKILL_TEMPLATE = '''name: {display_name}
description: "{description}"

## 🧠 智能体使用说明

### 适用场景
- 待补充

### run 模式命令格式
```
python {{baseDir}}/main.py <参数>
```

### 参数说明
- `<参数>`: 待补充

### 示例
```
python {{baseDir}}/main.py example_arg
```

### 注意事项
1. 待补充
'''

SCRIPT_TEMPLATE = '''"""
MyClaw {display_name} Skill
用法: python main.py <参数>
"""
import sys


def main():
    # TODO: 实现核心逻辑
    if len(sys.argv) < 2:
        print("用法: python main.py <参数>")
        sys.exit(1)

    arg = sys.argv[1]
    result = f"处理结果: {{arg}}"
    print(result)


if __name__ == "__main__":
    main()
'''


def create_skill(english_name: str, display_name: str, description: str):
    """创建技能目录和模板文件"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_dir = os.path.join(base_dir, english_name)

    # 检查是否已存在
    if os.path.exists(skill_dir):
        print(f"⚠️ 技能 '{english_name}' 已存在，取消创建。")
        print(f"   路径: {skill_dir}")
        return False

    # 创建目录
    os.makedirs(skill_dir, exist_ok=True)

    # 写入 skill.md
    skill_content = SKILL_TEMPLATE.format(
        display_name=display_name,
        description=description
    )
    with open(os.path.join(skill_dir, "skill.md"), "w", encoding="utf-8") as f:
        f.write(skill_content)

    # 写入 main.py
    script_content = SCRIPT_TEMPLATE.format(display_name=display_name)
    with open(os.path.join(skill_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(script_content)

    print(f"✅ 技能模板已创建!")
    print(f"   目录: {skill_dir}")
    print(f"   ├── skill.md  (中文名: {display_name})")
    print(f"   └── main.py   (入口脚本)")
    print(f"")
    print(f"📝 下一步：")
    print(f"   1. 编辑 skill.md，补全使用说明")
    print(f"   2. 编辑 main.py，实现核心逻辑")
    print(f"   3. 下次启动 MyClaw 自动生效！")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python scaffold.py <英文名> <中文名> <描述>")
        print("示例: python scaffold.py web_fetch 网页抓取 \"抓取网页提取纯文本\"")
        sys.exit(1)

    name = sys.argv[1]
    dname = sys.argv[2]
    desc = sys.argv[3]

    success = create_skill(name, dname, desc)
    sys.exit(0 if success else 1)
