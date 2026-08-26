# CaO-FeO-MgO-SiO2 combined multiphase file provenance and limits

One ChemSage .dat holding every candidate phase of the system so a full multi-phase
equilibrium can be run: the ferromagnesian silicates crystallizing from the slag melt.
Built 2026-08-26.

  liquid   CAO-FEO-MGO-SIO2-LIQUID (MQMQA SUBQ)
  solid solutions   OLIVINE, ORTHOPYROXENE, CLINOPYROXENE (CEF SUBL)
  oxide solids      CRISTOBALITE, LIME, PERICLASE, WUSTITE (stoichiometric)

## Assembly

The liquid block is spliced **byte-for-byte** from CaO-FeO-MgO-SiO2-liquid.dat; the three
CEF blocks are spliced byte-for-byte from data/olivine-opx-cpx/Olivine-Opx-Cpx-CEF.dat; the
four oxide solids come from the same solid-oxide Gibbs coefficients the binaries use.
Element order Ca, Fe, Mg, Si, O throughout. Nothing is refit.

## What is validated (the machinery)

- **pycalphad reads all eight phases** and runs a full multi-phase `equilibrium`.
- **The splice is faithful**: the liquid block is byte-identical to the standalone liquid
  file, and the olivine / opx / cpx CEF Gibbs energies equal the standalone solids database
  to machine precision.
- **The melting is calibrated (v0.2) and the primary-phase fields are physical.** The
  silicate solids and the liquid are put on one absolute scale by below-melting Gibbs
  intervals on the liquid oxide endmembers (the FeO-MgO-SiO2 technique): MgO(l) is fit so
  forsterite melts congruently at 2163 K, FeO(l) so the FeO-SiO2 diagram is right, and the
  new **CaO(l) interval (data/cao-feo-mgo-sio2 liquid v0.2) is fit so diopside CaMgSi2O6
  melts congruently at 1670 K**. Checked: diopside melts at 1670 K and forsterite at 2163 K
  (both to within the grid step), and hedenbergite comes out near its measured ~1413 K
  (unfitted, from the FeO(l) + CaO(l) endmembers). With this, the crystallization is
  physical: a mafic low-Ca melt crystallizes **olivine** first, a diopsidic / Ca-rich melt
  crystallizes **clinopyroxene**, and an iron-rich melt crystallizes olivine (fayalitic).
  Before the CaO(l) calibration the R&H-vs-MQMQA reference offset over-stabilized the
  silicates and cpx was primary everywhere.

## Known limits

- **One Ca-silicate anchor.** CaO(l) is fit to diopside; the other Ca-silicate melting
  points (wollastonite, larnite, hedenbergite) are then predictions, close but not exact,
  since a single endmember shift cannot hit every calcium silicate. Adding those line
  compounds and refining against their melting is a later step.
- **No Ca-silicate line compounds** (wollastonite, rankinite, larnite, ...) are in the
  file yet, so the CaO-SiO2 edge of the diagram is represented by lime + cristobalite + the
  melt only; the silicate solid solutions (olivine, pyroxenes) are the crystallizing phases.
- **Near-endmember / congruent compositions** remain numerically stiff for the global
  solver (occasional non-convergence at exact pure-endmember boundaries).

## Sources

Every phase's parameters come from the shipped databases (data/cao-feo-mgo-sio2 liquid,
data/olivine-opx-cpx solids, and the binary oxide builders); their PROVENANCE files carry
the citations. Nothing new is introduced here.

Repro: `build_combined_dat.py` (splices the shipped liquid + solids into
CaO-FeO-MgO-SiO2-combined.dat), `validate_combined.py` (the checks above).
