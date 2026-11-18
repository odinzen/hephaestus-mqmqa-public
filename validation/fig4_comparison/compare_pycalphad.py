"""Figure 4a (FeO-MgO-SiO2 liquidus projection) against pycalphad and against Bowen and Schairer.

pycalphad's own equilibrium solver reads the same FeO-MgO-SiO2-combined.dat and finds, at every
node of the figure's grid (150 steps per side), the liquidus temperature and the first solid to
crystallize. The MQMQA liquid energy in Hephaestus is a C translation of pycalphad's model, so
this checks the equilibrium mapping (which solid, at what temperature, where the isotherms run)
and whether the isotherms come out smooth, not the model.

The two codes find the liquidus differently. Hephaestus drives the liquid's tangent plane across
temperature on its refined hull (vis3d.liquidus_point). Here pycalphad gets a temperature ladder,
25 K, then 1 K, then 0.05 K steps, and the liquidus is the highest step that still holds a solid.

Bowen and Schairer's Table I (data/feo-mgo-sio2/bs1935_table1.csv) is scored by both codes with
the field grouping of data/feo-mgo-sio2/bs1935_liquidus.py, the scorer behind the manuscript's
21 K.

pycalphad's equilibrium samples each phase at pdens 60 unless told otherwise, and at that density
it misses the liquid in places. Every node where the codes disagree, and a random 500 where they
agree, are solved again at pdens 2000 on a 5 K ladder around both answers (`recheck`); where
they still differ, Hephaestus's general solver (src/gem.c) is run too. Neither is the last word,
so `energy` asks pycalphad itself: at the midpoint between the two answers, is the lowest state
it can find with a solid below the lowest it can find with liquid only? `driving` asks the same
with the solid's driving force against the lower of the two codes' liquids.

`reader` reads the whole grid again with the point reader after its split-liquid fix, and
`verify` checks each node it moved, or that still differs from pycalphad, with both codes'
lowest states 0.3 K either side of the new temperature.

    python validation/fig4_comparison/compare_pycalphad.py run       # 14.6 h on 14 processes
    python validation/fig4_comparison/compare_pycalphad.py recheck   # 2.6 h
    python validation/fig4_comparison/compare_pycalphad.py energy    # about 15 min
    python validation/fig4_comparison/compare_pycalphad.py driving   # about 4 min
    python validation/fig4_comparison/compare_pycalphad.py reader    # 78 min
    python validation/fig4_comparison/compare_pycalphad.py verify    # 15 min
    python validation/fig4_comparison/compare_pycalphad.py export    # re-derive the figure's fields
    python validation/fig4_comparison/compare_pycalphad.py report    # a minute, from the .npz files
"""
import csv
import importlib.util
import json
import sys
import time
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SYS = ROOT / "data" / "feo-mgo-sio2"
DAT = SYS / "FeO-MgO-SiO2-combined.dat"
FIG_JSON = ROOT / "web" / "ternary_feo_mgo_sio2.json"
NPZ = HERE / "liquidus.npz"
NPZ_DENSE = HERE / "liquidus_pdens2000.npz"
NPZ_ENERGY = HERE / "energy_check.npz"
NPZ_DF = HERE / "driving_force.npz"
NPZ_READER = HERE / "liquidus_reader_fixed.npz"
NPZ_VERIFY = HERE / "reader_verified.npz"
PDENS_DENSE = 2000
N_SPOT = 500
RESULTS_JSON = HERE / "results.json"
FIG_OUT = HERE / "fig4a_vs_pycalphad.png"
sys.path.insert(0, str(ROOT / "python"))

NGRID = 150
EPS = 1e-4                     # nodes on an edge are moved this far inside, for both codes
T_LO, T_HI = 1300.0, 3200.0
SOLID_MIN = 1e-4               # mole fraction of solid that counts as crystallized
LIQ = "FEO-MGO-SIO2-LIQUID"
PHASES = [LIQ, "OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE", "CRISTOBALITE"]
FIELD_PHASES = ["CRISTOBALITE", "OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE"]   # figure digits
LEVELS_K = [c + 273.15 for c in (1200, 1300, 1400, 1500, 1600, 1700)]           # figure levels
H = np.sqrt(3) / 2


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def grid_nodes(n=NGRID):
    """(i, j, x_Fe, x_Si) in the figure's order, x_Fe = i/n, x_Si = j/n, nudged inside by EPS."""
    out = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            x = np.array([i / n, j / n, 1.0 - (i + j) / n])        # Fe, Si, Mg
            x = (x + EPS) / (1.0 + 3 * EPS)
            out.append((i, j, x[0], x[1]))
    return out


def measured_points():
    bs = _load("bs1935", SYS / "bs1935_liquidus.py")
    rows = list(csv.DictReader(open(SYS / "bs1935_table1.csv", encoding="ascii")))
    return bs, rows, [bs.cation_fractions(r) for r in rows]          # (x_Fe, x_Mg, x_Si)


# ---------------------------------------------------------------- workers

_dbf = _db = _pdens = None


def _init(pdens=None):
    global _dbf, _db, _pdens
    _pdens = pdens
    warnings.filterwarnings("ignore")
    from pycalphad import Database
    import mqmqa
    _dbf = Database(str(DAT))
    _db = mqmqa.Database.read(str(DAT))


def _solids(x_fe, x_si, temps):
    """Per temperature, the total solid amount (nan where pycalphad returned nothing) and the
    most abundant solid."""
    from pycalphad import equilibrium, variables as v
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si                 # atoms per cation, oxygen charge-slaved
    eq = equilibrium(_dbf, ["FE", "MG", "SI", "O"], PHASES,
                     {v.T: list(map(float, temps)), v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot},
                     calc_opts={"pdens": _pdens} if _pdens else None)
    ph = eq.Phase.values.reshape(len(temps), -1).astype(str)
    np_ = eq.NP.values.reshape(len(temps), -1)
    solid, name = np.full(len(temps), np.nan), [""] * len(temps)
    for t in range(len(temps)):
        if not np.isfinite(np_[t]).any():
            continue
        amounts = {}
        for p, a in zip(ph[t], np_[t]):
            if p and p != LIQ and np.isfinite(a):
                amounts[p] = amounts.get(p, 0.0) + a
        solid[t] = sum(amounts.values())
        if amounts:
            name[t] = max(amounts, key=amounts.get)
    return solid, name


