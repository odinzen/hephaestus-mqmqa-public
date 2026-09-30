"""Shipped databases stay copies of their sources, and every one is in data/databases.toml.

The first test runs the real repo in check mode, so a hand-edited web/ copy, a database dropped
into web/ without a registry entry, or stale load buttons fail here. The rest plant one bad
input each in a scratch repo and require the sync to refuse or repair it.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_databases", ROOT / "scripts" / "sync_databases.py")
sd = importlib.util.module_from_spec(_spec)
sys.modules["sync_databases"] = sd  # dataclasses look their module up by name
_spec.loader.exec_module(sd)

MARKERS = "".join(
    f"<!-- shipped-databases:{c} (generated from data/databases.toml by scripts/sync_databases.py) -->\n"
    f"      <!-- /shipped-databases:{c} -->\n" for c in ("load", "xtdb"))


def test_repo_is_in_sync():
    assert sd.sync(ROOT, check=True) == []


def test_every_loadable_entry_has_a_button_in_the_page():
    html = (ROOT / "web" / "index.html").read_text("utf-8")
    for e in sd.load_registry(ROOT):
        if e.card:
            assert f'id="{e.button}"' in html and f'="{e.file}"' in html


def scratch(tmp_path, entries, files=None, index=MARKERS):
    (tmp_path / "data" / "s").mkdir(parents=True)
    (tmp_path / "web").mkdir()
    for rel, text in (files or {"data/s/a.dat": "A"}).items():
        (tmp_path / rel).write_text(text)
    (tmp_path / "web" / "index.html").write_text(index)
    (tmp_path / "data" / "databases.toml").write_text(entries)
    return tmp_path


DAT = '[[database]]\nfile = "a.dat"\nsource = "data/s/a.dat"\nformat = "dat"\n'
LOADABLE = DAT + 'card = "load"\nbutton = "b-a"\nlabel = "Load A"\ntitle = "A"\nkind = "slag"\nblurb = "x"\n'


def test_sync_copies_source_and_generates_button(tmp_path):
    root = scratch(tmp_path, LOADABLE)
    assert sd.sync(root, check=True)                       # check reports, changes nothing
    assert not (root / "web" / "a.dat").exists()
    sd.sync(root)
    assert (root / "web" / "a.dat").read_text() == "A"
    html = (root / "web" / "index.html").read_text()
    assert 'id="b-a"' in html and 'data-shipped="a.dat"' in html
    assert sd.sync(root, check=True) == []                  # idempotent


def test_hand_edited_web_copy_is_drift(tmp_path):
    root = scratch(tmp_path, DAT)
    sd.sync(root)
    (root / "web" / "a.dat").write_text("edited by hand")
    assert any("differs" in c for c in sd.sync(root, check=True))
    sd.sync(root)
    assert (root / "web" / "a.dat").read_text() == "A"


def test_unregistered_web_database_refused(tmp_path):
    root = scratch(tmp_path, DAT)
    (root / "web" / "dropped.tdb").write_text("x")
    with pytest.raises(sd.SyncError, match="no registry entry"):
        sd.sync(root)


def test_missing_source_refused(tmp_path):
    root = scratch(tmp_path, DAT.replace("data/s/a.dat", "data/s/gone.dat"))
    with pytest.raises(sd.SyncError, match="not a file under data"):
        sd.sync(root)


def test_extension_must_match_format(tmp_path):
    root = scratch(tmp_path, DAT.replace('format = "dat"', 'format = "tdb"'))
    with pytest.raises(sd.SyncError, match="must both end in .tdb"):
        sd.sync(root)


def test_utdb_needs_existing_parts(tmp_path):
    files = {"data/s/u.utdb": "U", "data/s/a.dat": "A"}
    utdb = '[[database]]\nfile = "u.utdb"\nsource = "data/s/u.utdb"\nformat = "utdb"\n'
    with pytest.raises(sd.SyncError, match="halves"):
        sd.sync(scratch(tmp_path, utdb, files))
    root = tmp_path / "second"
    root.mkdir()
    with pytest.raises(sd.SyncError, match="does not exist"):
        sd.sync(scratch(root, utdb + 'parts = ["data/s/a.dat", "data/s/gone.tdb"]\n', files))


def test_xtdb_belongs_on_the_xtdb_card(tmp_path):
    files = {"data/s/x.xtdb": "X"}
    entry = ('[[database]]\nfile = "x.xtdb"\nsource = "data/s/x.xtdb"\nformat = "xtdb"\ncard = "load"\n'
             'button = "b"\nlabel = "L"\ntitle = "T"\nkind = "alloy"\nblurb = "b"\n')
    with pytest.raises(sd.SyncError, match="xtdb card"):
        sd.sync(scratch(tmp_path, entry, files))


def test_duplicate_button_refused(tmp_path):
    files = {"data/s/a.dat": "A", "data/s/b.dat": "B"}
    second = LOADABLE.replace("a.dat", "b.dat")
    with pytest.raises(sd.SyncError, match="duplicate"):
        sd.sync(scratch(tmp_path, LOADABLE + second, files))


def test_missing_markers_refused(tmp_path):
    root = scratch(tmp_path, DAT, index="<html>no markers</html>")
    with pytest.raises(sd.SyncError, match="markers are missing"):
        sd.sync(root)


def test_gitignored_shipped_file_refused(tmp_path):
    root = scratch(tmp_path, DAT)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("web/*.dat\n")
    with pytest.raises(sd.SyncError, match="gitignore would hide"):
        sd.sync(root)
