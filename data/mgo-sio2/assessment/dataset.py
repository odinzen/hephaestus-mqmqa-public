"""MgO-SiO2 experimental dataset for the CALPHAD assessment of the liquid.

Every datum is a measured (or evaluated) experimental point with a value, the phase
composition where relevant, a weight (roughly 1/uncertainty^2 in the residual's own
units), and its source. This is the open equivalent of a curated assessment dataset -
the assessment optimizer (assess.py) fits the liquid excess parameters to reproduce ALL
of these simultaneously, weighted, instead of point-fitting a few landmarks.

Compositions are mole fraction SiO2 unless noted. Temperatures in K. Sources are the
open literature (DOIs / refs in data/mgo-sio2/PROVENANCE.md and the project memory).

Weights: expressed so that (residual / sigma) is dimensionless and O(1) for a typical
point. T sigma in K, composition sigma in mole fraction, enthalpy sigma in kJ/mol-oxide.
"""

# --- Invariant temperatures (and compositions where measured) ---
# type: congruent | eutectic | peritectic. x = liquid composition (mole fraction SiO2).
INVARIANTS = [
    dict(name="periclase-forsterite eutectic", type="eutectic", T=2123.0, sigT=20.0,
         x=0.265, sigx=0.02, solids=("MgO(periclase)", "M2S(forsterite)"),
         src="Bowen & Andersen 1914 (MgO 65 wt%)"),
    dict(name="forsterite congruent", type="congruent", T=2163.0, sigT=20.0,
         x=1.0/3.0, sigx=0.005, solids=("M2S(forsterite)",),
         src="Bowen & Andersen 1914 (MgO 57.2 wt%)"),
    dict(name="enstatite peritectic", type="peritectic", T=1830.0, sigT=15.0,
         x=0.512, sigx=0.01, solids=("MS(enstatite)",),
         src="Bowen & Andersen 1914 Table I(b, c): 1557 C, liquid MgSiO3 97.5 + SiO2 2.5 wt%"),
    dict(name="enstatite-cristobalite eutectic", type="eutectic", T=1816.0, sigT=15.0,
         x=0.553, sigx=0.01, solids=("MS(enstatite)", "SiO2(cristobalite)"),
         src="Bowen & Andersen 1914 Table I(d): 1543 C, MgSiO3 87.5 + SiO2 12.5 wt%"),
]

# --- Liquidus: quench brackets (midpoint), x mole fraction SiO2, T in K, primary solid ---
# Between the invariants, where the invariants alone leave the curves free: without these
# the fit put forsterite on an incongruent melt and the enstatite-cristobalite eutectic at
# x = 0.59 (2026-09-30). Bowen & Andersen 1914, Am. J. Sci. (4) 37, 487; Greig 1927, Am. J.
# Sci. (5) 13, 1 (Table IV A). 1914 degC read as printed (within a few K of ITS-90 here).
LIQUIDUS = [
    dict(x=0.4809, T=1903.0, sig=20.0, phase="M2S(forsterite)",
         src="B&A Table I(a): MgO 42 SiO2 58 wt%, glass + minute forsterite at 1625 C"),
    dict(x=0.5000, T=1850.15, sig=10.0, phase="M2S(forsterite)",
         src="B&A Table I(a): MgSiO3, forsterite 1576 C, glass only 1578 C"),
    dict(x=0.5141, T=1829.15, sig=10.0, phase="MS(enstatite)",
         src="B&A Table I(e): MgO 38.8 SiO2 61.2 wt%, 1555 / 1557 C"),
    dict(x=0.5439, T=1825.15, sig=10.0, phase="MS(enstatite)",
         src="B&A Table I(e): MgO 36 SiO2 64 wt%, 1550 / 1554 C"),
    dict(x=0.5877, T=1933.65, sig=10.0, phase="SiO2(cristobalite)",
         src="Greig 1927 Table IV A: MgO 32 SiO2 68 wt%, cristobalite 1654 C, glass 1667 C"),
]

