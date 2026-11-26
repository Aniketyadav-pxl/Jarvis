"""Speech in and out: Groq Whisper (STT) + ElevenLabs (TTS, with Scribe fallback).
Keys stay here; the browser only ever sees text, mp3 bytes, and transcripts."""
import json, re, urllib.request, urllib.error, uuid
import data

USED = {"chars": 0, "listens": 0}


class VoiceError(Exception):
    pass


def _api():
    return data.env("ELEVENLABS_API", "https://api.elevenlabs.io/v1")


def _key():
    k = data.env("ELEVENLABS_API_KEY")
    if not k:
        raise VoiceError("No ElevenLabs key. Set ELEVENLABS_API_KEY in .env.")
    return k


def _groq_key():
    return (data.env("GROQ_API_KEY") or "").strip()


def _call(req, provider="ElevenLabs"):
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(raw)
            d = j.get("detail") or j.get("error") or raw
            raw = d.get("message") or d.get("status") if isinstance(d, dict) else str(d)
        except ValueError:
            pass
        raise VoiceError("%s said %d: %s" % (provider, e.code, str(raw)[:200]))
    except OSError as e:
        raise VoiceError("Can't reach %s: %s" % (provider, e))


def status():
    k = data.env("ELEVENLABS_API_KEY")
    stt = "groq-whisper" if _groq_key() else "elevenlabs-scribe"
    return {
        "ok": bool(k or _groq_key()),
        "error": None if k else "No ElevenLabs key (TTS off). Set ELEVENLABS_API_KEY in .env.",
        "chars": USED["chars"],
        "cap": int(data.env("ELEVENLABS_MAX_CHARS", "20000")),
        "listens": USED["listens"],
        "stt": stt,
    }


def speak(text):
    """Text to mp3 bytes via ElevenLabs. Capped per run so a loop can't quietly spend."""
    text = " ".join(str(text).split())[:600]
    if not text:
        raise VoiceError("Nothing to say.")
    cap = int(data.env("ELEVENLABS_MAX_CHARS", "20000"))
    if USED["chars"] + len(text) > cap:
        raise VoiceError("Voice cap hit: %d characters this run. Raise ELEVENLABS_MAX_CHARS in .env, or restart." % cap)
    voice = data.env("ELEVENLABS_VOICE_ID") or "pNInz6obpgDQGcFmaJgB"
    req = urllib.request.Request(
        "%s/text-to-speech/%s?output_format=mp3_44100_64" % (_api(), voice),
        data=json.dumps({"text": text, "model_id": data.env("ELEVENLABS_MODEL", "eleven_turbo_v2_5")}).encode(),
        headers={"xi-api-key": _key(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    audio = _call(req, "ElevenLabs")
    USED["chars"] += len(text)
    return audio


def _multipart(fields, file_field, filename, ctype, blob):
    b, parts = uuid.uuid4().hex, []
    for n, v in fields:
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, n, v)).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (b, file_field, filename, ctype)).encode() + blob + b"\r\n")
    parts.append(("--%s--\r\n" % b).encode())
    return b, b"".join(parts)


def listen(audio, ctype):
    """Recorded audio to transcript via Groq Whisper (default if GROQ_API_KEY is set) or ElevenLabs Scribe."""
    if len(audio) < 1500:
        raise VoiceError("Recording too short.")
    m = re.match(r"audio/[\w.+-]+", ctype or "")
    ctype = m.group(0) if m else "audio/webm"
    ext = ctype.split("/")[-1].split(";")[0].replace("mpeg", "mp3") or "webm"

    gk = _groq_key()
    if gk:
        fields = [
            ("model", data.env("GROQ_STT_MODEL", "whisper-large-v3-turbo")),
            ("response_format", "json"),
        ]
        if data.env("SCRIBE_LANG"):
            fields.append(("language", data.env("SCRIBE_LANG")))
        b, body = _multipart(fields, "file", "speech." + ext, ctype, audio)
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": "Bearer " + gk,
                "Content-Type": "multipart/form-data; boundary=" + b,
                "User-Agent": "Mozilla/5.0",
            },
        )
        out = json.loads(_call(req, "Groq") or b"{}")
        USED["listens"] += 1
        return (out.get("text") or "").strip()

    if USED["listens"] >= int(data.env("ELEVENLABS_MAX_LISTENS", "200")):
        raise VoiceError("Transcription cap hit. Raise ELEVENLABS_MAX_LISTENS in .env, or restart.")
    fields = [("model_id", "scribe_v1"), ("tag_audio_events", "false")]
    if data.env("SCRIBE_LANG"):
        fields.append(("language_code", data.env("SCRIBE_LANG")))
    b, body = _multipart(fields, "file", "speech." + ext, ctype, audio)
    req = urllib.request.Request(
        _api() + "/speech-to-text",
        data=body,
        headers={"xi-api-key": _key(), "Content-Type": "multipart/form-data; boundary=" + b},
    )
    out = json.loads(_call(req, "ElevenLabs") or b"{}")
    USED["listens"] += 1
    return (out.get("text") or "").strip()