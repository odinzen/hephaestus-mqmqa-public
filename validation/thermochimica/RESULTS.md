# Hephaestus against Thermochimica: result and referee

The sealed Thermochimica values were opened once, on Michael's go, on 15 November 2026, and
`compare.py` was run once against the frozen predictions (commit 1d55633, engine 66560d7). Its
output, `comparison.md` and `comparison.json`, was committed unedited (304e892). Everything below
that line is analysis after unsealing and is not blind.

## The blind score

Against Thermochimica's own runs, 308 points (63 test conditions and 245 extended-grid points):

| Class | Points |
|---|---|
| agree (total Gibbs energy within 1e-6 relative, same phases) | 125 |
| close (within 1e-4) | 14 |
| disagree | 62 |
| refused by Hephaestus | 107 |

The 107 refusals were all declared before unsealing: 10 invalid inputs that Thermochimica's tests
also refuse, 1 test that edits the database in memory, 30 FeTiVO points (chemical-group overrides),
6 points of a SUBI file with an ambiguous term, and 60 SUBM points (format not documented).

Against the reference values written in Thermochimica's test programs (63 conditions): agree 13,
close 13, disagree 10, refused 27.

## Who was right: the referee

`referee.py` judges each code by its own model. Each disputed answer is split into its phases and
each phase's element amounts are given to the other code as a problem of its own; the pieces add up
to the original bulk, so their summed energy is a state the pricing code's own model allows.
A sum below a code's own answer means that code missed a lower state of its own model. Results in
`referee.md` and `referee.json`; the Thermochimica runs are in `referee_runs/`.

The 76 points classed close or disagree, by cause:

| Cause | Points | Tests | What it is |
|---|---|---|---|
| Thermochimica missed a lower state of its own model | 15 | 30 (2 grid), 31, 64, 65 (1 grid) | Miscibility gaps the files give one copy of the phase for. Thermochimica, on Hephaestus's sets, prices them within 0.6 J of Hephaestus and 4.7 J to 394 kJ below its own answer. For 31 and 64 Thermochimica's own test programs assert the single-set values. |
| Probably the same, not confirmed | 6 | 32 | Hephaestus opens a three-set gap 25 MJ below; Thermochimica fails on the pieces, so it cannot price them. |
| Hephaestus missed a lower state of its own model | 4 | 55 | Hydrogen dissolved in two BCC sets instead of forming H2 gas at 1000 atm. Fixed after unsealing (below). Thermochimica also missed here, by 2.05 kJ of its own model. |
| Gas reference pressure | 1, and part of 55 and 62 | 90 (grid 5) | Thermochimica takes the data's gas energies at 1 bar, Hephaestus at 1 atm: a constant RT ln 1.01325 per mole of gas (shown by running Thermochimica on pure H2 at 0.986923 atm, where it equals Hephaestus at 1 atm). |
| Above a species' last temperature range | 14 | 73, 74 (2 grid), 76 | Hephaestus read a ChemSage species as zero above its last range (as pycalphad's MQMQA liquid does); Thermochimica extends the last range. CsTe-2 Te ends at 1600 K, CaMnS and FeMnCaS liquid endmembers at 2000 K. |
| Order of a mixing pair in odd Redlich-Kister terms | 4 | 56 | Hephaestus sorts the pair by name (as pycalphad does), Thermochimica keeps the file's order. CuFeC-Kang fcc Fe,Cu L1 = -1882.8: the sign flip is worth exactly the 103 J seen at 3% Cu. Declared as a possible difference before unsealing. |
| Al-rich salt-metal liquid of ClAlNa | 12 | 62, 63 | A reading difference of 0.6 to 1.7 kJ in the SUBQ liquid where Al, the Al2 dimer and the vacancy mix. Pure NaCl liquid and pure Al agree to the millijoule. Not resolved; this liquid had no independent check before either. |
| Same energy, different phase name | 6 | 71 | HCP_A3 and HCP_ORD at 0.03 J of each other. |
| Input checking | 1 | 03 | The test omits units and expects a refusal; Hephaestus's driver took moles. |
| Small, not traced | 13 | 30 (3), 74 (4), 77 (6) | 0.7 to 1 J of 0.46 MJ (30), 63 J (74 at 1700 to 1900 K), 2 to 3 J (77, ionic liquids). |

