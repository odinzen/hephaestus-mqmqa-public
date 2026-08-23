# MgO-SiO2-liquid.dat provenance

Open MgO-SiO2 liquid-slag MQMQA database, now at **v0.4** (central liquid + silica-rich
miscibility gap). Built by `build_dat.py`; endmembers validated by `validate.py`, the v0.2
central excess by `validate_v02.py`, invariants classified by `phase_hull.py`; fits
reproduced by `v02_fit.py` (central) and `v04_fit.py` (+ silica gap), the gap-lever mapped
in `v04_explore.py`. Second system in the open slag family (after CaO-SiO2); chosen because
it exercises the two phenomena CaO-SiO2 could not yet capture - a liquid-liquid
**miscibility gap** and an **incongruent (peritectic) melting**. v0.2 fit the central
liquid (forsterite congruent melting, enstatite peritectic); v0.4 adds the silica-rich gap
(Greig conjugate liquids 0.59/0.99) via a silica-weighted excess - NOT via SiO2-specific
coordination, which direct experiments showed is a gauge no-op here (see the v0.4 section).

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
  the v0.4 model-form step, documented below. (v0.4 now DOES model it - see the v0.4 section.)

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

## v0.4 excess (silica-rich miscibility gap)

v0.4 adds the model-form term that places Greig's silica-rich liquid-liquid gap (1968 K
monotectic, conjugate liquids x_SiO2 ~ 0.59 and ~0.99). Reproduce with `v04_fit.py`; the
lever was mapped in `v04_explore.py`.

### What the lever actually is (correcting the earlier coordination hypothesis)

An earlier note here proposed that SiO2-specific, non-charge-proportional COORDINATION Z
places the gap (as FactSage FToxid is said to do). Direct engine experiments
(`v04_explore.py`) REFUTE that for this single-anion (Mg,Si / O) binary:

- **Coordination Z (and pair zeta) is a GAUGE no-op for the ideal mixing.** With one
  anion, the pure-quadruplet stoichiometry locks Z_Si = 2*Z_O, and scaling the SiO2 quad's
  (Z_Si, Z_O, zeta) together leaves the endmember AND the ideal delta_g_mix exactly
  invariant (identical to machine precision across factors 1-6). zeta alone is likewise a
  no-op. So coordination creates no asymmetry by itself here.
- **Coordination only moves an EXCESS-driven gap toward MgO, never toward silica.** With a
  fixed positive excess, scaling Z_Si up opens an MgO-rich spinodal (x ~ 0.05-0.40);
  scaling it down suppresses the gap entirely. It cannot point the gap at the silica corner.
- **The real lever is a SILICA-WEIGHTED EXCESS.** A single Q-code term on (Mg,Si,O,O) with
  the chi_Si exponent, (0,q), L > 0, opens a spinodal whose silica edge marches outward with
  q: (0,3) -> 0.81, (0,5) -> 0.89, (0,6) -> 0.92 (at fixed L). Because chi_Si^q ~ 0 for
  x_SiO2 < ~0.55, the term is nearly orthogonal to the central v0.2 excess - it opens the
  gap without disturbing the forsterite/enstatite region. The excess (its sign and chi
  weighting), not the coordination, sets where the gap sits. This applies to the whole
  silica-gap family (the CaO-SiO2 silica gap too).

### Model and fitted values

v0.4 = v0.2 (central) + one silica-weighted term, with the symmetric g00 enthalpy
re-tuned to hold forsterite melting (the silica term slightly destabilises the liquid at
x=1/3). g10 (chi_Mg skew) and the g00 entropy slope carry over from v0.2 unchanged:

| term | code | (p,q) | coefficients, J/mol |
|---|---|---|---|
| g00 | Q | (0,0) | -79055.6 - 3.5875*T |
| g10 | Q | (1,0) | +30163.1 |
| g_si | Q | (0,5) | +100958.1 |

Two anchors fix the two re-fit coefficients (they solve almost separably): forsterite
congruent melting = 2163 K fixes g00's enthalpy; the MgO-side conjugate liquid = 0.59 at
1968 K fixes L_si. The chi_Si exponent q = 5 is the fitted network order (q = 4 gives too
narrow a gap, q = 6 slightly too silica-ward); it is our own choice on the open Greig data,
not a FactSage parameter.

### Results (reproduce with v04_fit.py / phase_hull.py)

- **A silica-rich two-liquid miscibility gap forms** - the v0.4 feature. The *isolated*-liquid
  binodal (delta_g_mix hull, no solids) at 1968 K is 0.588-0.982, matching Greig's conjugate
  liquids 0.59/0.99 - that is what the fit anchored. In the FULL diagram cristobalite preempts
  the silica-rich liquid, so the actual model monotectic (gap meeting the cristobalite
  liquidus) sits at ~2365 K, conjugates ~0.64/0.96, dome closing at a consolute ~3115 K - too
  hot (see Honest limitations). So the gap is at roughly the right COMPOSITION but the wrong
  TEMPERATURE.
