# Held-out literature test: rules

Fixed before any measured value is collected. Changes after unsealing are listed at the end.

## Roles

- Collector, round 1: a separate AI agent that writes no Hephaestus code and edits no database,
  launched with Michael E. Bustamante's approval on 2026-11-14. It finds the measurements, fills
  the template and seals the file. Michael may add later rounds himself, each with its own
  round name and seal.
- Code side (everyone else, including AI sessions): sees only `conditions.csv` (compositions,
  temperatures, what was measured, sources) until the predictions are committed.

## Which systems

The open databases Hephaestus ships, and only where the database claims to apply:

- Oxide slags: CaO-Al2O3-SiO2, FeO-MgO-SiO2, CaO-FeO-MgO-SiO2 (iron-saturated, Fe2+ only), and
  their binaries Al2O3-SiO2, CaO-Al2O3, CaO-SiO2, FeO-SiO2, MgO-SiO2.
- Chloride salts: NaCl-KCl-MgCl2 and its binaries, LiCl-KCl.

Measurements inside ternary and quaternary compositions come first, because that is where a
database extrapolates. Binary measurements count if their source was not used in the fit.

## Which measurements

Measured, not calculated: liquidus and solidus temperatures, invariant (eutectic, peritectic)
temperatures and compositions, compositions of coexisting phases, activities, and enthalpies of
mixing or solution.

## Which sources

- A source is eligible if it reports measurements in one of the systems above and is not used
  in that database's fit. `USED_SOURCES.txt` lists the sources the databases cite. If unsure,
  include it; the code side checks every flagged source against the provenance files and
  excludes it by this rule before unsealing, with the reason written down.
- Take every point the source reports for the system, not a selection. Values read off a figure
  are marked `digitized = yes`.
- Choose sources without looking at how the Hephaestus calculator does at those compositions.
- Stop when at least 5 sources and 100 points are in, or on a date the collector sets, whichever
  comes first. Sources found later go into a second round with its own seal.

## How to fill and seal

1. Open `template.csv` in Excel, delete the example row, and add one row per measured point.
   Composition as `CaO=0.25; Al2O3=0.15; SiO2=0.60`, with the basis (mass or mole fraction).
   For a measured temperature, leave `T_K` empty and put the temperature in `value`.
2. Save as "CSV UTF-8" under any name, for example `my_values.csv`, in this folder.
3. In a terminal opened in this folder, run `python seal.py my_values.csv round1` (a new round
   name for each seal). It writes `conditions_round1.csv` (values removed), copies the full file
   into `../sealed/`, and prints the fingerprint (SHA-256).
4. Tell the code side it is sealed. The fingerprint gets committed; the code side never opens
   `../sealed/`.
5. Keep your own copy of `my_values.csv` anywhere you like, unchanged.

## Scoring (fixed now)

- Temperatures: root-mean-square and median absolute error in K; fraction of points within the
  stated measurement uncertainty (or 10 K where none is stated).
- Activities: root-mean-square error of log10(activity).
- Enthalpies: root-mean-square error in kJ/mol.
- Phase identity: fraction of liquidus points where the calculated primary phase is the one
  reported.
- Baseline: the same database with its ternary and higher-order terms removed, so the liquid is
  extrapolated from the binaries alone. Hephaestus is reported against the baseline, whichever
  wins.
- Every point is reported. A point the engine refuses or fails to converge on is listed as such.

## After unsealing

No rule, point or score changes. A database or code error found through the test may be fixed;
the first result stays in the record and the corrected one is reported beside it.

## Decisions recorded before predicting (2026-11-14)

- Round 1 sealed by the collector agent: 480 points from 7 sources, fingerprint
  237cd910dc4c696bb1b021f50076e0f6c5a25b99a237ac3ea2c025a441e73ec9.
- The `phase_or_species` column of liquidus rows names the reported primary phase, so the
  phase-identity score is not blind. It is reported, labelled as not blind; the prediction script
  does not read that column for liquidus rows.
- The collector flagged Xu 2018 (two NaCl-KCl-MgCl2 melting onsets). Before unsealing, the code
  side checks those against the salt provenance files and excludes them if a fit used them.
- The collector searched the local literature trove and its ledger, then the web, not Zotero or
  the OneDrive folders. Round 2 covers those and the paywalled papers listed in
  `COLLECTOR_NOTES_round1.md`.
- Coverage is thin for the chloride salts (3 points) and absent for LiCl-KCl, NaCl-KCl, NaCl-MgCl2
  and FeO-MgO-SiO2; round 1 scores only what it holds.

## How each quantity is read (fixed 2026-11-16, before predicting)

