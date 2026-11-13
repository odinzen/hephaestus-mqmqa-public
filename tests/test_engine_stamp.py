"""The page and the 3D worker must load the engine under a URL that changes with the engine.

A page written for a new engine, served next to a cached old one, crashes on the first
function the old one lacks (this happened with ?v=20260909b, unchanged for two months).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stamp_engine  # noqa: E402


def test_every_engine_reference_carries_the_current_fingerprint():
    fp = stamp_engine.fingerprint()
    for name, value in stamp_engine.stamped_versions().items():
        assert value == fp, f"{name} loads hephaestus.js?v={value}; run scripts/stamp_engine.py ({fp})"
