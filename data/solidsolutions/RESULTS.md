# SevenNet-predicted Fe-Mg mixing excess for the ship-ideal CEF solid solutions

The combined slag database carries olivine and orthopyroxene as solid solutions and treats
spinel and clinopyroxene as ideal, because no open Fe-Mg mixing calorimetry exists for those
joins. This campaign supplies the missing excess from a foundation MLIP (SevenNet-0), using the
protocol that olivine calorimetry validates. All values are **MLIP-predicted, not measured**.

## Method

Identical to the olivine control (`../olivine/_mlip/VALIDATION.md`). For each mineral the pure-Mg
end-member structure is taken from the Crystallography Open Database, Fe is substituted for Mg on
the mixing sites (Ca, Al, Si, O fixed), a handful of orderings per composition are relaxed with
SevenNet-0 (cell + positions, 0 GPa) and averaged, and H_mix(x) is taken as a difference against
the two end members so any constant MLIP offset cancels. Reported as Redlich-Kister L0, L1 per
formula unit. Scripts: `_mlip/campaign.py`, `_mlip/cpx_firmup.py`. Structures: `_mlip/cif/`.

**Superseded 2026-09-22 by special quasirandom structures (SQS).** Averaging a handful of random
orderings in one unit cell turned out to be the weak step. On olivine it scattered by about
1 kJ/mol per ordering, and an 8-site cell cannot hold a random arrangement at x = 0.5 at all (see
`../olivine/_mlip/VALIDATION.md`). The joins were re-run on icet 3.0 SQS cells at 16 and 32
mixing sites (plus 64 for orthopyroxene), same model, same relaxation, same end members
(reproduced to 0.1 meV/formula). Orthopyroxene has two site classes (M1, M2), so its SQS were
annealed with Fe split evenly between them; unconstrained, the annealer drifted to a partly
ordered 32-site cell. Scripts, cells and logs: `_sqs/`. The tables below give both.

Endmember sources (COD): forsterite 1572966, spinel 1010129 (MgAl2O4, Fd-3m), diopside 1000007
(CaMgSi2O6), enstatite 1000047 (Mg2Si2O6).

## Control

Olivine, run through the identical script, reproduces the measurement and the prior SevenNet run:

| | L0 | L1 | H_mix @ x=0.5 |
|---|---:|---:|---:|
| Wood & Kleppa 1981 (measured) | 12552 | 4184 | +3138 |
| SevenNet-0, ordering average (this run) | 9746 | 1107 | +3168 |
| SevenNet-0, SQS 32 sites | 12213 | -3803 | **+3001** |

With SQS the olivine L0 is within 3% of the measurement and the RMS over the join is 617 J/mol
(861 for the ordering average), which bounds the systematic error of the approach. The 30 J/mol
agreement at x = 0.5 of the ordering average was partly luck. SevenNet gets the sign of L1
wrong on olivine, so L1 is the least trustworthy output on every join.

## Results (MLIP-predicted, J/mol per formula unit)

SQS, largest cell (32 mixing sites; 64 for orthopyroxene):

| Solid solution | Join | x = 0.25 | x = 0.50 | x = 0.75 | L0 | L1 |
|---|---|---:|---:|---:|---:|---:|
| Spinel | MgAl2O4-FeAl2O4 | -2611 | **-3186** | -2257 | -12868 | 1888 |
| Clinopyroxene | Di-Hd | -765 | **+792** | +1301 | 2248 | 11014 |
| Orthopyroxene | En-Fs | +1765 | **+2693** | +1898 | 10241 | 709 |

Convergence in cell size (largest change between the two biggest cells, any composition):
spinel 194, orthopyroxene 183, clinopyroxene 598 J/mol (at x = 0.5; the 32-site cell matches
the random correlations exactly, so it is the value to use).

Earlier ordering average, for comparison:

| Solid solution | Join | L0 | L1 | H_mix @ x=0.5 |
|---|---|---:|---:|---:|
| Spinel | MgAl2O4-FeAl2O4 | -14732 | 2558 | -3739 |
| Clinopyroxene | Di-Hd | 610 | 9244 | +327 |
| Orthopyroxene | En-Fs | 10726 | 4989 | +1707 |

Signs are physically sensible as a set: spinel mixes favorably (negative), the pyroxenes and
olivine unfavorably (positive), reflecting the different mixing-site geometries. This is why
assuming all of them ideal was a placeholder rather than physics.

## Reliability, per mineral

- **Orthopyroxene (+2693): converged, and now the same shape as the measurement.** The 32- and
  64-site SQS agree within 183 J/mol. The curve is nearly symmetric (L1 = 709), like the
  measured regular solution, where the ordering average had a spurious L1 of 4989. The M1/M2
  sites are treated as randomly mixed, which matches the shipped model; real orthopyroxene puts
  Fe preferentially on M2. The 16-site SQS (the COD cell, 5.2 A along c) happens to land closest
  to the measurement, but it is the worst SQS of the three and that agreement is not meaningful.
- **Spinel (-3186): converged, one modeling assumption.** The 16- and 32-site SQS agree within
  194 J/mol. The ordering average was 553 J/mol more negative at x = 0.5 despite its small
  per-ordering scatter (1-2 meV), which is sampling bias, not noise. It treats spinel as fully
  **normal** (ordered) and ignores cation inversion. Take the sign and rough magnitude as
  reliable, the exact value as a bound on how negative it gets.
- **Clinopyroxene (+792): converged at the wings, less so at x = 0.5.** The 16- and 32-site SQS
  agree within 140 J/mol at x = 0.25 and 0.75 but differ by 598 J/mol at x = 0.5; the 32-site
  cell reproduces the random correlations exactly and is the value to use. The strong asymmetry
  (L1 = 9000 to 12000 in every cell and method, mildly favorable when Fe is dilute and unfavorable
  toward hedenbergite) is a stable feature of the SevenNet prediction, though L1 is also the
  quantity SevenNet gets wrong on olivine.

## Caveat across all of them

On olivine, the one join with calorimetry, SevenNet with SQS reproduces L0 to 3% but reverses the
asymmetry (L1 = -3803 against a measured +4184). The x = 0.25 point comes out 720 J/mol high and
x = 0.75 778 J/mol low. So H_mix at x = 0.5 and L0 are the trustworthy outputs; L1 is not
reliable even in sign. None of the three unknowns has calorimetry to check against; they are
validated only indirectly through olivine (and orthopyroxene, below).

## Reconciliation with the shipped databases

Tracing where each excess would go shows the campaign **corroborates the existing database choices
rather than supplying a missing excess** - nothing needs wiring in. The SQS re-run does not change
that.

- **Olivine** (`data/olivine`, in the web slag DB) already uses the *measured* Wood-Kleppa excess.
  SevenNet reproduces it; that is the control, not a replacement.
- **Orthopyroxene** (`data/olivine-opx`, in the web slag DB) already uses the *measured*
  Chatillon-Colinet excess (W_H = 950 cal/MSiO3 = 7949.6 J per M2Si2O6, symmetric, H_mix@0.5 =
  +1987). The SQS value is +2693, 706 J/mol above it at x = 0.5, with an RMS of 496 J/mol over the
  three compositions (the ordering average: +1707 and 1041). That is within the olivine-set
  uncertainty (617 J/mol RMS), so the measured value stands - overwriting measured data with an
  MLIP prediction would be a downgrade.
- **Clinopyroxene** (`data/clinopyroxene`, in the CaO-FeO-MgO-SiO2 crystallization model) ships
  **ideal by a documented decision**: a prior 7-model MLIP study found the di-hed excess scatters
  near zero (L0 spread -5.4 to +1.3 kJ) and a sensitivity test shifted the liquidus <= 20 K without
  ever changing the crystallizing phase. SevenNet's SQS value (+792 J/mol at x = 0.5, L0 = +2248)
  is a little larger than its earlier +327 but still small next to olivine's +3138, and the
  decision stands.
- **Spinel** is not a phase in any shipped database, so the -3186 value stands as a standalone
  MLIP prediction (normal-spinel, inversion ignored), not a database parameter.

Net: no database change is warranted. The campaign's value is an independent MLIP backing the
measured orthopyroxene excess and the ideal clinopyroxene treatment. Raw data:
`_mlip/campaign_results.json`, `_mlip/cpx_firmup.json` (ordering average);
`_sqs/out/energies.json`, `_sqs/out/structures.json` (SQS).