`predict.py` computes every row, with the general solver, from the conditions file alone.

- Database: the lowest-order shipped file that holds the system with its solids. CaO-SiO2 and
  CaO-Al2O3-SiO2 use CaO-Al2O3-SiO2.dat; MgO-SiO2 and FeO-SiO2 use FeO-MgO-SiO2-combined.dat;
  both CaO-FeO-MgO-SiO2 faces use CaO-FeO-MgO-SiO2-combined.dat; the salt points use
  NaCl-KCl-MgCl2.dat.
- Compositions: mass fractions become moles through the database's own atomic masses. Fe2O3
  counts as FeO by its iron, as the authors' diagrams recalculate it; FetO counts as FeO. The
  databases hold Fe2+ only and no metallic iron, so "iron-saturated" is read as FeO alone.
- Activity of SiO2 against pure solid SiO2: exp((mu_SiO2 - G_cristobalite)/RT), mu_SiO2 from the
  equilibrium at the stated bulk and temperature (whatever phases it holds), cristobalite being
  the databases' only silica phase.
- Liquidus: the highest temperature at which a solid is stable, scanned down from 3200 K in
  100 K steps, then bisected to 0.01 K. The primary phase is the solid stable just below it.
- Solidus: the lowest temperature at which liquid is stable, scanned up from 500 K the same way.
- Invariants (temperature, liquid composition, coexisting solid composition): the named solids are
  mapped to database phases (polymorphs the databases do not distinguish, a- and b-CaSiO3 or a-
  and b-Ca2SiO4, map to one phase; tridymite to cristobalite; Ca-Fe olivine to the Fe-Mg olivine,
  which holds no Ca; diopside to clinopyroxene; periclase to magnesiowustite). The bulk is the
  centroid of the named endmembers; its solidus is the invariant temperature and the first liquid
  its composition. Classes: `not_represented` when a named solid has no database phase
  (akermanite, monticellite, merwinite-like 5CaO.2MgO.6SiO2, kirschsteinite) or the named solids
  map to fewer than three phases; `wrong_assemblage` when the database has the phases but the
  bulk holds other solids below its solidus, which counts as a miss.
- Coexisting solid composition: the endmember cation's share of the non-Si cations in the mapped
  phase just below the invariant (1 for Fe2SiO4 in the Ca-free olivine of the CaO-FeO-SiO2 face,
  1 for CaSiO3 in stoichiometric wollastonite, 0 for Fe2SiO4 in larnite).
- Enthalpy of mixing (FeO-SiO2): H of the liquid alone at the stated composition, H = G - T dG/dT
  by central differences of 0.5 K, less that of liquid FeO and of cristobalite, per mole of
  FeO + SiO2.
- Baseline: the same file with every ternary term of the liquid (MQMX terms with a third ion) set
  to zero in memory.
- Scoring of compositions, which the scoring rules above do not name: the error is calculated
  minus measured in the reported unit (mass fraction of each oxide in the invariant liquid;
  fraction of the named endmember in a coexisting solid), and its RMS is reported per system.
  `score.py` holds every score and was committed with the predictions, before unsealing.
- Excluded before predicting: rows 478 and 479 (Xu 2018, NaCl-KCl-MgCl2). The KCl-MgCl2 fit
  uses a "Xu 2018" eutectic and fusion enthalpy without a DOI, and it cannot be shown to be a
  different paper; they are predicted and listed but not scored.

## Changes after unsealing

Unsealed on Michael's go, 16 November 2026; the sealed file's SHA-256 matched the committed one.
The first result is `score_round1.*`, unchanged; nothing below alters a rule, a point or a score.

1. `score.py` keyed the sealed values by a `row` column the sealed file does not have (seal.py
   adds it only to the conditions file, numbering rows by position from 1). It now numbers them the
   same way and stops unless every row's system, quantity, composition and phase column equal the
   conditions file's. A reading fault, found on the first run, before any score was produced.
2. A code error found through the test: `predict.py` computed the activity of SiO2 for every
   activity row, though 158 of the 254 name CaO, AlO1.5 or MgO in the conditions file
   ("CaO in liquid slag (reference: pure solid CaO)"). Those rows compared a silica prediction
   with another oxide's measurement. The corrected predictor computes the oxide each row names,
   against that oxide's pure solid in the database (a compound, or MgO as the endmember of
   magnesiowustite); its SiO2 rows equal the frozen ones exactly. Only the activity rows were
   recomputed (`predictions_round1_corrected.json`, scored in `score_round1_corrected.*`); the
   correction reads nothing the conditions file did not already hold.
