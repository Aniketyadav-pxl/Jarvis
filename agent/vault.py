"""Folders -> graph. Pure parsing; every file read goes through data.py."""
import re, sys, zlib, collections
import data

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)


def pdf_text(raw):
    """Best-effort stdlib PDF text: Flate streams, Tj/TJ strings. No font-encoded (CID) text."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        s = m.group(1)
        try:
            s = zlib.decompress(s)
        except zlib.error:
            pass
        for op in re.finditer(rb"\[((?:[^\]\\]|\\.)*)\]\s*TJ|(\((?:[^\\()]|\\.)*\))\s*Tj", s, re.S):
            body = op.group(1) or op.group(2)
            out.append("".join(re.sub(rb"\\(.)", rb"\1", x).decode("latin-1")
                               for x in re.findall(rb"\(((?:[^\\()]|\\.)*)\)", body)))
    return "\n".join(out)


def parse(d):
    path, ext = d["path"], d["ext"]
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    meta = {}
    if ext == ".pdf":
        text = pdf_text(d["raw"])
    else:
        text = d["raw"].decode("utf-8-sig", "replace")
        m = FM.match(text)
        if m:
            for line in m.group(1).splitlines():
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip()
            text = text[m.end():]
    h = re.search(r"^#\s+(.+)$", text, re.M) if ext != ".pdf" else None
    top = path.split("/")[0] if "/" in path else ""
    top = {"people": "person"}.get(top.lower(), top[:-1] if top.endswith("s") and len(top) > 3 else top)
    kind = meta.get("type") or top or ("document" if ext == ".pdf" else "note")
    aliases = [a.strip() for a in meta.get("aliases", "").strip("[]").split(",") if a.strip()]
    return {"id": d["root"] + "/" + path, "path": path, "title": meta.get("title") or (h.group(1).strip() if h else stem),
            "stem": stem, "type": kind.lower(), "ext": ext, "aliases": aliases, "text": text,
            "links": [t.strip().split("/")[-1] for t in LINK.findall(text)]}


def build():
    skipped = {}
    notes = [parse(d) for d in data.scan(skipped)]
    idx = {}
    for n in notes:
        for k in [n["title"], n["stem"]] + n["aliases"]:
            idx.setdefault(k.lower(), n["id"])
    edges, dangling = set(), 0
    for n in notes:
        for t in n["links"]:
            tid = idx.get(t.lower())
            if tid is None:
                dangling += 1
            elif tid != n["id"]:
                edges.add(tuple(sorted((n["id"], tid))))
    deg = collections.Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    for n in notes:
        n["degree"] = deg[n["id"]]
    return {"notes": notes, "edges": sorted(edges), "dangling": dangling, "skipped": skipped}


STOP = set("the and for what who how was were are did does you your with that this from have has not about when which".split())


def search(g, q, k=5):
    """Score notes against a question. Whole-word match (plural-tolerant). frac = share of query terms found; the router uses it."""
    terms = [t for t in re.findall(r"\w+", q.lower()) if len(t) > 2 and t not in STOP]
    has = lambda t, bag: t in bag or (t[:-1] in bag if t.endswith("s") else t + "s" in bag)
    out = []
    for n in g["notes"]:
        ws, tw = collections.Counter(re.findall(r"\w+", n["text"].lower())), set(re.findall(r"\w+", n["title"].lower()))
        hit = [t for t in terms if has(t, ws) or has(t, tw)]
        if not hit:
            continue
        lines = [l.strip() for l in n["text"].splitlines() if l.strip() and not l.startswith("#")] or [n["title"]]
        best = max(lines, key=lambda l: sum(t in l.lower() for t in terms))
        s = sum(2 if has(t, tw) else 1 for t in hit) + 0.1 * min(sum(ws[t] + ws[t + "s"] for t in hit), 10)
        out.append({"score": s, "frac": len(hit) / len(terms), "terms": len(hit), "path": n["path"], "title": n["title"], "type": n["type"], "line": best[:240], "text": n["text"]})
    return sorted(out, key=lambda h: -h["score"])[:k]


def report(g):
    ns = g["notes"]
    print("%s | %d notes | %d links | %d unresolved [[links]]" % ("DEMO" if data.DEMO else "REAL", len(ns), len(g["edges"]), g["dangling"]))
    print("folders:", ", ".join(str(r) for r in data.roots()))
    print("\nBY TYPE")
    for t, c in collections.Counter(n["type"] for n in ns).most_common():
        print("  %-12s %d" % (t, c))
    print("\nBY FORMAT", dict(collections.Counter(n["ext"] for n in ns)))
    print("\nTOP 10 HUBS")
    for n in sorted(ns, key=lambda x: (-x["degree"], x["title"]))[:10]:
        print("  %3d  %s  [%s]" % (n["degree"], n["title"], n["type"]))
    blank = [n["path"] for n in ns if n["ext"] == ".pdf" and not n["text"].strip()]
    if blank:
        print("\nPDF, NO READABLE TEXT (scanned or font-encoded):", ", ".join(blank))
    if g["skipped"]:
        print("\nSKIPPED", g["skipped"])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report(build())
