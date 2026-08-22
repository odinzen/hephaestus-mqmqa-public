# MLIP robustness checks for the CaO-SiO2 v0.3 liquid

Independent cross-checks behind the v0.3 excess (see ../PROVENANCE.md, v0.3 section).
Run in the `mlip-screen` conda env (MatterSim, ORB, phonopy, pymatgen on CPU torch):

- `mlip_mix.py <model>` - liquid enthalpy of mixing at x_SiO2=0.5 (melt-mixing MD).
- `mlip_scan.py <model>` - dH_mix across x_SiO2=0.2..0.7 (shape + silica demixing).
- `mlip_hf.py` - formation-enthalpy spot-check vs measured calorimetry (MLIP validation).
- `mlip_phonon.py` - solid S298/Cp from MLIP phonons vs Haas evaluated values.
- `gibbs_duhem.py` - internal-consistency check of Stolyarova's a(CaO) vs a(SiO2).

Crystal structures are fetched from the open Crystallography Open Database (COD IDs are
in the scripts): 9017535 (CaSiO3), 9012789 (Ca2SiO4), 1540704 (Ca3SiO5), 9009666 (quartz).
Foundation MLIPs (MatterSim, ORB) and their weights are open. No proprietary content.