- The only liquid instability is this silica gap; no spurious MgO-rich gap.
- **forsterite Mg2SiO4 CONGRUENT melting = 2159-2163 K** (target 2163); the silica term even
  resolves the v0.2 hull near-coincidence, so forsterite now classifies cleanly congruent.
- **enstatite MgSiO3 INCONGRUENT / peritectic (-> liquid + forsterite)** at ~1946 K (measured
  ~1830; the type is right, the T solid-model-limited).
- Central liquid depth preserved: dH_mix(x=1/3) = -24.5 kJ/mol-oxide (= the v0.2 MLIP
  anchor); dH_mix(x=1/2) = -18.7 (the silica term makes the enstatite side ~4 kJ shallower).

### Honest limitations

- **The gap runs too HOT.** Only the *isolated-liquid* binodal compositions (0.59/0.99) were
  anchored, at 1968 K. In the full diagram cristobalite preempts the silica-rich liquid, so
  the actual model monotectic (gap meeting the cristobalite liquidus) is at ~2365 K with
  conjugates ~0.64/0.96, and the two-liquid dome closes at a consolute ~3115 K - both far
  above the measured monotectic (Greig, 1968 K). Adding an excess ENTROPY term (b*T) to the
  silica excess lowers the consolute but NOT the monotectic: our left conjugate liquid is
  MgO-rich (~0.64), so the long tie-line to pure cristobalite preempts the silica liquid up
  to ~2300 K regardless. A quantitatively correct monotectic is a genuine model-form limit of
  this minimal two-cation / single-anion binary, not a tuning miss.
- The **periclase-forsterite eutectic** remains near-coincident with forsterite melting (the
  refractory-MgO limit carried from v0.2), and the **enstatite peritectic (~1946 K) and
  enstatite-cristobalite eutectic (~1935 K) are squeezed into a ~10 K band** (measured 1830 /
  1816 K, ~14 K apart) - so the silica-intermediate region shows no clean eutectic valley;
  the two invariants overlap. Solid-model-limited (Neumann-Kopp Cp, no polymorphs).
- q = 5 is an empirical network order; a physically-derived silica-network treatment (or a
  richer structural model) is a further refinement.
- Built only from open data (Greig 1927 gap; the v0.2 sources); the silica term is our own
  fit, no FactSage/FToxid parameters.

## v0.5 excess (CALPHAD-style fit to the invariants AND the measured liquid enthalpy)

v0.4 placed the gap composition and classified the melting types correctly, but its invariant
TEMPERATURES were off (enstatite peritectic +116 K, enstatite-cristobalite eutectic +124 K,
periclase-forsterite eutectic +43 K), because its liquid was anchored to a single point
(forsterite melting) rather than fit to the whole invariant set. v0.5 fits the liquid excess
SIMULTANEOUSLY to the four condensed invariants, following the published method (a CALPHAD
assessment IS a parameter optimization to the whole dataset - the reason FactSage reproduces
the measured diagram is fitting, not secret physics; the MQM method itself is published, our
clean-room basis: Pelton, Degterov, Eriksson et al., Metall. Mater. Trans. B 31 (2000) 651 and
Metall. Mater. Trans. A 32 (2001) 1355/1409; the specific MgO-SiO2 optimization is Wu, Eriksson
& Pelton, J. Eur. Ceram. Soc. 2004, and Decterov & Pelton, J. Am. Ceram. Soc. 2002 - method
only, none of their fitted parameters are used here).

### Model and fitted values

Same charge-proportional Z and same Pelton-structured excess as v0.2/v0.4 (a (0,0) constant, a
(1,0) MgO-side term, and a (0,5) silica-side term on the (Mg,Si,O,O) quadruplet). Our engine's
excess variable chi = X_ii / (X_ii + X_ij + X_jj) is built from the quasichemical QUADRUPLET
fractions, so it IS Pelton's pair-fraction expansion (Part I Eq 17): the (1,0) term acts only on
the MgO-rich side (where X_SiSi -> 0) and the (0,5) term only on the silica side (where
X_MgMg -> 0), so the two halves are fit almost independently.

| term | code | (p,q) | coefficients (a + b*T), J/mol |
|---|---|---|---|
| g00 | Q | (0,0) | -110881.5 - 3.78*T |
| g10 | Q | (1,0) | +88436.1 |
| g_si | Q | (0,5) | +138675.2 |

