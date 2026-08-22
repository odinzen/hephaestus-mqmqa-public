# MgO-SiO2-liquid.dat provenance

Open MgO-SiO2 liquid-slag MQMQA database, now at **v0.2** (central negative-deviation
liquid). Built by `build_dat.py`; endmembers validated by `validate.py`, the fitted
excess by `validate_v02.py`, invariants classified by `phase_hull.py`; fit reproduced by
`v02_fit.py`. Second system in the open slag family (after CaO-SiO2); chosen because it
exercises the two phenomena CaO-SiO2 could not yet capture - a liquid-liquid
**miscibility gap** and an **incongruent (peritectic) melting**. v0.2 fits the central
liquid (forsterite congruent melting, enstatite peritectic) and correctly classifies the
enstatite peritectic; the silica-rich gap is the deferred v0.4 model-form step.

## Primary sources (all open)

- **CODATA Key Values** (Cox, Wagman, Medvedev 1989): MgO dHf(298) = -601.5 kJ/mol,
  S(298) = 26.95 J/mol/K.
- **NIST-JANAF** (Chase 1998): MgO periclase Cp tabulation (298-2000 K) - the
  Haas-Fisher coefficients below are a least-squares fit to it (max residual 0.32
  J/mol/K). MgO melting Tm = 3098 K (2825 degC), dHfus ~ 77 kJ/mol. SiO2 fusion.
- **Robie & Hemingway 1995** (USGS Bull. 2131, public domain): SiO2 (cristobalite)
  endmember, cross-check on MgO S298/Cp.
- Phase-equilibrium + calorimetry data for the excess fit (v0.2 uses Bowen-Andersen and
  Charlu-Newton-Kleppa; Greig is deferred to v0.4):
  **Greig 1927** (Am. J. Sci.) - the silica-rich liquid-liquid immiscibility dome:
  monotectic at 1968 K with conjugate liquids at ~68 and ~99 wt% SiO2. **Bowen &
  Andersen 1914** - forsterite congruent melting 2163 K, periclase-forsterite eutectic
  2123 K. Enstatite (MgSiO3) melts incongruently. Compound formation enthalpies:
  Charlu-Newton-Kleppa 1975 (Mg2SiO4 -60.25, MgSiO3 -36.86 kJ/mol from oxides).

## v0.1 endmembers (per formula unit)

| Symbol | MgO | SiO2 | Source |
|---|---|---|---|
| dHf(298) | -601500 J/mol | -908400 J/mol | CODATA / R&H (cristobalite) |
| S(298) | 26.95 J/mol/K | 43.4 J/mol/K | CODATA / R&H |
| Cp a,b,c (a+bT+cT^-2) | 48.2425, 3.906e-3, -1.1082e6 | 72.75, 1.300e-3, -4.132e6 | MgO: fit to JANAF Cp; SiO2: R&H |
| Tm | 3098 K | 1996 K | NIST-JANAF |
| dHfus | 77000 J/mol | 9581 J/mol | NIST-JANAF |

MgO Cp coefficients are a Haas-Fisher fit to the open JANAF periclase Cp points
(reproduces Cp(298)=37.1 and Cp(2000)=55.7 within 0.3 J/mol/K). SiO2 uses the same
cristobalite endmember as CaO-SiO2 (consistency across the slag family).

## Model-structure choices (v0.1, no fitted physics)

- Cations Mg+2, Si+4; anion O-2. Pairs MgO, SiO2.
- Charge-proportional coordination Z = 0.68872*charge (framework default, not fitted),
  same convention as CaO-SiO2.
- **Excess: none in v0.1 (ideal).** The interior mixing is fit in v0.2 (below).

## v0.2 excess (phase-diagram + MLIP-triangulated central liquid)

v0.2 adds the liquid-mixing (ordering) energy that v0.1 left ideal, on the MgO-rich /
central side. MgO-SiO2 has no measured liquid activities, so - unlike CaO-SiO2, where
activities competed with the phase diagram - the phase diagram is the primary constraint
here, with an independent MLIP as a genuine second constraint on the liquid depth. The
silica-rich liquid-liquid gap is NOT modelled (it needs SiO2-specific coordination Z, the
v0.4 model-form step documented below).

### Solid Gibbs functions (for the melting/eutectic/peritectic anchors)

The invariants are computed against solid Gibbs energies built by Neumann-Kopp on our own
MgO and SiO2(cristobalite) solid endmembers plus each compound's measured enthalpy and
entropy of formation from the oxides (so every solid sits on exactly the engine's
endmember scale). Built in `phase_diagram.py`:

    G_compound(T) = n_MgO*G_MgO_solid(T) + n_SiO2*G_SiO2_solid(T) + dHf_ox - T*dSf_ox
    dSf_ox = S298_compound - n_MgO*S298_MgO - n_SiO2*S298_SiO2

