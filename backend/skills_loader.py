import os
import importlib

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

_registry = {}

def load_all_skills():
    _registry.clear()
    if not os.path.isdir(SKILLS_DIR):
        return

    for filename in os.listdir(SKILLS_DIR):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        skill_id = filename[:-3]
        try:
            module = importlib.import_module(f"skills.{skill_id}")
            if not hasattr(module, "TOOL") or not hasattr(module, "run"):
                print(f"[skills] 跳过 {skill_id}：缺少 TOOL 或 run")
                continue
            _registry[skill_id] = {
                "id": skill_id,
                "tool": module.TOOL,
                "run": module.run,
                "name": module.TOOL["function"]["name"],
                "description": module.TOOL["function"]["description"],
            }
            print(f"[skills] 已加载：{skill_id}")
        except Exception as e:
            print(f"[skills] 加载 {skill_id} 失败：{e}")

def list_skills():
    return [
        {"id": s["id"], "name": s["name"], "description": s["description"]}
        for s in _registry.values()
    ]

def get_tools(enabled_ids):
    return [_registry[sid]["tool"] for sid in enabled_ids if sid in _registry]

def execute_tool(tool_name, arguments):
    for s in _registry.values():
        if s["name"] == tool_name:
            try:
                return s["run"](**arguments)
            except Exception as e:
                return f"执行失败：{e}"
    return f"未找到工具：{tool_name}"