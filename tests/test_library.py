"""The Database library build must never put a private system on the public page.

Each refusal is proven with a planted bad input; the committed web/library.json is checked
against the rules too.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_library", ROOT / "scripts" / "build_library.py")
bl = importlib.util.module_from_spec(_spec)
sys.modules["build_library"] = bl  # dataclasses look their module up by name
_spec.loader.exec_module(bl)

INDEX = '<button id="example">x</button>'


def row(sid, cls="in_development", stage=2, status="extracting"):
    return {"id": sid, "classification": cls, "stage": stage, "status": status,
            "n_papers": 3, "n_measurements": 10, "n_phase_equilibrium": 1}


def entry(sid, shelf="in_progress", kind="salt"):
    return {"id": sid, "title": sid, "kind": kind, "shelf": shelf, "blurb": "b"}


@pytest.fixture
def web(tmp_path):
    (tmp_path / "a.dat").write_text("x")
    return tmp_path


def build(triage, systems, web, available=None):
    shelf = {"system": systems, "available": available or []}
    return bl.build(triage, shelf, INDEX, web, "2026-01-01")


def test_clean_build(web):
    avail = [{"button": "example", "file": "a.dat", "title": "A", "kind": "slag", "blurb": "b"}]
    d = build([row("nacl-kcl"), row("x", cls="proprietary")], [entry("nacl-kcl")], web, avail)
    assert [s["id"] for s in d["systems"]] == ["nacl-kcl"]
    assert d["systems"][0]["stage_label"] == "Data extracted"
    assert len(d["available"]) == 1


def test_proprietary_refused(web):
    with pytest.raises(bl.LibraryError, match="never be shown"):
        build([row("fe-al", cls="proprietary")], [entry("fe-al")], web)


def test_unclassified_refused(web):
    with pytest.raises(bl.LibraryError, match="never be shown"):
        build([row("llzo", cls=None)], [entry("llzo")], web)


def test_status_mentioning_proprietary_refused(web):
    r = row("coo-ga2o3", status="in_development (provisional, likely-proprietary)")
    with pytest.raises(bl.LibraryError, match="proprietary"):
        build([r], [entry("coo-ga2o3")], web)


def test_public_system_must_be_placed(web):
    with pytest.raises(bl.LibraryError, match="no entry"):
        build([row("cu-o", cls="public_academic")], [], web)


def test_unknown_system_refused(web):
    with pytest.raises(bl.LibraryError, match="not in the triage"):
        build([], [entry("ghost")], web)


def test_bad_shelf_and_kind_refused(web):
    with pytest.raises(bl.LibraryError, match="shelf"):
        build([row("a")], [entry("a", shelf="secret")], web)
    with pytest.raises(bl.LibraryError, match="kind"):
        build([row("a")], [entry("a", kind="gossip")], web)


def test_missing_button_or_file_refused(web):
    bad_button = [{"button": "nope", "file": "a.dat", "title": "A", "kind": "slag", "blurb": "b"}]
    with pytest.raises(bl.LibraryError, match="no button"):
        build([], [], web, bad_button)
    bad_file = [{"button": "example", "file": "gone.dat", "title": "A", "kind": "slag", "blurb": "b"}]
    with pytest.raises(bl.LibraryError, match="does not exist"):
        build([], [], web, bad_file)


def test_committed_library_json_follows_the_rules():
    d = json.loads((ROOT / "web" / "library.json").read_text("utf-8"))
    html = (ROOT / "web" / "index.html").read_text("utf-8")
    for s in d["available"]:
        assert f'id="{s["button"]}"' in html and (ROOT / "web" / s["file"]).is_file()
    for s in d["systems"]:
        assert s["shelf"] in bl.SHELVES and s["kind"] in bl.KINDS
        assert s["stage_label"] == bl.PUBLIC_STAGES[s["stage"]]
        # only counts and human blurbs are published, never raw workspace status notes
        assert set(s) == {f for f in bl.Announced.__dataclass_fields__}
