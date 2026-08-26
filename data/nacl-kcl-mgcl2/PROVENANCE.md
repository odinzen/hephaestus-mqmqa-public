# NaCl-KCl-MgCl2 v0.1 provenance and limits

The molten-salt CSP ternary (concentrated-solar / molten-salt-reactor heat-transfer
fluid), assembled from the three shipped binaries. Built 2026-08-26. Nothing ternary is
fitted: the liquid is the Muggianu combination of the binary excesses, and the Mohan et
al. 2018 measured eutectic is a pure validation target.

## Liquid (SUBQ, Na+1 / K+1 / Mg+2 / Cl-1)

Z = 6 for all three cations (MQM salt convention, via `Component.z_cat`); the shared-anion
coordination is charge-neutral per pair (Cl gets 6 in the Na and K pairs, 3 in the Mg
pair). The three shipped binary liquid excesses are carried **verbatim** and combined by
the writer's Muggianu extension, with no ternary term:

| binary | Delta_g / Cl (J/mol) | source |
|---|---|---|
| NaCl-KCl | -715.1 | NaCl-KCl v0.1 (Hersh-Kleppa dH_mix) |
| KCl-MgCl2 | -15895.0 - 88.5*chi_K | KCl-MgCl2 v0.1 |
| NaCl-MgCl2 | -4749.5 - 4732.3*chi_Na | NaCl-MgCl2 v0.1 |

## Solids

The binary endmembers NaCl, KCl, MgCl2 and the KCl-MgCl2 double salt KMgCl3, all
stoichiometric (values identical to the binary databases). The (Na,K)Cl **halite solid
solution** from NaCl-KCl v0.1 is not included here: the NaCl-KCl edge is represented by
the two stoichiometric solids. Adding halite (and any MgCl2-rich double salts) is the
v0.2 refinement.

## Validation

- **The assembly is exact: the C engine and pycalphad agree on the liquid Gibbs energy
  to +/-0.000 J/mol-atom** at the Mohan composition, 700 K and 900 K. The Muggianu
  combination of three binaries (including the divalent-Mg pairs) is emitted by the
  writer and evaluated by the engine identically to pycalphad.
- **Ternary-eutectic melting (pure prediction): the model's liquidus at the Mohan
  eutectic composition is 706 K vs the measured 660 K (387 degC), +46 K.** Mohan et al.
  2018 located the eutectic with FactSage (24.5/20.5/55 wt% NaCl/KCl/MgCl2) and measured
  its melting by DSC at 387 degC; only the melting temperature is experimental (the
  composition is FactSage-derived, i.e. validation-target). Nothing ternary was fitted,
  so the +46 K is the honest Muggianu-extrapolation error, in line with the binary
  prediction quality. NaCl is the primary crystallizing solid just below the liquidus.
- **Eutectic-liquid heat capacity (not fitted): model 0.93 vs measured 1.18 J/g/K.** The
  SUBQ liquid Cp is inherited from the endmembers (the excess is temperature-independent),
  so it carries no configurational Cp; the ~20 percent shortfall is expected and bounds
  what a T-independent excess can do.

## Known limits and the v0.2 path

- **No ternary term.** The +46 K eutectic over-prediction is the same signature CaO-Al2O3-SiO2
  showed on its basic corner before a single MQMX ternary term (Poschmann Eq. 25-26)
  brought it into line. The engine and writer already support that term, so a v0.2 fit of
  one ternary term to the Mohan melting point (and, if an open ternary liquidus is
  digitized, to more points) is the direct next step.
- **Stoichiometric solids only.** The halite (Na,K)Cl solid solution and any MgCl2-rich
  double salts beyond KMgCl3 are deferred; they matter most on the NaCl-KCl edge, away
  from the MgCl2-rich CSP eutectic.
- **The eutectic composition is not independently located** here (the open literature's
  eutectic composition is FactSage-derived); v0.1 reports the model melting at the
  measured composition, not a from-scratch ternary invariant search.

## Sources

- Mohan, Venkataraman, Coventry et al., *Assessment of a novel ternary eutectic chloride
  salt for next generation high-temperature sensible heat storage*, Energy Convers.
  Manag. 167 (2018) 156, DOI 10.1016/j.enconman.2018.04.100 (measured ternary-eutectic
  melting 387 degC and liquid Cp 1.18 J/g/K; composition FactSage-located, validation
  target only).
- The three binary databases (NaCl-KCl, KCl-MgCl2, NaCl-MgCl2 v0.1) supply every fitted
  parameter; see their PROVENANCE files.

Repro: `build_dat.py` (imports the three binaries and writes NaCl-KCl-MgCl2.dat),
`validate_ternary.py` (the three checks above), `liquidus_projection.py` (draws the
ternary liquidus surface from the model).
