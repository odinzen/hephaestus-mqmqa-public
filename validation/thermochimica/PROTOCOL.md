# Cross-check against Thermochimica: protocol

Written and committed before any comparison is run. Changes to this file after the
first unsealing are listed at the end with their date and reason; nothing above that
list changes.

## Why

Hephaestus's MQMQA energy is a C translation of pycalphad's model, so agreement with
pycalphad shows the translation is faithful and nothing more. This check compares
Hephaestus with codes that are not derived from pycalphad:

- Thermochimica (ORNL-CEES/thermochimica, BSD-3-Clause, commit
  1c076b20f958be65bac750f00af2e59ef4f28d9e of 2026-10-27), built with gfortran 16.2 and run
  as an external program. Its own suite passed 65 of 65 on this build.
- The reference values that Thermochimica's test programs hold, where the program states
  their source (FactSage or another code).
- Published FactSage results (collected separately, see `../factsage_literature/`).

## What keeps the check independent

- Thermochimica's source (`src/`) is not opened while Hephaestus code is written. Only its
  executables, input files, test programs (for conditions) and data files are used. If its
  source is ever opened for any reason, that is recorded here and in NOTICE, and the cases
  touched by what was read are reported as translation checks, not independent ones.
- Where Hephaestus needs the ChemSage grammar of a phase type it does not yet read, the
  source consulted (pycalphad's `io/cs_dat.py`, already credited in NOTICE, or the data
  files themselves) is recorded in the commit and in NOTICE.

## The sealed envelope

1. A separate agent, which writes no Hephaestus code, reads Thermochimica's test programs and
   writes two files:
   - `conditions.json` (committed, readable): for each test, the database, temperature,
     pressure, element amounts, and what quantities the test checks.
   - `expected.json` (sealed): the reference values and their stated source.
2. The same agent runs Thermochimica on every condition plus an extended grid (below) and
   writes its results to `thermochimica_results.json` (sealed).
3. Sealed files are stored outside the repository, in
   a folder on the author's machine (`SEALED_DIR` in the scripts). Only their SHA-256 hashes are
   committed (`SEALED_HASHES.txt`) before Hephaestus is run on any condition.
4. Hephaestus runs every condition and writes `predictions.json`, which is committed together
   with the engine fingerprint. The comparison script `compare.py` is committed in the same
   commit.
5. Then the sealed files are copied in, their hashes checked against the committed ones, and
   `compare.py` runs once.

The session writing Hephaestus code does not open the sealed files before step 5. That cannot
be proven from the record alone; the commit order and hashes show what was fixed when.

## Extended grid

For each Thermochimica database containing a phase that Hephaestus models, at the composition
of each test: 5 temperatures spaced evenly from 200 K below to 200 K above the test
temperature (within the data's validity range). This adds conditions that no test author
tuned against.

## What is compared

- The stable phase assemblage (names of phases present).
- The total Gibbs energy of the system (J).
- Moles of each stable phase.
- Element chemical potentials (J/mol).

## How results are classed (fixed in advance)

| Class | Rule |
|---|---|
| agree | same assemblage, relative Gibbs energy difference below 1e-6, phase amounts and chemical potentials within 1e-4 relative or 1e-6 mol / 1 J/mol absolute |
| close | same assemblage, relative Gibbs energy difference below 1e-4 |
| disagree | different assemblage, or anything larger |
| refused | Hephaestus declines the database or phase, with the reason it gives |
| failed | Hephaestus crashes or fails to converge without a reason |

Against FactSage reference values the same classes apply, except that a value printed with
fewer significant figures is compared to the digits printed.

Every case is reported in one class. None is dropped.

## After unsealing

- No condition, tolerance or class rule changes.
- A bug found through the comparison may be fixed. The result before the fix stays in the
  record and the paper; the result after it is reported separately as corrected after
  unsealing, never in place of the first.

## Changes after first unsealing

(none)

## Notes recorded before unsealing (2026-11-14)

- None of Thermochimica's test programs states where its reference values come from; none
  cites FactSage or another code. The sealed `expected.json` is therefore treated as
  Thermochimica's own reference results, a second Thermochimica source beside
  `thermochimica_results.json`, not as FactSage values. FactSage numbers come only from
  published papers (`../factsage_literature/`).
- 63 of 70 test programs became conditions (7 skipped: MSTDB database not shipped, a timing
  demo with a missing file, two missing-file tests). 11 are input-validation tests that
  Hephaestus should also refuse; they are scored as refusals, not as Gibbs energy comparisons.
- The extended grid has 246 run points (4 below 298.15 K not run).
- `sealed/thermochimica_raw/` is fixed by `RAW_OUTPUT_MANIFEST.txt` (per-file hashes).
- Expected source of disagreement, noted before any comparison: Hephaestus orders a SUBL
  (and SUBLM) pair mixing on one sublattice by constituent name, as pycalphad does, so where a
  file lists the pair in another order (CuFeC-Kang's FCC_A1 lists Fe before Cu) an odd-order
  Redlich-Kister term takes the opposite sign from the file's order. RKMP terms keep the file's
  order. If Thermochimica disagrees on such a phase, this is the first suspect; it is not changed
  before unsealing.
- SUBI (two-sublattice ionic liquid) is written from Sundman, Calphad 15 (1991) 109, the paper
  ChemApp's documentation cites for it. Expected sources of disagreement, noted before any
  comparison: (1) a binary's odd Redlich-Kister orders take the file's order of the pair; (2) a
  reciprocal term with an anion takes eq. 37's order (odd orders on the anion pair, even on the
  cation pair); (3) the two vacancy terms follow the paper's rule of pairs, where pycalphad's
  ionic liquid carries one more factor y_Va. ZIRC_no_liq_mod2 is refused: its term of two
  cations with Va and a neutral has three parameters, which the paper's eqs. 34 and 37 read
  differently.
- QKTO (Kohler polynomial solutions) is written from Pelton, Calphad 12 (1988) 127, the paper
  ChemApp's documentation cites for it. Expected sources of disagreement, noted before any
  comparison: (1) a ternary term inside four or five components takes Kohler's weights
  (eq. 12), s^3 times three ratios, not the plain product of mole fractions; (2) above a
  record's last temperature its energy is zero (ChemApp's convention). FeTiVO now reads, but
  its SLAGBSOLN liquid carries chemical-group overrides that the quadruplet engine does not
  model, so its conditions are refused unless that phase is suspended.
