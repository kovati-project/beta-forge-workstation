"""
OpenAI-compatible speech API in front of a Wyoming Piper server.

ghcr.io/linuxserver/piper only speaks the Wyoming protocol (newline-delimited
JSON events over raw TCP on 10200). Open WebUI's "openai" TTS engine, the
Loadout Manager voice API and scripts/validate-phase12.sh all expect HTTP
`POST /v1/audio/speech`. This adapter translates one into the other.

Standard library only, so it runs on the stock python image with no build step
(the file is bind-mounted, see docker/compose.voice.yml).

Endpoints
  POST /v1/audio/speech   {"input": str, "voice"?: str, "model"?: str,
                           "response_format"?: str, "speed"?: float}
  GET  /v1/audio/voices   {"default": str, "voices": [{"name", "languages", "description"}]}
  GET  /v1/models         OpenAI-style model list ("piper")
  GET  /health            200 if the Wyoming port accepts a connection, else 503

Response formats: "pcm" returns raw signed 16-bit little-endian mono audio with
`Content-Type: audio/pcm;rate=<hz>;channels=1`. Every other format (including the
OpenAI default "mp3") returns WAV with `Content-Type: audio/wav`, because the
standard library has no MP3 encoder. Open WebUI reads the Content-Type and
transcodes non-MP3 audio itself, so that is enough for it.

`voice`: OpenAI voice names (alloy, nova, ...) and an empty value use the voice
Piper was started with (PIPER_VOICE). Anything else is passed to Piper as a
voice name, e.g. "en_US-ryan-high"; Piper downloads it on first use.
`speed` is accepted and ignored (Wyoming synthesize has no per-request rate).
"""

import io
import json
import logging
import os
import re
import socket
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PIPER_HOST = os.getenv("PIPER_HOST", "piper")
PIPER_PORT = int(os.getenv("PIPER_PORT", "10200"))
PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-lessac-high")
LISTEN_HOST = os.getenv("HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("PORT", "8000"))
TIMEOUT = float(os.getenv("PIPER_TIMEOUT", "60"))
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "4096"))

OPENAI_VOICES = {
    "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx",
    "sage", "shimmer", "verse",
}
VOICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")

log = logging.getLogger("piper-openai")


class WyomingError(Exception):
    """Piper answered with an error event or broke the protocol."""


# ── Wyoming client ───────────────────────────────────────────────────────────

def _send_event(sock, event_type, data=None):
    header = {"type": event_type}
    if data is not None:
        header["data"] = data
    sock.sendall((json.dumps(header) + "\n").encode("utf-8"))


def _read_event(stream):
    """Read one Wyoming event. Returns (type, data, payload) or None at EOF."""
    line = stream.readline()
    if not line:
        return None
    try:
        header = json.loads(line)
    except ValueError as e:
        raise WyomingError(f"bad event header from piper: {line[:80]!r}") from e
    data = dict(header.get("data") or {})
    if header.get("data_length"):
        data.update(json.loads(stream.read(header["data_length"])))
    payload = b""
    if header.get("payload_length"):
        payload = stream.read(header["payload_length"])
    return header.get("type"), data, payload


def _connect():
    return socket.create_connection((PIPER_HOST, PIPER_PORT), timeout=TIMEOUT)


def synthesize(text, voice=None):
    """Return (pcm_bytes, rate, width, channels) for `text`."""
    data = {"text": text}
    if voice:
        data["voice"] = {"name": voice}
    with _connect() as sock:
        _send_event(sock, "synthesize", data)
        stream = sock.makefile("rb")
        fmt = None
        pcm = bytearray()
        while True:
            event = _read_event(stream)
            if event is None:
                raise WyomingError("piper closed the connection before audio-stop")
            etype, edata, payload = event
            if etype == "audio-start":
                fmt = edata
            elif etype == "audio-chunk":
                fmt = fmt or edata
                pcm += payload
            elif etype == "audio-stop":
                break
            elif etype == "error":
                raise WyomingError(edata.get("text") or "piper returned an error")
    if not fmt:
        raise WyomingError("piper sent no audio format")
    return bytes(pcm), int(fmt["rate"]), int(fmt["width"]), int(fmt["channels"])


def describe():
    """Return the list of TTS voices Piper reports."""
    with _connect() as sock:
        _send_event(sock, "describe")
        stream = sock.makefile("rb")
        while True:
            event = _read_event(stream)
            if event is None:
                raise WyomingError("piper closed the connection before info")
            etype, edata, _ = event
            if etype == "info":
                break
    voices = []
    for program in edata.get("tts") or []:
        for v in program.get("voices") or []:
            voices.append({
                "name": v.get("name"),
                "languages": v.get("languages") or [],
                "description": v.get("description") or "",
            })
    return voices


def piper_alive():
    try:
        with socket.create_connection((PIPER_HOST, PIPER_PORT), timeout=3):
            return True
    except OSError:
        return False


def to_wav(pcm, rate, width, channels):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def resolve_voice(voice):
    """None means 'Piper's default voice'. Raises ValueError for junk."""
    if voice is None:
        return None
    if not isinstance(voice, str):
        raise ValueError("voice must be a string")
    voice = voice.strip()
    if not voice or voice.lower() in OPENAI_VOICES or voice == PIPER_VOICE:
        return None
    if not VOICE_NAME_RE.match(voice):
        raise ValueError(f"invalid voice name: {voice!r}")
    return voice


# ── HTTP ─────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "piper-openai/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # route access logs through logging
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, status, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message, etype="invalid_request_error"):
        self._send(status, {"error": {"message": message, "type": etype}})

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/health":
            if piper_alive():
                self._send(200, {"status": "ok"})
            else:
                self._error(503, f"piper not reachable at {PIPER_HOST}:{PIPER_PORT}",
                            "service_unavailable")
        elif path == "/v1/models":
            self._send(200, {"object": "list", "data": [
                {"id": "piper", "object": "model", "owned_by": "rhasspy"},
            ]})
        elif path == "/v1/audio/voices":
            try:
                self._send(200, {"default": PIPER_VOICE, "voices": describe()})
            except (OSError, WyomingError) as e:
                self._error(502, f"piper describe failed: {e}", "upstream_error")
        else:
            self._error(404, f"no route for GET {path}")

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path != "/v1/audio/speech":
            self._error(404, f"no route for POST {path}")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
        except ValueError as e:
            self._error(400, f"invalid JSON body: {e}")
            return

        text = body.get("input")
        if not isinstance(text, str) or not text.strip():
            self._error(400, "'input' must be a non-empty string")
            return
        if len(text) > MAX_INPUT_CHARS:
            self._error(400, f"'input' is longer than {MAX_INPUT_CHARS} characters")
            return
        try:
            voice = resolve_voice(body.get("voice"))
        except ValueError as e:
            self._error(400, str(e))
            return

        try:
            pcm, rate, width, channels = synthesize(text, voice)
        except (OSError, WyomingError) as e:
            log.warning("synthesis failed: %s", e)
            self._error(502, f"piper synthesis failed: {e}", "upstream_error")
            return

        if (body.get("response_format") or "").lower() == "pcm":
            self._send(200, pcm, f"audio/pcm;rate={rate};channels={channels}")
        else:
            self._send(200, to_wav(pcm, rate, width, channels), "audio/wav")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    log.info("listening on %s:%d, piper at %s:%d", LISTEN_HOST, LISTEN_PORT, PIPER_HOST, PIPER_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
