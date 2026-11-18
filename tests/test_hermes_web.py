"""The Hermes tab of web/index.html: shipped files and the worker's Python.

The worker's Python (the String.raw block in web/hermes_worker.js) is run here against the
shipped Fe3Pt example when Hermes 0.3.0 is importable, and checked against values Hermes
gives natively on the same file. In the browser it returned the same numbers bit for bit.
"""

import json
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DEMO = WEB / "hermes" / "fe3pt_demo.npz"
FIELDS = ("helmholtz_energies", "helmholtz_energies_dV", "helmholtz_energies_d2V2",
          "entropies", "heat_capacities")


def test_demo_file_is_complete():
    z = np.load(DEMO, allow_pickle=False)
    names = [str(n) for n in z["names"]]
    assert names == ["FM", "SF22", "SF28"]
    assert str(z["ground_state"]) in names
    shape = (len(z["temperatures"]), len(z["volumes"]))
    assert shape == (101, 250)
    for n in names:
        assert int(z[f"{n}/multiplicity"]) > 0
        for k in FIELDS:
            assert z[f"{n}/{k}"].shape == shape, (n, k)
            assert np.isfinite(z[f"{n}/{k}"]).all(), (n, k)


def test_worker_and_page_name_the_shipped_wheel():
    wheels = sorted(p.name for p in (WEB / "hermes").glob("hermes-*.whl"))
    assert wheels == ["hermes-0.3.0-py3-none-any.whl"]
    worker = (WEB / "hermes_worker.js").read_text(encoding="utf-8")
    assert "hermes/" + wheels[0] in worker
    page = (WEB / "index.html").read_text(encoding="utf-8")
    assert "10.5281/zenodo.23923573" in page and "Hermes 0.3.0" in page


def _worker_python():
    src = (WEB / "hermes_worker.js").read_text(encoding="utf-8")
    return re.search(r"const PY = String\.raw`(.*?)`;", src, re.S).group(1)


def test_worker_python_reproduces_hermes():
    pytest.importorskip("hermes.system")
    ns = {}
    exec(_worker_python(), ns)

    class Raw(bytes):
        def to_bytes(self):  # stands in for Pyodide's JsProxy of a Uint8Array
            return bytes(self)

    info = json.loads(ns["load"](Raw(DEMO.read_bytes()), "npz"))
    assert info["ground_state"] == "FM" and info["number_of_atoms"] == 12
    r = json.loads(ns["compute"](0.0))
    i = r["T"].index(300.0)
    # Hermes 0.3.0 run natively on fe3pt_demo.npz, 0 GPa, 300 K
    assert r["V0"][i] == pytest.approx(157.77892382119038, rel=1e-12, abs=0)
    assert r["G0"][i] == pytest.approx(-93.32653027589606, rel=1e-12, abs=0)
    assert r["Cp"][i] == pytest.approx(0.0030977075252682862, rel=1e-10, abs=0)
    assert r["probabilities"]["FM"][i] == pytest.approx(0.8707389998433821, rel=1e-10, abs=0)
    assert len(r["Cp"]) == len(r["T_mid"]) == len(r["T"]) - 1