- SUBM stays refused (decided by Michael Bustamante, 14 November 2026, before any comparison): the model is Pelton's (Calphad 12 (1988) 127), but how a ChemSage file records its excess terms is documented nowhere that may be read for this check: not in that paper, not in ChemApp's or Thermochimica's manuals, not in FactSage's public notes, and pycalphad does not read SUBM at all. The one file that uses it (ZrFeKClNaFOLi, a synthetic test) admits at least two readings of its records, which differ in whether a binary term's powers count from 0 or from 1, and the only source that would settle it is Thermochimica's code, which this check keeps closed. ZrFeKClNaFOLi's 10 tests (TestThermo80-89) and their 50 extended-grid points are reported as refused for this reason.

## How each quantity is read (fixed 15 November 2026, before unsealing)

Written with `compare.py` and before any sealed file was opened. The sources read for it are
Thermochimica's user manual (`doc/thermochimica_user_manual.pdf`, sections 2 and 3.5-3.6),
`doc/plotGUI.md`, the key names and the G-to-potential ratio of the example output Thermochimica
ships (`outputs/c-o.json`, not one of these conditions), and this folder's `run/` scripts for the
layout of the sealed files. No Thermochimica source code and no sealed file.

- Phase names are matched after folding case, spaces and underscores; Thermochimica's `NAME#n`
  instances of one phase are paired with Hephaestus's sets of that phase by closest composition.
  A phase is stable in Thermochimica's result when it reports moles > 0, with no threshold.
- Total Gibbs energy is Thermochimica's "integral Gibbs energy" (J) against Hephaestus's G per
  mole of atoms times the moles of atoms in the system.
- Phase amounts are compared in moles of atoms: Thermochimica's raw output lists the moles of
  each element in each phase, and their sum is the phase's atoms. A test program's phase amount
  is Thermochimica's dMolesPhase, which the manual (eq. 1) counts in the phase's own species or
  formula units; Hephaestus's atoms are converted to that unit with the moles-per-atom ratio
  that Thermochimica's own run at the same condition reports for that phase.
- Element chemical potentials are Thermochimica's "element potential" in J/mol (in the shipped
  example the integral Gibbs energy equals the sum of element moles times these potentials to
  1e-15). That sum is reported for every point, so a unit slip on either side is visible.
- Against a test program's values, "same assemblage" means every phase the test names (in a
  phase-amount check, or BCC_A2 in TestThermo64) is present; the tests list no full assemblage.
- Test checks of species mole fractions (49), site fractions (50), heat capacity (20) and the
  magnetic properties (6) are not among the four quantities above. They are listed as not
  compared, with their reference values, and do not enter any class.
- Where Thermochimica returned no result, the point is counted as "no reference", apart from
  the five classes.
- For the 11 input-validation tests a Hephaestus refusal is the required outcome and is marked
  so; computing a result for one would be "disagree". Reading the parse-only test's file is
  "agree".
