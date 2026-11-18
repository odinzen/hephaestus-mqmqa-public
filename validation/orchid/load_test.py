"""Read every ORCHID TDB with Hephaestus, one subprocess per file so a crash costs one file.

    python -I load_test.py <orchid databases dir> <hephaestus python dir> <out.jsonl> [workers]
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[2])
import mqmqa
try:
    db = mqmqa.Database.read(sys.argv[1])
    names = list(db.phase_names) if hasattr(db, "phase_names") else None
    print(json.dumps({"ok": True, "phases": names}))
except Exception as e:
    print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
"""


def one(path, pydir):
    t = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", "-c", CHILD, str(path), pydir],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout 120 s"}
    line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        r = {"ok": False, "error": f"crash rc={p.returncode}: {p.stderr.strip()[-300:]}"}
    r["seconds"] = round(time.time() - t, 2)
    return r


def main():
    root, pydir, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() == ".tdb")
    done = set()
    if out.exists():
        done = {json.loads(l)["file"] for l in out.read_text(encoding="utf-8").splitlines() if l}
    todo = [f for f in files if str(f.relative_to(root)) not in done]
    print(f"{len(files)} files, {len(todo)} to do", flush=True)
    with ThreadPoolExecutor(workers) as ex, out.open("a", encoding="utf-8") as fh:
        for i, (f, r) in enumerate(zip(todo, ex.map(lambda f: one(f, pydir), todo)), 1):
            r["file"] = str(f.relative_to(root))
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            if i % 200 == 0:
                print(f"{i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
