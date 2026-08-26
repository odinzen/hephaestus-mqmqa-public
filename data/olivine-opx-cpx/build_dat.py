"""The Ca-Fe-Mg-Si silicate solid-solution system: olivine + orthopyroxene +
clinopyroxene in one ChemSage SUBL .dat (three CEF phases sharing Fe-Mg).

  OLIVINE        (Mg,Fe)2 (Si)1 (O)4          forsterite / fayalite
  ORTHOPYROXENE  (Mg,Fe)2 (Si)2 (O)6          enstatite / ferrosilite (per M2Si2O6)
  CLINOPYROXENE  (Ca)1 (Mg,Fe)1 (Si)2 (O)6    diopside / hedenbergite

Every endmember, and every excess, is imported verbatim from the shipped single-phase
databases (data/olivine, data/olivine-opx, data/clinopyroxene): forsterite/fayalite and
enstatite/ferrosilite from Robie-Hemingway with the assessed enstatite high-T interval;
diopside/hedenbergite from Robie-Hemingway with the MLIP-triangulated (Fe,Mg) excess.
Nothing is refit here; the assembly only lets the three phases coexist so their Fe-Mg
exchange (K_D) can be computed. Constituents are name-sorted [Fe, Mg]. See PROVENANCE.md.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Endmember modules and the cpx excess load cleanly by unique path (no bare imports).
_ol_em = _load("oox_ol_em", D / "olivine" / "endmembers.py")
_cpx_em = _load("oox_cpx_em", D / "clinopyroxene" / "endmembers.py")
_cpx = _load("oox_cpx", D / "clinopyroxene" / "build_dat.py")

# Olivine and orthopyroxene excesses, verbatim from the shipped single-phase databases.
# (data/olivine/olivine.py and data/olivine-opx/build_dat.py rely on bare imports, so their
# constants are carried here explicitly; keep in sync with those files.)
CAL = 4.184
OL_L0, OL_L1 = 3000.0 * CAL, 1000.0 * CAL           # Wood & Kleppa 1981 subregular (J/mol)
L_OPX = 2.0 * 950.0 * CAL                           # Chatillon-Colinet 1983, per M2Si2O6
ENSTATITE_T_BREAK = 1360.0                          # ortho -> proto-enstatite transition
ENSTATITE_HT_B = 18.014 * (1830.0 - 1000.0) / (1830.0 - ENSTATITE_T_BREAK)

ELEMENTS = [("CA", 40.078), ("FE", 55.845), ("MG", 24.305), ("SI", 28.085), ("O", 15.9994)]


def _fmt(x):
    return f"{x:.10E}"


def _endmember_lines(name, coeffs, stoich, ht_break=None, ht_dA=0.0, ht_dB=0.0):
    std, sqrt_c = coeffs[:6], coeffs[6]
    eq_type = 4 if sqrt_c != 0.0 else 1
    intervals = ([(6000.0, std)] if ht_break is None else
                 [(ht_break, std),
                  (6000.0, [std[0] + ht_dA, std[1] + ht_dB] + list(std[2:]))])
    lines = [f" {name}",
             f"   {eq_type}   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich)]
    for t_max, cf in intervals:
        lines.append(f"   {t_max:.4f}   " + "   ".join(_fmt(v) for v in cf))
        if eq_type == 4:
            lines.append(f"   1   {_fmt(sqrt_c)}   {_fmt(0.5)}")
    return lines


def _phase_block(name, endmembers, site_ratios, constituents, em_con_idx, excess_L):
    """One SUBL phase; the mixing sublattice may sit at any position (its constituent
    list has two entries). The excess index line lists every constituent's global index;
    the reader finds the sublattice with two listed and pins the rest."""
    L = [f" {name}", " SUBL"]
    for sp, coeffs, stoich, *kw in endmembers:
        L += _endmember_lines(sp, coeffs, stoich, **(kw[0] if kw else {}))
    L.append(f"   {len(site_ratios)}")
    L.append("   " + "   ".join(f"{r:.6f}" for r in site_ratios))
    L.append("   " + "   ".join(str(len(c)) for c in constituents))
    for con in constituents:
        L.append("   " + "   ".join(con))
    for row in em_con_idx:
        L.append("   " + "   ".join(str(i) for i in row))
    n_con = sum(len(c) for c in constituents)
    L.append("   " + "   ".join(str(i) for i in [n_con] + list(range(1, n_con + 1))))
    L.append(f"   {len(excess_L)}")
    for Lv in excess_L:
        L.append("   " + "   ".join(_fmt(v) for v in (Lv, 0, 0, 0, 0, 0)))
    L.append("   0")
    return L


def build(out=None):
    fo = _ol_em.gibbs_coeffs("forsterite")
    fa = _ol_em.gibbs_coeffs("fayalite")
    en2 = [2.0 * c for c in _ol_em.gibbs_coeffs("enstatite")]     # Mg2Si2O6
    fs2 = [2.0 * c for c in _ol_em.gibbs_coeffs("ferrosilite")]   # Fe2Si2O6
    di = _cpx_em.gibbs_coeffs("diopside")
    hd = _cpx_em.gibbs_coeffs("hedenbergite")

    out_lines = [" Ca-Fe-Mg-Si silicate solid solutions (olivine + opx + cpx) - open CEF "
                 "model, provenance data/olivine-opx-cpx/PROVENANCE.md",
                 f"   {len(ELEMENTS)}   3   2   2   2   0",   # n_el, n_soln=3, counts, n_stoich=0
                 "   " + "   ".join(e[0] for e in ELEMENTS),
                 "   " + "   ".join(f"{m:.6f}" for _, m in ELEMENTS),
                 "   6   1   2   3   4   5   6",
                 "   6   1   2   3   4   5   6"]

    # element order CA, FE, MG, SI, O
    out_lines += _phase_block(
        "OLIVINE",
        [("FAYALITE", fa, [0.0, 2.0, 0.0, 1.0, 4.0]),
         ("FORSTERITE", fo, [0.0, 0.0, 2.0, 1.0, 4.0])],
        [2.0, 1.0, 4.0], [["FE", "MG"], ["SI"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [OL_L0, OL_L1])

    out_lines += _phase_block(
        "ORTHOPYROXENE",
        [("FE2SI2O6", fs2, [0.0, 2.0, 0.0, 2.0, 6.0]),
         ("MG2SI2O6", en2, [0.0, 0.0, 2.0, 2.0, 6.0],
          dict(ht_break=ENSTATITE_T_BREAK,
               ht_dA=-ENSTATITE_HT_B * ENSTATITE_T_BREAK, ht_dB=ENSTATITE_HT_B))],
        [2.0, 2.0, 6.0], [["FE", "MG"], ["SI"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [L_OPX])

    out_lines += _phase_block(
        "CLINOPYROXENE",
        [("HEDENBERGITE", hd, [1.0, 1.0, 0.0, 2.0, 6.0]),
         ("DIOPSIDE", di, [1.0, 0.0, 1.0, 2.0, 6.0])],
        [1.0, 1.0, 2.0, 6.0], [["CA"], ["FE", "MG"], ["SI"], ["O"]],
        [[1, 1], [1, 2], [1, 1], [1, 1]],
        [_cpx.L0, _cpx.L1])

    path = out or (HERE / "Olivine-Opx-Cpx-CEF.dat")
    Path(path).write_text("\n".join(out_lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
