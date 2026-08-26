# CaO-Al2O3-SiO2 v0.1 — provenance and limits

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
- **anorthite CaAl2Si2O8**: dHf -4234.0 kJ, S298 199.3, Cp own Maier-Kelley fit to the
  R&H points 298-1000 K (a 266.4025, b 6.058556e-2, c -6.55428e6; max resid
  1.4 J/mol/K).

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

## Known limits

- No ternary excess term (by construction in v0.1). The Zaitsev bias above IS the
  measurement of what is missing; fitting a ternary term to those 21 points is the
  designated v0.2 step (the writer does not yet emit ternary MQMX terms).
- Every binary edge inherits its own documented limits (CaO-SiO2 silica gap
  temperature, CaO-Al2O3 +-90 K invariants, Al2O3-SiO2 Al-rich flank).
- Ternary liquidus surfaces/invariants not yet mapped (the FeO-MgO-SiO2 ternary
  machinery applies and is the natural follow-up).
- Both engines load all 15 phases; the SUBQ+stoich ternary code path is the one
  validated end-to-end on FeO-MgO-SiO2 (phase sets 15/16 vs pycalphad).

Repro: `build_dat.py` (writes CaO-Al2O3-SiO2.dat), `validate_kt.py` (the 45-point
prediction test; prints per-source RMS and bias).
