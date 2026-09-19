TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"],
        },
    },
}

def run(city: str):
    mock = {"北京": "晴，25°C", "上海": "多云，28°C", "青岛": "阴，22°C"}
    return mock.get(city, f"暂未收录 {city} 的天气数据")