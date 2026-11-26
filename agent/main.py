"""HTTP server + API. Localhost only. Run: python agent/main.py"""
import json, sys, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import data, vault, tools, chat, voice

PORT = int(data.env("JARVIS_PORT", "8765"))
ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui"
BUILDS = ROOT / "builds"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
}
G = vault.build()
N = G["notes"]
ID = {n["id"]: i for i, n in enumerate(N)}
EDGES = [[ID[a], ID[b]] for a, b in G["edges"]]
ADJ = [[] for _ in N]
for a, b in EDGES:
    ADJ[a].append(b)
    ADJ[b].append(a)
GRAPH = {"demo": data.DEMO, "skipped": G["skipped"], "dangling": G["dangling"], "edges": EDGES,
         "nodes": [{"t": n["title"], "k": n["type"], "d": n["degree"], "p": n["path"]} for n in N]}


tools.init(G)


class H(BaseHTTPRequestHandler):
    def ok(self):  # blocks DNS-rebinding and cross-site calls
        return self.headers.get("Host") in ("localhost:%d" % PORT, "127.0.0.1:%d" % PORT) and self.headers.get("Origin") in (None, "http://localhost:%d" % PORT, "http://127.0.0.1:%d" % PORT)

    def log_message(self, *a):
        pass

    def send(self, body, mime, code=200):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if not self.ok():
            return self.send({"error": "forbidden"}, "application/json", 403)
        n = int(self.headers.get("Content-Length") or 0)
        ct = self.headers.get("Content-Type", "")
        if self.path == "/api/listen" and ct.startswith("audio/") and 0 < n <= 8000000:
            try:
                return self.send({"text": voice.listen(self.rfile.read(n), ct)}, "application/json")
            except voice.VoiceError as e:
                return self.send({"error": str(e)}, "application/json", 502)
        if self.path not in ("/api/ask", "/api/speak") or "application/json" not in ct or n > 10000:
            return self.send({"error": "bad request"}, "application/json", 400)
        try:
            b = json.loads(self.rfile.read(n))
            tool = b.get("tool")
            assert tool in (None, "brief_me", "plan_day", "read_inbox", "memory_list")
        except (ValueError, AssertionError, AttributeError):
            return self.send({"error": "bad request"}, "application/json", 400)
        if self.path == "/api/speak":
            try:
                return self.send(voice.speak(b.get("text", "")), "audio/mpeg")
            except voice.VoiceError as e:
                return self.send({"error": str(e)}, "application/json", 502)
        self.send(chat.ask(str(b.get("text", ""))[:2000], tool), "application/json")

    def do_GET(self):
        if not self.ok():
            return self.send({"error": "forbidden"}, "application/json", 403)
        u = urlparse(self.path)
        if u.path == "/api/status":
            return self.send(dict(chat.status(), voice=voice.status()), "application/json")
        if u.path == "/api/graph":
            return self.send(GRAPH, "application/json")
        if u.path == "/api/note":
            try:
                i = int(parse_qs(u.query)["i"][0])
                n = N[i]
            except (KeyError, ValueError, IndexError):
                return self.send({"error": "no such note"}, "application/json", 404)
            return self.send({"t": n["title"], "k": n["type"], "p": n["path"], "text": n["text"][:2500], "links": ADJ[i]}, "application/json")
        if u.path.startswith("/builds/"):
            rel = u.path[len("/builds/"):].lstrip("/")
            target = (BUILDS / rel).resolve()
            if target.is_dir():
                target = (target / "index.html").resolve()
            if BUILDS.resolve() in target.parents and target.is_file():
                return self.send(target.read_bytes(), MIME.get(target.suffix.lower(), "application/octet-stream"))
            return self.send({"error": "build not found"}, "application/json", 404)
        f = (UI / ("index.html" if u.path == "/" else u.path.lstrip("/"))).resolve()
        if UI.resolve() in f.parents and f.is_file():
            return self.send(f.read_bytes(), MIME.get(f.suffix.lower(), "application/octet-stream"))
        self.send({"error": "not found"}, "application/json", 404)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = "http://localhost:%d" % PORT
    print("JARVIS %s | %d notes | %d links | %s" % ("DEMO" if data.DEMO else "REAL", len(N), len(EDGES), url))
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass