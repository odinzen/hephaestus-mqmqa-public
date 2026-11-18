# Supplementary Material S2: A held-out test against measurements

## How the test was run

Measured values not used in any fit of the shipped databases were collected by a separate agent
that writes no Hephaestus code, under rules fixed before collection: the systems the databases
claim to cover, measured quantities only, every point a source reports, and sources not cited by
the database being tested. The collector sealed 480 values from seven sources and committed only
their conditions (compositions, temperatures, what was measured), with the SHA-256 fingerprint of
the sealed file. How each quantity would be computed was written into the rules before any
prediction; every point was then predicted from the conditions alone, as shipped and with the
liquid's ternary terms removed (the baseline), and the predictions and the scoring script were
committed before the values were opened. The sealed file was opened once and scored once. The
rules, conditions, predictions, scores and the scripts are in validation/literature in the
repository.

Two Xu 2018 salt points were excluded before predicting, because the KCl-MgCl~2~ fit cites a Xu
2018 eutectic that could not be shown to come from another paper.

## A prediction error found by the test

The first score showed activity errors above one log unit. They came from the prediction script,
not the databases: 158 of the 254 activity points measure CaO, AlO~1.5~ or MgO, as the conditions
file stated, but the script computed the activity of SiO~2~ for all of them. The rules allow a
code error found through the test to be fixed, with the first result kept and the corrected one
reported beside it. Both are given below; the correction recomputed only the activity points, and
its SiO~2~ values equal the first run's.

## Results

Errors are calculated minus measured.

Table S2.1: Activities against the pure solid oxide, root-mean-square error in log~10~ units.

| System | Points | Corrected | First result | Baseline (corrected) |
|---|---|---|---|---|
| CaO-Al~2~O~3~-SiO~2~ | 151 | 0.28 | 1.33 | 0.41 |
| CaO-MgO-SiO~2~ (quaternary database, FeO-free face) | 75 | 0.17 | 1.32 | 0.17 |
| CaO-SiO~2~ | 24 | 0.18 | 1.49 | 0.18 |
| MgO-SiO~2~ | 4 | 0.09 | 0.39 | 0.09 |

Silica activities are reproduced to 0.03 to 0.19 log units. Lime activities are too high in
every system, by about a factor of 1.8 on average, the shortfall Table 2 already states for the
CaO-SiO~2~ liquid. The CaO-Al~2~O~3~-SiO~2~ ternary terms lower the error from 0.41 to 0.28.

Table S2.2: The iron-saturated CaO-FeO-SiO~2~ face of the quaternary database, against Bowen,
Schairer and Posnjak (1933).

| Quantity | Points | RMS (K) | Median absolute (K) | Mean (K) |
|---|---|---|---|---|
| Liquidus | 85 | 79 | 69 | +58 |
| Solidus | 15 | 48 | 35 | -7 |

The liquidus is high in the wollastonite, olivine and rankinite fields (+48 to +90 K on average)
and low in the silica field (-28 K). This face carries no fitted terms (CaO-FeO is ideal), and the
databases hold neither Ca in olivine nor Fe in wollastonite, both present in the measured solid
solutions. The reported primary phase is reproduced at 58% of the liquidus points; that score is
not blind, because the conditions file named the phase.

The FeO-SiO~2~ heat of mixing at 1693 K (Ban-ya 1985, 25 points) is reproduced to 10.2 kJ/mol RMS:
the database is about four times too exothermic, -15 kJ/mol near 25% SiO~2~ against -3 to -4
measured. Its liquid term, -58.7 kJ + 40.3 T J, offsets a large enthalpy with a large entropy; it
was fitted to activities and the phase diagram, with no calorimetry, and reproduces those data but
not the measured heat.

None of the 23 named invariant points could be compared. Twenty name phases the databases do not
hold (akermanite, monticellite, merwinite-like 5CaO.2MgO.6SiO~2~, kirschsteinite, Ca-bearing
olivine) or polymorphs they do not distinguish; three name phases the database holds, but the
database predicts a different assemblage at that composition, and these count as misses.

The one scored salt point, the NaCl-KCl-MgCl~2~ solidus of Wang 2021, is 8 K low (baseline 29 K
high).

References for this supplement are added at the Zotero pass; until then each source's DOI is in
validation/literature/conditions_round1.csv.
