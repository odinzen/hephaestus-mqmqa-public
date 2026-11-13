"""Stamp web/ with a fingerprint of web/hephaestus.js.

Browsers cache the engine under its URL, so every page and worker that loads it adds
?v=<fingerprint>. A rebuilt engine then gets a new URL and is never mixed with a page
written for the old one. The fingerprint is taken over the file with line endings
normalised, so a Windows checkout and the served copy agree. Run by build_wasm.sh;
tests/test_engine_stamp.py fails if the stamp and the file disagree.
"""
import hashlib
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
# (file, pattern of the engine reference to stamp)
TARGETS = [("index.html", r"(hephaestus\.js)(\?v=[0-9a-zA-Z]*)?(?=\")"),
           ("vis3d_worker.js", r"(hephaestus\.js)(\?v=[0-9a-zA-Z]*)?(?=')")]


def fingerprint():
    data = (WEB / "hephaestus.js").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:12]


def stamped_versions():
    """The ?v= value each target currently carries (None when unstamped)."""
    out = {}
    for name, pat in TARGETS:
        m = re.search(pat, (WEB / name).read_text(encoding="utf-8"))
        out[name] = m.group(2)[3:] if m and m.group(2) else None
    return out


def stamp():
    fp = fingerprint()
    for name, pat in TARGETS:
        path = WEB / name
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        new, n = re.subn(pat, lambda m: m.group(1) + "?v=" + fp, text)
        if n != 1:
            sys.exit(f"{name}: expected one engine reference, found {n}")
        path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    print(f"engine stamp {fp}")


if __name__ == "__main__":
    stamp()
