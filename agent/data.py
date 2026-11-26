"""THE ONLY FILE THAT TOUCHES REAL DATA.
Reads .env and the indexed folders, read-only (no write calls exist here).
JARVIS_DEMO is read here and nowhere else."""
import os, runpy
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
EXTS = {".md", ".txt", ".pdf"}
MAX_BYTES = 2 * 1024 * 1024


def _load_env():
    p = APP / ".env"
    if p.is_file():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()


def env(name, default=""):
    return os.environ.get(name, default)


DEMO = env("JARVIS_DEMO", "1") != "0"  # opt IN to real data


def roots():
    if DEMO:
        demo = APP / "data" / "demo"
        if not demo.is_dir():
            runpy.run_path(str(APP / "data" / "generate_demo.py"))
        return [demo]
    return [Path(p).expanduser() for p in env("JARVIS_FOLDERS").split(os.pathsep) if p.strip()]


def scan(skipped):
    """Yield {root, path, ext, raw} per readable file. Counts skips into `skipped`."""
    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1
    for root in roots():
        if not root.is_dir():
            skip("missing folder: %s" % root)
            continue
        if root.resolve() == APP:
            skip("folder is the app's own folder: %s. Point JARVIS_FOLDERS at your notes" % root)
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and Path(dp, d).resolve() != APP]
            for fn in fns:
                p = Path(dp, fn)
                if p.suffix.lower() not in EXTS:
                    continue
                try:
                    if p.stat().st_size > MAX_BYTES:
                        skip("over 2 MB")
                        continue
                    raw = p.read_bytes()
                except OSError:
                    skip("unreadable")
                    continue
                yield {"root": root.name, "path": p.relative_to(root).as_posix(), "ext": p.suffix.lower(), "raw": raw}


# ---- inbox + calendar (real data too, so they live here) ----
import datetime as dt, imaplib, email, json, re, urllib.request
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime


class NotConnected(Exception):
    pass


def inbox(limit=12):
    """Newest first: [{from,email,subject,unread,days_ago}]. IMAP opened READ-ONLY, so nothing gets marked seen."""
    if DEMO:
        return json.loads((APP / "data" / "demo_inbox.json").read_text("utf-8"))
    u, p = env("GMAIL_ADDRESS"), env("GMAIL_APP_PASSWORD")
    if not (u and p):
        raise NotConnected("Gmail isn't connected. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env.")
    out = []
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=20)
        try:
            m.login(u, p)
            m.select("INBOX", readonly=True)
            ids = m.search(None, "ALL")[1][0].split()[-limit:]
            for i in reversed(ids):
                d = m.fetch(i, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")[1][0]
                h = email.message_from_bytes(d[1])
                name, addr = parseaddr(str(make_header(decode_header(h.get("From", "")))))
                try:
                    ago = (dt.datetime.now(dt.timezone.utc) - parsedate_to_datetime(h.get("Date"))).days
                except Exception:
                    ago = 0
                out.append({"from": name or addr, "email": addr, "subject": str(make_header(decode_header(h.get("Subject", "")))),
                            "unread": b"\\Seen" not in d[0], "days_ago": max(ago, 0)})
        finally:
            try:
                m.logout()
            except Exception:
                pass
    except (imaplib.IMAP4.error, OSError) as e:
        raise NotConnected("Gmail refused or timed out: %s. Check the App Password and that IMAP is on." % e)
    return out


def _ics(text):
    text, evs, skipped = re.sub(r"\r?\n[ \t]", "", text), [], 0
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def g(k):
            m = re.search(r"^%s[^:\r\n]*:(.*)$" % k, blk, re.M)
            return m.group(1).strip() if m else ""
        if g("RRULE"):
            skipped += 1
            continue
        v = g("DTSTART")
        try:
            if len(v) == 8:
                d, t = dt.datetime.strptime(v, "%Y%m%d").date(), "all day"
            else:
                x = dt.datetime.strptime(v.rstrip("Z"), "%Y%m%dT%H%M%S")
                if v.endswith("Z"):
                    x = x.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
                d, t = x.date(), x.strftime("%H:%M")
        except ValueError:
            continue
        evs.append({"date": d, "time": t, "title": g("SUMMARY").replace("\\,", ",")})
    return evs, skipped


def events(days=2):
    """([events today..+days], note). Recurring events are NOT expanded; the note says how many were skipped."""
    today = dt.date.today()
    if DEMO:
        rows = json.loads((APP / "data" / "demo_calendar.json").read_text("utf-8"))
        evs, skipped = [{"date": today + dt.timedelta(days=r["day"]), "time": r["time"], "title": r["title"]} for r in rows], 0
    else:
        f, url = env("JARVIS_ICS_FILE"), env("JARVIS_ICS_URL")
        try:
            if f:
                text = Path(f).read_text("utf-8", "replace")
            elif url:
                text = urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "replace")
            else:
                raise NotConnected("Calendar isn't connected. Set JARVIS_ICS_URL or JARVIS_ICS_FILE in .env.")
        except OSError as e:
            raise NotConnected("Couldn't read the calendar feed: %s" % e)
        evs, skipped = _ics(text)
    evs = sorted((e for e in evs if today <= e["date"] < today + dt.timedelta(days=days)), key=lambda e: (e["date"], e["time"]))
    return evs, ("%d recurring events not expanded." % skipped) if skipped else ""
