# CaO-Al2O3-SiO2 — provenance and limits

## Scope: dry slags only (2026-10-01)

These files describe the **dry** CaO-Al2O3 system: no water in the melt or the solids.
Ca12Al14O33 (C12A7, mayenite) is therefore not a phase. It is stable only when the solid holds a
little absorbed water (under 1 mass%) and does not form in a dry atmosphere (Nurse, Welch & Majumdar
1965, Trans. Br. Ceram. Soc. 64, 409-418; confirmed by DTA in argon by Jerebtsov & Mikhailov 2001,
Ceram. Int. 27, 25-28, doi:10.1016/S0272-8842(00)00037-7). In the dry system every calcium
aluminate melts peritectically. Water is unlikely in a molten slag, so the dry diagram is the one
that applies to slag practice; the older air measurements (Shepherd, Rankin & Wright 1909; Rankin &
Wright 1915) are used only where they do not involve Ca12Al14O33.

## v0.2 (2026-08-26): the ternary term

v0.1's validation isolated a uniform +3.28 bias in ln a(SiO2) over the 21 Zaitsev
CaO-rich points — the measured signature of the missing ternary interaction. v0.2 adds
exactly one term: the CaO-SiO2 quadruplet gains an additional-constituent (AlO1.5)
term, L = -110000 J/mol with r = 1 (Poschmann Eq. 25-26; the FactSage
additional-mixing-constituent mechanism), fitted to those 21 points by scanning L on
pycalphad-computed activities. Result over all 45 KEMS points:

- Zaitsev (21, CaO-rich): RMS ln a 3.43 -> **0.48**, bias +3.28 -> **-0.10**
- Kay & Taylor (24, silica-rich): RMS 0.38 -> 0.46, bias -0.11 -> +0.08

The engine gained evaluation of this term (single chemical group, r = 1: the binary
mixing term times the third cation's pair fraction Y_m; r >= 2 and multi-group then
returned NaN loudly; the engine has since added both for single-anion liquids, see
mqmqa_excess_term_status). Verified: engine equilibrium GM matches pycalphad to < 0.005 J/mol-atom
on this file at Zaitsev-corner compositions, and to < 0.5 J on the dedicated
regression test system; the WASM build reproduces the native value; the prior
FeO-MgO-SiO2 oracle value (-321252.12 at 1700 K) is unchanged.

## v0.1 (2026-08-26): assembly and validation

The cement-and-slag flagship ternary, assembled 2026-08-26 from the three shipped
binaries. No ternary parameter is fitted; the 45 independent KEMS silica activities in
the assessment workspace are used only to VALIDATE the assembly. No value derives from
any prior assessment or commercial database.

## Liquid

SUBQ (Ca+2, Al+3, Si+4 / O-2), components CaO, AlO1.5, SiO2. The three binary excesses
are carried verbatim from the shipped systems and combined by the writer's Muggianu
extension:

| binary | excess (J/mol) | source |
|---|---|---|
| CaO-SiO2 | (-189763.5 + 15.706 T) + 57170.8 chi_Ca | v0.3 shipped .dat |
| CaO-Al2O3 | (-156581.1 + 2.159 T) + 133468.2 chi_Ca | v0.1 |
| Al2O3-SiO2 | 9317.3 + 33855.3 chi_Si^5 | v0.1 |

## Solids (15 phases total)

The three binary edges' compounds, all carried exactly as in their source systems
(CaO-SiO2 compounds by the same Neumann-Kopp + measured dHf_ox construction as the
shipped binary phase model, quartz-to-cristobalite corrected), plus two ternary
compounds from Robie & Hemingway (1995):

- **gehlenite Ca2Al2SiO7**: dHf -3985.0 kJ, S298 210.1, Haas-Fisher Cp with the
  T^-0.5 term (a 405.7, b -0.007099, c -1.188e6, d -3174) — carried exactly via the
  additional-terms block.
- **anorthite CaAl2Si2O8**: fitted to the Robie & Hemingway high-temperature table (Bull.
  2131 p. 362, 298-1800 K; `rh1995_anorthite.csv`, extracted from the bulletin's text layer
  and checked row by row against -(G-H298)/T = S - (H-H298)/T) with the calcium silicates'
  fit (`data/cao-sio2/silicates.py`): within 33 J of the table, 20 J from 1000 K up. Until
  2026-09-30 the Cp was a Maier-Kelley fit to the table's points to 1000 K only; that
  function sat up to 785 J off the table and 0.8 kJ too stable at the 1830 K melting point.

## Validation: 45 KEMS silica activities (prediction, nothing fitted)

a(SiO2) computed vs the cristobalite reference (matching the measurements' silica-
saturation reference) from liquid-only pycalphad equilibria on the written file
(validate_kt.py):