| compound | x_SiO2 | dHf_ox (kJ/mol, vs qz) | S298 (J/mol/K) | source |
|---|---|---|---|---|
| forsterite Mg2SiO4 | 0.333 | -60.25 | 94.11 | Charlu-Newton-Kleppa 1975 / Robie 1982 |
| enstatite MgSiO3 | 0.500 | -36.86 | 66.27 | Charlu-Newton-Kleppa 1975 / R&H 1995 (orthoenstatite) |

dHf_ox is on the alpha-quartz reference (as reported); the small quartz->cristobalite
shift (+2.3 kJ/mol-SiO2, R&H 1995) converts it to our cristobalite endmember. Neumann-Kopp
(dCp_ox = 0) is the standard silicate approximation; solid-solid polymorph transitions are
not resolved (a documented refinement). Charlu, Newton & Kleppa 1975, Geochim. Cosmochim.
Acta 39, 1487 (high-T oxide-melt solution calorimetry) - open measured data.

### Model and fitted values

Two Q-code cation-mixing terms on the (Mg+2, Si+4 / O, O) quadruplet (linear indices
(1,2,3,3)), giving the composition-dependent ordering energy

    Delta_g(Mg,Si)/O = (-75900.6 - 3.5875*T) + 30163.1 * chi_Mg      J/mol

where chi_Mg is the coordination-equivalent fraction of Mg among the two mixing cations.
As MQMX entries (term basis 1,T,TlnT,T^2,T^3,1/T):

| term | code | (p,q) | coefficients (a + b*T), J/mol |
|---|---|---|---|
| g00 | Q | (0,0) | -75900.6 - 3.5875*T |
| g10 | Q | (1,0) | +30163.1 |

The g00 entropy term (b*T) is what separates enthalpy from entropy: it lets one excess fit
both the ~2100-2200 K melting and the MLIP mixing enthalpy. Two terms are the minimum that
carries the depth and the (mild) composition dependence; no third term is used (it would
only fit MD scatter and risk a spurious spinodal). Reproduce with `v02_fit.py` (fit + write).

### Method: three anchors, cleanly separating enthalpy and entropy

The engine is its own optimizer (as in CaO-SiO2): for trial coefficients it computes the
liquid Gibbs, the compound melting, and dH_mix, and `v02_fit.py` least-squares matches:

1. **forsterite Mg2SiO4 congruent melting = 2163 K** (Bowen & Andersen 1914) - fixes the
   excess entropy (the T-slope of G_liq - G_solid). Solved as G_liq(x=1/3,T) = G_solid.
2. **bias-corrected MLIP dH_mix(x=1/3) = -24.5 kJ/mol-oxide** - the enthalpy at the
   forsterite composition.
3. **bias-corrected MLIP dH_mix(x=1/2) = -22.4 kJ/mol-oxide** - the composition dependence.

**MLIP triangulation (`_mlip/`, mlip-screen env).** Melt-quench-sample MD at 3200 K (both
oxides molten) with MatterSim gives the RAW liquid enthalpy of mixing dH_mix(x=1/3) = -21.8
+- 0.8 and dH_mix(x=1/2) = -16.2 +- 0.9 kJ/mol-oxide. The MLIP is first VALIDATED and its
bias measured by a formation-enthalpy spot-check of the solid compounds vs the measured
calorimetry (mlip_hf.py): MatterSim under-binds forsterite by +8.0 kJ/mol-formula (+2.7 per
oxide unit) and enstatite by +12.3 (+6.2 per oxide unit). Applying that same under-binding
to the liquid deepens the raw MD to the bias-corrected -24.5 and -22.4 above. These
independently CONFIRM the depth the phase diagram requires: the forsterite melting alone (a
T-const excess) implies dH_mix(x=1/3) = -27.6, dH_mix(x=1/2) = -23.2 kJ/mol-oxide - the same
shallow depth, within ~3 kJ. This is a much shallower liquid than CaO-SiO2 (-58 at x=0.5),
as expected: the Mg-silicates are less strongly bound than the Ca-silicates (Mg2SiO4
dHf_ox -60 vs Ca2SiO4 -126 kJ/mol; Mg is a weaker network modifier).

### Results (reproduce with v02_fit.py / validate_v02.py / phase_hull.py)

- **Fit anchors hit exactly** (residual norm 0.000): forsterite congruent melting 2163 K;
  dH_mix(x=1/3) = -24.5, dH_mix(x=1/2) = -22.3 kJ/mol-oxide (= the MLIP targets).
