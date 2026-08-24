# Open oxide-slag database (Hephaestus data)

An open, citable thermodynamic database for oxide slags in the ChemSage `.dat` format
that the Hephaestus MQMQA engine reads. The first system is the CaO-SiO2 liquid slag.

This database is the open-data counterpart to the engine: no free MQMQA oxide-slag
database exists, so every commercial workflow depends on closed sources. The goal here is
a database whose every parameter is traceable to a published, openly available source.

## License

The data in this directory (the `.dat` databases and the derived tables) are licensed
under Creative Commons Attribution 4.0 International (CC-BY-4.0); see `LICENSE`. This is
deliberately different from the engine's MIT license: the engine is code, this is data,
and CC-BY is the appropriate instrument for a citable dataset. Attribution requirements
under CC-BY are met by citing this repository and the primary sources listed in each
system's `PROVENANCE.md`.

## Scope and status

- `cao-sio2/` - CaO-SiO2 liquid slag, MQMQA (ChemSage SUBQ). Version 0.1.
  - `CaO-SiO2-liquid.dat` - the database.
  - `build_dat.py` - the build script (computes every coefficient from open data).
  - `validate.py` - loads the `.dat` in the engine and checks it against published data.
  - `PROVENANCE.md` - the per-number source for everything in the `.dat`.
- `mgo-sio2/` - MgO-SiO2 liquid slag, MQMQA (ChemSage SUBQ). Assessed liquid; see its
  `PROVENANCE.md`.
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