def pycalphad_liquidus(x_fe, x_si, lo=T_LO, hi=T_HI, step=25.0):
    """(T in K, primary solid, status, ladder points with no result), from a ladder over
    [lo, hi] refined twice by 25 and 20 steps."""
    misses = 0
    temps = np.arange(lo, hi + 1e-9, step)
    prim = ""
    for stage, npts in enumerate((None, 26, 21)):
        if npts:
            temps = np.linspace(lo, lo + step, npts)
            step = step / (npts - 1)
        s, names = _solids(x_fe, x_si, temps)
        misses += int(np.isnan(s).sum())
        has = np.nan_to_num(s, nan=0.0) > SOLID_MIN
        if not has.any():
            return np.nan, "", "below" if stage == 0 else "lost", misses
        k = int(np.nonzero(has)[0].max())
        if k == len(temps) - 1:
            return np.nan, "", "above" if stage == 0 else "lost", misses
        lo = temps[k]
        if stage == 1:
            prim = names[k]                              # within one fine step of the liquidus
    return lo + 0.5 * step, prim, "ok", misses


def pycalphad_window(x_fe, x_si, T_a, T_b, pad=40.0):
    """The ladder on a window around two candidate liquidus temperatures, 5 K steps, widened to
    the full range if the window does not bracket pycalphad's own liquidus."""
    lo = max(T_LO, 5.0 * np.floor((min(T_a, T_b) - pad) / 5.0))
    hi = min(T_HI, 5.0 * np.ceil((max(T_a, T_b) + pad) / 5.0))
    r = pycalphad_liquidus(x_fe, x_si, lo, hi, 5.0)
    return pycalphad_liquidus(x_fe, x_si) if r[2] in ("above", "below") else r


def _gem_solid(x_fe, x_si, T):
    from mqmqa import gem
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si
    b = {"Fe": x_fe / tot, "Mg": x_mg / tot, "Si": x_si / tot, "O": (x_fe + x_mg + 2.0 * x_si) / tot}
    for dT in (0.0, 0.004, -0.004):
        try:                        # a congruent melting point can leave the certificate unmet
            r = gem.equilibrium(_db, T + dT, b)
            break
        except RuntimeError:
            r = None
    if r is None:
        raise RuntimeError(f"gem found no equilibrium at {T:.3f} K")
    amounts = {}
    for s in r.sets:
        if s.phase != LIQ:
            amounts[s.phase] = amounts.get(s.phase, 0.0) + s.amount
    return sum(amounts.values()), (max(amounts, key=amounts.get) if amounts else "")


def gem_liquidus(x_fe, x_si, T_a, T_b, pad=20.0, tol=0.05):
    """Liquidus from Hephaestus's general solver (src/gem.c), a different code path from the
    refined hull behind the figure: the bracket is widened until a solid is present at its foot
    and absent at its top, then bisected."""
    lo, hi = min(T_a, T_b) - pad, max(T_a, T_b) + pad
    while _gem_solid(x_fe, x_si, lo)[0] <= SOLID_MIN and lo > T_LO:
        lo -= 50.0
    while _gem_solid(x_fe, x_si, hi)[0] > SOLID_MIN and hi < T_HI:
        hi += 50.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if _gem_solid(x_fe, x_si, mid)[0] > SOLID_MIN:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), _gem_solid(x_fe, x_si, lo)[1]


def _grid_task(node):
    from mqmqa import vis3d
    i, j, x_fe, x_si = node
    t0 = time.perf_counter()
    T_p, prim_p, status, misses = pycalphad_liquidus(x_fe, x_si)
    t1 = time.perf_counter()
    try:
        T_h, prim_h = vis3d.liquidus_point(_db, 1.0 - x_fe - x_si, x_si, T_LO, T_HI, t_tol=0.05)
    except Exception:
        T_h, prim_h = np.nan, ""
    return i, j, T_p, prim_p, status, misses, T_h, prim_h, t1 - t0


def _measured_task(x):
    from mqmqa import vis3d
    T_p, prim_p, status, misses = pycalphad_liquidus(x[0], x[2])
    T_h, prim_h = vis3d.liquidus_point(_db, x[1], x[2], 1350.0, 2300.0)   # as bs1935_liquidus
    return T_p, prim_p, status, T_h, prim_h


def run(nproc=14):
    nodes = grid_nodes()
    _, rows, comps = measured_points()
    print(f"{len(nodes)} grid nodes and {len(comps)} measured points on {nproc} processes")
    t0 = time.time()
    with Pool(nproc, initializer=_init) as pool:
        meas = pool.map(_measured_task, comps, chunksize=1)
        print(f"measured points done in {time.time() - t0:.0f} s")
        res = []
        for k, r in enumerate(pool.imap_unordered(_grid_task, nodes, chunksize=4), 1):
            res.append(r)
            if k % 500 == 0:
                print(f"  {k}/{len(nodes)} nodes, {time.time() - t0:.0f} s", flush=True)
    res.sort(key=lambda r: (r[0], r[1]))
    cols = list(zip(*res))
    mcols = list(zip(*meas))
    np.savez_compressed(
        NPZ, i=np.array(cols[0]), j=np.array(cols[1]), T_pyc=np.array(cols[2]),
        prim_pyc=np.array(cols[3]), status=np.array(cols[4]), misses=np.array(cols[5]),
        T_heph=np.array(cols[6]), prim_heph=np.array(cols[7]), secs=np.array(cols[8]),
        meas_T_pyc=np.array(mcols[0]), meas_prim_pyc=np.array(mcols[1]),
        meas_status=np.array(mcols[2]), meas_T_heph=np.array(mcols[3]),
        meas_prim_heph=np.array(mcols[4]), ngrid=NGRID, eps=EPS)
    print(f"wrote {NPZ} after {time.time() - t0:.0f} s")


def _disagree(z, tol_K=1.0):
    T_p, T_h = z["T_pyc"], z["T_heph"]
    return (~np.isfinite(T_p) | ~np.isfinite(T_h) | (z["prim_pyc"] != z["prim_heph"])
            | (np.abs(np.nan_to_num(T_p - T_h, nan=1e9)) > tol_K))


def _recheck_task(job):
    """pycalphad at pdens 2000 on a window around both earlier answers; where it still differs
    from Hephaestus by over 1 K or in the phase, the general solver referees."""
    x_fe, x_si, T_p0, T_h, prim_h, referee = job
    T_p, prim_p, status, misses = pycalphad_window(x_fe, x_si, np.nan_to_num(T_p0, nan=T_h), T_h)
    T_g, prim_g = np.nan, ""
    if referee or not np.isfinite(T_p) or abs(T_p - T_h) > 1.0 or prim_p != prim_h:
        try:
            T_g, prim_g = gem_liquidus(x_fe, x_si, np.nan_to_num(T_p, nan=T_h), T_h)
        except RuntimeError:
            prim_g = "failed"
    return T_p, prim_p, status, misses, T_g, prim_g


