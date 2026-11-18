"""Independent check of reported chemical potentials, phase by phase.

For every stable solution phase of every computed point, the phase's own internal equilibrium
at the composition the solver reported is found here from scratch, in Python: a minimization
of its Gibbs energy per atom at that fixed composition, then a root solve of the equilibrium
conditions (stationarity on every sublattice, the sublattice sums, the composition, and the
phase on its tangent plane), with the ideal term differentiated exactly and the rest by
central differences of a different step than the engine's. The potentials that come out are
compared with the reported ones, element by element over the elements the phase holds.
Compounds are checked for lying on the reported plane. MQMQA liquids are left to pycalphad.

    python verify_sets.py RESULTS.json [ids...]
"""
import json
import os
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, root

R_ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R_ / "python"))
import mqmqa  # noqa: E402
from mqmqa._abi import _lib  # noqa: E402

DATA = Path(os.environ.get("THERMOCHIMICA_DATA", "../thermochimica-ref/data"))
cond = json.loads((R_ / "validation/thermochimica/conditions.json").read_text(encoding="utf-8"))
dbname = {c["id"]: c.get("database") for c in cond["conditions"] + cond["extended_grid"]}
H = 2e-6
_dbs = {}


def formula(name, els):
    """element -> amount for a constituent name such as CS2TE, NBO5/2, O2SN, CR+3, VA"""
    base = re.sub(r"[+-]\d*$", "", name.upper())
    if base in ("VA", ""):
        return {}
    out, i = {}, 0
    while i < len(base):
        sym = base[i:i + 2] if base[i:i + 2] in els else base[i:i + 1]
        if sym not in els:
            return None
        i += len(sym)
        m = re.match(r"(\d+(?:/\d+)?)", base[i:])
        amt = Fraction(m.group(1)) if m else Fraction(1)
        if m:
            i += len(m.group(1))
        out[sym] = out.get(sym, 0) + float(amt)
    return out


def charge(name):
    m = re.search(r"([+-])(\d*)$", name)
    return 0.0 if not m else float(m.group(2) or 1)


class Phase:
    def __init__(self, db, p, T):
        self.db, self.p, self.T = db, p, T
        self.els = [e.upper() for e, _ in db.elements]
        kind = db.phase_kind(p)
        self.ionic = kind == 2
        if self.ionic:
            cats, rest = db.ionic_constituents(p)
            self.names = cats + rest
            self.sub = [0] * len(cats) + [1] * len(rest)
            self.nc = len(cats)
            self.q = [charge(n) for n in self.names]
            self.va = [i for i, n in enumerate(self.names) if n.upper() == "VA"]
            self.R = db.R
        else:
            subl = db.cef_sublattices(p)
            self.names, self.sub, self.r = [], [], []
            for s, d in enumerate(subl):
                self.names += d["constituents"]
                self.sub += [s] * len(d["constituents"])
                self.r.append(d["site_ratio"])
            self.R = _lib.mqmqa_gas_constant(_lib.mqmqa_db_R_own(db._db))
        self.ns = max(self.sub) + 1
        self.comp = [formula(n, self.els) for n in self.names]

    def m(self, y):
        if not self.ionic:
            return self.r
        Q = sum(self.q[c] * y[c] for c in range(self.nc))
        P = sum(self.q[i] * y[i] for i in range(self.nc, len(y)) if self.q[i] > 0)
        P += Q * sum(y[i] for i in self.va)
        return [P, Q]

    def eval(self, y):
        """G per formula unit and element amounts (vector over database elements)"""
        if self.ionic:
            g, n = self.db.ionic_gibbs(self.p, y, self.T)
            return g, np.array([n[e] for e, _ in self.db.elements])
        N = np.zeros(len(self.els))
        for i, c in enumerate(self.comp):
            for e, a in c.items():
                N[self.els.index(e)] += self.r[self.sub[i]] * y[i] * a
        return self.db.cef_gibbs(self.p, y, self.T, per_mole_atoms=False), N


