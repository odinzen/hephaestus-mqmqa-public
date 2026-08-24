# FeO-SiO2-liquid.dat provenance

Open FeO-SiO2 liquid-slag MQMQA database, **v0.3 (activity-pinned excess + FeO(l)
recalibration)**. The Fe-side counterpart of `data/mgo-sio2`, and the second binary the
FeO-MgO-SiO2 ternary slag needs (for the olivine + orthopyroxene + liquid diagram).
**Iron-saturated**: all iron is Fe2+ / FeO, no Fe3+ - matching the iron-crucible conditions
of Bowen & Schairer's phase-equilibrium work, and avoiding redox for now.

Built by `build_dat.py` (endmembers) and `v03_fit.py` (excess + calibration); validated by
`validate.py` (endmembers) and `validate_v03.py` (interior mixing). Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/feo-sio2/validate_v03.py

## Pure-oxide liquid endmembers (open)

| Quantity | FeO | SiO2 | Source | Access |
|---|---|---|---|---|
| dHf(298) from elements | -272.044 kJ/mol | -908.4 kJ/mol (cristobalite) | NIST-JANAF (Chase 1998) / R&H 1995 | open |
| S(298), third law | 60.752 J/mol/K | 43.4 J/mol/K | NIST-JANAF / R&H 1995 | open |
| Cp(T) solid, Haas-Fisher a,b,c | 50.663, 8.711e-3, -3.134e5 | 72.75, 1.300e-3, -4.132e6 | fit to JANAF FeO(cr) 298-1500 K (max resid 0.35) / R&H | open |
| Fusion Tm | 1650 K | 1996 K | NIST-JANAF | open |
| Fusion dHfus | 24.058 kJ/mol | 9.581 kJ/mol | NIST-JANAF | open |

The FeO numbers are the NIST-JANAF (Chase 1998) critically-evaluated values for stoichiometric
FeO, already digitized in the assessment workspace
(`assessments/FeO-SiO2/data_tables/paper_nist_janaf__table_JANAF_web_table_Fe-020.csv`); the
Haas-Fisher Cp is a least-squares fit to the six tabulated FeO(crystal) Cp points (298-1500 K).
SiO2 is identical to `data/mgo-sio2` (Robie-Hemingway solid, JANAF fusion). Both endmember Gibbs
energies read back by the engine match a direct H - T*S evaluation to ~1e-7 J/mol, and both
reproduce their fusion temperatures exactly (dG_fus = 0 at Tm).

## v0.3 excess (pinned on measured iron-saturated activities)

v0.2 fixed the excess depth by scaling the MgO-SiO2 liquid (no FeO-SiO2 activity data were
digitized then) and reproduced fayalite melting with an **unphysical** `b00 = +78.62 J/mol/K`
that cancelled a too-stable ideal-liquid baseline (its net excess was actually *positive* near
1580 K, giving too-high activities). v0.3 replaces both with measured data, in two decoupled
steps (`v03_fit.py`).

### Step 1 - excess from the measured a(FeO) curve

`activities_feo_bjorkman1985_fig3.csv` holds 23 measured a(FeO) points digitized from the
**symbols** of Björkman 1985 Fig 3 (Calphad 9:271, DOI 10.1016/0364-5916(85)90012-4), which
replots three primary iron-saturated measurements (stoichiometric FeO(l) standard state,
a(FeO) vs bulk X(FeO), melt in equilibrium with metallic iron):

- **Bodsworth 1959** (J. Iron Steel Inst. 193:13), 1578 K, H2/H2O method (16 pts pooled with S&E)
- **Schuhmann & Ensio 1951** (JOM 3:401, DOI 10.1007/BF03397323), 1590 K, CO/CO2 method
- **Distin et al. 1971**, 2153 K (Björkman ref 26) - a second temperature for the entropy lever