Reproduce with `v05_reconcile.py` (fit + write); `--fit` re-runs the optimization.

### Method: fit to the invariants AND the measured mixing enthalpy

The key modelling point (the arbitration behind v0.5): fitting ONLY the invariants lets the
optimizer deepen the symmetric g00 without limit, producing a liquid ~2x deeper than the
independently-measured mixing enthalpy (dH_mix(x=1/3) ~ -47 to -54 vs the MLIP+calorimetry
-24.5 kJ/mol-oxide) - it matches the diagram by distorting the liquid, which is not physical.
v0.5 therefore adds dH_mix(x=1/3) = -24.5 and dH_mix(x=1/2) = -22.4 (the v0.2 MLIP anchors) as
FIT TARGETS alongside the invariants. The model reproduces BOTH: this works because the
quasichemical CONFIGURATIONAL (short-range-order) entropy carries the stabilization, so a
SHALLOW enthalpy is enough to melt the compounds at the observed temperatures - exactly the
mechanism Pelton reports (Part I: a strongly ordered binary fits the phase diagram + activities
+ dH_mix with a few temperature-independent terms, because the SRO entropy is structural, not a
fitted polynomial). Charge-proportional Z already places maximum SRO at the orthosilicate:
X_SiO2(max SRO) = Z_Mg/(Z_Mg+Z_Si) = 1/3 when Z_Si = 2*Z_Mg (Part I), which is our default.

### Solid model: measured compound Cp tested and REJECTED (kept Neumann-Kopp)

The brief hypothesised that Neumann-Kopp compounds (dCp_ox = 0) melt ~115 K too high and that
using each compound's own measured Cp(T) would pull the invariants down. Tested directly with
the real Robie-Hemingway 1995 coefficients (USGS Bull. 2131, public domain, pp.60-61; form
Cp = A1 + A2*T + A3*T^-2 + A4*T^-0.5 + A5*T^2; reproduces the R&H Cp(298) exactly - forsterite
118.60, enstatite 83.10) and it is BACKWARDS: dCp_ox is POSITIVE for these silicates (~+3 to
+7 J/mol/K), so measured Cp makes the compounds melt HIGHER (forsterite +141 K), not lower, and
degrades the achievable fit (max invariant residual 41 K with measured Cp vs 21 K with
Neumann-Kopp) while forcing an even deeper liquid. Neumann-Kopp's small errors partly cancel
against the liquid fit. So v0.5 keeps Neumann-Kopp; the measured-Cp path is implemented
(`phase_diagram.USE_COMPOUND_CP`, default off, and `v05_probe.py`) and documented as tested and
rejected, not a defect. (Enstatite R&H Cp is fit only to 1000 K; above it dCp_ox = 0 resumes -
the standard assessment convention once calorimetry runs out.)

### Results (reproduce with v05_reconcile.py; invariants by phase_hull / v05_fit)

| invariant | measured (K) | v0.4 | v0.5 |
|---|---|---|---|
| forsterite congruent | 2163 | 2163 | 2130 (-33) |
| periclase-forsterite eutectic | 2123 | 2166 (+43) | 2152 (+29) |
| enstatite peritectic | 1830 | 1946 (+116) | 1830 (0) |
| enstatite-cristobalite eutectic | 1816 | 1940 (+124) | 1820 (+4) |
| silica gap @1968 K (mole frac) | 0.59/0.99 | 0.591/0.981 | 0.591/0.990 |
| dH_mix(x=1/3) kJ/mol-oxide | -24.5 (MLIP) | -24.5 | -25.2 |
| dH_mix(x=1/2) kJ/mol-oxide | -22.4 (MLIP) | -18.7 | -21.4 |

The silica-intermediate invariants that were +116/+124 K off are now within ~5 K, WITH a liquid
that reproduces the measured mixing enthalpy. Worst-case invariant error drops from 124 K to
33 K.

### Honest limitations

