"""The Windows DLL must not carry thread-local data its TLS directory leaves out.

Linked by lld against the mingw-w64 5.3 CRT, the TLS directory of a DLL with
_Thread_local variables covers only 8 bytes, while the variables sit elsewhere in .tls.
Every thread-local write then went past an 8-byte heap block the loader allocated,
corrupting the heap (intermittent 0xc0000374 crashes and silently altered values)."""
import struct
from pathlib import Path

import pytest

DLL = Path(__file__).resolve().parents[1] / "python" / "mqmqa" / "mqmqa.dll"


def tls_bytes_outside_template(path):
    """Bytes of the .tls section outside the loader's TLS template and the directory."""
    img = Path(path).read_bytes()
    pe = struct.unpack_from("<I", img, 0x3C)[0]
    n_sec, opt_size = struct.unpack_from("<H12xH", img, pe + 6)
    opt = pe + 24
    image_base = struct.unpack_from("<Q", img, opt + 24)[0]
    tls_rva = struct.unpack_from("<I", img, opt + 112 + 9 * 8)[0]
    if tls_rva == 0:
        return 0
    sections = []
    for k in range(n_sec):
        h = opt + opt_size + 40 * k
        name = img[h:h + 8].rstrip(b"\0")
        vsize, va, _, raw = struct.unpack_from("<IIII", img, h + 8)
        sections.append((name, va, vsize, raw))
    va, raw = next((va, raw) for _, va, vsize, raw in sections if va <= tls_rva < va + vsize)
    start, end, _, _, zero_fill = struct.unpack_from("<QQQQI", img, raw + tls_rva - va)
    template = end - start + zero_fill
    tls = [s for s in sections if s[0] == b".tls"]
    if not tls:
        return 0
    _, va, vsize, _ = tls[0]
    directory = 40 if va <= tls_rva < va + vsize else 0
    return vsize - template - directory


@pytest.mark.skipif(not DLL.exists(), reason="Windows DLL build only")
def test_tls_template_covers_thread_local_data():
    # alignment padding is allowed, data is not
    assert tls_bytes_outside_template(DLL) <= 64
