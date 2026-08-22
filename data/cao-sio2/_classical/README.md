# Classical MD cross-check (Pedone/OpenMM) - CaO-SiO2 melt

Independent classical-MD check of the MLIP structure + demixing (see ../PROVENANCE.md).
Run in the `classmd` conda env (OpenMM 8.6, GPU via OpenCL).

- `openmm_pedone.py` - Pedone et al. 2006 rigid-ion potential in OpenMM (Coulomb PME +
  Morse + C/r^12). Params are the standard 2006 set; verify against the paper before
  quantitative use. Build/smoke-test the engine.
- `openmm_analyze.py` - Si-O/Ca-O coordination + Qn speciation, and a Ca-Ca demixing
  enrichment metric.
- `openmm_demix.py` - silica-rich melt below the consolute; Ca-Ca clustering vs time.

Findings (2026-08-22): structure at CaSiO3 is Q2-dominant (agrees with MLIP MatterSim);
the classical demixing probe at x=0.8/1800 K/150 ps showed NO clustering (enrichment ~1.0)
- likely finite box/time or Pedone lacking this gap. The demixing TENDENCY is established
thermodynamically by the MLIP dH_mix scan (convex toward silica), not by direct MD.
