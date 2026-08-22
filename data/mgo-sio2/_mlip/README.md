# MLIP triangulation for the MgO-SiO2 v0.2 liquid

Independent cross-checks behind the v0.2 excess (see ../PROVENANCE.md, v0.2 section).
MgO-SiO2 has no measured liquid activities, so the MLIP dH_mix is a genuine second
constraint on the liquid depth (not just an arbiter as in CaO-SiO2). Run in the
`mlip-screen` conda env (MatterSim, ORB, pymatgen on CPU torch):

- `mlip_hf.py` - formation-enthalpy spot-check of forsterite (Mg2SiO4) and enstatite
  (MgSiO3) from the oxides vs measured calorimetry (Charlu-Newton-Kleppa 1975). This
  VALIDATES the MLIP for the chemistry and measures its under-binding bias, applied to
  the liquid dH_mix. MatterSim under-binds by +8.0 kJ/mol-formula (forsterite, x=1/3)
  and +12.3 (enstatite, x=1/2), i.e. +2.7 and +6.2 kJ/mol-oxide-unit.
- `mlip_mix.py <model> [T melt eq samp seed]` - liquid enthalpy of mixing at the
  forsterite (x=1/3) and enstatite (x=1/2) compositions by melt-quench-sample MD at
  3200 K (both oxides molten). Bias-corrected, these are fit anchors 2 and 3.

Crystal structures are fetched from the open Crystallography Open Database (COD IDs in
the scripts): 9006398 (forsterite Mg2SiO4), 1000047 (enstatite MgSiO3), 9009666
(quartz SiO2); periclase MgO is built from its rocksalt spacegroup. Foundation MLIPs
(MatterSim, ORB) and their weights are open. No proprietary content.
