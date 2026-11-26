"""Sandboxed multi-file website builder. Writes ONLY inside jarvis/builds/<project>/."""
import re, subprocess, webbrowser
from pathlib import Path
import data
import os

BUILDS = (Path("/tmp/jarvis_builds") if os.environ.get("VERCEL") else Path(__file__).resolve().parent.parent / "builds").resolve()
ALLOWED_FILES = ("index.html", "styles.css", "app.js")

SYS_BUILD = (
    "You are an expert frontend engineer and UI designer. "
    "Generate a complete, agency-grade, zero-dependency website split into three files: "
    "index.html, styles.css, and app.js. Do NOT use external CDNs, Tailwind, Bootstrap, or icon fonts. "
    "Link styles.css (<link rel=\"stylesheet\" href=\"styles.css\">) and app.js (<script src=\"app.js\" defer></script>) inside index.html.\n\n"
    "Design & Code Standards:\n"
    "- HTML: Semantic HTML5 (<header>, <main>, <section>, <footer>), complete SEO <meta name=\"description\">, responsive viewport, and crisp inline <svg> icons (never broken image URLs).\n"
    "- CSS: Modern vanilla CSS with :root design tokens (colors, spacing, radii, shadows), system UI font stack, fluid typography with clamp(), text-wrap: balance on headings, native CSS nesting, CSS Grid/Flexbox bento layouts, subtle glassmorphism/borders, smooth hover states, and full mobile responsiveness.\n"
    "- JS: Clean vanilla JS in app.js for mobile menu toggle, smooth scrolling, IntersectionObserver scroll-reveal animations, and interactive elements (pricing toggles, tabs, or form validation with clear feedback).\n\n"
    "Format your response EXACTLY like this with no extra commentary outside the blocks:\n"
    "=== FILE: index.html ===\n<!DOCTYPE html>...\n"
    "=== FILE: styles.css ===\n...\n"
    "=== FILE: app.js ===\n..."
)

SYS_EDIT = (
    "You are an expert frontend engineer. Apply the requested changes to the provided website files "
    "while preserving the zero-dependency modern vanilla CSS design system (no external CDNs). "
    "Return ONLY the updated files using the exact format:\n"
    "=== FILE: index.html ===\n...\n"
    "=== FILE: styles.css ===\n...\n"
    "=== FILE: app.js ===\n...\n"
    "Only include files that need changes (or all three). No markdown fences or commentary."
)


def _port():
    return int(data.env("JARVIS_PORT", "8765"))


def _url(slug):
    if os.environ.get("VERCEL"):
        return f"/builds/{slug}/"
    return f"http://localhost:{_port()}/builds/{slug}/"

def _open_brave(url):
    if os.environ.get("VERCEL"):
        return
    try:
        subprocess.Popen(["cmd", "/c", "start", "brave", url], shell=False)
    except Exception:
        webbrowser.open(url)


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "site").lower()).strip("-")
    return s[:48] or "site"


def _project_dir(slug):
    BUILDS.mkdir(parents=True, exist_ok=True)
    d = (BUILDS / slug).resolve()
    d.relative_to(BUILDS)  # blocks path traversal
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clean_block(text):
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_files(raw):
    files = {}
    parts = re.split(r"===\s*FILE:\s*([a-zA-Z0-9._-]+)\s*===", raw or "")
    if len(parts) >= 3:
        for i in range(1, len(parts) - 1, 2):
            fname = parts[i].strip().lower()
            if fname in ALLOWED_FILES:
                content = _clean_block(parts[i + 1])
                if content:
                    files[fname] = content
    if not files:
        # Fallback if model returned a single HTML file
        m = re.search(r"(<!DOCTYPE html.*</html>|<html.*</html>)", raw or "", re.I | re.S)
        if m:
            files["index.html"] = m.group(1).strip()
    if not files:
        raise ValueError("Model did not return valid website files.")
    return files


def build(name, spec, code_fn):
    if not code_fn:
        raise RuntimeError("No AI model connected to generate code.")
    slug = _slug(name)
    raw = code_fn(SYS_BUILD, f"Project name: {name}\nRequirements: {spec}")
    files = _parse_files(raw)
    proj = _project_dir(slug)
    for fname, content in files.items():
        (proj / fname).write_text(content, encoding="utf-8")
    url = _url(slug)
    _open_brave(url)
    return slug, url, sorted(files.keys())


def edit(name, changes, code_fn):
    if not code_fn:
        raise RuntimeError("No AI model connected to edit code.")
    slug = _slug(name)
    proj = _project_dir(slug)
    existing = []
    for fname in ALLOWED_FILES:
        p = proj / fname
        if p.is_file():
            existing.append(f"=== FILE: {fname} ===\n{p.read_text(encoding='utf-8')}")
    if not existing:
        raise FileNotFoundError(f"No built site found at builds/{slug}/")
    raw = code_fn(SYS_EDIT, f"Requested changes: {changes}\n\nCurrent files:\n" + "\n\n".join(existing))
    files = _parse_files(raw)
    for fname, content in files.items():
        (proj / fname).write_text(content, encoding="utf-8")
    url = _url(slug)
    _open_brave(url)
    return slug, url, sorted(files.keys())


def list_builds():
    if not BUILDS.is_dir():
        return []
    out = []
    for d in sorted(BUILDS.iterdir()):
        if d.is_dir() and (d / "index.html").is_file():
            out.append((d.name, _url(d.name)))
    return out


def open_vscode(name):
    slug = _slug(name)
    proj = (BUILDS / slug).resolve()
    proj.relative_to(BUILDS)
    if not proj.is_dir():
        raise FileNotFoundError(f"No built site found at builds/{slug}/")
    subprocess.Popen(["cmd", "/c", "code", str(proj)], shell=False)
    return slug, str(proj)