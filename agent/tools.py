"""Tools. Each returns {"spoken": 1-2 sentences, "card": {"title", "rows": [{"h", "b"}]}}.
Vault folders remain read-only; website builds write only inside builds/."""
import os, re, html, webbrowser,subprocess, urllib.request, urllib.parse
import data, vault, memory, builder

G = None


def init(g):
    global G
    G = g


def _notes():
    return G["notes"] + memory.read_all()


def find(q, k=5):
    return vault.search({"notes": _notes()}, q, k)


def _fn(name, desc, props, req=()):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()}, "required": list(req)}}}


SCHEMA = [
    _fn("search_brain", "Find a specific fact in the user's own files. Never for small talk.", {"query": "what to look for"}, ["query"]),
    _fn("research_web", "Look something up on the web, then relate it to the user's own numbers.", {"query": "web search query"}, ["query"]),
    _fn("read_inbox", "Read-only: recent email, who wrote, and whether they appear in the user's files.", {}),
    _fn("brief_me", "Calendar, unread mail, and what slipped.", {}),
    _fn("remember", "Save ONE durable fact the user asked to keep, or that will matter in three months.", {"fact": "the fact, one sentence"}, ["fact"]),
    _fn("plan_day", "Plan the day: five items max, ordered by what moves money.", {}),
    _fn("build_website", "Build a complete single-file HTML/CSS/JS website, save it in builds/<name>/, and open it in the browser.",
        {"name": "short project slug, e.g. ai-agency", "description": "detailed requirements, style, and sections"}, ["name", "description"]),
    _fn("edit_website", "Modify an existing website previously built in builds/<name>/ and open the updated page.",
        {"name": "existing project slug", "changes": "what to change or add"}, ["name", "changes"]),
    _fn("list_websites", "List all websites previously built in builds/ with their preview URLs.", {}),
    _fn("open_in_vscode", "Open a built website project folder in VS Code.", {"name": "existing project slug"}, ["name"]),
    _fn("play_music", "Open a song, artist, or playlist on YouTube Music (default) or Spotify.",
        {"query": "song, artist, or playlist name", "source": "youtube_music or spotify"}, ["query"]),
]
INJ = re.compile(r"ignore (all |any |your |previous |prior )*(instructions|rules)|you are now|reveal .*system prompt", re.I)
AMT = re.compile(r"(\d[\d,]*)\s*(USD|INR|EUR|GBP)")


def _amt(t):
    m = AMT.search(t)
    return (int(m.group(1).replace(",", "")), m.group(2)) if m else None


def _status(t):
    m = re.search(r"Status:\s*([A-Za-z]+)", t)
    return m.group(1).lower() if m else None


def _card(title, rows, extra=None):
    return {"title": title, "rows": [{"h": h, "b": b} for h, b in rows] + ([{"h": "note", "b": extra}] if extra else [])}


def search_brain(query, say):
    hits = find(query, 3)
    if not hits:
        return {"spoken": "Not in your files.", "card": _card("No match", [(query, "No file matched.")])}
    facts = "\n".join("[%s] %s" % (h["path"], h["line"]) for h in hits)
    spoken = say("Answer the question in one or two short sentences using ONLY these lines. Name every file you used; if three, say three files and name all three. If the lines don't answer it, say: Not in your files.",
                 "Question: %s\n%s" % (query, facts))
    if not spoken:
        spoken = "Found it in %s." % hits[0]["title"] if len(hits) == 1 else "%d files: %s." % (len(hits), ", ".join(h["title"] for h in hits))
    inj = any(INJ.search(h["text"]) for h in hits)
    return {"spoken": spoken + (" One file has instruction-like text. Ignored." if inj else ""),
            "card": _card("From your files", [(h["path"], h["line"]) for h in hits])}


