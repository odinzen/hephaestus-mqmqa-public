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
         x=0.55, sigx=0.04, solids=("MS(enstatite)",),
         src="evaluated (Bowen & Andersen 1914; Greig 1927)"),
    dict(name="enstatite-cristobalite eutectic", type="eutectic", T=1816.0, sigT=15.0,
         x=0.545, sigx=0.03, solids=("MS(enstatite)", "SiO2(cristobalite)"),
         src="evaluated (~64 wt% SiO2)"),
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
# it is an independent computational constraint, not direct melt calorimetry. ---
DH_MIX = [
    dict(x=1.0/3.0, value=-24.5, sig=4.0, src="MatterSim MLIP, bias-corrected"),
    dict(x=0.5, value=-22.4, sig=4.0, src="MatterSim MLIP, bias-corrected"),
]

# --- Consolute / dome-height note ---
# The consolute is the single most important immiscibility constraint (dome height);
# T_c = 2240 K is experimental (Hageman & Oonk), corroborated by the Belmonte 2017
# assessment. The monotectic (1968 K) is the firm bottom of the two-liquid field.