The model curves in the figure were NOT digitized (measured points only). A symmetric
cation-mixing excess `Delta_g(Fe,Si)/O = a00 + b00*T` is fitted to `ln a(FeO)` at every point.
The two temperatures (~1580 K and 2153 K, a 573 K lever) separate the enthalpy `a00` from the
excess entropy `b00`. A chi_Fe skew (a10) was tried and rejected (the optimizer drives it to
~4 J/mol; it does not reduce the residual).

Result: **`a00 = -42839.4, b00 = +17.83 J/mol/K`** (a10 = 0). This is a genuinely **deep**
liquid: `dG_mix(1/3, 1580 K) = -12.2 kJ/mol-oxide` and `dH_mix(1/3) = -12.5` (v0.2's net was
~-3), single-welled `delta_g_mix` (no spurious gap), and the physical `b00` retires the +78.6.
Fit quality: RMS `ln a = 0.067` overall (0.027 for the 2153 K set, 0.079 for the ~1580 K set).

### Step 2 - FeO(l) below-melting calibration from the fayalite liquidus

The activity-matched liquid is **~7 kJ/mol-oxide too stable** to melt fayalite at its measured
1478 K (Bowen & Schairer 1932) if the FeO liquid endmember is the JANAF-fusion form
extrapolated below its own 1650 K melting point. Björkman's assessment fixes dfG(FeO,l) below
~1644 K from the iron-silicate liquidus rather than from that fusion extrapolation; we do the
same. `build_dat.feo_liq_beta` adds a below-1650 K correction `dG = beta*(T - 1650)` to the
FeO liquid endmember (a second temperature interval), continuous at 1650 K and identically zero
at and above it. `beta` is fit to fayalite congruent melting = 1478 K **after** the excess is
fixed, because the correction is **exactly orthogonal to the activities** - it shifts the pure
FeO reference and the FeO chemical potential by the same amount, so a(FeO) and a(SiO2) are
unchanged (verified to machine precision; regression-tested). The **measured fayalite solid
dHf_ox stays at -25.7 kJ** (from the crystalline oxides, R&H 1995); the recalibrated block is
the uncertain supercooled FeO liquid, not the calorimetric solid.

Result: **`beta = -69.84 J/mol/K`** (FeO(l) destabilized by +12.0 kJ/mol at 1478 K). Fayalite
melts congruently at exactly 1478 K.

### Honest limits (v0.4 targets)

- **High-X_FeO systematic.** The measured a(FeO) coefficient turns slightly *positive*
  (a(FeO) > X_FeO by ~5%) for X_FeO > 0.8, while it is strongly negative on the silica-rich
  side - an S-shape a symmetric excess cannot make. The model under-predicts a(FeO) there by
  ~0.1 in ln a; those points sit in the crowded upper-right of Fig 3, near the digitization
  limit. The dominant silica-rich depth (the point of v0.3) is well reproduced. A higher-order
  asymmetric term (and/or the known FeO-rich behaviour) is a v0.4 refinement; it was not added
  here to avoid overfitting scattered digitized points.
- **beta is a sizeable supercooled-liquid calibration** (+12 kJ/mol at 172 K undercooling).
  It is the standard, published route (Björkman) and is contained to this binary, but a full
  Fe-O liquid assessment giving FeO(l) below 1650 K from first principles would replace it.
- **No measured a(SiO2).** Fig 3 (and the other trove papers) give only a(FeO); a(SiO2) in the
  assessments is Gibbs-Duhem-integrated model output, which is not ingested. The model's a(SiO2)
  is therefore a prediction, not a fit target.
- The MLIP melt-mixing MD story of v0.2 is superseded: the depth now comes from measured
  activities, not from the dHf_ox scaling / MLIP bias-check.

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. Björkman 1985 supplies **measured data points**
(digitized from its replot of the primary sources) and its **method** (below-melting FeO(l)
calibration from the liquidus) - both published and open; its fitted model parameters/curves are
never used. The Shishin/Jak FeO-Fe2O3-SiO2 assessments remain validation targets only. The FeO
endmember above 1650 K is a JANAF single-substance evaluated value (allowed as an input).