def recheck(nproc=14):
    z = np.load(NPZ)
    bad = np.nonzero(_disagree(z))[0]
    good = np.nonzero(~_disagree(z))[0]
    spot = np.random.default_rng(0).choice(good, size=min(N_SPOT, len(good)), replace=False)
    idx = np.r_[bad, np.sort(spot)]
    n = int(z["ngrid"])
    jobs = [((z["i"][k] / n + EPS) / (1 + 3 * EPS), (z["j"][k] / n + EPS) / (1 + 3 * EPS),
             float(z["T_pyc"][k]), float(z["T_heph"][k]), str(z["prim_heph"][k]), False)
            for k in idx]
    _, _, comps = measured_points()
    mjobs = [(x[0], x[2], float(a), float(b), str(p), True) for x, a, b, p in
             zip(comps, z["meas_T_pyc"], z["meas_T_heph"], z["meas_prim_heph"])]
    print(f"{len(bad)} disagreeing and {len(spot)} spot-check nodes at pdens {PDENS_DENSE}",
          flush=True)
    t0 = time.time()
    with Pool(nproc, initializer=_init, initargs=(PDENS_DENSE,)) as pool:
        meas = pool.map(_recheck_task, mjobs, chunksize=1)
        print(f"measured points done in {time.time() - t0:.0f} s", flush=True)
        res = []
        for m, r in enumerate(pool.imap(_recheck_task, jobs, chunksize=2), 1):
            res.append(r)
            if m % 250 == 0:
                print(f"  {m}/{len(jobs)} nodes, {time.time() - t0:.0f} s", flush=True)
    cols, mcols = list(zip(*res)), list(zip(*meas))
    np.savez_compressed(
        NPZ_DENSE, k=idx, spot=np.r_[np.zeros(len(bad), bool), np.ones(len(spot), bool)],
        T_pyc=np.array(cols[0]), prim_pyc=np.array(cols[1]), status=np.array(cols[2]),
        misses=np.array(cols[3]), T_gem=np.array(cols[4]), prim_gem=np.array(cols[5]),
        meas_T_pyc=np.array(mcols[0]), meas_prim_pyc=np.array(mcols[1]),
        meas_status=np.array(mcols[2]), meas_T_gem=np.array(mcols[4]),
        meas_prim_gem=np.array(mcols[5]), pdens=PDENS_DENSE)
    print(f"wrote {NPZ_DENSE} after {time.time() - t0:.0f} s")


def _gm(x_fe, x_si, T, phases):
    """(GM in J per mole of atoms, solid amount, most abundant solid) from pycalphad restricted
    to the given phases."""
    from pycalphad import equilibrium, variables as v
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si
    eq = equilibrium(_dbf, ["FE", "MG", "SI", "O"], phases,
                     {v.T: float(T), v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot},
                     calc_opts={"pdens": _pdens})
    amounts = {}
    for p, a in zip(eq.Phase.values.ravel().astype(str), eq.NP.values.ravel()):
        if p and p != LIQ and np.isfinite(a):
            amounts[p] = amounts.get(p, 0.0) + a
    solid = sum(amounts.values())
    return float(eq.GM.values.squeeze()), solid, (max(amounts, key=amounts.get) if amounts else "")


def _energy_task(job):
    """At the midpoint between the two liquidus answers one code says a solid is present and the
    other says liquid only. pycalphad's own energies decide: the lowest state it can find with a
    solid against the lowest it can find without one."""
    x_fe, x_si, T_mid, solids = job
    with_solid, liquid_only = [], []
    for phases in [PHASES, [LIQ]] + [[LIQ, s] for s in solids]:
        g, solid, _ = _gm(x_fe, x_si, T_mid, phases)
        (with_solid if solid > SOLID_MIN else liquid_only).append(g)
    return (min(with_solid) if with_solid else np.nan,
            min(liquid_only) if liquid_only else np.nan)


def energy(nproc=14):
    """Energy arbitration on every node where pdens 2000 still disagrees with Hephaestus."""
    z, zd = np.load(NPZ), np.load(NPZ_DENSE)
    n, k = int(z["ngrid"]), zd["k"]
    T_h, prim_h = z["T_heph"][k], z["prim_heph"][k].astype(str)
    T_p, prim_p = zd["T_pyc"], zd["prim_pyc"].astype(str)
    differ = (np.abs(np.nan_to_num(T_p - T_h, nan=1e9)) > 1.0) | (prim_p != prim_h)
    pick = np.nonzero(differ)[0]
    jobs = [((z["i"][k[m]] / n + EPS) / (1 + 3 * EPS), (z["j"][k[m]] / n + EPS) / (1 + 3 * EPS),
             0.5 * (T_h[m] + T_p[m]), sorted({prim_h[m], prim_p[m]} - {""})) for m in pick]
    print(f"{len(jobs)} nodes", flush=True)
    t0 = time.time()
    with Pool(nproc, initializer=_init, initargs=(PDENS_DENSE,)) as pool:
        res = pool.map(_energy_task, jobs, chunksize=1)
    g_s, g_l = map(np.array, zip(*res))
    np.savez_compressed(NPZ_ENERGY, m=pick, G_solid=g_s,
                        G_liquid=g_l, T_mid=np.array([j[2] for j in jobs]))
    print(f"wrote {NPZ_ENERGY} after {time.time() - t0:.0f} s")


