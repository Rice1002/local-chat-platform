TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "联网搜索实时信息",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"],
        },
    },
}

def run(query: str):
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "没有找到相关结果"
        return "\n\n".join(
            f"【{r['title']}】\n{r['body']}\n来源：{r['href']}"
            for r in results
        )
    except Exception as e:
        return f"搜索失败：{e}"