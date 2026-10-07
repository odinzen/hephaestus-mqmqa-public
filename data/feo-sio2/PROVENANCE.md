# FeO-SiO2-liquid.dat provenance

Open FeO-SiO2 liquid-slag MQMQA database, **v0.4 (assessed against the phase diagram and the
activities together)**. The Fe-side counterpart of `data/mgo-sio2`, and the second binary the
FeO-MgO-SiO2 ternary slag needs. **Iron-saturated**: all iron is Fe2+ / FeO, no Fe3+ -
matching the iron-crucible conditions of Bowen & Schairer's phase-equilibrium work.

Built by `build_dat.py`, which holds the assessed parameters (`ASSESSED_EXCESS`,
`FEO_LIQ_BETA`), from `assessment/assess.py` against `assessment/dataset.py`. Run:

    python data/feo-sio2/assessment/assess.py [--fit] [--write]

## Pure-oxide endmembers (open)

| Quantity | FeO (iron-saturated wustite) | SiO2 (cristobalite) | Source |
|---|---|---|---|
| Solid G(T) | Fe0.947O + 0.053 Fe, per mole O | beta-cristobalite Cp, effective 298 K constants | Robie & Hemingway 1995 p. 190; SGTE Fe (espei) / R&H 1995 |
| dHf, S298 used (effective) | -266.6125 kJ, 57.126 J/K | -905.5885 kJ, 50.8333 J/K | fitted to the tables, see below |
| Cp a, b, c | 41.672, 1.540e-2, 1.01017e6 | 72.75, 1.300e-3, -4.132e6 | |
| Fusion Tm, dHfus | 1650 K, 24.058 kJ | 1996 K, 9.581 kJ | NIST-JANAF (Chase 1998) |

**FeO.** Until 2026-09-29 this was NIST-JANAF stoichiometric FeO, which is 9-10 kJ more stable
than iron-saturated wustite at 1200-1600 K: at 1200 K it put the iron-wustite oxygen buffer
at -195.0 kJ against -185.9 kJ from R&H wustite (-185.0 kJ measured). The slags are
iron-saturated, so the solid is Fe0.947O plus 0.053 Fe per mole of O (R&H 1995 wustite with
the SGTE GHSERFE iron from `espei.refdata`, its analytic Cp without the small magnetic term).
A Cp of the a, b, c form is fitted to that sum over 400-1600 K and dHf/S298 are its effective
298 K constants (G within 53 J of the sum, 600-1600 K). This removed the conflict v0.3 papered
over with a -69.8 J/K FeO(l) correction.

**SiO2.** R&H give the beta-cristobalite Cp; the repository had paired it with the alpha
298 K values. dHf/S298 are now the effective constants of the beta form (G within 12.6 J of
the R&H cristobalite table, 600-1800 K); the true 298 K values stay as `dHf_ref`/`S298_ref`
for formation-from-oxides conversions.

## v0.4 assessment

The solids are the ones the ternaries use: fayalite from `data/olivine/endmembers.py` (R&H),
wustite and cristobalite as above. The liquid excess and the FeO(l) below-melting slope are
fitted in one weighted least squares to:

- **Liquidus**: Bowen & Schairer 1932 (Am. J. Sci. 24, 177-213) Table 1, twelve
  iron-saturated points, total Fe as FeO (sigma 2 K near fayalite, 5 K elsewhere), each also
  checked for another solid crystallizing first.
- **Two liquids**: their Fig. 4 (p. 200) draws cristobalite + two liquids at 1690 degC
  (1963 K) with liquids at 42.8 and 3.0 wt% FeO (x_SiO2 0.615 and 0.975). They could not
  measure above 1515 degC in iron; the point is Greig's (1927, Am. J. Sci. 14, 479) by a
  short extrapolation, so it carries sigma 10 K and 0.02 in x. The residual is the model's
  own three-phase temperature (cristobalite on the two-liquid tangent), not a liquidus read
  at the measured composition, which inside the model's gap would be metastable.
- **a(FeO)**: the 23 Bjorkman 1985 points (below). Those below 1644 K are referred to the
  supercooled iron-saturated melt, so they are fitted up to one offset in ln a (0.24).

Excess (Q terms on (Fe,Si,O,O), chi_Fe^p chi_Si^q): [0,0] -58713.8 + 40.268 T, [1,0]
-28132.9, [0,3] -24367.9, [0,5] +102533.0 J/mol; FeO(l) below 1650 K: -28.34 (T - 1650)
J/mol. No [0,1]: in a binary it equals [0,0] minus [1,0] exactly. The [0,5] term is what
lets the two-liquid field reach its measured temperature (the four-term form put it at
1883 K); adding a [0,7] improved the cost from 35.7 to 31.2 only with alternating
coefficients up to 178 kJ, so it was not kept.

| Target | Model | Measured |
|---|---|---|
| wustite-fayalite eutectic | 1456 K, x 0.255 | 1450 K |
| fayalite congruent | 1475 K | 1478 K |
| fayalite-silica eutectic | 1460 K, x 0.417 | 1451 K |
| monotectic (silica + two liquids) | 1937 K, liquids 0.536 / 0.958 | 1963 K, 0.615 / 0.975 |
| a(FeO) | RMS 0.57 sigma (0.03 in ln a) | |

Weighted RMS residual 1.14 over 50 residuals.

### Limits

- The iron-rich limb of the two liquids sits 0.07 in x on the FeO side of Greig's
  extrapolated value in every form tried; the silica-rich limb and the temperature are close.
- The two tridymite points at 1533 and 1638 K, 0.013 apart in x, pull in opposite
  directions (+2 and -5 sigma); the model has one silica phase, cristobalite.
- The sub-1644 K activity offset and the FeO(l) slope are nuisance-like: both concern the
  supercooled FeO liquid, which no measurement sees directly.
- The excess entropy is large (+40.3 J/K on the [0,0] term): the total entropy of mixing at
  the fayalite composition comes out -4.0 J/K per mole of oxide at 1800 K. A strongly
  ordered melt can have that, but no measurement here constrains it; it is what reconciles
  the 2153 K activities with the lower-temperature data and the diagram. Flagged, not
  tested against.

## History: v0.3 (activity-pinned excess + FeO(l) recalibration)


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

### Limits of v0.3 (addressed by v0.4)

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
