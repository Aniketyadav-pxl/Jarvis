# JARVIS

A voice-controlled assistant over your own notes, mail and calendar. Python standard library on the server, vanilla JS in the browser. No frameworks, no build step, no package manager.

## Run it

```
python agent\main.py
```
Opens http://localhost:8765. Needs Python 3.9 or newer. Add `--no-open` to skip opening the browser.

## Setup (once)

1. **Ollama** (the model): install it, then pull a model, e.g. `ollama pull llama3.1`. JARVIS uses the first model Ollama reports, or `OLLAMA_MODEL`. Small models (3B) talk fine but pick tools unreliably; JARVIS never offers tools on greetings and intercepts tool calls printed as text. A 7-8B model usually picks better.
2. **`.env`**: copy `.env.example` to `.env` and fill in what you use. It is gitignored and never sent to the browser. On Windows, lock it: `icacls .env /inheritance:r /grant:r "%USERNAME%:(R,W)"`.
3. **Voice**: `ELEVENLABS_API_KEY`. Optional: `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL`, `SCRIBE_LANG`.
4. **Mail** (read-only): turn on 2-Step Verification, create a Google App Password, set `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. IMAP opens read-only and never marks mail as read.
5. **Calendar**: in Google Calendar settings, copy "Secret address in iCal format" into `JARVIS_ICS_URL` (or point `JARVIS_ICS_FILE` at a local .ics). Recurring events are not expanded; the brief says how many were skipped.

## The demo switch

`JARVIS_DEMO` is read in one file (`agent/data.py`). Default is **demo** (`1`): invented data, safe to screen-record, identical every run (`data/generate_demo.py`, fixed seed). Set `JARVIS_DEMO=0` and `JARVIS_FOLDERS=D:\Notes` (separate several with `;`) to use your real folders. The JARVIS app folder is never indexed. Markdown, text and PDF, up to 2 MB, `node_modules` and `.git` skipped. PDF text is best-effort: scanned or font-encoded PDFs are listed by name, never faked.

## Using it

- Press **mic** once, then talk. About 900 ms of quiet ends your turn (`SILENCE_MS` at the top of `ui/app.js`). The mic is deaf while JARVIS thinks or speaks. Barge in with mic, **Space**, or **Esc**.
- Captions show status live ("hearing you...", "transcribing..."); your words appear when the turn ends.
- **mute** stops JARVIS speaking. **brief** and **plan** run those tools directly. **memory** lists saved facts.
- Graph: hover lights links, click focuses, shift-click traces the shortest path, drag/scroll to pan/zoom.

## Tools

`search_brain`, `research_web` (scrapes DuckDuckGo HTML: free but fragile), `read_inbox`, `brief_me`, `plan_day`, `remember`. Each returns a short spoken line and a separate card. `plan_day` and `brief_me` look for folders named `invoices`, `proposals`, `applications` and for `Status:` and "600 USD" patterns; if your notes differ they say so rather than guess.

## Guardrails

Never sends. Never writes to your folders (only `memory/`). Never saves memory silently. Never spends past the caps below. Never invents. Instructions found in files or mail are reported, not obeyed. Check them: `python tests\guardrails.py`.
`remember` only saves facts that came from your message.

## What it costs

- **Ollama, Gmail, calendar, web search**: no fees. Ollama uses your own CPU/GPU and RAM.
- **ElevenLabs**: the only metered service. Speech out is billed by characters, speech in by audio length, against your ElevenLabs plan. I haven't verified current prices; check your plan on their site. JARVIS caps each run at `ELEVENLABS_MAX_CHARS` (20000) and `ELEVENLABS_MAX_LISTENS` (200), and the "voice on" badge shows usage. Replies are spoken by default, typed ones too; **mute** stops that.

## When it breaks (it says so on screen)

| You see | Fix |
|---|---|
| "model missing" | `ollama serve`, `ollama pull <model>` |
| "Microphone blocked" | Allow the mic for localhost (lock or Shields icon, Brave included) |
| "voice missing" | Set `ELEVENLABS_API_KEY` |
| "ElevenLabs said 401" | The key lacks a permission (text-to-speech, speech-to-text) |
| "Folder not found" / "app's own folder" | Fix `JARVIS_FOLDERS` |
| "Gmail refused" | Check the App Password; IMAP must be enabled |

## Layout

`agent/` main.py (server, API), vault.py (folders to graph, search), tools.py, chat.py (conversation loop), data.py (the only file that touches your data), voice.py, memory.py, prompt.md. `ui/`, `data/` (demo fixtures + generator), `memory/` (one dated file per fact), `CLAUDE.md` (who you are, loaded every session), `tests/`.