def _df_task(job):
    """Largest driving force (J per mole of atoms) for any of the named solids to crystallize
    from the liquid at T: above zero, the liquid is supersaturated and T lies below the
    liquidus. Each code's liquid-only equilibrium is found and the lower one is used, because
    either can miss the liquid's split into two near the silica corner. The solid's energy comes
    from pycalphad. Returns (driving force, G of pycalphad's liquid, G of Hephaestus's liquid)."""
    from mqmqa import gem
    from pycalphad import calculate, equilibrium, variables as v
    x_fe, x_si, T, solids = job
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si
    comps = ["FE", "MG", "SI", "O"]
    eq = equilibrium(_dbf, comps, [LIQ],
                     {v.T: float(T), v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot},
                     calc_opts={"pdens": _pdens})
    g_p = float(eq.GM.values.squeeze())
    mu = dict(zip(eq.component.values.astype(str), eq.MU.values.ravel()))
    b = {"FE": x_fe / tot, "MG": x_mg / tot, "SI": x_si / tot, "O": (x_fe + x_mg + 2 * x_si) / tot}
    try:
        r = gem.equilibrium(_db, float(T), b, suspend=PHASES[1:])
        g_h = r.G
    except RuntimeError:
        g_h = np.nan
    if np.isfinite(g_h) and not (g_p <= g_h):
        mu = {"O": 0.0} | {e.upper(): u for e, u in r.mu.items()}   # gem sets mu_O to zero;
        # every phase here is charge balanced, so the plane is the same in either gauge
    best = -np.inf
    for s in solids:
        c = calculate(_dbf, comps, s, T=float(T), P=1e5, N=1, pdens=_pdens, output="GM")
        X = c.X.values.reshape(-1, len(c.component))
        plane = X @ np.array([mu[e] for e in c.component.values.astype(str)])
        best = max(best, float(np.nanmax(plane - c.GM.values.ravel())))
    return best, g_p, g_h


def driving(nproc=14):
    """Driving-force test at the midpoint of every node `energy` looked at."""
    z, zd, ze = np.load(NPZ), np.load(NPZ_DENSE), np.load(NPZ_ENERGY)
    n, k, m = int(z["ngrid"]), zd["k"], ze["m"]
    prim_h, prim_p = z["prim_heph"][k].astype(str), zd["prim_pyc"].astype(str)
    jobs = [((z["i"][k[q]] / n + EPS) / (1 + 3 * EPS), (z["j"][k[q]] / n + EPS) / (1 + 3 * EPS),
             float(t), sorted({prim_h[q], prim_p[q]} - {""})) for q, t in zip(m, ze["T_mid"])]
    t0 = time.time()
    with Pool(nproc, initializer=_init, initargs=(PDENS_DENSE,)) as pool:
        df, g_p, g_h = map(np.array, zip(*pool.map(_df_task, jobs, chunksize=2)))
    np.savez_compressed(NPZ_DF, m=m, driving_force=df, G_liq_pyc=g_p, G_liq_heph=g_h)
    print(f"wrote {NPZ_DF} for {len(df)} nodes after {time.time() - t0:.0f} s")


def _reader_task(node):
    from mqmqa import vis3d
    i, j, x_fe, x_si = node
    try:
        return vis3d.liquidus_point(_db, 1.0 - x_fe - x_si, x_si, T_LO, T_HI, t_tol=0.05)
    except Exception:
        return np.nan, ""


def reader(nproc=14):
    """Hephaestus's point reader again on every node, after the split-liquid fix (exact
    plane from the general solver, and the bracket check)."""
    nodes = grid_nodes()
    t0 = time.time()
    with Pool(nproc, initializer=_init) as pool:
        res = pool.map(_reader_task, nodes, chunksize=8)
    T, prim = zip(*res)
    np.savez_compressed(NPZ_READER, T_heph=np.array(T), prim_heph=np.array(prim))
    print(f"wrote {NPZ_READER} after {time.time() - t0:.0f} s")


def _lowest(x_fe, x_si, T):
    """(lowest G with a solid present, lowest G with liquid only), J per mole of atoms, over
    the states both codes find: each code's full equilibrium and each code's liquid alone."""
    from mqmqa import gem
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si
    b = {"FE": x_fe / tot, "MG": x_mg / tot, "SI": x_si / tot, "O": (x_fe + x_mg + 2 * x_si) / tot}
    # any solid with mass counts here: a degree under a flat liquidus it can be 1e-4 or less
    with_solid, liquid = [np.inf], [np.inf]
    for phases in (PHASES, [LIQ]):
        g, solid, _ = _gm(x_fe, x_si, T, phases)
        (with_solid if solid > 1e-9 else liquid).append(g)
    for suspend in ((), PHASES[1:]):
        try:
            r = gem.equilibrium(_db, T, b, suspend=suspend)
        except RuntimeError:
            continue
        solid = sum(st.amount for st in r.sets if st.phase != LIQ)
        (with_solid if solid > 1e-9 else liquid).append(r.G)
    return min(with_solid), min(liquid)


def _verify_task(job):
    x_fe, x_si, T, d = job
    return _lowest(x_fe, x_si, T - d) + _lowest(x_fe, x_si, T + d)


def verify(nproc=14, d=0.3):
    """The fixed reader against both codes' lowest states, d below and above its liquidus,
    wherever it moved by over 0.1 K or still differs from pycalphad by over 1 K."""
    z, zd, zr = np.load(NPZ), np.load(NPZ_DENSE), np.load(NPZ_READER)
    n = int(z["ngrid"])
    T_old, T_new = z["T_heph"], zr["T_heph"]
    T_p = z["T_pyc"].copy()
    T_p[zd["k"]] = zd["T_pyc"]
    sel = np.nonzero((np.abs(T_new - T_old) > 0.1) | (np.abs(np.nan_to_num(T_new - T_p, nan=1e9)) > 1.0))[0]
    jobs = [((z["i"][q] / n + EPS) / (1 + 3 * EPS), (z["j"][q] / n + EPS) / (1 + 3 * EPS),
             float(T_new[q]), d) for q in sel]
    print(f"{len(jobs)} nodes", flush=True)
    t0 = time.time()
    with Pool(nproc, initializer=_init, initargs=(PDENS_DENSE,)) as pool:
        res = np.array(pool.map(_verify_task, jobs, chunksize=2))
    np.savez_compressed(NPZ_VERIFY, sel=sel, d=d, G_solid_below=res[:, 0], G_liquid_below=res[:, 1],
                        G_solid_above=res[:, 2], G_liquid_above=res[:, 3])
    print(f"wrote {NPZ_VERIFY} after {time.time() - t0:.0f} s")


def export_check():
    """Re-derive the figure's field digits with the current engine and compare with the shipped
    web/ternary_feo_mgo_sio2.json, so the figure is known to be what the code makes today."""
    ex = _load("export_ternary_json", SYS / "export_ternary_json.py")
    t0 = time.time()
    rows = ex.field_rows()
    shipped = json.load(open(FIG_JSON, encoding="utf-8"))["field_rows"]
    diff = sum(a != b for r, s in zip(rows, shipped) for a, b in zip(r, s))
    print(f"field digits re-derived in {time.time() - t0:.0f} s: {diff} of "
          f"{sum(map(len, shipped))} differ from the shipped figure data")
    return diff


