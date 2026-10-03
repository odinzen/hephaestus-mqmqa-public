# Open oxide-slag database (Hephaestus data)

An open, citable thermodynamic database for oxide slags in the ChemSage `.dat` format
that the Hephaestus MQMQA engine reads. The first system is the CaO-SiO2 liquid slag.

This database is the open-data counterpart to the engine: no free MQMQA oxide-slag
database exists, so every commercial workflow depends on closed sources. The goal here is
a database whose every parameter is traceable to a published, openly available source.

## License

The data in this directory (the `.dat` databases and the derived tables) are licensed
under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0); see
`LICENSE`. The engine is code and carries AGPL-3.0-only; this is data, and CC BY-SA is the
instrument for a citable dataset that must stay open. Attribution is met by citing this
repository and the primary sources listed in each system's `PROVENANCE.md`. Any adapted
version that is shared, including one converted to another file format, must be shared
under CC BY-SA 4.0 with the same credits and without technical measures that restrict it.
Releases up to and including v0.6.0 were published under CC BY 4.0 and keep those terms.

## Shipped databases

Every database the calculator ships is listed in `databases.toml`, and each one's source lives
here under `data/<system>/` with its `PROVENANCE.md`. The copies in `web/` are generated from
these sources by `scripts/sync_databases.py`, which also generates the calculator's load
buttons; never edit a database in `web/` directly. To add one, put its source in its system
folder, add an entry to `databases.toml`, and run the sync. Store one format per database
(`.dat` for slags and salts, `.tdb` for alloys, `.utdb` only for an alloy and a melt together,
`.xtdb` for third-generation data); the calculator converts to the others on demand.

## Scope and status

- `cao-sio2/` - CaO-SiO2 liquid slag, MQMQA (ChemSage SUBQ). Version 0.1.
  - `CaO-SiO2-liquid.dat` - the database.
  - `build_dat.py` - the build script (computes every coefficient from open data).
  - `validate.py` - loads the `.dat` in the engine and checks it against published data.
  - `PROVENANCE.md` - the per-number source for everything in the `.dat`.
- `mgo-sio2/` - MgO-SiO2 liquid slag, MQMQA (ChemSage SUBQ). Assessed liquid; see its
  `PROVENANCE.md`.
- `feo-sio2/` - FeO-SiO2 liquid slag, MQMQA (ChemSage SUBQ), v0.2 (fitted excess).
  Iron-saturated (Fe2+ only); FeO endmember from NIST-JANAF. The Fe-side binary for the
  FeO-MgO-SiO2 ternary slag; the excess is anchored on fayalite congruent melting (1478 K,
  Bowen-Schairer 1932) with an MLIP-informed / dHf_ox-scaled depth. See
  `feo-sio2/PROVENANCE.md`.
- `olivine/` - olivine (Mg,Fe)2SiO4 solid solution, the first **compound-energy-formalism
  (CEF)** system. A CEF model on the shared `cef/cef.py` kernel and a ChemSage SUBL `.dat`
  the C reader parses, validated against pycalphad to machine precision and against open
  olivine calorimetry (incl. the metastable solvus by the multiphase solver). See
  `olivine/PROVENANCE.md`.
- `olivine-opx/` - olivine + orthopyroxene (Mg,Fe) Fe-Mg **exchange equilibrium**: two CEF
  solid solutions in one SUBL `.dat`, their partitioning (K_D) computed through the C kernel
  and validated against pycalphad's two-phase equilibrium (~1e-9) and the measured K_D of
  von Seckendorff & O'Neill 1993. See `olivine-opx/PROVENANCE.md`.
- `INVENTORY.md` - the digitized open data available for this system and its sources.

### What v0.1 is

A well-formed MQMQA liquid phase with the two pure-oxide liquid endmembers, CaO(liq) and
SiO2(liq), assembled entirely from open pure-substance data (Robie & Hemingway 1995,
public domain, for the solid reference and heat capacity; NIST-JANAF for fusion). The
file loads in the engine, the engine reads its cations, anion, pairs, and coordination,
and the endmember energies round-trip exactly (see the validation output below).

### What v0.1 is NOT (yet)

The interior mixing of v0.1 is IDEAL: the excess (short-range-order) MQMQA parameters are
zero. An ideal CaO-SiO2 liquid does not reproduce the measured eutectics or the strong
negative-deviation silica activities, because those are set by the ordering energy around
the orthosilicate composition. Producing those requires excess MQMQA parameters, and no
open source publishes them in the SUBQ quadruplet form the engine reads. They are not
fabricated and not taken from any proprietary source, so they are left at zero and the
model is labeled ideal.

## Roadmap: the excess-parameter fit

The next increment adds the excess terms by optimizing against the open digitized data in
`INVENTORY.md`:

1. Liquid activities (Kay & Taylor 1960 a(SiO2); Stolyarova 1991 if it can be sourced
   openly) constrain the ordering energy directly.
2. The silica-side two-liquid dome (Greig 1927, public domain) constrains the
   silica-rich excess terms.
3. The experimental invariants and congruent meltings (Abdul et al. 2023, CC-BY)
   constrain the liquidus, once open intermediate-solid Gibbs functions are added on the
   same reference.

Tooling note: ESPEI fits two-sublattice ionic and CEF liquids, not the MQMQA quadruplet
model, so this optimization needs an MQMQA-aware optimizer, not ESPEI. Published MQMQA
CaO-SiO2 parameter sets exist in the assessment literature (for example Pelton & Blander
1986, DOI 10.1007/bf02657144, the foundational silicate MQM paper) and are the reference
point for the fit; they are cited, not silently copied, and any transcription would be a
documented model conversion, not a claim of an independent fit.

## Reproducing and validating

From the repository root, with the engine built:

```
PYTHONPATH=python python data/cao-sio2/build_dat.py      # regenerate the .dat
PYTHONPATH=python python data/cao-sio2/validate.py       # load + check vs published data
```

The validation script reports the load, the endmember round-trip against an independent
H - T*S evaluation of the open Robie-Hemingway/JANAF data, the reproduction of the
published fusion points (dG_fus -> 0 at Tm(SiO2)=1996 K and Tm(CaO)=3200 K), and the
pure-oxide-limit reduction. See `PROVENANCE.md` for the citation behind each number.

## Before an assessment ships

Three checks, for every assessment that goes public:

1. **One Gibbs function per phase.** A fitting script never carries its own copy or correction of
   a phase's energy. A correction (polymorph shift, heat-capacity fix, enthalpy shift) lives in the
   module the builder writes from, and the fit imports it.
2. **The fitting code matches the shipped file.** `tests/test_fit_tools_match_shipped.py` compares
   each binary's fitting solids with the shipped files at 800-2200 K; a new assessment adds its
   solids there. From 2026-08-22 to 2026-09-29 the MgO-SiO2 and CaO-SiO2 fitting code made pure
   cristobalite 2.3 kJ more stable than any shipped file, and every fit in that window was made
   against it.
3. **Quoted numbers come from the shipped file.** Every invariant, liquidus or activity quoted in a
   `PROVENANCE.md`, a table or a paper is recomputed from the written file with all its phases, and
   only stable equilibria count.
