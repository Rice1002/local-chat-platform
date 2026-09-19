from datetime import datetime

TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取当前日期和时间",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

def run():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")