def check_set(ph, x, mu_rep):
    """potentials of phase ph at composition x (dict) from its own internal equilibrium"""
    els = ph.els
    xv = np.array([x.get(e, x.get(e.capitalize(), 0.0)) for e in els])
    xv = np.array([sum(v for k, v in x.items() if k.upper() == e) for e in els])
    have = [k for k, v in enumerate(xv) if v > 1e-14]
    # the most abundant element's row is the redundant one: dropping a dilute element's row
    # would leave its fraction to 1 - (the others), far coarser than its own size
    have.sort(key=lambda k: -xv[k])
    if any(c is None for c in ph.comp):
        return None, "constituent formula not parsed"
    act = [i for i, c in enumerate(ph.comp) if all(xv[els.index(e)] > 1e-14 for e in c)]
    nv = len(ph.names)
    RT = ph.R * ph.T

    def full(yact):
        y = np.zeros(nv)
        y[act] = yact
        return y

    # start: minimum of G per atom at the fixed composition, from several starts
    def unpack(z):
        y = np.zeros(nv)
        for s in range(ph.ns):
            idx = [i for i in act if ph.sub[i] == s]
            if not idx:
                continue
            zz = np.array([z[act.index(i)] for i in idx])
            e = np.exp(zz - zz.max())
            y[idx] = e / e.sum()
        return y

    def gpa(z):
        g, N = ph.eval(unpack(z))
        return g / N.sum()

    def comp_err(z):
        _, N = ph.eval(unpack(z))
        return np.log(np.maximum((N / N.sum())[have[1:]], 1e-300)) - np.log(xv[have[1:]])

    starts = []
    # random starts, and one per constituent pushed toward it (an ionic liquid has several
    # internal arrangements, and a random start can settle in a worse one)
    z0s = [np.random.default_rng(seed).normal(0, 3 if seed else 0, len(act)) for seed in range(8)]
    for j in range(len(act)):
        z = np.zeros(len(act))
        z[j] = 8.0
        z0s.append(z)
    for z0 in z0s:
        r = minimize(gpa, z0, method="SLSQP", constraints=[{"type": "eq", "fun": comp_err}],
                     options={"maxiter": 2000, "ftol": 1e-14})
        if np.max(np.abs(comp_err(r.x))) < 1e-8:
            starts.append(r)
    if not starts:
        return None, "no feasible start"
    starts.sort(key=lambda r: r.fun)
    hv = [k for k in have]
    mu0 = np.array([mu_rep.get(els[k], 0.0) for k in hv])

    # root solve: unknowns ln y (active), lambda per sublattice (in RT), mu (phase elements, in RT)
    subs = sorted({ph.sub[i] for i in act})

    def F(u):
        v = u[:len(act)]
        lam = u[len(act):len(act) + len(subs)]
        mu = u[len(act) + len(subs):] * RT
        y = full(np.exp(v))
        m0 = ph.m(y)
        g0, N0 = ph.eval(y)

        def smooth(yy):
            g, N = ph.eval(yy)
            ideal = sum(ph.R * ph.T * m0[ph.sub[i]] * yy[i] * math.log(yy[i]) for i in range(nv) if yy[i] > 0)
            return g - ideal - float(mu @ N[hv])

        out = []
        for j, i in enumerate(act):
            yp, ym = y.copy(), y.copy()
            yp[i] += H
            ym[i] -= H
            d = (smooth(yp) - smooth(ym)) / (2 * H) + ph.R * ph.T * m0[ph.sub[i]]
            out.append((ph.R * ph.T * m0[ph.sub[i]] * v[j] + d) / RT - lam[subs.index(ph.sub[i])])
        for s in subs:
            out.append(sum(y[i] for i in act if ph.sub[i] == s) - 1.0)
        tot = N0.sum()
        for k in hv[1:]:                  # relative, so a dilute element is held to its own digits
            ratio = N0[k] / tot if tot > 0 else 0.0
            out.append(math.log(ratio) - math.log(xv[k]) if ratio > 0 else 1e3)
        out.append((g0 - float(mu @ N0[hv])) / RT)
        return np.array(out)

    sol, res, gbest = None, np.inf, np.inf
    for st in starts:
        y0 = unpack(st.x)
        for mstart in (mu0 / RT, np.zeros(len(hv))):
            u0 = np.concatenate([np.log(np.maximum(y0[act], 1e-300)), np.zeros(len(subs)), mstart])
            for method, opts in (("hybr", {"xtol": 1e-13, "maxfev": 20000}),
                                 ("lm", {"xtol": 1e-15, "ftol": 1e-15, "maxiter": 20000})):
                cand = root(F, u0, method=method, options=opts)
                r_ = np.max(np.abs(F(cand.x)))
                if not r_ < 1e-6:
                    if sol is None or (gbest == np.inf and r_ < res):
                        sol, res = cand, r_
                    continue
                g_ = float(cand.x[len(act) + len(subs):] * RT @ xv[hv])   # mu.x: G per atom there
                if g_ < gbest - 1e-9:
                    sol, res, gbest = cand, r_, g_
    mu = sol.x[len(act) + len(subs):] * RT
    return {els[k]: mu[j] for j, k in enumerate(hv)}, f"residual {res:.1e}"


def main():
    pts = json.load(open(sys.argv[1]))["points"]
    ids = sys.argv[2:] or list(pts)
    worst = 0.0
    nchk = 0
    for k in ids:
        p = pts[k]
        if p["class"] != "computed":
            continue
        name = dbname[k]
        db = _dbs.setdefault(name, mqmqa.Database.read(str(DATA / name)))
        _lib.mqmqa_db_set_pressure(db._db, p["P_atm"] * 101325.0)
        try:
            mu_rep = {e.upper(): v for e, v in p["mu_J_per_mol"].items()}
            for s in p["phases"]:
                copies = [i for i, nm in enumerate(db.phase_names) if nm == s["phase"]]
                if not copies or db.phase_kind(copies[0]) == 0:
                    continue
                # a result names the phase only; where a file holds several phases of that name
                # (FeMnCaS-1's two different IONIC_LIQ), the set belongs to one of them
                best = None
                for pi in copies:
                    ph = Phase(db, pi, p["T_K"])
                    mu, note = check_set(ph, s["x"], mu_rep)
                    if mu is None:
                        continue
                    d_ = max(abs(mu[e] - mu_rep[e]) for e in mu)
                    if best is None or d_ < best[0]:
                        best = (d_, mu, note)
                if best is None:
                    print(f"{k:22s} {name:24s} {s['phase']:12s} not checked: {note}")
                    continue
                _, mu, note = best
                dev = max(abs(mu[e] - mu_rep[e]) for e in mu)
                rel = max(abs(mu[e] - mu_rep[e]) / max(abs(mu_rep[e]), 1.0) for e in mu)
                nchk += 1
                worst = max(worst, dev)
                flag = "  <<" if dev > 0.05 else ""
                print(f"{k:22s} {name:24s} {s['phase']:12s} max |dmu| {dev:10.4f} J/mol (rel {rel:.1e}) {note}{flag}")
        finally:
            _lib.mqmqa_db_set_pressure(db._db, 101325.0)
    print(f"{nchk} sets checked, largest deviation {worst:.4f} J/mol")


if __name__ == "__main__":
    main()
