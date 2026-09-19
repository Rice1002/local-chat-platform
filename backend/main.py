from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx, json, sqlite3, os
from typing import Optional

from skills_loader import load_all_skills, list_skills, get_tools, execute_tool

OLLAMA = "http://localhost:11434"
DB_PATH = os.path.join(os.path.dirname(__file__), "chat.db")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '新对话',
            model TEXT DEFAULT 'qwen2.5:7b',
            system_prompt TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

init_db()
load_all_skills()

# ---------- Pydantic ----------
class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"
    model: Optional[str] = "qwen2.5:7b"
    system_prompt: Optional[str] = ""

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None

class ChatRequest(BaseModel):
    content: str
    skills: list[str] = []

# ---------- 模型 ----------
@app.get("/api/models")
async def list_models():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA}/api/tags", timeout=5)
            return r.json()
    except Exception as e:
        raise HTTPException(503, f"Ollama 不可用: {e}")

# ---------- 技能 ----------
@app.get("/api/skills")
def api_list_skills():
    return list_skills()

# ---------- 会话 ----------
@app.get("/api/conversations")
def list_conversations():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, model, system_prompt, updated_at FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/conversations")
def create_conversation(data: ConversationCreate):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO conversations (title, model, system_prompt) VALUES (?, ?, ?)",
        (data.title, data.model, data.system_prompt)
    )
    conn.commit()
    cid = cur.lastrowid
    row = conn.execute(
        "SELECT id, title, model, system_prompt FROM conversations WHERE id=?", (cid,)
    ).fetchone()
    conn.close()
    return dict(row)

@app.get("/api/conversations/{cid}")
def get_conversation(cid: int):
    conn = get_db()
    conv = conn.execute(
        "SELECT id, title, model, system_prompt FROM conversations WHERE id=?", (cid,)
    ).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")
    msgs = conn.execute(
        "SELECT id, role, content FROM messages WHERE conversation_id=? ORDER BY id", (cid,)
    ).fetchall()
    conn.close()
    result = dict(conv)
    result["messages"] = [dict(m) for m in msgs]
    return result

@app.patch("/api/conversations/{cid}")
def update_conversation(cid: int, data: ConversationUpdate):
    conn = get_db()
    if not conn.execute("SELECT id FROM conversations WHERE id=?", (cid,)).fetchone():
        conn.close()
        raise HTTPException(404, "对话不存在")
    fields, values = [], []
    if data.title is not None:
        fields.append("title=?"); values.append(data.title)
    if data.model is not None:
        fields.append("model=?"); values.append(data.model)
    if data.system_prompt is not None:
        fields.append("system_prompt=?"); values.append(data.system_prompt)
    if fields:
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(cid)
        conn.execute(f"UPDATE conversations SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: int):
    conn = get_db()
    conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/conversations")
def delete_all_conversations():
    conn = get_db()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM conversations")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('conversations', 'messages')")
    conn.commit()
    conn.close()
    return {"ok": True}

# ---------- 聊天 ----------
@app.post("/api/conversations/{cid}/chat")
async def chat(cid: int, req: ChatRequest):
    conn = get_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id", (cid,)
        ).fetchall()
    ]

    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (cid, req.content)
    )
    if not history and conv["title"] == "新对话":
        new_title = req.content[:20] + ("..." if len(req.content) > 20 else "")
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_title, cid)
        )
    else:
        conn.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
    conn.commit()

    conv_model = conv["model"]
    conv_system = conv["system_prompt"]
    conn.close()

    messages = []
    if conv_system:
        messages.append({"role": "system", "content": conv_system})
    messages.extend(history)
    messages.append({"role": "user", "content": req.content})

    enabled_tools = get_tools(req.skills)

    async def stream():
        full = ""
        async with httpx.AsyncClient(timeout=None) as client:
            base_payload = {
                "model": conv_model,
                "messages": messages,
                "stream": False,
            }
            if enabled_tools:
                base_payload["tools"] = enabled_tools

            r = await client.post(f"{OLLAMA}/api/chat", json=base_payload)
            data = r.json()
            msg = data.get("message", {})

            if msg.get("tool_calls"):
                # 把模型发起的工具调用加入历史
                messages.append(msg)

                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}

                    result = execute_tool(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "content": str(result),
                    })

                # 把工具结果发回模型，拿到最终流式回答
                final_payload = {
                    "model": conv_model,
                    "messages": messages,
                    "stream": True,
                }
                async with client.stream("POST", f"{OLLAMA}/api/chat", json=final_payload) as r2:
                    async for line in r2.aiter_lines():
                        if line.strip():
                            yield line + "\n"
                            try:
                                d = json.loads(line)
                                chunk = d.get("message", {}).get("content")
                                if chunk:
                                    full += chunk
                            except Exception:
                                pass
            else:
                # 没有工具调用，直接流式重新请求
                stream_payload = {
                    "model": conv_model,
                    "messages": messages,
                    "stream": True,
                }
                async with client.stream("POST", f"{OLLAMA}/api/chat", json=stream_payload) as r3:
                    async for line in r3.aiter_lines():
                        if line.strip():
                            yield line + "\n"
                            try:
                                d = json.loads(line)
                                chunk = d.get("message", {}).get("content")
                                if chunk:
                                    full += chunk
                            except Exception:
                                pass

        # 保存助手回复
        conn2 = get_db()
        conn2.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (cid, full)
        )
        conn2.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
        conn2.commit()
        conn2.close()

    return StreamingResponse(stream(), media_type="application/x-ndjson")