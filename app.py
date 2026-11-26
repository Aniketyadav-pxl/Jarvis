"""Vercel FastAPI entrypoint for JARVIS (Demo / Cloud Mode)."""
import os, sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "agent"))

# Force demo mode on Vercel so it uses bundled sample notes instead of D:\Notes
if os.environ.get("VERCEL"):
    os.environ.setdefault("JARVIS_DEMO", "1")

import data, vault, tools, chat, voice, builder

G = vault.build()
N = G["notes"]
ID = {n["id"]: i for i, n in enumerate(N)}
EDGES = [[ID[a], ID[b]] for a, b in G["edges"]]
ADJ = [[] for _ in N]
for a, b in EDGES:
    ADJ[a].append(b)
    ADJ[b].append(a)
GRAPH = {
    "demo": data.DEMO,
    "skipped": G["skipped"],
    "dangling": G["dangling"],
    "edges": EDGES,
    "nodes": [{"t": n["title"], "k": n["type"], "d": n["degree"], "p": n["path"]} for n in N],
}
tools.init(G)

app = FastAPI(title="JARVIS")


@app.get("/api/status")
def api_status():
    return dict(chat.status(), voice=voice.status())


@app.get("/api/graph")
def api_graph():
    return GRAPH


@app.get("/api/note")
def api_note(i: int):
    if i < 0 or i >= len(N):
        raise HTTPException(status_code=404, detail="no such note")
    n = N[i]
    return {"t": n["title"], "k": n["type"], "p": n["path"], "text": n["text"][:2500], "links": ADJ[i]}


@app.post("/api/ask")
async def api_ask(request: Request):
    b = await request.json()
    tool = b.get("tool")
    if tool not in (None, "brief_me", "plan_day", "read_inbox", "memory_list"):
        raise HTTPException(status_code=400, detail="bad request")
    return chat.ask(str(b.get("text", ""))[:2000], tool)


@app.post("/api/speak")
async def api_speak(request: Request):
    b = await request.json()
    try:
        audio = voice.speak(b.get("text", ""))
        return Response(content=audio, media_type="audio/mpeg")
    except voice.VoiceError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.post("/api/listen")
async def api_listen(request: Request):
    ct = request.headers.get("content-type", "audio/webm")
    body = await request.body()
    if not (0 < len(body) <= 4_500_000):
        raise HTTPException(status_code=400, detail="audio too large or empty")
    try:
        return {"text": voice.listen(body, ct)}
    except voice.VoiceError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/builds/{slug}/{file_path:path}")
@app.get("/builds/{slug}/")
def serve_build(slug: str, file_path: str = "index.html"):
    base = builder.BUILDS.resolve()
    target = (base / slug / (file_path or "index.html")).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="build not found")
    mime = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}.get(target.suffix.lower(), "application/octet-stream")
    return Response(content=target.read_bytes(), media_type=mime)


# Mount UI last so all /api/* and /builds/* routes take priority
app.mount("/", StaticFiles(directory=str(ROOT / "ui"), html=True), name="ui")