# Local Chat Platform

本地优先的 AI 对话平台，基于 **Ollama + FastAPI + SQLite**，支持多会话管理和可插拔技能系统。所有数据存在本地，模型跑在自己的电脑上。

## ✨ 功能

- **本地运行**：模型通过 Ollama 本地推理，数据不出电脑
- **多会话管理**：新建、切换、删除对话，历史持久化到 SQLite
- **流式输出**：逐字返回，Markdown 实时渲染
- **预设模式**：一键切换「润色文案」「PPT 大纲」「文档撰写」「普通聊天」
- **可插拔技能**：技能放在 `skills/` 目录，前端可自由开关
- **模型切换**：顶部下拉框选择本地已安装的任意 Ollama 模型

## 🧩 技术栈

| 层 | 技术 |
|---|---|
| 推理 | [Ollama](https://ollama.com/) |
| 后端 | FastAPI + Uvicorn |
| 数据库 | SQLite（Python 标准库） |
| 前端 | 原生 HTML + JS + Marked.js |

## 📦 依赖

- Python 3.10+
- Ollama（已安装并运行）
- 至少一个本地模型，推荐：
  ```bash
  ollama pull qwen2.5:7b
  ollama pull qwen2.5-coder:1.5b
  ```

Python 依赖：

```bash
pip install fastapi "uvicorn[standard]" httpx
```

可选（启用联网搜索技能）：

```bash
pip install duckduckgo-search
```

## 🚀 启动

**1. 确保 Ollama 在运行**

```bash
ollama list
```

**2. 启动后端**

```bash
cd backend
python -m uvicorn main:app --reload --port 8001
```

启动成功后会看到：

```
[skills] 已加载：time
[skills] 已加载：weather
[skills] 已加载：web_search
INFO:     Application startup complete.
```

**3. 打开前端**

双击 `chat.html`，或在浏览器里打开这个文件。

## 📁 项目结构

```
chat_ai/
├── chat.html                 # 前端单页
├── backend/
│   ├── main.py               # FastAPI 后端（核心逻辑）
│   ├── skill_loader.py       # 技能加载器
│   ├── chat.db               # SQLite 数据库（自动生成）
│   └── skills/               # 技能目录
│       ├── __init__.py
│       ├── time.py
│       ├── weather.py
│       └── web_search.py
└── README.md
```

## 🔌 添加新技能

在 `backend/skills/` 下新建一个 `.py` 文件，必须包含两个东西：

**1. `TOOL`**：告诉模型这个技能是干什么的、需要什么参数

**2. `run()`**：模型决定调用后，实际执行的 Python 函数

示例：新建 `backend/skills/calc.py`

```python
import ast, operator

TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "计算数学表达式，如 '2 + 3 * 4'",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"],
        },
    },
}

def run(expression: str):
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
    }
    def eval_node(n):
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.BinOp):
            return ops[type(n.op)](eval_node(n.left), eval_node(n.right))
        raise ValueError("不支持的表达式")
    try:
        return str(eval_node(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"计算失败：{e}"
```

保存后**重启后端**，刷新前端页面，顶栏会自动出现新技能按钮。**不需要修改任何核心代码。**

## 🎯 使用说明

- **技能按钮默认灰色**，点击变蓝才会启用。发送消息时只把已启用的技能传给模型。
- **每个对话独立**：模型、系统提示、消息记录都按对话隔离。
- **切换模型**：顶部下拉框即时切换，只影响当前对话。
- **清空所有数据**：左下角按钮，会删除数据库里所有对话，不可恢复。

## ⚠️ 注意事项

- `chat.db` 包含所有对话记录，**不要提交到 Git**（已在 `.gitignore` 中排除）。
- 技能在本地执行，新增技能时注意做好参数校验，避免被恶意 prompt 诱导。
- 技能调用依赖模型的 function calling 能力。`qwen2.5:7b` 支持，但小模型偶尔不稳定。如果发现模型不调用工具，可以试试在系统提示里加一句：「遇到时间、天气、搜索类问题，必须调用对应工具」。

## 📄 License

MIT