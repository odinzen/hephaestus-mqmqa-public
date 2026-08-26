# Clinopyroxene di-hed mixing: MLIP triangulation

No open diopside-hedenbergite mixing calorimetry exists (Davidson & Lindsley 1985 is a
phase-equilibrium activity model, assessment-class, and paywalled), so the (Fe,Mg) M1
excess is computed from a foundation MLIP, the same triangulation used for the CaO-SiO2
and MgO-SiO2 liquids. Because the mixing enthalpy is a *difference* between the alloy and
its endmembers, the MLIP's systematic per-atom error largely cancels.

## Method

- Structures: diopside CaMgSi2O6 (COD 1000007, C2/c, ambient) as the common framework;
  hedenbergite is the all-Fe M1 substitution, fully relaxed to its own structure.
  (`cif/`, gitignored.)
- `mlip_mix.py`: the 40-atom conventional cell (4 M1 sites), every distinct Fe/Mg
  ordering per composition relaxed (cell + positions, 0 GPa) with MatterSim v1.0.0-5M.
- `mlip_mix2.py`: the doubled cell (2x1x1, 80 atoms, 8 M1 sites) for a cleaner
  configurational average, x = 0.125..0.875, up to 8 orderings each.
- H_mix(x) = <E(x)> - (1-x) E(diopside) - x E(hedenbergite), per formula (per mole of
  mixing cation); a Redlich-Kister excess is fit to the interior points.

## Result

The 40-atom cell placed H_mix(0.5) near zero (+52 J/mol) but with a per-ordering spread
(~1 kJ) larger than the composition signal, so it only bounded the excess. The doubled
cell sharpened the average (spreads 0-4 meV) and resolved a **small, asymmetric,
near-ideal** excess: H_mix negative on the Mg-rich side (-443 J/mol at x = 0.125, the
symmetry-locked clean point), positive on the Fe-rich side (+108 J/mol at x = 0.875),
crossing near mid-composition. |H_mix| < 0.5 kJ/mol everywhere, too small for a
miscibility gap (di-hed is a complete solid solution) and consistent with the
petrological consensus.

Uncertainty-weighted Redlich-Kister fit (`fit_excess.py`, sigma floor 50 J/mol),
G_xs = y_Fe*y_Mg*[L0 + L1*(y_Fe - y_Mg)]:

    L0 = -576 +/- 142 J/mol,  L1 = +3442 +/- 280 J/mol

carried into data/clinopyroxene/build_dat.py; the .dat reproduces the fit to < 0.05 J/mol.
`dihed_hmix.png` is the figure.

Volumes: MatterSim over-expands both endmembers by ~3.5-4% (di 454.6 vs 438.6 A^3,
hed relaxes larger, Fe > Mg), a systematic offset that cancels in the mixing energy; the
Fe-Mg volume trend is reproduced.

`cif/`, `*.log` and `*.json` here are gitignored build artifacts; the scripts are the
reproducible record.