# ---------------------------------------------------------------- report

def _xy(x_fe, x_si):
    return np.asarray(x_fe) + 0.5 * np.asarray(x_si), H * np.asarray(x_si)


def _contours(x_fe, x_si, T, levels):
    """Raw liquidus isotherms (no smoothing) as polylines in (x_Fe, x_Si), interior arcs only,
    selected exactly as the figure's exporter selects them."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bs = _load("bs_comparison", SYS / "bs_comparison.py")
    ok = np.isfinite(T)
    fig, ax = plt.subplots()
    out = {}
    for lev in levels:
        cs = ax.tricontour(x_fe[ok], x_si[ok], T[ok], levels=[lev])
        out[lev] = [run for s in cs.allsegs[0] for run in bs._interior_runs(np.asarray(s))
                    if bs._arclen(run) > 0.2]
    plt.close(fig)
    return out


def _resample(P, h):
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    s = np.arange(0, d[-1], h)
    return np.column_stack([np.interp(s, d, P[:, 0]), np.interp(s, d, P[:, 1])])


def _dist_to(P, Q):
    """Distance from each point of P to the polyline Q (both Cartesian)."""
    from scipy.spatial import cKDTree
    return cKDTree(_resample(Q, 1e-4)).query(P)[0]


def _turning_rms(arcs, h):
    """RMS change of direction, in degrees, between steps of one grid spacing along the arcs:
    a staircase turns by tens of degrees at every step, a smooth curve by a degree or two."""
    turns = []
    for P in arcs:
        R = _resample(P, h)
        if len(R) < 3:
            continue
        a = np.arctan2(*np.diff(R, axis=0).T[::-1])
        turns.append((np.diff(a) + np.pi) % (2 * np.pi) - np.pi)
    t = np.degrees(np.concatenate(turns))
    return float(np.sqrt(np.mean(t ** 2))), float(np.abs(t).max())


def _stats(d):
    d = np.asarray(d, float)
    return {"n": int(d.size), "mean": float(d.mean()), "rms": float(np.sqrt(np.mean(d ** 2))),
            "mean_abs": float(np.abs(d).mean()), "max_abs": float(np.abs(d).max())}


def _pointwise(T_p, prim_p, T_h, prim_h, fig_name, X, Y, x_fe, x_si, n):
    """Primary phase against the figure's digits and against Hephaestus node by node, and the
    liquidus temperature difference."""
    from scipy.spatial import cKDTree
    both = (fig_name != "") & (prim_p != "")
    miss = both & (fig_name != prim_p)
    to_edge = []                    # grid steps from each disagreeing node to a figure boundary
    for k in np.nonzero(miss)[0]:
        other = (fig_name != fig_name[k]) & (fig_name != "")
        to_edge.append(cKDTree(np.column_stack([X[other], Y[other]])).query([X[k], Y[k]])[0] * n)
    to_edge = np.array(to_edge)
    out = {"field_vs_figure": {
        "compared": int(both.sum()), "agree": int((both & ~miss).sum()), "differ": int(miss.sum()),
        "differ_within_1_step_of_boundary": int((to_edge <= 1.0 + 1e-9).sum()),
        "differ_within_2_steps_of_boundary": int((to_edge <= 2.0 + 1e-9).sum()),
        "max_grid_steps_from_boundary": float(to_edge.max()) if len(to_edge) else 0.0,
        "differ_by_pair": {f"{a} -> {b}": int(((fig_name == a) & (prim_p == b) & miss).sum())
                           for a in FIELD_PHASES for b in FIELD_PHASES
                           if ((fig_name == a) & (prim_p == b) & miss).any()}}}
    same = (prim_h != "") & (prim_p != "")
    out["field_vs_hephaestus_pointwise"] = {"compared": int(same.sum()),
                                            "agree": int((same & (prim_h == prim_p)).sum())}
    ok = np.isfinite(T_p) & np.isfinite(T_h)
    dT = T_p[ok] - T_h[ok]
    st = _stats(dT)
    st.update({f"p{q}_abs": float(np.percentile(np.abs(dT), q)) for q in (50, 95, 99)})
    st.update({f"nodes_over_{c}K": int((np.abs(dT) > c).sum()) for c in (0.5, 1, 5, 20)})
    out["liquidus_pyc_minus_heph_K"] = st
    worst = np.argsort(-np.abs(np.where(ok, T_p - T_h, 0)))[:8]
    out["worst_nodes"] = [{"x_Fe": round(float(x_fe[k]), 4), "x_Si": round(float(x_si[k]), 4),
                           "T_pyc": round(float(T_p[k]), 1), "T_heph": round(float(T_h[k]), 1),
                           "prim_pyc": str(prim_p[k]), "prim_heph": str(prim_h[k])}
                          for k in worst]
    return out, miss


def report():
    z = np.load(NPZ)
    zd = np.load(NPZ_DENSE)
    n = int(z["ngrid"])
    i, j = z["i"], z["j"]
    x_fe = (i / n + EPS) / (1 + 3 * EPS)
    x_si = (j / n + EPS) / (1 + 3 * EPS)
    T_h, prim_h = z["T_heph"], z["prim_heph"].astype(str)
    T_p0, prim_p0 = z["T_pyc"], z["prim_pyc"].astype(str)
    # final pycalphad answer: pdens 2000 wherever it was solved again
    k = zd["k"]
    T_p, prim_p = T_p0.copy(), prim_p0.copy()
    T_p[k], prim_p[k] = zd["T_pyc"], zd["prim_pyc"].astype(str)
    out = {"ngrid": n, "nodes": int(len(i)),
           "pycalphad_status_pdens60": {s: int((z["status"] == s).sum())
                                        for s in np.unique(z["status"])},
           "pycalphad_ladder_points_without_result_pdens60": int(z["misses"].sum()),
           "hephaestus_failed": int(np.isnan(T_h).sum()),
           "pycalphad_seconds_per_node_pdens60": float(z["secs"].mean())}

    d = json.load(open(FIG_JSON, encoding="utf-8"))
    assert d["ngrid"] == n and d["phases"] == FIELD_PHASES
    fig_name = np.array([FIELD_PHASES[int(c)] if c != "." else ""
                         for c in (d["field_rows"][a][b] for a, b in zip(i, j))])
    X, Y = _xy(i / n, j / n)
    out["pdens60"], _ = _pointwise(T_p0, prim_p0, T_h, prim_h, fig_name, X, Y, x_fe, x_si, n)
    out["final"], miss = _pointwise(T_p, prim_p, T_h, prim_h, fig_name, X, Y, x_fe, x_si, n)

    spot = zd["spot"]
    ks, kb = k[spot], k[~spot]
    moved = ((np.abs(np.nan_to_num(zd["T_pyc"][spot] - T_p0[ks], nan=1e9)) > 0.5)
             | (zd["prim_pyc"][spot].astype(str) != prim_p0[ks]))
    dense_ok = ((np.abs(np.nan_to_num(zd["T_pyc"][~spot] - T_h[kb], nan=1e9)) <= 1.0)
                & (zd["prim_pyc"][~spot].astype(str) == prim_h[kb]))
    out["recheck_pdens2000"] = {
        "disagreeing_nodes_rechecked": int((~spot).sum()),
        "of_which_now_agree_within_1K_same_phase": int(dense_ok.sum()),
        "spot_check_agreeing_nodes": int(spot.sum()),
        "spot_check_changed_by_over_0p5K_or_phase": int(moved.sum()),
        "status": {s: int((zd["status"] == s).sum()) for s in np.unique(zd["status"])}}

    # where pdens 2000 still differs, the general solver referees (within 1 K and same phase)
    T_g, prim_g = zd["T_gem"], zd["prim_gem"].astype(str)
    ref = (prim_g != "") & (prim_g != "failed")
    side_h = ref & (np.abs(np.nan_to_num(T_g - T_h[k], nan=1e9)) <= 1.0) & (prim_g == prim_h[k])
    side_p = (ref & (np.abs(np.nan_to_num(T_g - zd["T_pyc"], nan=1e9)) <= 1.0)
              & (prim_g == zd["prim_pyc"].astype(str)))
    out["referee_general_solver"] = {
        "nodes_refereed": int(ref.sum() + (prim_g == "failed").sum()),
        "solver_failed": int((prim_g == "failed").sum()),
        "sides_with_hephaestus_only": int((side_h & ~side_p).sum()),
        "sides_with_pycalphad_only": int((side_p & ~side_h).sum()),
        "sides_with_both": int((side_h & side_p).sum()),
        "sides_with_neither": int((ref & ~side_h & ~side_p).sum()),
        "gem_minus_hephaestus_K": _stats((T_g - T_h[k])[ref]) if ref.any() else None,
        "gem_minus_pycalphad_K": (_stats((T_g - zd["T_pyc"])[ref & np.isfinite(zd["T_pyc"])])
                                  if ref.any() else None),
        "neither": [{"x_Fe": round(float(x_fe[kk]), 4), "x_Si": round(float(x_si[kk]), 4),
                     "T_heph": round(float(T_h[kk]), 1), "T_pyc": round(float(tp), 1),
                     "T_gem": round(float(tg), 1), "prim_heph": str(prim_h[kk]),
                     "prim_pyc": str(pp), "prim_gem": str(pg)}
                    for kk, tp, tg, pp, pg in zip(k[ref & ~side_h & ~side_p],
                                                  zd["T_pyc"][ref & ~side_h & ~side_p],
                                                  T_g[ref & ~side_h & ~side_p],
                                                  zd["prim_pyc"][ref & ~side_h & ~side_p],
                                                  prim_g[ref & ~side_h & ~side_p])][:40]}

    # pycalphad's own energies at the midpoint between the two answers decide which is right.
    # Primary test: the driving force for the solid from the lower of the two codes' liquid-only
    # equilibria (above zero, a solid is present at T_mid). Corroboration: the lowest state
    # pycalphad finds with a solid against the lowest liquid-only state either code finds.
    ze, zf = np.load(NPZ_ENERGY), np.load(NPZ_DF)
    m = ze["m"]
    assert np.array_equal(m, zf["m"])
    Tp_e, Th_e = zd["T_pyc"][m], T_h[k[m]]
    df = zf["driving_force"]
    g_liq = np.fmin(ze["G_liquid"], zf["G_liq_heph"])      # pycalphad can miss the liquid split
    dG = ze["G_solid"] - g_liq
    split = np.abs(Tp_e - Th_e) > 1.0
    solid = df > 0.01
    liquid = df < -0.01
    heph_high = Th_e > Tp_e
    heph_right = split & ((heph_high & solid) | (~heph_high & liquid))
    pyc_right = split & ((heph_high & liquid) | (~heph_high & solid))
    dg_solid, dg_liquid = dG < -1e-3, dG > 1e-3
    agree = (solid & dg_solid) | (liquid & dg_liquid)
    contra = (solid & dg_liquid) | (liquid & dg_solid)

    def _nodes(sel):
        return [{"x_Fe": round(float(x_fe[k[q]]), 4), "x_Si": round(float(x_si[k[q]]), 4),
                 "T_heph": round(float(T_h[k[q]]), 1), "T_pyc": round(float(zd["T_pyc"][q]), 1),
                 "driving_force_J": round(float(f), 3)} for q, f in zip(m[sel], df[sel])]

    out["energy_test"] = {
        "nodes": int(len(m)), "differ_in_phase_only": int((~split).sum()),
        "undecided_driving_force_within_10mJ": int((split & ~solid & ~liquid).sum()),
        "pycalphad_high_wrong": int((split & ~heph_high & liquid).sum()),
        "pycalphad_high_right": int((split & ~heph_high & solid).sum()),
        "hephaestus_high_wrong": int((split & heph_high & liquid).sum()),
        "hephaestus_high_right": int((split & heph_high & solid).sum()),
        "hephaestus_right": int(heph_right.sum()), "pycalphad_right": int(pyc_right.sum()),
        "lowest_state_test_agrees": int((split & agree).sum()),
        "lowest_state_test_contradicts": int((split & contra).sum()),
        "lowest_state_test_found_no_solid_state": int((split & np.isnan(dG)).sum()),
        "liquid_of_hephaestus_lower_by_over_1mJ": int((zf["G_liq_pyc"] - zf["G_liq_heph"] > 1e-3).sum()),
        "liquid_of_pycalphad_lower_by_over_1mJ": int((zf["G_liq_heph"] - zf["G_liq_pyc"] > 1e-3).sum()),
        "liquid_gap_max_J": float(np.nanmax(np.abs(zf["G_liq_pyc"] - zf["G_liq_heph"]))),
        "hephaestus_error_K_where_pycalphad_right": _stats((Th_e - Tp_e)[pyc_right])
        if pyc_right.any() else None,
        "pycalphad_error_K_where_hephaestus_right": _stats((Tp_e - Th_e)[heph_right])
        if heph_right.any() else None,
        "pycalphad_right_nodes": _nodes(pyc_right)[:150],
        "contradicted_nodes": _nodes(split & contra)}
    # the best liquidus at each node: Hephaestus unless pycalphad's own energies say otherwise
    T_best = T_h.copy()
    T_best[k[m[pyc_right]]] = zd["T_pyc"][m[pyc_right]]
    st = _stats(T_h - T_best)
    st["nodes_off_by_over_1K"] = int((np.abs(T_h - T_best) > 1.0).sum())
    out["hephaestus_minus_energy_settled_K"] = st

    # the point reader after the split-liquid fix, checked by both codes' lowest states
    zr, zv = np.load(NPZ_READER), np.load(NPZ_VERIFY)
    T_new = zr["T_heph"]
    sel = zv["sel"]
    below = zv["G_solid_below"] - zv["G_liquid_below"]     # below zero: solid stable under T
    above = zv["G_liquid_above"] - zv["G_solid_above"]     # below zero: liquid only over T
    ok = (below < 1e-3) & (above < 1e-3)
    tie = ok & ((np.abs(below) < 1e-3) | (np.abs(above) < 1e-3))
    out["point_reader_fixed"] = {
        "failed": int(np.isnan(T_new).sum()),
        "nodes_moved_over_1K": int((np.abs(T_new - T_h) > 1.0).sum()),
        "primary_phase_changed": int((zr["prim_heph"].astype(str) != prim_h).sum()),
        "nodes_checked": int(len(sel)), "check_d_K": float(zv["d"]),
        "checked_and_confirmed": int(ok.sum()),
        "of_which_within_1mJ_at_one_side": int(tie.sum()),
        "not_confirmed": [{"x_Fe": round(float(x_fe[q]), 4), "x_Si": round(float(x_si[q]), 4),
                           "T_old": round(float(T_h[q]), 2), "T_new": round(float(T_new[q]), 2),
                           "G_solid_minus_liquid_below_J": round(float(gb), 4),
                           "G_liquid_minus_solid_above_J": round(float(ga), 4)}
                          for q, gb, ga in zip(sel[~ok], below[~ok], above[~ok])],
        "new_minus_old_K_over_moved_nodes": _stats((T_new - T_h)[np.abs(T_new - T_h) > 1.0])
        if (np.abs(T_new - T_h) > 1.0).any() else None,
        "new_minus_energy_settled_K_where_old_was_off": _stats((T_new - T_best)[k[m[pyc_right]]]),
        "new_minus_energy_settled_K_all_nodes": _stats(T_new - T_best),
        "new_off_energy_settled_by_over_1K": int((np.abs(T_new - T_best) > 1.0).sum())}

    # isotherms: pycalphad's raw contours against the figure's drawn arcs
    step = 1.0 / n
    fig_arcs = {round(it["degC"] + 273.15, 2): [np.column_stack(_xy(*np.asarray(a).T))
                                                for a in it["arcs"]] for it in d["isotherms"]}
    raw_p = _contours(x_fe, x_si, T_p, LEVELS_K)
    raw_h = _contours(x_fe, x_si, T_h, LEVELS_K)
    quant = _contours(x_fe, x_si, np.floor(T_p / 10.0) * 10.0, LEVELS_K)
    raw_b = _contours(x_fe, x_si, T_best, LEVELS_K)
    iso = {}
    for lev in LEVELS_K:
        key = round(lev, 2)
        cart = {name: [np.column_stack(_xy(*P.T)) for P in arcs[lev]]
                for name, arcs in (("pyc", raw_p), ("heph", raw_h), ("q", quant), ("best", raw_b))}
        row = {"figure_arcs": len(fig_arcs.get(key, [])), "pycalphad_arcs": len(cart["pyc"]),
               "energy_best_arcs": len(cart["best"])}
        for name in ("pyc", "best"):
            if fig_arcs.get(key) and cart[name]:
                dist = np.concatenate([np.min([_dist_to(_resample(P, step / 4), A)
                                               for A in fig_arcs[key]], axis=0)
                                       for P in cart[name]])
                row[f"{name}_to_figure_grid_steps"] = {
                    "mean": float(dist.mean() / step), "p95": float(np.percentile(dist, 95) / step),
                    "max": float(dist.max() / step)}
        if cart["pyc"]:
            row["turning_rms_deg"] = {
                "pycalphad_raw": _turning_rms(cart["pyc"], step)[0],
                "hephaestus_raw": _turning_rms(cart["heph"], step)[0] if cart["heph"] else None,
                "figure": _turning_rms(fig_arcs[key], step)[0] if fig_arcs.get(key) else None,
                "energy_settled": _turning_rms(cart["best"], step)[0] if cart["best"] else None,
                "pycalphad_in_10K_steps": _turning_rms(cart["q"], step)[0] if cart["q"] else None}
        iso[f"{lev:.2f}"] = row
    out["isotherms"] = iso

    # Bowen and Schairer Table I, by field
    bs, rows, comps = measured_points()
    Tm = np.array([float(r["T_C"]) + 273.15 for r in rows])
    prim_meas = [r["primary"] for r in rows]
    meas = {}
    for code, T, prim in (
            ("hephaestus", z["meas_T_heph"], z["meas_prim_heph"].astype(str)),
            ("pycalphad_pdens60", z["meas_T_pyc"], z["meas_prim_pyc"].astype(str)),
            ("pycalphad_pdens2000", zd["meas_T_pyc"], zd["meas_prim_pyc"].astype(str)),
            ("general_solver", zd["meas_T_gem"], zd["meas_prim_gem"].astype(str))):
        by = {}
        for field, keys in bs.FIELDS.items():
            sel = np.array([p in keys for p in prim_meas]) & np.isfinite(T)
            by[field] = _stats(T[sel] - Tm[sel])
        scored = [(bs.MODEL_PHASE[p], q) for p, q in zip(prim_meas, prim) if bs.MODEL_PHASE[p]]
        by["primary_as_measured"] = f"{sum(a == b for a, b in scored)} of {len(scored)}"
        meas[code] = by
    out["bowen_schairer_1935"] = meas
    out["measured_points"] = [
        {"x_Fe": round(float(c[0]), 3), "x_Si": round(float(c[2]), 3), "T_meas": round(t, 1),
         "primary_meas": p, "T_heph": round(float(a), 1), "T_pyc_pdens2000": round(float(b), 1),
         "T_general_solver": round(float(g), 1), "prim_heph": str(pa),
         "prim_pyc_pdens2000": str(pb), "prim_general_solver": str(pg)}
        for c, t, p, a, b, g, pa, pb, pg in zip(
            comps, Tm, prim_meas, z["meas_T_heph"], zd["meas_T_pyc"], zd["meas_T_gem"],
            z["meas_prim_heph"], zd["meas_prim_pyc"], zd["meas_prim_gem"])]

    RESULTS_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "measured_points"}, indent=1))
    heph_off = np.zeros(len(T_h), bool)
    heph_off[k[m[pyc_right]]] = True
    plot(x_fe, x_si, fig_arcs, raw_p, miss, comps, prim_meas, T_p - T_new, heph_off)


def plot(x_fe, x_si, fig_arcs, raw_p, miss, comps, prim_meas, dT, heph_off):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, TwoSlopeNorm
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon
    from scipy.interpolate import griddata

    plt.rcParams.update({"font.family": "serif",
                         "font.serif": ["Times New Roman", "DejaVu Serif"]})
    colour = {"CRISTOBALITE": "#8f84c9", "OLIVINE": "#44a065", "ORTHOPYROXENE": "#3d78d6",
              "MAGNESIOWUSTITE": "#d07a43"}
    d = json.load(open(FIG_JSON, encoding="utf-8"))
    n = d["ngrid"]
    fi, fj, fk = [], [], []
    for a, row in enumerate(d["field_rows"]):
        for b, c in enumerate(row):
            if c != ".":
                fi.append(a); fj.append(b); fk.append(int(c))
    NX, NY = _xy(np.array(fi) / n, np.array(fj) / n)
    gx, gy = np.meshgrid(np.linspace(0, 1, 900), np.linspace(0, H, int(900 * H)))
    xs = gy / H
    xf = gx - 0.5 * xs
    inside = (xf >= 0) & (xs >= 0) & (xf + xs <= 1)

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.6, 5.6), dpi=300)
    field = griddata(np.column_stack([NX, NY]), np.array(fk), (gx, gy), method="nearest")
    field = np.where(inside, field, np.nan)
    cmap = ListedColormap([colour[p] for p in FIELD_PHASES])
    axa.imshow(field, origin="lower", extent=(0, 1, 0, H), cmap=cmap, vmin=-0.5, vmax=3.5,
               interpolation="nearest", alpha=0.55)
    for arcs in fig_arcs.values():
        for P in arcs:
            axa.plot(P[:, 0], P[:, 1], color="#1a1a1a", lw=2.4, zorder=3)
    for lev, arcs in raw_p.items():
        for P in arcs:
            C = np.column_stack(_xy(*P.T))
            axa.plot(C[:, 0], C[:, 1], color="#ffffff", lw=0.9, ls=(0, (3, 2)), zorder=4)
    MX, MY = _xy(x_fe[miss], x_si[miss])
    axa.plot(MX, MY, ".", color="#c81e2c", ms=2.5, zorder=5)
    marker = {"ol": "o", "cpx": "s", "trid": "^", "crist": "^", "trid+cpx": "D"}
    for c, p in zip(comps, prim_meas):
        px, py = _xy(c[0], c[2])
        axa.plot(px, py, marker[p], ms=5.5, mfc="white", mec="#1a1a1a", mew=1.0, zorder=6)
    handles = [Line2D([], [], color="#1a1a1a", lw=2.4, label="Figure 4a isotherm (Hephaestus)"),
               Line2D([], [], color="#7a7a7a", lw=0.9, ls=(0, (3, 2)),
                      label="pycalphad isotherm, unsmoothed"),
               Line2D([], [], color="#c81e2c", ls="", marker=".", label="primary phase differs"),
               Line2D([], [], color="#1a1a1a", ls="", marker="o", mfc="white",
                      label="measured, olivine first"),
               Line2D([], [], color="#1a1a1a", ls="", marker="s", mfc="white",
                      label="measured, pyroxene first"),
               Line2D([], [], color="#1a1a1a", ls="", marker="^", mfc="white",
                      label="measured, silica first"),
               Line2D([], [], color="#1a1a1a", ls="", marker="D", mfc="white",
                      label="measured, silica and pyroxene together")]
    axa.legend(handles=handles, loc="upper center", fontsize=9, frameon=False, ncol=2,
               bbox_to_anchor=(0.5, 0.0), columnspacing=1.2)

    ok = np.isfinite(dT)
    DX, DY = _xy(x_fe[ok], x_si[ok])
    grid_dT = np.where(inside, griddata(np.column_stack([DX, DY]), dT[ok], (gx, gy),
                                        method="linear"), np.nan)
    lim = max(1.0, float(np.nanpercentile(np.abs(dT[ok]), 99.5)))
    im = axb.imshow(grid_dT, origin="lower", extent=(0, 1, 0, H), cmap="RdBu_r",
                    norm=TwoSlopeNorm(0.0, -lim, lim), interpolation="nearest")
    OX, OY = _xy(x_fe[heph_off], x_si[heph_off])
    axb.plot(OX, OY, ".", color="#1a1a1a", ms=2.5, zorder=5)
    axb.legend(handles=[Line2D([], [], color="#1a1a1a", ls="", marker=".",
                               label="point reader off by over 1 K before the fix")],
               loc="upper center", fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0))
    cax = axb.inset_axes([0.15, -0.2, 0.7, 0.035])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("pycalphad minus Hephaestus liquidus, fixed point reader (K)", fontsize=11)

    for ax, tag in ((axa, "(a)"), (axb, "(b)")):
        ax.add_patch(Polygon([(0, 0), (1, 0), (0.5, H)], closed=True, fill=False, ec="#1a1a1a",
                             lw=1.2, zorder=7))
        ax.text(-0.012, -0.025, "MgO", fontsize=12, ha="right", va="top")
        ax.text(1.012, -0.025, "FeO", fontsize=12, ha="left", va="top")
        ax.text(0.5, H + 0.02, "SiO$_2$", fontsize=12, ha="center", va="bottom")
        ax.set_xlim(-0.1, 1.1); ax.set_ylim(-0.08, H + 0.08)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(tag, fontsize=14)
    fig.savefig(FIG_OUT, bbox_inches="tight", facecolor="white")
    print(f"wrote {FIG_OUT}")


if __name__ == "__main__":
    {"run": run, "recheck": recheck, "energy": energy, "driving": driving, "reader": reader,
     "verify": verify,
     "export": export_check,
     "report": report}[sys.argv[1]]()