- `compare.py` checks every sealed file against its committed hash before using it and will not
  run a second time over an existing result. `tests/test_thermochimica_compare.py` runs it on
  invented sealed files that reach every class and on tampered files.
- Where every stable phase is a compound and their compositions do not fix each element's
  potential (solid CsI alone fixes mu(Cs) + mu(I), not the split), the potentials are compared
  through what the phases fix, the plane's height mu.x at each stable composition, with the same
  tolerance. A test program's check of one such potential is listed as not compared.
- Two instances of one phase within 0.002 of each other in every element fraction are counted
  as one set, on both sides. A ChemSage file lists a phase twice for a possible miscibility gap,
  and where none opens both copies can hold an amount at one composition. Hephaestus merges
  them the same way.

## Engine changes made before freezing (15 November 2026)

A trial run of every condition, made before any sealed file was opened, showed reported
chemical potentials that were loose where a phase holds a dilute constituent. The engine was
changed before the predictions were frozen, and checked only against independent solutions,
never against a Thermochimica value.

- The CsI gas at 1e-5 atm (TestThermo90, grid point 5) was 769 J/mol from the exact mass-action
  solution of its own ideal gas. At the 51 test points where the answer is a single phase whose
  tangent at the bulk can be computed directly, 17 were more than 0.5 J/mol off (worst 16.6).
- The solver now finishes by solving the equilibrium conditions exactly (Newton) when every
  stable phase is a compound or a one-lattice solution, stops at 1e-6 J/mol below the plane
  instead of 1e-3, and merges same-named copies of a phase. After the change the CsI gas matches
  mass action to 0.0001 J/mol and the 51 points match their tangents to 1e-4 J/mol. Shipped
  liquids are unchanged bit for bit (146 points) and a sample of 48 Figure 3 cells is unchanged.
- Expected source of disagreement, noted before any comparison: phases with more than one
  sublattice, the MQMQA liquid and SUBI keep potentials from the sampled plane. Between stopping
  settings these moved by up to about 1e-4 of their value at the test points (ZIRC-noSUBI,
  ZIRC-test64), the size of the agree bound, so a "close" from potentials alone there is
  expected from the solver, not the model.

## Predictions frozen again before unsealing (15 November 2026)

Michael Bustamante asked, before any sealed file was opened, that the expected source of "close"
results named in the previous section be removed rather than recorded. The predictions of commit
37bb27e were replaced by those of the engine at commit 66560d7, with the sealed folder still
unopened. 37bb27e stays in the history and was never compared with anything.

- Every kind of stable phase is now finished exactly: sublattice phases of any shape, the SUBI
  ionic liquid, the MQMQA liquid (its quadruplets as species) and charge-balanced oxide systems.
  All 201 computed points finish exactly (`exact_finish` in predictions.json).
- Three faults found on the way changed results. In ClAlNa (TestThermo63 and its five grid points)
  a sampled liquid whose fixed-composition solve had missed its composition by 0.26 entered as a
  second liquid and pulled the total Gibbs energy 1.0 to 1.3% too low; the fixed result has a small
  Al-rich metallic liquid, or none. In FeMnCaS-1 the two phases named IONIC_LIQ are different
  phases (48 kJ/mol apart), not copies, and are no longer merged. The previous freeze would have
  scored TestThermo63 on a solver fault.
- Checked against solutions that share no code with the finish (validation/thermochimica/
  solver_checks): all 314 sublattice-phase and ionic-liquid sets agree with their own internal
  equilibrium found from scratch within 0.01 J/mol; the 8 ideal gas sets meet mass action to
  2e-14; the 51 single-phase points match the tangent at the bulk to 1e-4 J/mol; the CuFeC-Kang
  liquid matches pycalphad to 1e-4 J/mol. Shipped liquids are unchanged bit for bit and a sample of
  48 Figure 3 cells is unchanged.
- The expected source of disagreement for multi-sublattice, MQMQA and SUBI potentials noted in the
  previous section no longer applies.
- Limits that remain, noted before any comparison: ClAlNa's liquid (Al2 dimer and vacancy anion)
  has no independent check of its model reading, as pycalphad reads the file differently, so a
  disagreement there may come from the reading; a compound standing alone fixes only a sum of
  potentials (compared through mu.x, as fixed above); potentials of a phase with fewer than 1e-15
  free atoms cannot be resolved in double precision by any code.

## Unsealed, 15 November 2026

On Michael's go the sealed folder was opened and `compare.py` run once, against predictions
1d55633 (engine 66560d7); its output was committed unedited in 304e892. Every change and every
reading of the result after that commit is post hoc and is recorded as such in RESULTS.md, with
the referee (`referee.py`) that judges each code by its own model. The frozen predictions and the
committed comparison are never regenerated over.