- delta-G_mix(2100 K) minimum -35.1 kJ/mol-oxide at x_SiO2 = 0.40.
- **Enstatite classifies INCONGRUENT/peritectic (-> liquid + forsterite)** - the measured
  behaviour, and the requested v0.2 result. Computed peritectic ~1698 K vs measured ~1830 K
  (solid-model limited; the peritectic liquid is silica-ward, near the deferred gap).
- Stable across the whole join: d2 Gmix/dx2 > 0 everywhere, no spurious spinodal (the
  positive chi_Mg skew does not open a gap).
- Ideal MQMQA with charge-proportional Z gives a(i) = x(i), so the excess is wholly
  responsible for the deviation (same as CaO-SiO2).

### Honest limitations (what v0.2 is NOT)

- **Not a quantitative phase diagram; a validated central LIQUID.** Forsterite congruent
  melting is reproduced (it is the fit anchor), and the independent MLIP confirms the depth,
  but the other invariant TEMPERATURES are solid-model-limited:
  - The **periclase-forsterite eutectic** comes out near-coincident with forsterite melting
    (~2160-2180 K at x_SiO2 ~ 0.33) instead of 40 K below at x ~ 0.265 (measured 2123 K). The
    MgO endmember is too refractory (Tm 3098 K) under Neumann-Kopp for the shallow eutectic
    valley to resolve. The hull classifier consequently marks forsterite as marginally
    coexisting with periclase, though its direct congruent melting is 2163 K.
  - The **enstatite-silica eutectic** (1574 vs measured 1816 K) is off - it is silica-rich,
    in the deferred-gap region.
- **Silica-rich miscibility gap not modelled** (Greig 1927). It is a positive deviation the
  charge-proportional-Z cation-mixing excess structurally cannot place at the silica corner -
  the v0.4 model-form step (SiO2-specific coordination Z), documented below.

## Statement on sources

Built only from open/public-domain data: endmembers from CODATA, NIST-JANAF, Robie-Hemingway
1995; the v0.2 solid compounds from the measured calorimetry of Charlu, Newton & Kleppa 1975
(dHf_ox) and Robie 1982 / R&H 1995 (S298); the phase-diagram anchors from Bowen & Andersen
1914; and our own MD with the open MatterSim foundation MLIP (weights open) plus its
formation-enthalpy validation against the same open calorimetry. No FactSage/FToxid or other
external-TDB optimized parameters, and no assessment-workspace fitted parameters - the excess
coefficients are our own least-squares result against the melting anchor and the MLIP. Crystal
structures for the MLIP checks are open COD entries (9006398 forsterite, 1000047 enstatite,
9009666 quartz).

## Miscibility-gap finding (v0.x / v0.4 model-form, 2026-08-22)

Attempting the excess fit surfaced the model-form limit head-on. The target is Greig's
silica-rich liquid-liquid gap: at 1968 K two conjugate liquids at x_SiO2 ~ 0.59 and ~0.99
(monotectic with cristobalite).

Tested against the engine:
- **The engine CAN produce a miscibility gap.** A positive Q-code excess raises the mixed
  quadruplet energy and yields a spinodal (d2 Gmix/dx2 < 0). So gaps are representable -
  earlier "cation-mixing can only deviate negative" was too strong; the sign of L sets it.
- **But charge-proportional Z misplaces it.** A symmetric positive term puts the gap
  MgO-rich (x_SiO2 ~ 0.10-0.35). Si-weighted positive terms ((0,q), q up to 3) move it
  silica-ward but saturate at ~0.33-0.70 - they cannot reach the measured 0.59-0.99.
- **The lever is the coordination Z, not the excess.** The gap can't be placed at the
  silica corner while Z stays charge-proportional (Z = 0.68872*charge). Real silicate MQM
  databases (FactSage FToxid) use SiO2-specific, non-charge-proportional coordination to
  capture the silica network and put the gap where it belongs. Adopting SiO2-specific Z is
  a model-structure change (it re-defines the pure-SiO2 endmember reference), so it is the
  v0.4 step, done carefully, not a parameter tweak.

Consequence for the plan: the CENTRAL, negative-deviation part (forsterite congruent melting
2163 K, periclase-forsterite eutectic 2123 K, enstatite incongruent) is fittable now with a
cation-mixing excess + the hull classifier, as in CaO-SiO2 - that is the achievable v0.2.
The silica-rich gap is deferred to v0.4 (SiO2-specific coordination), and the hull classifier
+ MLIP triangulation carry over unchanged.
