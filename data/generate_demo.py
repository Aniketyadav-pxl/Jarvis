"""Builds the DEMO vault. Fixed seed: identical graph every run. Writes only inside data/demo."""
import random, shutil, zlib
from pathlib import Path

R = random.Random(42)
OUT = Path(__file__).resolve().parent / "demo"
HUBS = ["Reusable components", "Margin model", "Weekly review", "Pricing tiers"]
CONCEPTS = HUBS + ["Retainer vs fixed", "RAG basics", "Prompt patterns", "Cold outreach", "Demo script", "Case studies", "Ollama setup"]
PROJ = ["Taskrail", "Pocket CRM", "Resume Parser", "Lead Scorer", "Invoice Bot", "Portfolio v3", "Docs Search", "Pricing Page Kit", "Meeting Digest", "Site Auditor"]
CLIENTS = ["Maple Dental", "Quill Accounting", "Redwood Physio", "Tidewater Logistics", "Saffron Kitchen", "Northgate Realty", "Pixel Studio", "Bluebird Tutors"]
PEOPLE = ["Riya Sen", "Dev Malhotra", "Kabir Rao", "Meera Iyer", "Arjun Nair", "Sana Qureshi", "Ishaan Bose", "Tara Menon"]
COMPANIES = ["Lattice Labs", "Orbit Pay", "Fathom AI", "Brightpath", "Nimbus Works", "Kite Health", "Vertex Robotics", "Plume Software"]


def L(pool, n):
    return ", ".join("[[%s]]" % x for x in R.sample(pool, n))


def put(folder, title, body, fm=""):
    p = OUT / folder
    p.mkdir(parents=True, exist_ok=True)
    (p / (title + ".md")).write_text(fm + "# " + title + "\n" + body + "\n", encoding="utf-8")


def pdf(name, lines, flate):
    s = ("BT /F1 12 Tf 50 750 Td 16 TL " + " ".join("(%s) Tj T*" % l for l in lines) + " ET").encode()
    f = b""
    if flate:
        s, f = zlib.compress(s), b"/Filter/FlateDecode"
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d%s>>\nstream\n" % (len(s), f) + s + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)
    (OUT / "invoices").mkdir(parents=True, exist_ok=True)
    (OUT / "invoices" / name).write_bytes(out)


if OUT.exists():
    shutil.rmtree(OUT)

for c in CONCEPTS:
    put("concepts", c, "Working notes. Related: %s." % L([x for x in CONCEPTS if x != c], 2))
for p in PROJ:
    put("projects", p, "Status: %s. Stack: %s.\nUses %s. Built for [[%s]]." % (
        R.choice(["building", "shipped", "paused"]), R.choice(["React + Node", "Python + Ollama", "Vanilla JS"]),
        L(CONCEPTS, 2), R.choice(CLIENTS)))
for i, c in enumerate(CLIENTS):
    put("clients", c, "Contact: [[%s]]. Needs: %s.\nProjects: %s. Proposal: [[Proposal %s]]." % (
        PEOPLE[i], R.choice(["booking site", "lead follow-up bot", "invoice automation", "dashboard"]), L(PROJ, 2), c))
    put("proposals", "Proposal " + c, "Quote: %d USD. Terms: %s.\nSee [[%s]], [[Margin model]], [[Pricing tiers]]." % (
        R.choice([450, 600, 900, 1200, 1500]), R.choice(["fixed", "retainer"]), c))
for i, c in enumerate(CLIENTS[:6], 1):
    put("invoices", "Invoice 2026-%03d" % i, "Client: [[%s]]. Total: %d USD. Status: %s." % (
        c, R.choice([450, 600, 900]), R.choice(["paid", "unpaid"])))
for i, c in enumerate(CLIENTS[:3], 7):
    pdf("Invoice 2026-%03d.pdf" % i, ["Invoice 2026-%03d" % i, "Client: %s" % c, "Total: %d USD" % R.choice([600, 900, 1200])], flate=i != 7)
for i, co in enumerate(COMPANIES):
    put("applications", "Application " + co, "Role: %s. Status: %s.\nShow them [[%s]]. Contact: [[%s]]." % (
        R.choice(["Junior AI engineer", "Full-stack intern", "Frontend developer"]),
        R.choice(["applied", "interview", "waiting", "rejected"]), R.choice(PROJ), R.choice(PEOPLE)))
for p in PEOPLE:
    put("people", p, "Met via %s. Works with [[%s]]." % (R.choice(["a call", "LinkedIn", "a referral"]), R.choice(CLIENTS + COMPANIES)))
for i in range(14):
    c = R.choice(CLIENTS)
    put("calls", "Call %s %02d" % (c, i + 1), "With [[%s]] and [[%s]]. Topics: %s." % (c, R.choice(PEOPLE), L(CONCEPTS, 2)))
for w in range(1, 11):
    put("notes", "Weekly review W%02d" % w, "Wins: %s. Next: [[Weekly review]], [[Reusable components]], [[%s]]." % (L(PROJ, 2), R.choice(CLIENTS)),
        fm="---\ntype: review\n---\n")

import json
(OUT.parent / "demo_inbox.json").write_text(json.dumps([
    {"from": "Dev Malhotra", "email": "dev@maple-dental.example", "subject": "Booking site: can we move the call?", "unread": True, "days_ago": 0},
    {"from": "Priya Kapoor", "email": "priya@brightleaf.example", "subject": "Need a landing page, what's your rate?", "unread": True, "days_ago": 1},
    {"from": "Lattice Labs", "email": "talent@lattice-labs.example", "subject": "Interview slots", "unread": True, "days_ago": 4},
    {"from": "Meera Iyer", "email": "meera@tidewater.example", "subject": "Re: invoice", "unread": False, "days_ago": 2},
], indent=1), encoding="utf-8")
(OUT.parent / "demo_calendar.json").write_text(json.dumps([
    {"day": 0, "time": "10:00", "title": "Call: Maple Dental"},
    {"day": 0, "time": "15:30", "title": "Interview: Orbit Pay"},
    {"day": 1, "time": "11:00", "title": "Demo: Pocket CRM"},
], indent=1), encoding="utf-8")
