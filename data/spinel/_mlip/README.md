# Spinel-hercynite Fe-Mg mixing: MLIP triangulation

No open Fe-Mg spinel-hercynite (MgAl2O4-FeAl2O4) mixing calorimetry exists, so the A-site
excess is computed from a foundation MLIP (MatterSim), the MLIP-for-solids method proven on
clinopyroxene, here on a new cubic Fd-3m structure. The mixing enthalpy is a difference
between the alloy and its endmembers, so the MLIP's systematic per-atom error cancels.

## Method

- Structure: MgAl2O4 conventional cell (COD 9010342, Fd-3m, 56 atoms, 8 tetrahedral
  A-sites); hercynite is the all-Fe A-site substitution, fully relaxed. (`cif/`, gitignored.)
- `mlip_mix.py`: for k Fe of 8 A-sites (x = 0, .25, .5, .75, 1), distinct Fe/Mg orderings
  (capped at 6, random subset) are relaxed (cell + positions, 0 GPa) and averaged;
  H_mix(x) = <E(x)> - (1-x) E(spinel) - x E(hercynite), per formula. Normal-spinel: a static
  relaxation does not swap cation identities, so Fe/Mg stay on A and Al on B.

## Result

A small, **favourable (negative), asymmetric** excess, well resolved (per-ordering spread
<= 0.7 meV/formula vs a signal of hundreds of J): H_mix -475 / -766 / -920 J/mol at
x = .25 / .5 / .75. Redlich-Kister fit L0 = -3411, L1 = -2373 J/mol (per MAl2O4 formula),
carried into data/spinel/build_dat.py. Negative mixing means no miscibility gap (complete
spinel-hercynite solid solution), as observed.

`cif/`, `*.log` and `*.json` here are gitignored build artifacts; the script is the record.