def _tx(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def research_web(query, say):
    req = urllib.request.Request("[https://html.duckduckgo.com/html/?q=](https://html.duckduckgo.com/html/?q=)" + urllib.parse.quote(query), headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    res = []
    for href, title, snip in re.findall(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', page, re.S)[:5]:
        m = re.search(r"uddg=([^&]+)", href)
        res.append((urllib.parse.unquote(m.group(1)) if m else href, _tx(title), _tx(snip)))
    if not res:
        return {"spoken": "Web search came back empty.", "card": _card("Web", [(query, "No results parsed. The search page may have changed or blocked the request.")])}
    mine = find(query, 3)
    facts = "WEB:\n" + "\n".join("%s | %s" % (t, s) for _, t, s in res[:4]) + "\nUSER FILES:\n" + "\n".join("[%s] %s" % (h["path"], h["line"]) for h in mine)
    spoken = say("One or two short sentences. State the web fact, then land it on the user's own numbers from USER FILES (e.g. what it does to his margin). Use only numbers present below and say which came from the web and which from his files. If no user number applies, say so.",
                 "Question: %s\n%s" % (query, facts))
    return {"spoken": spoken or "Top hit: %s. Model's offline, so not tied to your numbers." % urllib.parse.urlparse(res[0][0]).netloc,
            "card": _card("Web", [(u, "%s - %s" % (t, s)) for u, t, s in res] + [(h["path"], h["line"]) for h in mine])}


def _known(m):
    keys = [k.lower() for k in (m["email"], m["from"]) if len(k) > 3]
    for n in G["notes"]:
        blob = (n["title"] + " " + n["text"]).lower()
        if any(k in blob for k in keys):
            return n["title"]
    return None


def read_inbox(say=None):
    try:
        mails = data.inbox()
    except data.NotConnected as e:
        return {"spoken": "Inbox isn't connected.", "card": _card("Inbox", [("setup", str(e))])}
    un = [m for m in mails if m["unread"]]
    rows = []
    for m in mails:
        k = _known(m)
        rows.append(("%s%s" % ("* " if m["unread"] else "", m["from"]), "%s | %s" % (m["subject"], ("in your files: " + k) if k else "not in your files")))
    new = [m["from"] for m in un if not _known(m)]
    spoken = "%d unread of %d." % (len(un), len(mails)) + (" Not in your files: %s." % ", ".join(new[:3]) if new else " All senders are in your files." if un else "")
    inj = any(INJ.search(m["subject"]) for m in mails)
    return {"spoken": spoken + (" One subject has instruction-like text. Ignored." if inj else ""), "card": _card("Inbox (read-only, * = unread)", rows)}


def _slipped():
    out = []
    for n in G["notes"]:
        if n["type"] == "invoice" and _status(n["text"]) in ("unpaid", "overdue"):
            a = _amt(n["text"])
            out.append((n["path"], "%s marked %s%s" % (n["title"], _status(n["text"]), " (%d %s invoiced)" % a if a else "")))
    return out


def brief_me(say=None):
    rows, extra = [], ""
    try:
        evs, extra = data.events(2)
        rows += [("%s %s" % (e["date"].strftime("%a"), e["time"]), e["title"]) for e in evs] or [("calendar", "Nothing in the next two days.")]
    except data.NotConnected as e:
        evs = []
        rows.append(("calendar", str(e)))
    unread, late = None, []
    try:
        mails = data.inbox()
        unread = sum(m["unread"] for m in mails)
        late = [m for m in mails if m["unread"] and m["days_ago"] >= 3]
        rows.append(("unread", "%d unread. %d older than 3 days: %s" % (unread, len(late), ", ".join(m["from"] for m in late) or "none")))
    except data.NotConnected as e:
        rows.append(("inbox", str(e)))
    sl = _slipped()
    rows += [("slipped: " + p, t) for p, t in sl]
    today = [e for e in evs if e["date"] == data.dt.date.today()]
    inv = [t for _, t in sl]
    parts = ["%d today%s." % (len(today), ", first %s %s" % (today[0]["time"], today[0]["title"]) if today else "")]
    parts.append(("%d unread, %d over 3 days old." % (unread, len(late))) if unread is not None else "Inbox offline.")
    parts.append("%d invoices marked unpaid." % len(inv) if inv else "No invoices marked unpaid.")
    return {"spoken": " ".join(parts), "card": _card("Brief", rows, extra)}


def plan_day(say=None):
    items = []
    for n in G["notes"]:
        st, a = _status(n["text"]), _amt(n["text"])
        if n["type"] == "invoice" and st == "unpaid" and a:
            items.append((0, -a[0], n["title"], "Chase it: %d %s invoiced, marked unpaid" % a, n["path"]))
        elif n["type"] == "proposal" and a:
            items.append((1, -a[0], n["title"], "Follow up: quoted %d %s" % a, n["path"]))
        elif n["type"] == "application" and st in ("interview", "applied"):
            items.append((2, 0, n["title"], "Job lead, status %s" % st, n["path"]))
    items = [(t, n, "files: " + b, p) for _, _, t, b, p in sorted(items)]
    note = ""
    try:
        evs, note = data.events(1)
        items += [(e["title"], e["time"], "calendar today", "calendar") for e in evs]
    except data.NotConnected as e:
        note = str(e)
    items = items[:5]
    if not items:
        return {"spoken": "Nothing money-linked found.", "card": _card("Plan", [("empty", "No unpaid invoices, quotes, live applications or events.")], note)}
    return {"spoken": "%d items. Start with %s." % (len(items), items[0][0]), "card": _card("Plan (most money first, then calendar)", [(t, "%s | %s" % (b, p)) for t, _, b, p in
            [(x[0], x[1], x[2], x[3]) for x in items]], note)}


def remember(fact, say=None):
    name = memory.write(fact)
    return {"spoken": "Saved: %s" % " ".join(str(fact).split())[:300], "card": _card("Memory written", [("memory/" + name, "One dated file. Delete it to forget.")])}


def memory_list(say=None):
    ms = memory.read_all()
    if not ms:
        return {"spoken": "Nothing saved yet.", "card": _card("Memory", [("memory/", "No files yet.")])}
    return {"spoken": "%d saved." % len(ms), "card": _card("Memory (newest first; delete a file to forget it)", [(m["path"], m["text"]) for m in ms[:30]])}


def build_website(name, description, say):
    code_fn = getattr(say, "code", None)
    slug, url, files = builder.build(name, description, code_fn)
    return {
        "spoken": f"Built {slug} with {len(files)} files and opened it in Brave.",
        "card": _card("Website Built", [("project", slug), ("files", ", ".join(files)), ("preview", url)]),
    }


def edit_website(name, changes, say):
    code_fn = getattr(say, "code", None)
    slug, url, files = builder.edit(name, changes, code_fn)
    return {
        "spoken": f"Updated {slug} and reopened it in Brave.",
        "card": _card("Website Updated", [("project", slug), ("files", ", ".join(files)), ("preview", url)]),
    }


def list_websites():
    sites = builder.list_builds()
    if not sites:
        return {"spoken": "You haven't built any websites yet.", "card": _card("Websites", [("builds/", "Empty")])}
    return {
        "spoken": f"You have {len(sites)} built websites: " + ", ".join(s for s, _ in sites[:5]) + ".",
        "card": _card("Built Websites", sites),
    }


def open_in_vscode(name):
    slug, path = builder.open_vscode(name)
    return {
        "spoken": f"Opening {slug} in VS Code.",
        "card": _card("VS Code", [("project", slug), ("folder", path)]),
    }


def _open_url(url):
    if os.environ.get("VERCEL"):
        return
    try:
        subprocess.Popen(["cmd", "/c", "start", "brave", url], shell=False)
    except Exception:
        webbrowser.open(url)


def _first_youtube_id(query):
    """Fetch YouTube search HTML with consent cookie and return the first video ID."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+667",
        },
    )
    page = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")
    m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', page)
    return m.group(1) if m else None


def play_music(query, source="youtube"):
    q = (query or "").strip()
    src = (source or "youtube").lower()
    if "spotify" in src and hasattr(os, "startfile"):
        uri = "spotify:search:" + urllib.parse.quote(q)
        os.startfile(uri)
        return {"spoken": f"Opening {q} on Spotify.", "card": _card("Music", [("Spotify", q), ("URI", uri)])}

    vid = None
    try:
        vid = _first_youtube_id(q)
    except Exception:
        pass

    if vid:
        domain = "music.youtube.com" if "music" in src else "www.youtube.com"
        url = f"https://{domain}/watch?v={vid}"
        _open_url(url)
        return {"spoken": f"Playing {q}.", "card": _card("Now Playing", [("Query", q), ("URL", url)])}

    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)
    _open_url(url)
    return {"spoken": f"Opened search for {q}.", "card": _card("Music Search", [("Query", q), ("URL", url)])}


def run(name, args, say):
    f = {
        "search_brain": lambda: search_brain(args.get("query", ""), say),
        "research_web": lambda: research_web(args.get("query", ""), say),
        "read_inbox": lambda: read_inbox(),
        "brief_me": lambda: brief_me(),
        "plan_day": lambda: plan_day(),
        "remember": lambda: remember(args.get("fact", "")),
        "memory_list": lambda: memory_list(),
        "build_website": lambda: build_website(args.get("name", "site"), args.get("description", ""), say),
        "edit_website": lambda: edit_website(args.get("name", "site"), args.get("changes", ""), say),
        "list_websites": lambda: list_websites(),
        "open_in_vscode": lambda: open_in_vscode(args.get("name", "")),
        "play_music": lambda: play_music(args.get("query", ""), args.get("source", "youtube_music")),
    }.get(name)
    if not f:
        return {"spoken": "No such tool.", "card": _card("Error", [(name, "Unknown tool.")])}
    try:
        r = f()
    except Exception as e:
        return {"spoken": "%s failed." % name, "card": _card("Error", [(type(e).__name__, str(e))])}
    r["tool"] = name
    return r