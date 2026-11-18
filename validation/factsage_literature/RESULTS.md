# FactSage cases A, B and C: results

Unsealed 18 November 2026 on Michael's go. The predictions were committed first (case C in
6c60ce1, cases A and B in edfbe62) and the scoring script with its rules in 950c2fe. Then
`compare.py` ran once against `factsage_published.json`, whose SHA-256 matched the committed one.
Full table in `comparison.md`, raw rows in `comparison.json`. Nothing below changes a class.

| Case | What is compared | agree | disagree |
|---|---|---|---|
| A, ACl-ThCl4 (FactSage 7.2) | 15 invariants, T to the kelvin, 6 liquid compositions | 4 | 11 |
| B, (Li,Na)F-(La,Ce)F3 (FactSage 8.3) | 8 invariants, T to the kelvin, 6 liquid compositions | 2 | 6 |
| C, KF-NiF2 liquid at 1600 K (digitized) | 30 values of G, H and S | 30 | 0 |

## Case A

The three alkali chloride melting points and the alpha-beta transition of ThCl4 agree within
0.15 K. Every invariant that involves ThCl4 and the liquid comes out higher than FactSage's, by
0.5 to 2.2 K, and the liquid compositions differ by 0.0015 or less (a mole fraction). Under the
fixed rule an integer kelvin must be met within 0.5 K, so these are classed disagree.

Pure ThCl4 melting (A05) is 1.0 K high. It depends only on the beta-ThCl4 and ThCl4(l) data, and
the engine reproduces the transcribed table to 1e-6 J/mol (`check_cases.py`), so the offset is in
the printed parameters, not in the solver. Moving the melting point to 1042 K takes a change of
30 to 89 J/mol in the energy difference of the two phases (entropy of fusion 59 J/K/mol). The
table prints the enthalpy of beta-ThCl4 to 0.1 kJ (-1186.3 kJ/mol), so its rounding alone can be
up to 50 J/mol. A ThCl4 liquid that is slightly too unstable would also raise every liquid-bearing
invariant on the ThCl4 side, which is the sign seen. This is consistent with the printed
precision but not proven; the database FactSage used is not published.

## Case B

The two LiF eutectics (B01, B05) agree in temperature and composition. B02, B03 and B06 are
within 1.1 K and 0.004. Three results are far off, and all three involve the NaF-(La,Ce)F3
hexagonal solid solution or the compounds that decompose into it:

- B04, NaLaF4 = NaF + LaF3 eutectoid: 634.5 K against 686 K. With the reaction entropy near
  9.5 J/K/mol, 51 K is about 490 J/mol, ten times what the printed precision of NaLaF4 allows.
- B07, NaCeF4 peritectic: 8.4 K high, liquid composition 0.013 high.
- B08, NaCeF4 = NaF + CeF3 eutectoid: FactSage gives 226 K, below 298.15 K where every Cp range
  starts. The engine scans from 298.15 K and finds NaCeF4 already stable there, so it reports
  nothing. Carrying the 298.15 K enthalpies and entropies down unchanged puts the pure-compound reaction
  near 215 K, so the two codes are not far apart below the range, but the rule classes it
  disagree.

This points at how the hexagonal phase was read, which `conditions.json` flags as inferences made
before unsealing: the paper does not define its chi subscript notation, and the NaF end member of
the hexagonal phase was taken to be NaF(alpha). Rechecked after unsealing; see below.

### Recheck of case B (18 November 2026, after unsealing)

The paper (OSTI 3367480, filed in Juno) was read from rendered page images.

- Transcription. Every value in Tables 1, 2 and 3 used for these binaries matches
  `conditions.json`, Cp coefficients and ranges included. The paper's own figure of 1.95 kJ/mol
  for the formation enthalpy of NaCeF4 from NaF and CeF3 comes out of the transcribed values
  (1.952 kJ/mol).
- Reading. Eq. 4 defines the solid solution excess as a single-sublattice polynomial in site
  fractions, sum of Y_A^i Y_B^j L^ij, which is what the files carry. The engine's hexagonal excess
  equals the printed polynomial to 0.03 J/mol at four compositions in each binary.
- A check the paper prints in its text, not part of the sealed set: FactSage's largest NaF
  solubility in the hexagonal phase is 0.091 mole fraction in LaF3 and 0.089 in CeF3. The files
  give 0.080 (at 1056 K) and 0.067 (at 1088 K). Raising them to the paper's values would take the
  NaF potential in the hexagonal phase about 1.1 kJ/mol lower in LaF3 and 2.5 kJ/mol lower in
  CeF3, so no single shift of the NaF(alpha) end member does both.

The printed model, read as the paper defines it, does not reproduce the paper's own hexagonal
solubility, and this one fact accounts for the direction of B04, B07 and B08. Something the
FactSage run used is not in the printed tables (as with the LiF-NaF parameters, which the paper
also leaves out), or the hexagonal phase is set up in a way the text does not state. Hephaestus
calculates the printed model correctly; the case B misses are a limit of the source. No reading
was fitted to the unsealed numbers, and the classes stand.

## Case C

All 30 values lie within the stated read uncertainty (1.0 kJ for G, 0.8 kJ for H, 0.15 J/K for
S). The differences in G and H are all zero or positive, up to 0.6 kJ per mole of atoms, and in S
0.004 to 0.095 J/K. Digitized points cannot resolve more than this.
