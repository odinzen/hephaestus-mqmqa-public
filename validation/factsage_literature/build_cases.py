"""ChemSage files for cases A and B, built from the transcribed tables in conditions.json.

    python validation/factsage_literature/build_cases.py

One file per binary system in data/ (case A: LiCl-, NaCl-, KCl-ThCl4; case B: LiF-LaF3,
LiF-CeF3, NaF-LaF3, NaF-CeF3), each holding the MQMQA liquid of the two salts, the solid
compounds, and in NaF-LaF3 and NaF-CeF3 the hexagonal solution. Nothing here is taken from
FactSage output; the papers' FactSage results stay sealed.

Each species' Gibbs energy is integrated term by term from its tabulated Cp, from dfH298 and S298
at 298.15 K, interval by interval with H and S carried continuously across each breakpoint (the
tables give no transition enthalpies inside a species). A Cp term k*T^n gives G terms
    n = 0:  -k T lnT + k(1 + ln T0) T - k T0
    n != 0, -1:  -k/(n(n+1)) T^(n+1) + (k T0^n / n) T - k T0^(n+1)/(n+1)
with T0 the interval's lower bound.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
T0 = 298.15
MASS = {"Li": 6.94, "Na": 22.99, "K": 39.098, "Th": 232.0377, "Cl": 35.453, "La": 138.90547,
        "Ce": 140.116, "F": 18.998403}
CHARGE = {"Li": 1, "Na": 1, "K": 1, "Th": 4, "La": 3, "Ce": 3}

# Cp forms as printed: case A a + bT + cT^2 + dT^-2, case B a + bT + cT^-2 + dT^2 (+ e T^3)
CP_POWERS = {"A": {"a": 0, "b": 1, "c": 2, "d": -2}, "B": {"a": 0, "b": 1, "c": -2, "d": 2, "e_T3": 3}}
STD = {0: 0, 1: 1, "lnT": 2, 2: 3, 3: 4, -1: 5}     # term -> slot in (1, T, TlnT, T^2, T^3, 1/T)


def cp_terms(seg, case):
    return [(CP_POWERS[case][k], v) for k, v in seg.items() if k in CP_POWERS[case] and v]


def h_s_increment(terms, ta, tb):
    """H(tb) - H(ta) and S(tb) - S(ta) for Cp = sum k T^n."""
    dh = ds = 0.0
    for n, k in terms:
        if n == 0:
            dh += k * (tb - ta)
            ds += k * math.log(tb / ta)
        elif n == -1:
            dh += k * math.log(tb / ta)
            ds += -k * (1.0 / tb - 1.0 / ta)
        else:
            dh += k * (tb ** (n + 1) - ta ** (n + 1)) / (n + 1)
            ds += k * (tb ** n - ta ** n) / n
    return dh, ds


def gibbs_intervals(rec, case, h_unit):
    """[(t_max, six standard coefficients, {exponent: extra coefficient})] for one species."""
    segs = sorted(rec["cp"], key=lambda s: s["T_range_K"][0])
    h = rec["dfH298_kJ"] * 1000.0 if h_unit == "kJ" else rec["dfH298_J"]
    s = rec["S298_J_K"]
    ta = T0
    out = []
    for i, seg in enumerate(segs):
        terms = cp_terms(seg, case)
        hi = seg["T_range_K"][1] if i + 1 < len(segs) else 6000.0
        c = [0.0] * 6
        extra = {}
        c[0] += h
        c[1] += -s
        for n, k in terms:
            if n == 0:
                c[STD["lnT"]] += -k
                c[1] += k * (1.0 + math.log(ta))
                c[0] += -k * ta
            elif n == -1:
                raise ValueError("a 1/T Cp term is not expected in these tables")
            else:
                p = n + 1
                coef = -k / (n * (n + 1))
                if p in STD:
                    c[STD[p]] += coef
                else:
                    extra[float(p)] = extra.get(float(p), 0.0) + coef
                c[1] += k * ta ** n / n
                c[0] += -k * ta ** (n + 1) / (n + 1)
        out.append((float(hi), c, extra))
        if i + 1 < len(segs):
            tb = float(segs[i + 1]["T_range_K"][0])
            if i + 1 < len(segs) and abs(tb - hi) > 1e-9:
                tb = float(hi)
            dh, ds = h_s_increment(terms, ta, tb)
            h, s, ta = h + dh, s + ds, tb
    # the first interval starts at 298.15 K, not at the printed 298
    return out


def fmt(x):
    return f"{x:.12E}"


def species_block(name, stoich, ivs, extra_ok=True):
    any_extra = any(e for _, _, e in ivs)
    lines = [f" {name}", f"   {4 if any_extra else 1}   {len(ivs)}   " + "   ".join(f"{v:.6f}" for v in stoich)]
    for t_max, c, extra in ivs:
        line = f"  {t_max:.4f}   " + "   ".join(fmt(v) for v in c)
        if any_extra:
            line += f"\n   {len(extra)}" + "".join(f"   {fmt(k)}   {e:.2f}" for e, k in extra.items())
        lines.append(line)
    return lines


def write(path, title, elements, liquid, solids, hexagonal=None):
    """liquid: dict(pairs=[(name, cation, n_anion, ivs)], anion, z_rows, terms); solids: [(name, stoich, ivs)]."""
    n_soln = 1 + (1 if hexagonal else 0)
    counts = [len(liquid["pairs"])] + ([len(hexagonal["species"])] if hexagonal else [])
    L = [f" System {title}  case built from published tables (validation/factsage_literature)",
         f"    {len(elements)}    {n_soln}    " + "    ".join(map(str, counts)) + f"    {len(solids)}",
         " " + "                       ".join(elements),
         "   " + "              ".join(f"{MASS[e]:.9f}" for e in elements),
         "    6   1   2   3   4   5   6", "    6   1   2   3   4   5   6",
         f" {title}-liquid", " SUBQ", f"   {len(liquid['pairs'])}   {len(liquid['z_rows'])}"]
    an = liquid["anion"]
    cats = [p[1] for p in liquid["pairs"]]
    for name, cat, n_an, ivs in liquid["pairs"]:
        stoich = [1.0 if e == cat else (float(n_an) if e == an else 0.0) for e in elements]
        L += species_block(name, stoich, ivs)
        L.append("  " + "   ".join(f"{v:.5f}" for v in (1.0, float(n_an), 0.0, 0.0, 0.0)))
        L.append("  1.3774438")
    L.append(f"   {len(cats)}   1")
    L.append(" " + "                     ".join(f"{c}+{CHARGE[c]}" for c in cats))
    L.append(f" {an}")
    L.append("  " + "      ".join(f"{float(CHARGE[c]):.5f}" for c in cats))
    L.append("   " + "   ".join(str(liquid["groups"][c]) for c in cats))
    L.append("  1.00000")
    L.append("   1")
    L.append("   " + "   ".join(str(i) for i in range(1, len(cats) + 1)))
    L.append("   " + "   ".join("1" for _ in cats))
    a_idx = len(cats) + 1
    for (ca, cb), (za, zb, zx) in liquid["z_rows"]:
        L.append(f"   {cats.index(ca) + 1}   {cats.index(cb) + 1}   {a_idx}   {a_idx}   "
                 f"{za:.15f}   {zb:.15f}   {zx:.15f}   {zx:.15f}")
    for (ca, cb), p, q, a, b in liquid["terms"]:
        L += ["   1", f" G   {cats.index(ca) + 1}   {cats.index(cb) + 1}   {a_idx}   {a_idx}   {p}   {q}   0   0",
              "  " + "   ".join("0.00000000" for _ in range(6)),
              "  " + "   ".join("0.00000000" for _ in range(6)),
              "   0   0   " + "   ".join(fmt(v) for v in (a, b, 0.0, 0.0, 0.0, 0.0))]
    L.append("   0")
    if hexagonal:
        L += [f" {title}-hexagonal", " QKTO"]
        for name, stoich, ivs in hexagonal["species"]:
            L += species_block(name, stoich, ivs)
            L.append("  1.00000      1")
        for idx, powers, a, b in hexagonal["terms"]:
            L += [f"   {len(idx)}", "   " + "   ".join(map(str, list(idx) + list(powers)))
                  + "   " + "   ".join(fmt(v) for v in (a, b, 0.0, 0.0, 0.0, 0.0))]
        L.append("   0")
    for name, stoich, ivs in solids:
        L += species_block(name, stoich, ivs)
    path.write_text("\n".join(L) + "\n", encoding="ascii")
    return path


def z_anion(qa, za, qb, zb, qx=1.0):
    """anion coordination from q_A/Z_A + q_B/Z_B = 2 q_X/Z_X"""
    return 2.0 * qx / (qa / za + qb / zb)


def case_a(case):
    data = case["parameters"]["end_members_and_compounds"]["data"]
    iv = {k: gibbs_intervals(v, "A", "kJ") for k, v in data.items()}
    zrows = {(r["A"].rstrip("+4").rstrip("+"), r["B"].rstrip("+4").rstrip("+")): (r["Z_A_AB/Cl"], r["Z_B_AB/Cl"])
             for r in case["parameters"]["liquid_coordination_numbers"]["rows"]}
    terms_src = case["parameters"]["liquid_excess"]["terms"]
    built = []
    for a, comp in (("Li", "Li4ThCl8(cr)"), ("Na", "Na2ThCl6(cr)"), ("K", None)):
        els = [a, "Th", "Cl"]
        z = {}
        for pair in ((a, a), ("Th", "Th"), (a, "Th")):
            za, zb = zrows[pair]
            z[pair] = (float(za), float(zb), z_anion(CHARGE[pair[0]], za, CHARGE[pair[1]], zb))
        t = next(x for x in terms_src if x["pair"] == f"{a}-Th")
        terms = [((a, "Th"), 0, 0, t["dg0"], 0.0)]
        for key, val in t.items():
            if key.startswith("g10"):
                terms.append(((a, "Th"), 1, 0, val, 0.0))
            elif key.startswith("g01"):
                terms.append(((a, "Th"), 0, 1, val, 0.0))
        liquid = {"pairs": [(f"{a}Cl", a, 1, iv[f"{a}Cl(l)"]), ("ThCl4", "Th", 4, iv["ThCl4(l)"])],
                  "anion": "Cl", "z_rows": list(z.items()), "terms": terms, "groups": {a: 1, "Th": 1}}

        def st(n_a, n_th):
            return [float(n_a), float(n_th), float(n_a + 4 * n_th)]
        solids = [(f"{a}Cl_cr", st(1, 0), iv[f"{a}Cl(cr)"]), ("ThCl4_alpha", st(0, 1), iv["alpha-ThCl4(cr)"]),
                  ("ThCl4_beta", st(0, 1), iv["beta-ThCl4(cr)"])]
        if a == "Li":
            solids.append(("Li4ThCl8", st(4, 1), iv["Li4ThCl8(cr)"]))
        elif a == "Na":
            solids.append(("Na2ThCl6", st(2, 1), iv["Na2ThCl6(cr)"]))
        else:
            solids += [("KThCl5", st(1, 1), iv["KThCl5(cr)"]), ("K2ThCl6", st(2, 1), iv["K2ThCl6(cr)"])]
        title = f"{a}Cl-ThCl4"
        built.append(write(HERE / "data" / f"caseA_{title}.dat", title, els, liquid, solids))
    return built


def case_b(case):
    par = case["parameters"]
    data = par["end_members_and_compounds"]["data"]
    iv = {k: gibbs_intervals(v, "B", "J") for k, v in data.items()}
    zrows = {(r["A"].rstrip("+3").rstrip("+"), r["B"].rstrip("+3").rstrip("+")): (r["Z_A"], r["Z_B"], r["Z_F"])
             for r in par["liquid_coordination_numbers"]["rows"]}
    # Table 3 as printed in conditions.json, chi weighted toward the trivalent cation
    liq_terms = {("Li", "La"): [(0, 0, -3953.3, -0.8172), (0, 1, -3679.5, 0.0)],
                 ("Na", "La"): [(0, 0, -13049.4, -0.599), (0, 1, -14614.4, 0.0)],
                 ("Li", "Ce"): [(0, 0, -4370.3, 0.0), (0, 1, -6293.2, 2.6)],
                 ("Na", "Ce"): [(0, 0, -17000.0, 3.2), (0, 1, -7500.0, 0.0)]}
    hex_terms = {"La": [((1, 2), (1, 1), -10000.0, 0.0), ((1, 2), (1, 3), -29500.0, 0.0)],
                 "Ce": [((1, 2), (1, 1), -29500.0, 0.0)]}
    built = []
    for a in ("Li", "Na"):
        for r in ("La", "Ce"):
            els = [a, r, "F"]

            def st(n_a, n_r):
                return [float(n_a), float(n_r), float(n_a + 3 * n_r)]
            z = {}
            for pair in ((a, a), (r, r), (a, r)):
                za, zb, zf = zrows[pair]
                zc = z_anion(CHARGE[pair[0]], za, CHARGE[pair[1]], zb)
                if abs(zc - zf) > 1e-9:
                    raise SystemExit(f"Table 1 Z_F {zf} for {pair} breaks charge balance ({zc})")
                z[pair] = (float(za), float(zb), float(zf))
            terms = [((a, r), p, q, ca, cb) for p, q, ca, cb in liq_terms[(a, r)]]
            liquid = {"pairs": [(f"{a}F", a, 1, iv[f"{a}F(l)"]), (f"{r}F3", r, 3, iv[f"{r}F3(l)"])],
                      "anion": "F", "z_rows": list(z.items()), "terms": terms, "groups": {a: 1, r: 2}}
            solids = [(f"{a}F_s", st(1, 0), iv[f"{a}F(s)"])]
            hexagonal = None
            if a == "Na":
                hexagonal = {"species": [("NaF_alpha", st(1, 0), iv["NaF(alpha)"]),
                                         (f"{r}F3_s", st(0, 1), iv[f"{r}F3(s)"])],
                             "terms": hex_terms[r]}
                solids.append((f"Na{r}F4", st(1, 1), iv[f"Na{r}F4(s)"]))
            else:
                solids.append((f"{r}F3_s", st(0, 1), iv[f"{r}F3(s)"]))
            title = f"{a}F-{r}F3"
            built.append(write(HERE / "data" / f"caseB_{title}.dat", title, els, liquid, solids, hexagonal))
    return built


def main():
    cases = {c["case"]: c for c in json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))["cases"]}
    for p in case_a(cases["A"]) + case_b(cases["B"]):
        print("wrote", p.relative_to(HERE))


if __name__ == "__main__":
    main()