- **Kay & Taylor 1960 (24 points, silica-rich, ~1820 K): RMS ln a = 0.38, bias -0.11.**
  Within the scatter typical of these measurements, and comparable to the CaO-SiO2
  binary's own activity-fit residual (0.32). The silica-rich ternary is predictive.
- **Zaitsev 1997 (21 points, CaO-rich aluminate valley, a(SiO2) down to 1e-5):
  RMS ln a = 3.43 with a UNIFORM bias of +3.28.** The model's silica activity is
  systematically ~e^3.3 high in the basic corner: the real melt stabilizes SiO2 beyond
  what the binary combination gives. A systematic (not scattered) deviation of this
  kind is the classic signature of a missing ternary interaction term.

## MLIP feasibility for the edge excess enthalpies (2026-09-10)

A separate feasibility test asked whether foundation machine-learned interatomic potentials
(MLIPs) agree well enough to anchor a liquid excess enthalpy, or spread too far to be useful.
Method (`_mlip/mlip_mix.py`, the melt-quench approach from data/cao-sio2/_mlip): NVT molecular
dynamics of the two pure oxide melts and their 50/50 oxide-fraction mix at 3000 K (1.5 ps melt
at 4000 K, 3 ps equilibration, 6 ps sampling), with dH_mix per oxide unit from the energy
difference so per-atom reference energies cancel. Three foundation models on CPU: SevenNet
(7net-0), MatterSim (v1.0.0-1M), and orb (orb-v2). This is a feasibility probe only; nothing
here is fitted into the database.

dH_mix at x = 0.5 (kJ/mol-oxide):

| Edge | SevenNet | MatterSim | orb | spread |
|---|---|---|---|---|
| CaO-Al2O3 | -24.9 +- 0.8 | -32.0 +- 0.7 | -25.9 +- 0.8 | ~7 |
| Al2O3-SiO2 | +19.1 +- 1.1 | +9.6 +- 1.0 | +1.6 +- 1.4 | ~17 |
| CaO-SiO2 (control) | -50.2 +- 0.9 | -55.9 +- 0.8 | -47.4 +- 0.8 | ~8 |

- All three models agree on the SIGN for every edge.
- The strongly-ordering edges (CaO-Al2O3, and the CaO-SiO2 control) cluster within ~7-8 kJ.
  The control's ~8 kJ spread, on a system known to order deeply, sets the floor on the model
  systematic error; MLIPs could seed the CaO-Al2O3 excess enthalpy to roughly +-5 kJ.
- Al2O3-SiO2 is NOT anchorable from MLIPs: the values fan from +1.6 (near-ideal) to +19.1, a
  factor of ~12. Only the positive sign (a weak demixing tendency) is robust; the magnitude
  needs a measured calorimetric datum. No single model is the consistent outlier, so the
  disagreement is largest where the interaction is weakest.

Bearing on this database: the MLIPs confirm the qualitative excess of each edge but do not
supply a usable magnitude for the aluminosilicate edge, so the excess terms stay fitted to the
measurements above, not to MLIP energies. Repro: `_mlip/mlip_mix.py <model> all 3000 1.5 3.0
6.0` (orb needs `TORCHDYNAMO_DISABLE=1` on a machine without an MSVC C++ compiler).

## Known limits

- No ternary excess term (by construction in v0.1). The Zaitsev bias above IS the
  measurement of what is missing; fitting a ternary term to those 21 points is the
  designated v0.2 step (the writer does not yet emit ternary MQMX terms).
- Every binary edge inherits its own documented limits (CaO-SiO2 silica gap
  temperature, CaO-Al2O3 +-90 K invariants, Al2O3-SiO2 Al-rich flank).
- Ternary liquidus surfaces/invariants not yet mapped (the FeO-MgO-SiO2 ternary
  machinery applies and is the natural follow-up). A first look (vis3d.liquidus_point,
  2026-09-29): anorthite melts at 2234 K (1960 degC) in the model against 1557 degC
  measured, and gehlenite at 1946 K (1672 degC) against about 1590 degC. The anorthite Cp is
  a fit to 1000 K; the missing ternary liquid term may carry part of it.
- The liquid alone has a CaO-rich two-liquid region off the CaO-Al2O3 edge (to x_Al 0.35
  on the edge at 1900 K), deep under the CaO liquidus, so solid CaO removes it from every
  equilibrium; it shows only in liquid-only views.
- Both engines load all 15 phases; the SUBQ+stoich ternary code path is the one
  validated end-to-end on FeO-MgO-SiO2 (phase sets 15/16 vs pycalphad).

Repro: `build_dat.py` (writes CaO-Al2O3-SiO2.dat), `validate_kt.py` (the 45-point
prediction test; prints per-source RMS and bias).