## Changes made after unsealing

Not blind; the frozen predictions and the comparison above are unchanged by them.

- `src/gem.c` sampling. A phase whose composition grid exceeds the 4000-point cap was sampled
  by listing the grid in order and stopping, which kept one corner only: the 29-species gas of
  ZIRC-noSUBI never had a point near H2, and the final certificate, which searches a phase from
  its own samples, skipped it. Past the cap a phase now gets its corners, points 90/99/99.9% of
  one constituent, pair midpoints and uniform random points; phases under the cap are sampled
  exactly as before. TestThermo55 then gives -51733.23 J (was -44893.51); Thermochimica, on each
  of the new sets, returns the same single phase and prices the whole at -51717.19 J, the 16 J
  being the gas reference. Guard: `tests/test_gem.py::test_gas_of_many_species_is_sampled_at_every_corner`
  (fails on the old sampler).
- `src/gem.c` certificate. A result whose final certificate still finds a state more than
  1e-3 J/mol below it is now refused instead of returned (NaCl at exactly 1:1 and 1200 K in
  ClAlNa came back as the solid with the liquid 1463 J/mol below). Guard:
  `test_a_failed_certificate_is_refused_not_returned` (skips without Thermochimica's data folder).

## Reading rules decided after unsealing (Michael, 15 November 2026)

None changes a number of any shipped database: no shipped ChemSage file has a gas phase or data
ending below 6000 K, and all 17 shipped sublattice phases give identical energies under either
pair order (checked with a build that kept the file's order).

1. ChemSage gas data refer to 1 bar: each species gains R T ln(P / 1 bar). Thermochimica's pure
   H2 at 0.986923 atm equals the record. Gas data that state another reference keep it (the
   separate NASA gas module stays at 1 atm, the reference of its data).
2. A mixing pair keeps the file's order, never sorted by name. The ChemSage sublattice reader
   sorted it, as pycalphad does, without changing the sign of odd terms; the TDB reader sorts
   but flips odd terms, which keeps the file's meaning and is left as it is.
3. Above the end of a species' data the last range is carried on, as Thermochimica does, and the
   result lists each species so used with where its data end (`beyond_data`). pycalphad 0.11.2
   is not consistent here (checked): it carries the last range on in TDB files and ChemSage
   one-lattice phases, but takes zero in its MQMQA liquid (Shishin's Sb2O3 drops from -569 kJ at
   1728 K to -0.5 J at 1730 K). The writers no longer add a zero range above the data. Thermo-Calc's behaviour was not found documented; FactSage's
   pure-substance documentation is reported to hold Cp constant above the last range (not opened).

After these, the cases behind them: CsTe-2 at 2500 K within 0.05 J of Thermochimica (was 9.8 kJ;
Te flagged as used above 1600 K), CuFeC fcc within 5 mJ (was 103 J), H2 gas within 1 mJ at 1 atm.
At Cs:Te = 1:3 Hephaestus is 686 J below Thermochimica with two liquids, which Thermochimica, on
the two pieces, prices within 0.1 J of Hephaestus: one more gap it did not open.

## The same points after the fixes and rules (post hoc, not blind)

`post_unsealing/`: the engine of 39b9566 predicted every point again and `compare.run` scored it
against the same sealed values, written to its own folder; the blind files above are untouched.

| Class | Blind | After |
|---|---|---|
| agree | 125 | 141 |
| close | 14 | 17 |
| disagree | 62 | 43 |
| refused | 107 | 107 |

No point that agreed before disagrees now. The 43 left: 24 where Thermochimica missed a lower
state of its own model (30 grid 1-2, 31, 55, 64 confirmed by the referee; 32 likely), 12 ClAlNa
(Al-rich liquid, unresolved), 6 the HCP_A3 / HCP_ORD tie, 1 the units check. Resolved: 56 (pair
order), 73 and 76 (last range), 74 grid 4-5 (now 63 J, close), 90 grid 5 (gas reference). At 55
Hephaestus is now 1.3 to 2.0 kJ below Thermochimica, the state the referee confirmed.

The engine of 28cca36 (face reduction, SUBI liquid of neutrals, exact finish on everywhere)
predicts all 308 points again with every class and every computed energy bit for bit as in
`post_unsealing/` (201 computed, largest difference 0 J), so that folder stands for it too.

## The Al-rich ClAlNa liquid, traced (16 November 2026)

Probing sub-systems at 1300 K: pure Al, pure Na, Na-Al and Na-NaCl agree with Thermochimica to
0.05 J or better; Al-AlCl3 (Al3Cl, AlCl) does not, Hephaestus 1.9 to 5.7 kJ higher. Thermochimica
prints the coordination numbers it uses for every quadruplet, and they equal Hephaestus's
exactly. At Thermochimica's own quadruplet distribution Hephaestus's energy is 12.2 kJ higher
(Al3Cl), so the two evaluate the same structure differently, with every excess term zero.

The cause is how a quadruplet mixing two anions (here Cl and the metal vacancy) is counted in the
reference energy. Hephaestus, following pycalphad, apportions it by the cation's coordination
number: Al-Al/Cl-Va counts 0.1875 AlCl3 + 0.1875 Al, which holds 0.5625 Cl where the quadruplet
holds 0.625. Apportioned by the anions' coordination numbers it is 0.208 AlCl3 + 0.167 Al, which
conserves every element, and 19.3 kJ per quadruplet lower. The two readings coincide when the
coordination numbers are equal (Na, the Al2 dimer), which is why Na-NaCl agrees, and in every
liquid with one anion: no shipped database (all have O or Cl alone) is affected.

The anion-weighted reference brings Al3Cl from 12.2 kJ to 0.4 kJ of Thermochimica and keeps
Na-NaCl at 0.04 J, but it is not exact, and with Na present it overshoots, so the pair fractions
in the entropy and the fully reciprocal quadruplets carry the same question. Not changed: the
answer has to come from Pelton, Chartrand and Eriksson (2001), Part IV, doi 10.1007/s11661-001-0230-7,
which defines these energies, not from fitting another code's output. The same holds for
pycalphad's multi-anion liquids (Shishin's Fe-Sb-O-S slag, where Hephaestus and pycalphad agree).

## Found while refereeing, and what became of them (16 November 2026)

- ClAlNa at Na:Cl = 1:1.0001 and 1080 K: "no phase combination reaches this bulk composition".
  Not a fault. Without Al, the file's only phase richer in Cl than NaCl is Cl2 gas, which it marks
  as a dummy; Thermochimica, run on the same input, also stops ("not representable in terms of the
  available species").
- ClAlNa Na + Al + 4 Cl (NaAlCl4) at 1200 K: the linear program failed. Fixed. The bulk lies on
  the plane Cl = Na + 3 Al with every phase on or below it, so metal-bearing states have zero
  amount, but their samples sat a hair off the plane and made the solver's bases singular. The
  solver now finds such a face by a linear program before sampling and holds those constituents
  at zero (docs/GENERAL_EQUILIBRIUM.md, item 9). NaAlCl4 gives liquid + gas, -1579342.18 J against
  Thermochimica's -1579342.15 J, and NaCl at exactly 1:1 now melts: liquid at 1080 and 1200 K
  equal to Thermochimica's to 1e-10 J (at 1200 K it had been refused). At 1050 K Thermochimica
  returns a liquid 622 J above Hephaestus's solid NaCl, which melts at 1074 K.
- A SUBI liquid was dropped when its cation's element was absent. Fixed: with only neutrals on the
  second sublattice P = 0 and the liquid is the neutrals alone (Sundman 1991), so pure Te in CsTe-2
  is liquid, the limit of the liquid with a trace of Cs. Thermochimica leaves this phase out too
  ("no phases remaining"), so pure Te has no Thermochimica value to compare.
