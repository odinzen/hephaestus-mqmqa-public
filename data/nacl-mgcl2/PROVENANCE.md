# NaCl-MgCl2 v0.1 provenance and limits

Fourth open salt system, the third leg of the MgCl2-KCl-NaCl CSP ternary, and the
second with a divalent cation. Liquid SUBQ (Na+1, Mg+2 / Cl-1) + NaCl and MgCl2 solids,
modeled as a **simple eutectic** with no intermediate compound. Built 2026-08-26. No
value derives from any prior assessment or commercial database.

## Endmembers (reused verbatim from the family; TKV via the workspace Chlorides reference)

| | dHf(298) kJ | S298 J/K | Tm K | dHfus kJ | solid Cp (Maier-Kelley, J/mol/K) |
|---|---|---|---|---|---|
| NaCl | -411.412 | 72.132 | 1074.15 | 28.200 | a 41.1961, b 2.280119e-2, c +2.46588e5 (shared with nacl-kcl) |
| MgCl2 | -644.796 | 89.537 | 987.0 | 43.095 | a 76.9, b 8.496e-3, c -7.463e5 (shared with kcl-mgcl2) |

## Liquid (SUBQ, Na+1 / Mg+2 / Cl-1)

Z = 6 for both cations (MQM salt convention, via `Component.z_cat`); the shared-anion
coordination follows per-pair charge neutrality (Cl gets 6 in the Na-Cl pair, 3 in the
Mg-Cl pair), the same divalent handling introduced for KCl-MgCl2.

Two Q-code cation-mixing terms on (Na,Mg,Cl,Cl), fitted to the single measured eutectic:

  Delta_g(Na,Mg)/Cl = -4749.5 - 4732.3*chi_Na  J/mol

| target | measured | model |
|---|---|---|
| eutectic temperature | 718.15 K (445 degC) | 718.1 K |
| eutectic composition | x(MgCl2) = 0.42 | 0.420 |

Two parameters, two targets, both hit (fit cost 1e-4). The eutectic is the DLR 2021
review's compiled experimental value (Table 1).

## Validation

- **Eutectic-liquid heat capacity (not fitted): model 75.6 J/mol/K vs Duemmler 2022
  ab-initio-MD 75 J/mol/K** at 42.7 mol% MgCl2, 1100 K. The liquid Cp is nowhere in
  the fit (the excess terms are T-independent), so this ~1 percent agreement is an
  independent cross-check on the endmember + mixing thermochemistry.
- The divalent-Mg liquid Gibbs energy matches pycalphad `calculate` (the same file, read
  natively) to within 30 J/mol across x(MgCl2) = 0.25/0.5/0.75; both solid endmembers
  match the analytic solid Gibbs to machine precision.
- pycalphad `equilibrium` reproduces the simple-eutectic topology: NaCl + MgCl2
  two-phase below the eutectic (no spurious intermediate phase), single liquid above.

## Known limits, the intermediate-compound question

Whether NaCl-MgCl2 carries the double salts NaMgCl3 and Na2MgCl4 is **unsettled in the
open literature**. The DLR engineering review treats the system as a plain binary
eutectic; other work reports two incongruently-melting compounds. The only source that
names them with coordinates (Wang/Villada 2022, FactSage: eutectic L = Na2MgCl4 +
NaMgCl3 at 459 degC / 57 mol% NaCl, with two peritectics) is a CALPHAD assessment, so
its numbers are validation-target class and are not ingested per the literature-only IP
boundary; they are also pinned to a different eutectic temperature (459 degC) than the
measured value adopted here (445 degC, DLR). No open primary-experimental source ties a
measured invariant to specific conjugate solids.

v0.1 therefore models the honest, open-data-supported picture: one measured eutectic,
reproduced exactly, with pure NaCl and MgCl2 as the conjugate solids. If an open primary
(a DSC + XRD determination) later fixes the compounds, adding them is a v0.2 refinement.
For the CSP ternary this binary contributes its liquid excess and the eutectic location,
both of which v0.1 pins.

## Sources

- Villada, Ding, Bauer et al., *Engineering molten MgCl2-KCl-NaCl salt for
  high-temperature thermal energy storage*, Sol. Energy Mater. Sol. Cells 232 (2021)
  111344, DOI 10.1016/j.solmat.2021.111344 (eutectic 445 degC at ~42 mol% MgCl2).
- Duemmler et al., *An ab initio molecular dynamics investigation of the thermophysical
  properties of molten NaCl-MgCl2*, J. Nucl. Mater. 2022, DOI
  10.1016/j.jnucmat.2022.153916 (AIMD eutectic-liquid Cp 75 J/mol/K).
- Wang et al., Front. Energy Res. 10 (2022) 809663, DOI 10.3389/fenrg.2022.809663,
  CC-BY (**compound topology only**; FactSage-derived, not ingested).

Repro: `build_dat.py` (writes NaCl-MgCl2.dat; `python build_dat.py` writes the fitted
model), `v01_fit.py` (evaluates; `--fit` re-derives the two liquid terms from the
eutectic).
