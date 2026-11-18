// Runs Hermes 0.3.0 (MIT, https://github.com/odinzen/hermes, doi 10.5281/zenodo.23923573)
// on Pyodide in a worker, so the page stays responsive. Every file comes from this site:
// web/vendor/pyodide and web/hermes, assembled by scripts/build_hermes_web.py.
// Messages in: {id, cmd: 'init' | 'load' | 'compute' | 'diagram', ...}; out: {id, ok, result | error}.

const BASE = new URL('./', self.location).href;
const WHEELS = [
  'vendor/pyodide/narwhals-2.29.0-py3-none-any.whl',
  'vendor/pyodide/plotly-7.1.0-py3-none-any.whl',
  'hermes/hermes-0.3.0-py3-none-any.whl',
];

const PY = String.raw`
import io, json, math
import numpy as np
from hermes.configuration import Configuration
from hermes.system import System

FIELDS = ("helmholtz_energies", "helmholtz_energies_dV", "helmholtz_energies_d2V2",
          "entropies", "heat_capacities")
state = {}


def _clean(a):
    # JSON has no NaN; Hermes leaves NaN where a property is undefined (end points, no minimum)
    a = np.asarray(a, dtype=float)
    return [None if not math.isfinite(v) else v for v in a.ravel().tolist()]


def _from_npz(raw):
    z = np.load(io.BytesIO(raw), allow_pickle=False)
    names = [str(n) for n in z["names"]]
    data = {"temperatures": z["temperatures"], "volumes": z["volumes"],
            "number_of_atoms": int(z["number_of_atoms"]), "ground_state": str(z["ground_state"]),
            "configurations": {}}
    for n in names:
        c = {"multiplicity": int(z[f"{n}/multiplicity"])}
        for k in FIELDS:
            if f"{n}/{k}" in z.files:
                c[k] = z[f"{n}/{k}"]
        data["configurations"][n] = c
    return data


def _build(data):
    T = np.asarray(data["temperatures"], dtype=float)
    V = np.asarray(data["volumes"], dtype=float)
    configs = {}
    for name, c in data["configurations"].items():
        missing = [k for k in FIELDS if k not in c]
        if missing:
            raise ValueError(f"configuration {name} lacks {', '.join(missing)}")
        arrays = {k: np.asarray(c[k], dtype=float) for k in FIELDS}
        configs[name] = Configuration(name=name, multiplicity=int(c["multiplicity"]),
                                      number_of_atoms=int(data["number_of_atoms"]),
                                      volumes=V, temperatures=T, **arrays)
    gs = data.get("ground_state") or next(iter(configs))
    if gs not in configs:
        raise ValueError(f"ground state {gs} is not one of the configurations")
    return System(configs, ground_state=gs)


def load(raw, kind):
    raw = raw.to_bytes()
    data = _from_npz(raw) if kind == "npz" else json.loads(raw.decode("utf-8"))
    system = _build(data)
    state.clear()
    state["system"] = system
    T, V = system.temperatures, system.volumes
    return json.dumps({
        "configurations": [{"name": n, "multiplicity": int(c.multiplicity)}
                           for n, c in system.configurations.items()],
        "ground_state": system.ground_state, "number_of_atoms": int(system.number_of_atoms),
        "T": [float(T[0]), float(T[-1]), int(len(T))], "V": [float(V[0]), float(V[-1]), int(len(V))],
    })


def compute(P):
    s = state["system"]
    s.calculate_pressure_properties(P)
    pp = s.pt_properties[f"{P:.2f}_GPa"]
    T = s.temperatures
    out = {"P": P, "T": _clean(T), "T_mid": _clean(T[:-1]),
           "probabilities": {n: _clean(c.probabilities_at_P[f"{P:.2f}_GPa"])
                             for n, c in s.configurations.items()}}
    for k in ("V0", "G0", "S0", "Sconf", "B0", "CTE", "LCTE", "Cp"):
        out[k] = _clean(pp[k])
    return json.dumps(out)


def diagram():
    s = state["system"]
    s.calculate_phase_diagrams()
    pd = s.pt_phase_diagram
    return json.dumps({k: {"P": _clean(pd[k]["P"]), "T": _clean(pd[k]["T"])}
                       for k in ("first_order", "second_order")})
`;

let py = null;

async function init() {
  const probe = await fetch(BASE + 'vendor/pyodide/pyodide.js', { method: 'HEAD' });
  if (!probe.ok) throw new Error('the Python runtime is not on this server (run scripts/build_hermes_web.py)');
  importScripts(BASE + 'vendor/pyodide/pyodide.js');
  py = await loadPyodide({ indexURL: BASE + 'vendor/pyodide/' });
  await py.loadPackage(['numpy', 'scipy', 'packaging'], { messageCallback: () => {} });
  for (const w of WHEELS) {
    const r = await fetch(BASE + w);
    if (!r.ok) throw new Error('missing ' + w + ' (run scripts/build_hermes_web.py)');
    py.unpackArchive(await r.arrayBuffer(), 'wheel');
  }
  py.runPython(PY);
  return py.runPython([
    'import sys, numpy, scipy, plotly, hermes',
    "f'Python {sys.version.split()[0]}, numpy {numpy.__version__}, scipy {scipy.__version__}'",
  ].join('\n'));
}

const call = (fn, ...args) => {
  const f = py.globals.get(fn);
  try { return JSON.parse(f(...args)); } finally { f.destroy(); }
};

self.onmessage = async (e) => {
  const { id, cmd } = e.data;
  try {
    let result;
    if (cmd === 'init') result = await init();
    else if (cmd === 'load') result = call('load', new Uint8Array(e.data.buffer), e.data.kind);
    else if (cmd === 'compute') result = call('compute', e.data.P);
    else if (cmd === 'diagram') result = call('diagram');
    else throw new Error('unknown command ' + cmd);
    self.postMessage({ id, ok: true, result });
  } catch (err) {
    // keep only the last line of a Python traceback, which carries the message
    const msg = String(err && err.message || err).trim().split('\n').filter(Boolean).pop();
    self.postMessage({ id, ok: false, error: msg });
  }
};
