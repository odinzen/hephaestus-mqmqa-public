# MQMQA in XTDB: a proposed form

XTDB (B. Sundman et al., "XTDB, an XML based format for Calphad databases", Calphad 90
(2025) 102849, open access under CC BY-NC) lists `MQMQA` as one of three standard values of
a phase's `Configuration`. Its documentation (github.com/sundmanbo/XTDB, the version 0.16
text) defines how the quadruplets of an MQMQA liquid are declared and calls that definition
tentative. It defines no parameter identifiers for the pair Gibbs energies, the excess
terms, or the chemical groups, so an MQMQA assessment cannot yet be written in XTDB in a
form another program would read the same way. No program reads MQMQA from XTDB today.

This page states the form `python/mqmqa/utdb_xtdb.py` writes. It keeps everything the XTDB
documentation does define and fills the gap with the parameter identifiers of the uTDB
dialect (`docs/UNIFIED_TDB_SPEC.md`), so a uTDB file converts mechanically. It is offered
as a proposal to the XTDB authors, not as part of their format.

## What follows the XTDB documentation

- The phase: `<Phase Id="..." Configuration="MQMQA" State="L">`.
- Quadruplets as species with an `MQMQA` attribute: the ions, cations before the slash and
  anions after it, two of a kind separated by a comma, then one coordination number per
  ion in the same order. A pure pair adds a third number, its zeta (the documentation's
  FNN/SNN factor). The `Stoichiometry` attribute is left out, as the documentation allows.

```xml
<Species Id="SI+4/O-2" MQMQA="SI+4/O-2 2.7548876 1.3774438 1.3774438" MQSTOI="1 2 0 0 0" />
<Species Id="MG+2SI+4/O-2" MQMQA="MG+2,SI+4/O-2 1.390538233268252 2.729187363250205 1.3774438" />
```

## What is proposed here

- **The phase lists its ions**, cations on sublattice 1 and anions on sublattice 2, as a
  TDB ionic phase does, rather than listing quadruplets. The full set of quadruplets, and
  the default coordination numbers of those without a species, follow from the ions; the
  ion order also fixes the order a program reports them in.
- **Only quadruplets with stated coordination numbers are species**, as in a ChemSage
  `.dat` file, whose quadruplet table the XTDB documentation mirrors. The others take the
  model's default rule.
- **`MQSTOI` attribute** on a pure pair: the five-entry quadruplet stoichiometry row of the
  ChemSage file, kept so the conversion loses nothing.
- **Parameters keep their uTDB identifiers:**

| Parameter Id | Meaning |
|---|---|
| `MQG(PHASE,A:X;0)` | Gibbs energy of the pure pair A-X, per mole of salt formula |
| `MQX<c>(PHASE,A,B:X,Y;p,q)` | excess term, ChemSage code `<c>` (Q, G, B or R), exponents p and q |
| `MQXT<c>(PHASE,A,B:X,Y;p,q,r:C)` | the same with a third constituent C at exponent r |
| `MQGRP(PHASE,ION)` | chemical group of an ion, for the group-dependent interpolation |

Expressions, `LowT`, `HighT` and `Trange` work as for any XTDB parameter.

## Where it stands

`python -m mqmqa.utdb_xtdb IN.utdb OUT.xtdb` converts a uTDB file, and the reverse,
`python -m mqmqa.utdb_xtdb IN.xtdb OUT.utdb`, reads this form back. In Python:
`mqmqa.utdb_xtdb.utdb_to_xtdb(text)` and `xtdb_to_utdb(text)`.

`tests/test_utdb_xtdb.py` checks the three shipped uTDB files two ways. Each converts to
XTDB and back and reads as the same database, the MQMQA liquid included, to 14 significant
digits; since one module writes and reads the proposed form, this is a translation check
only. Separately, pycalphad-xtdb reads the converted files and pycalphad computes every
compound-energy-formalism and stoichiometric phase, magnetic ones included, matching this
engine on the source files to within 5e-12 relative. Planted changes to an excess term, a
coordination number and a Curie temperature are each caught.

pycalphad-xtdb 0.1.2 stops at quadruplet species that have no `Stoichiometry`, although the
XTDB documentation allows one to be left out; the test removes those lines before handing
the file to it. That reader leaves the MQMQA phase out with a warning.

## Sources

Read while writing the converter: the XTDB paper (open access, CC BY-NC) and the
documentation in github.com/sundmanbo/XTDB (GPL-3.0; documents and example databases, no
program code); no text or data from either is copied into this repository. The magnetic
model identifiers follow the writer of pycalphad-xtdb (Odinzen, MIT).
