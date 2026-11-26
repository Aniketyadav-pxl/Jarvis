"""Writes to memory/ and nowhere else. One dated file per fact; never overwrites."""
import re, datetime as dt
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "memory"


def write(fact):
    fact = " ".join(str(fact).split())[:500]
    if not fact:
        raise ValueError("Nothing to remember.")
    slug = re.sub(r"[^a-z0-9]+", "-", fact.lower())[:40].strip("-") or "fact"
    DIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    for n in range(1, 100):
        p = DIR / ("%s-%s%s.md" % (today, slug, "" if n == 1 else "-%d" % n))
        if p.resolve().parent != DIR.resolve():
            raise OSError("Refusing to write outside memory/.")
        try:
            with open(p, "x", encoding="utf-8") as f:
                f.write("---\ndate: %s\n---\n%s\n" % (today, fact))
            return p.name
        except FileExistsError:
            continue
    raise OSError("Too many memory files with that name.")


def read_all(limit=200):
    """Newest first, shaped like vault notes so search can include them."""
    out = []
    for p in sorted(DIR.glob("*.md"), reverse=True)[:limit]:
        t = p.read_text("utf-8", "replace")
        m = re.match(r"---\n.*?\n---\n", t, re.S)
        out.append({"title": p.stem, "path": "memory/" + p.name, "type": "memory", "text": (t[m.end():] if m else t).strip()})
    return out
