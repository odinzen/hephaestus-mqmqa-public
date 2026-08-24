# MLIP triangulation for the FeO-SiO2 v0.2 liquid

Independent cross-checks behind the v0.2 excess (see ../PROVENANCE.md). Run in the
`mlip-screen` conda env (MatterSim, pymatgen on CPU torch).

- `mlip_hf.py` - formation-enthalpy spot-check of fayalite (Fe2SiO4) from the oxides vs
  the open standard enthalpies (R&H 1995 / JANAF). Validates MatterSim for the Fe-Si-O
  chemistry and measures its bias. **Result: MatterSim OVER-binds fayalite by +8.1
  kJ/oxide-unit** (dHf_ox -47.6 vs measured -23.4 kJ/mol), so its raw liquid melt-mixing
  enthalpy is too deep - the correction points the true liquid SHALLOW. FeO is built from
  its rocksalt spacegroup (COD 9009766, a=4.326); quartz (9009666) and fayalite (COD
  1000064) CIFs are in `cif/` (Crystallography Open Database, CC0).
- `mlip_mix.py <model> [T melt eq samp seed]` - liquid enthalpy of mixing at the fayalite
  (x=1/3) and metasilicate (x=1/2) compositions by melt-quench-sample MD. **Did not
  converge in practical time on the available CPU** (MatterSim is ~0.1 s/step here; the
  dense FeO endmember melt in particular was pathologically slow). The v0.2 enthalpy depth
  is therefore anchored on the `mlip_hf.py` over-binding bias-check plus the dHf_ox scaling
  from MgO-SiO2 (see PROVENANCE.md), which the measured fayalite congruent melting (1478 K)
  independently corroborates. A converged MD (GPU / faster CPU) is a v0.3 refinement.

Foundation MLIP (MatterSim) and its weights are open; CIFs are open (COD, CC0). No
proprietary content.