- **The two-liquid monotectic still runs too hot.** The gap COMPOSITION matches Greig (left
  conjugate 0.59, right ~0.99), but the isolated-liquid dome does not close until a consolute
  ~3000+ K, so cristobalite preempts the silica-rich liquid at ~2600 K vs the measured 1968 K
  monotectic. What actually sets the monotectic was pinned down by direct experiment (see the
  monotectic study below): it is the excess MAGNITUDE, not the coordination. Two candidate
  fixes were tested:
    1. *Coordination (composition-dependent Z)* - REFUTED. Neither fixed per-quadruplet Z nor
       a decoupled pure-vs-mixed quad Z (pure Si2O2 Z ~ 6 for the silica-clustering region,
       mixed MgSiO2 Z pinned at the ordering ratio) lowers the consolute at all - it only
       shifts the gap edge. So the "silica clustering needs Z ~ 6" reading of Pelton, applied
       as a coordination number, does NOT lower the dome here; an engine change to make Z
       composition-dependent would not have helped. (This corrects an earlier hypothesis.)
    2. *A temperature-dependent silica excess* L_si = a_si + b_si*T (b_si < 0), which weakens
       the silica-rich immiscibility as T rises - DOES lower the dome (monotectic ~2600 -> ~2180
       K, v0.6, `v06_fit.py`). But it plateaus ~200 K above the measured 1968 K, and pushing it
       degrades the physically-anchored quantities: the measured dH_mix match worsens
       (dH_mix(x=1/2) -22.4 -> -14.1) and the periclase-forsterite eutectic drifts to +55 K.
       Trading the measured enthalpy for the diagram is the same move rejected for the v0.5
       liquid, so v0.6 is NOT shipped; v0.5 (invariants + calorimetry matched) is retained.
  The genuine remaining limit is the single-oxygen-anion model form: one liquid cannot match the
  invariants, the measured mixing enthalpy, AND the monotectic at once. The real fix is anion
  speciation (a second anion / associate species, e.g. a silicate-network anion), the FToxid-style
  richer liquid - a substantial engine extension, kept as the next model-form step.
- **The MgO-rich side is ~30 K off and slightly inverted** (periclase-forsterite eutectic 2152
  computed above forsterite congruent 2130), the refractory-MgO-endmember limit carried from
  v0.2 (MgO Tm 3098 K is too high for the shallow ~40 K eutectic valley to resolve cleanly).
- Built only from open data and our own fit to it (invariants from Bowen-Andersen 1914 and Greig
  1927; dH_mix from the open MatterSim MLIP + Charlu-Newton-Kleppa calorimetry; compound Cp from
  Robie-Hemingway 1995). The MQM method is from the published Pelton papers; NO FactSage/FToxid
  or other optimized-TDB parameters are used.

## Scope: condensed phases only (no gas phase)

The database and every diagram computed from it are **condensed-only**: one liquid solution
phase plus the crystalline solids, no gas species. This is the standard convention for a
binary oxide phase diagram, but it is a real scope boundary, not a detail:

- **At high T the system vaporises.** Above ~2000-2200 K silica volatilises (mainly
  SiO2 -> SiO(g) + 1/2 O2, plus SiO2(g)), and MgO loses Mg(g) further up. A gas phase would
  cap how hot the condensed field persists and change the bulk composition by mass loss - the
  KEMS activity work these databases lean on literally measures that vapour. This is a second,
  independent reason the modelled two-liquid dome (consolute ~3115 K) is unphysical: at those
  temperatures the condensed phases would be substantially boiled off, so the dome could never
  reach them. It reinforces (does not replace) the missing-entropy limitation above.
- **Simplifications can mis-rank stability.** Like the omitted gas, the Neumann-Kopp solid Cp,
  the unresolved polymorphs, and the refractory-MgO endmember each shift invariants and can
  render a truly stable phase metastable in the model (and vice versa). The article should
  present the model diagram beside the measured one so these documented gaps are visible, not
  implied away.
- **FactSage does track the gas.** FactSage draws oxide slag equilibria from FToxid (oxide
  solutions) together with FactPS (pure substances, which supplies the gas species), and its
  Equilib module minimises Gibbs energy over all selected phases - gas included - at fixed T
  and P (1 atm). So a FactSage high-T oxide calculation carries SiO(g), Mg(g), O2, etc. as an
  ideal-gas mixture phase. Matching that means adding a gas phase to Hephaestus, below.

### Adding a gas phase (deferred, its own step)

What it takes, scoped:
1. **Data.** Open Gibbs functions for the gas species - SiO, SiO2, Mg, MgO, O, O2 (and O3) -
   from NIST-JANAF (open), as stoichiometric G(T) on the same term basis as the endmembers.
2. **Model.** One extra solution phase = an ideal-gas mixture (G = sum n_i[G_i(T) + RT ln(p_i)],
   p_i = partial pressure), at fixed total P = 1 atm. No excess needed for an ideal gas.
3. **Engine.** The reader already parses non-SUBQ/SUBG stoichiometric phases; the multiphase
   hull/equilibrium must admit a gas phase whose amount is set by the 1 atm constraint (the
   current single-phase solver and the binary hull are condensed-only). This is the real work.
4. **Result.** Vaporisation (fuming) boundaries, a realistic high-T ceiling on the condensed
   field, and vapour-pressure / activity output to compare against the KEMS data. It belongs
   to the steel-slag gas+liquid+solid goal, kept separate from the liquid-slag database steps.
