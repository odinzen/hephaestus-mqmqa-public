"""ORCHID's SGTE files against Hallstedt's own supplementary archive, byte for byte.

    python check_source.py <1-s2.0-S0364591625000367-mmc3.zip> <orchid sgte-binary dir>

The archive is the journal's supplementary file to Hallstedt, Calphad 89 (2025) 102833
(https://ars.els-cdn.com/content/image/1-s2.0-S0364591625000367-mmc3.zip).
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ARCHIVE_SHA256 = "6a0d53de8a1141fc77ae2a1636794bfe90d6c8bb74b144c70eae960ff976747d"


def main():
    archive, orchid = Path(sys.argv[1]), Path(sys.argv[2])
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    print("archive SHA-256", sha, "(matches ORCHID's record)" if sha == ARCHIVE_SHA256 else "(DIFFERS)")
    z = zipfile.ZipFile(archive)
    members = {Path(n).name: n for n in z.namelist() if n.lower().endswith(".tdb")}
    same = differ = missing = 0
    for name, member in sorted(members.items()):
        mine = orchid / name
        if not mine.exists():
            missing += 1
            print("missing in ORCHID:", name)
        elif z.read(member) == mine.read_bytes():
            same += 1
        else:
            differ += 1
            print("differs:", name)
    extra = sorted(p.name for p in orchid.glob("*.tdb") if p.name not in members)
    print(f"{len(members)} datasets in the archive: {same} identical, {differ} differ, {missing} missing;"
          f" in ORCHID only: {extra}")


if __name__ == "__main__":
    main()
