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
- **A slag melt crystallizes a silicate on cooling**: a CaO25/FeO10/MgO20/SiO2-45 melt is
  fully liquid at 2000 K and precipitates clinopyroxene below ~1880 K. The multiphase
  crystallization equilibrium runs end-to-end.

## What is NOT claimed, and the v0.2 calibration

**Absolute liquidus temperatures and primary-phase fields are not calibrated.** The
Robie-Hemingway solid minerals (olivine, pyroxene endmembers) and the MQMQA liquid oxide
endmembers (from the binary builders) are assessed on **independent absolute reference
scales**, so their difference (the melting free energy of each silicate) carries an
uncalibrated offset of tens of kJ per formula. In this file that offset over-stabilizes the
silicate solids relative to the melt (clinopyroxene comes out as the primary phase across a
wider composition range than it should, e.g. even for mafic low-Ca melts that ought to
crystallize olivine first). The near-endmember / congruent-melting compositions are also
numerically stiff for the global solver.

The fix is the standard one, already used on the FeO-MgO-SiO2 melt: **calibrate the liquid
oxide endmembers against measured silicate melting points** (a below-melting Gibbs interval
on each of CaO(l), FeO(l), MgO(l), SiO2(l), fit so diopside melts at 1670 K, forsterite at
2163 K, wollastonite, fayalite, etc.). That is a focused calibration campaign, the
designated v0.2 of this combined system; it changes only the liquid endmembers' absolute
levels, not the assessed mixing excesses. Until then this file is the validated multiphase
**machinery** (and a minimizer / reader regression), not a quantitative phase diagram.

## Sources

Every phase's parameters come from the shipped databases (data/cao-feo-mgo-sio2 liquid,
data/olivine-opx-cpx solids, and the binary oxide builders); their PROVENANCE files carry
the citations. Nothing new is introduced here.

Repro: `build_combined_dat.py` (splices the shipped liquid + solids into
CaO-FeO-MgO-SiO2-combined.dat), `validate_combined.py` (the checks above).
