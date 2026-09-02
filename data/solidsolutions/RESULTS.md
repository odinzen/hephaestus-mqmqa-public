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

Endmember sources (COD): forsterite 1572966, spinel 1010129 (MgAl2O4, Fd-3m), diopside 1000007
(CaMgSi2O6), enstatite 1000047 (Mg2Si2O6).

## Control

Olivine, run through the identical script, reproduces the measurement and the prior SevenNet run:

| | L0 | L1 | H_mix @ x=0.5 |
|---|---:|---:|---:|
| Wood & Kleppa 1981 (measured) | 12552 | 4184 | +3138 |
| SevenNet-0 (this run) | 9746 | 1107 | **+3168** |

Agreement at x=0.5 is 30 J/mol; the olivine RMS over the join is ~861 J/mol, which bounds the
systematic error of the whole approach.

## Results (MLIP-predicted, J/mol per formula unit)

| Solid solution | Join | L0 | L1 | H_mix @ x=0.5 |
|---|---|---:|---:|---:|
| Spinel | MgAl2O4-FeAl2O4 | -14732 | 2558 | **-3739** |
| Clinopyroxene | Di-Hd | 610 | 9244 | **+327** |
| Orthopyroxene | En-Fs | 10726 | 4989 | **+1707** |

Signs are physically sensible as a set: spinel mixes favorably (negative), the pyroxenes and
olivine unfavorably (positive), reflecting the different mixing-site geometries. This is why
assuming all of them ideal was a placeholder rather than physics.

## Reliability, per mineral

- **Orthopyroxene (+1707): solid.** Positive and modest, consistent with the known near-ideal to
  slightly positive enstatite-ferrosilite behavior. The 80-atom cell (16 Mg sites) gives real
  configurational scatter (10-30 meV), not error.
- **Spinel (-3739): well-determined, one modeling assumption.** Orderings nearly degenerate
  (1-2 meV scatter), so the number is tight, but it treats spinel as fully **normal** (ordered) and
  ignores cation inversion. Take the sign and rough magnitude as reliable, the exact value as a
  bound on how negative it gets.
- **Clinopyroxene (+327): firmed up in an 8-site supercell.** The conventional diopside cell has
  only 4 mixing sites; a 2x1x1 supercell with 10 orderings per composition (scatter down to
  ~190 J/mol at x=0.5) moved H_mix@0.5 from +959 to +327. The strong asymmetry (large L1, a sign
  flip to negative on the Mg-rich side) **survived the bigger cell with low scatter**, so it is a
  genuine feature of the SevenNet prediction, not a small-cell artifact: mixing is mildly favorable
  when Fe is dilute and mildly unfavorable toward the iron (hedenbergite) end.

## Caveat across all of them

SevenNet reproduces the mixing-enthalpy **peak** (x=0.5) well but underestimates the **wings**:
olivine's own x=0.25 / 0.75 came out ~700-1300 J/mol low versus measured. So the single H_mix@0.5
values are the trustworthy output; the full RK curve shape (L1) carries more uncertainty
everywhere. None of the three unknowns has calorimetry to check against; they are validated only
indirectly through olivine.

## Reconciliation with the shipped databases

Tracing where each excess would go shows the campaign **corroborates the existing database choices
rather than supplying a missing excess** - nothing needs wiring in.

- **Olivine** (`data/olivine`, in the web slag DB) already uses the *measured* Wood-Kleppa excess.
  SevenNet reproduces it; that is the control, not a replacement.
- **Orthopyroxene** (`data/olivine-opx`, in the web slag DB) already uses the *measured*
  Chatillon-Colinet excess (L = 7949.6 J per M2Si2O6, H_mix@0.5 approx +1987). SevenNet's +1707
  agrees within the method's ~861 J/mol uncertainty, so the measured value stands - overwriting
  measured data with an MLIP prediction would be a downgrade.
- **Clinopyroxene** (`data/clinopyroxene`, in the CaO-FeO-MgO-SiO2 crystallization model) ships
  **ideal by a documented decision**: a prior 7-model MLIP study found the di-hed excess scatters
  near zero (L0 spread -5.4 to +1.3 kJ) and a sensitivity test shifted the liquidus <= 20 K without
  ever changing the crystallizing phase. SevenNet's +327 J/mol (essentially zero) confirms that
  decision.
- **Spinel** is not a phase in any shipped database, so the -3739 value stands as a standalone
  MLIP prediction (normal-spinel, inversion ignored), not a database parameter.

Net: no database change is warranted. The campaign's value is an independent MLIP backing the
measured orthopyroxene excess and the ideal clinopyroxene treatment. Raw data:
`_mlip/campaign_results.json`, `_mlip/cpx_firmup.json`.