# --- Liquid-liquid immiscibility: conjugate compositions vs temperature ---
# Each row is one measured tie-line (monotectic or above); x_lo = MgO-rich limb,
# x_hi = silica-rich limb. The consolute (L1=L2) rows have x_lo=x_hi=x_c.
# Firm measured monotectic conjugates from several studies (the real data scatter on
# the MgO-rich limb, 0.60-0.66, is captured by keeping each study as its own point).
BINODAL = [
    dict(T=1968.0, x_lo=0.599, x_hi=0.988, sig=0.02, src="Greig 1927 (mol%)"),
    dict(T=1968.0, x_lo=0.610, x_hi=0.990, sig=0.03, src="Ol'shanskii 1951"),
    dict(T=1987.0, x_lo=0.590, x_hi=0.978, sig=0.02, src="Hageman & Oonk 1986 (1714 C)"),
    dict(T=1983.0, x_lo=0.660, x_hi=0.961, sig=0.03, src="Warshaw (1710 C)"),
    dict(T=1948.0, x_lo=0.626, x_hi=0.961, sig=0.03, src="Toropov & Bondar (1675 C)"),
]
CONSOLUTE = [
    dict(T=2240.0, x_c=0.84, sigT=40.0, sigx=0.05,
         src="Hageman & Oonk 1986 (1967 C, rapid quench)"),
]

# --- Liquid enthalpy of mixing (kJ per mole of oxide formula unit), solid... no,
# liquid-oxide reference; from the bias-corrected foundation-MLIP MD cross-checked to
# the Charlu-Newton-Kleppa compound calorimetry (see PROVENANCE v0.2). Moderate weight -
# it is an independent computational constraint, not direct melt calorimetry. Two assumptions
# stand behind it: that the solid formation bias carries over to a liquid-liquid mixing
# enthalpy, and the temperature. The MD ran at 3200 K and the targets are scored at 2100 K
# (assess.py); on the shipped liquid dH_mix is 2.3 kJ (x 1/3) and 0.9 kJ (x 1/2) shallower at
# 3200 K than at 2100 K, inside the 4 kJ sigma. ---
DH_MIX = [
    dict(x=1.0/3.0, value=-24.5, sig=4.0, src="MatterSim MLIP, bias-corrected"),
    dict(x=0.5, value=-22.4, sig=4.0, src="MatterSim MLIP, bias-corrected"),
]

# --- Enthalpy of fusion of the congruently melting compound (kJ per mole of formula) ---
# Without it the fit chooses the liquid's enthalpy-entropy split freely: fit M2 (2026-10-05) melted
# forsterite with 99.8 kJ, and forsterite came out ~4 kJ too unstable near 2100 K, setting both the
# forsterite melting point and the periclase-forsterite eutectic low. Scored at the measured melting
# point. Navrotsky et al. 1989 (doi:10.1007/BF00387206) give 114 +- 20 kJ at 2163 K, extrapolated from
# 89 +- 12 at 1773 K, not used here. Enstatite melts incongruently; the 73-75 kJ in circulation trace to
# a review and to a JANAF phase-diagram estimate, so no enstatite value is used (checked 2026-10-05).
FUSION = [
    dict(solid="M2S(forsterite)", T=2174.0, dH=142.0, sig=14.0,
         src="Richet, Leclerc & Benoist 1993, Geophys. Res. Lett. 20, 1675, doi:10.1029/93GL01836 "
             "(quantitative DTA, 142 +- 14 kJ/mol at 2174 K, per Mg2SiO4)"),
]

# --- Consolute / dome-height note ---
# The consolute is the single most important immiscibility constraint (dome height);
# T_c = 2240 K is experimental (Hageman & Oonk), corroborated by the Belmonte 2017
# assessment. The monotectic (1968 K) is the firm bottom of the two-liquid field.
