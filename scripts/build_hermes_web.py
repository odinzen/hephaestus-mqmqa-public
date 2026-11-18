"""Assemble the files the Hermes tab of web/index.html runs on.

The tab runs Hermes (MIT, https://github.com/odinzen/hermes) in the browser on Pyodide.
The page loads nothing from third parties, so everything it needs is served from web/:

    web/vendor/pyodide/   Pyodide core and the packages Hermes imports, each checked
                          against a pinned SHA-256 (git-ignored, about 40 MB)
    web/hermes/           the Hermes wheel built from the v0.3.0 release commit and the
                          Fe3Pt demonstration data in .npz form

Usage (from the repo root; needs git, pip and numpy):

    python scripts/build_hermes_web.py --hermes-repo ../hermes-public

--hermes-repo is any clone of odinzen/hermes that contains the v0.3.0 commit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pickle
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

PYODIDE_VERSION = "0.28.3"
PYODIDE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_CORE = {
    "pyodide.js": "24a458425dcb4ea9836eb5ce26701d18cb769374e2b79247602ba605bf093278",
    "pyodide.asm.js": "b22e5831eade9ff10e6fe2c811c68688cd91f10154377b4f80debcf5bafa1e56",
    "pyodide.asm.wasm": "5effb6a1a6cc4a1a85bec4622701aa797c031e1de923cbbaf2ad47abdc4ab325",
    "python_stdlib.zip": "71fee17f88a6260ec8c9c7c063533ee59c021fdc88a1ce76247378d3c4a35f4c",
    "pyodide-lock.json": "f6e6f42f451f42affbbcddb00e8c9a3278dcbf399f57aab9f3f568839a7ff4a6",
}
# Pyodide packages Hermes needs; their hashes come from the pinned pyodide-lock.json.
PYODIDE_PACKAGES = ["numpy", "scipy", "libopenblas", "packaging"]
# Pure-Python wheels from PyPI (Hermes imports plotly at module level).
PYPI_WHEELS = {
    "https://files.pythonhosted.org/packages/e5/7d/905a3a3d51087515719058c94cfbda2ff0fc14417c20d557ae3e82d8b250/plotly-7.1.0-py3-none-any.whl":
        "dbb7fa18afce40d0a8e80d1bf162eceb3faa0ce5a77fe741ad09a74cf78f53f3",
    "https://files.pythonhosted.org/packages/9e/2b/20b4b463c3795dc390db8fa6ec2b5c3e0aea90a760f813305da4c33dd814/narwhals-2.29.0-py3-none-any.whl":
        "1c69b3dc30240f6e848c5a673cafc86affa44184ecce721e25b7194663ad10dc",
}

HERMES_VERSION = "0.3.0"
HERMES_COMMIT = "1468389b0941beaee2d7838361f0a20eaddc7841"  # tag v0.3.0
HERMES_DOI = "10.5281/zenodo.23923573"
DEMO_PICKLE = "tests/test_data/Fe3Pt_three_configs.pkl"
# Every fourth point of the published 1000-point volume grid. Against the full grid the
# fixed-pressure results at 0 GPa move by at most 2e-4 (relative, Cp) and 4e-4 1/MK (LCTE).
DEMO_VOLUME_STEP = 4
DEMO_GROUND_STATE = "FM"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, digest: str, dest: Path) -> None:
    if dest.exists() and sha256(dest.read_bytes()) == digest:
        return
    with urllib.request.urlopen(url) as r:
        data = r.read()
    if sha256(data) != digest:
        raise SystemExit(f"checksum mismatch for {url}")
    dest.write_bytes(data)
    print(f"  {dest.relative_to(ROOT)} ({len(data) / 1e6:.1f} MB)")


def build_pyodide() -> None:
    out = WEB / "vendor" / "pyodide"
    out.mkdir(parents=True, exist_ok=True)
    for name, digest in PYODIDE_CORE.items():
        fetch(PYODIDE_URL + name, digest, out / name)
    lock = json.loads((out / "pyodide-lock.json").read_text())
    for pkg in PYODIDE_PACKAGES:
        entry = lock["packages"][pkg]
        fetch(PYODIDE_URL + entry["file_name"], entry["sha256"], out / entry["file_name"])
    for url, digest in PYPI_WHEELS.items():
        fetch(url, digest, out / url.rsplit("/", 1)[1])


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def build_hermes(repo: Path) -> None:
    out = WEB / "hermes"
    out.mkdir(parents=True, exist_ok=True)
    if git(repo, "cat-file", "-t", HERMES_COMMIT).strip() != b"commit":
        raise SystemExit(f"{repo} does not contain Hermes {HERMES_VERSION} ({HERMES_COMMIT})")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "hermes"
        archive = git(repo, "archive", "--format=tar", HERMES_COMMIT,
                      "pyproject.toml", "README.md", "LICENSE.txt", "hermes", DEMO_PICKLE)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(src, filter="data")
        for old in out.glob("hermes-*.whl"):
            old.unlink()
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                        "-q", "-w", str(out), str(src)], check=True)
        shutil.copyfile(src / "LICENSE.txt", out / "LICENSE-hermes.txt")
        write_demo(src, out / "fe3pt_demo.npz")


def write_demo(src: Path, dest: Path) -> None:
    # The pickle was written by pyzentropy, so its class paths name pyzentropy modules.
    sys.path.insert(0, str(src))
    import hermes.configuration
    import hermes.system
    sys.modules.setdefault("pyzentropy", hermes)
    sys.modules.setdefault("pyzentropy.configuration", hermes.configuration)
    sys.modules.setdefault("pyzentropy.system", hermes.system)
    with open(src / DEMO_PICKLE, "rb") as f:
        configs = pickle.load(f)
    first = next(iter(configs.values()))
    s = slice(None, None, DEMO_VOLUME_STEP)
    arrays = {
        "temperatures": np.asarray(first.temperatures, dtype=float),
        "volumes": np.asarray(first.volumes, dtype=float)[s],
        "number_of_atoms": np.asarray(first.number_of_atoms),
        "names": np.asarray(list(configs)),
        "ground_state": np.asarray(DEMO_GROUND_STATE),
    }
    for name, c in configs.items():
        arrays[f"{name}/multiplicity"] = np.asarray(int(c.multiplicity))
        for key in ("helmholtz_energies", "helmholtz_energies_dV", "helmholtz_energies_d2V2",
                    "entropies", "heat_capacities"):
            arrays[f"{name}/{key}"] = np.asarray(getattr(c, key), dtype=float)[:, s]
    np.savez_compressed(dest, **arrays)
    print(f"  {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hermes-repo", type=Path, required=True)
    args = ap.parse_args()
    print(f"Pyodide {PYODIDE_VERSION} -> web/vendor/pyodide")
    build_pyodide()
    print(f"Hermes {HERMES_VERSION} ({HERMES_DOI}) -> web/hermes")
    build_hermes(args.hermes_repo.resolve())


if __name__ == "__main__":
    main()
