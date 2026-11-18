# ORCHID shelf: what was checked and what passed

16 November 2026. The SGTE collection of binary datasets (Hallstedt 2025, 2,773 files plus his
unary file), as ORCHID distributes it, checked three ways before any dataset reached the
calculator's library. How to reproduce and the pinned versions are in `SOURCES.md`.

## 1. The files are the published ones

All 2,773 binary datasets are byte-identical to the journal's supplementary archive
(`check_source.py`).

## 2. Hephaestus reads 2,163 of the 2,774

Reading the collection first exposed seven faults in the TDB reader, all fixed and guarded by
`tests/test_tdb_sgte_dialect.py`. None changes a shipped database; every phase energy of every
shipped file is bit-identical before and after.

- Thermo-Calc's abbreviated keywords (`PAR`, `CONST`, `TEMP-LIM`, `TYPE-DEF`) were not recognised,
  so no SGTE file read at all.
- An empty temperature limit (`,,`), meaning the file's TEMP_LIM default, was refused.
- `*` (any constituent of a sublattice) and parameters naming a constituent the phase lacks were
  refused; they are now expanded and skipped, as Thermo-Calc and pycalphad do.
- A TYPE_DEFINITION written after the phase that uses it was ignored. The SGTE files declare the
  magnetic model this way, so the magnetic energy was silently left out, and ordered phases,
  which the reader cannot model, were silently computed without their ordering. Both now take
  effect wherever the definition appears; ordered phases are refused.
- `BMAG` (the magnetic moment) was skipped, and so was any parameter type the reader did not know,
  including types that change the Gibbs energy (THETA, GD, NT). Those are now refused; only
  volume, mobility and transport types are skipped.
- A fixed-composition phase with a magnetic term (pure Fe as BCC_A2, Co17Er2) lost the term. It is
  now built as a one-endmember solution phase, which carries it.
- A parameter with more sublattices than its phase (CeCr-09Cha, InYb-11Gao) and a parameter written
  out twice (AuNd-15Wan, where pycalphad adds the two and Thermo-Calc keeps the later; AlCo-15Liu
  with two different values) were read silently. Both are now refused. A "*" parameter adds to the
  specific parameters it covers and is not counted as a repeat.

The 611 SGTE files refused, each with its reason (`results/load.jsonl`): order-disorder phases
217, functions outside the expression subset 212 (mostly the third-generation Einstein form), the
ionic two-sublattice liquid 140, an energy-bearing parameter type 13, a parameter written out
twice 5, a parameter array longer than its phase 2, and 22 others (three-constituent or
two-sublattice interactions, undeclared elements, phases with no Gibbs energy). A file is
counted under the first reason the reader meets.

## 3. 2,159 of 2,165 agree with pycalphad within 0.05 J/mol

Every phase of every file Hephaestus read before the last two refusals were added (2,168 files of
all ORCHID families), at four random compositions and temperatures between 300 K and the lowest
upper limit the file states (2,500 K at most): 61,615 points, 17,038 phases
(`results/compare.jsonl`). 2,159 agree within 0.05 J/mol and one within 0.06; the remaining
difference is the gas constant (the files define R = 8.31451, pycalphad uses its own). Two of the
larger differences were the defective files now refused (CeCr-09Cha, AuNd-15Wan). The rest:

- three pycalphad cannot read (AlTi-92Kat, CeLa-10Guo, EuMg-08Tao declare a type for a phase
  the file does not define);
- CuLi-09Gas writes a compound energy as L(...), which Thermo-Calc and Hephaestus read as G and
  pycalphad drops;
- MgTl-08Liu puts two statements on one line, which pycalphad partly loses;
- ErTe-22Ben has an odd-order interaction written in non-alphabetical order, whose sign pycalphad
  flips: written alphabetically with the sign changed, the two codes agree to 0.005 J/mol.

In the last three Hephaestus gives the Thermo-Calc reading. All six are shelved as "check before
use", with the reason.

## 4. 1,745 datasets trace every parameter to a checked source

Each dataset names its assessment and tags every parameter with a source. 2,425 of the 2,541 cited
papers resolve to a DOI whose registry record matches on first author, year, volume and first page
(through Hallstedt's reference list, else a Crossref field search). Per dataset (`verdict.py`):

| Verdict | Datasets |
|---|---|
| traced: assessment verified, every binary parameter from it, another verified paper, or a stated rule | 1,745 |
| assessment verified, some parameters from unknown (328), unpublished (197) or adjusted (98) sources | 636 |
| assessment not verifiable (no DOI, unpublished, or registry disagrees) | 387 |
| no assessment named | 6 |

"Stated rule" means the compiler's labelled conventions (the same interaction as the stable phase,
the Laves convention, a linear combination of lattice stabilities): 2,314 parameters. Hallstedt
added these where the original paper gave none; the library card counts them separately.

Found along the way: fifteen DOIs in Hallstedt's reference list (Z. Metallkd., 10.3139/ijmr-...)
do not exist at doi.org, and some datasets carry a corrupted Dinsdale reference
("A.T. DinsdFEe, CFEphad"), apparently from a search-and-replace.

## The shelf

All 2,163 datasets Hephaestus reads are on the shelf (Michael, 16 November 2026). 1,352 pass all
three checks (read, agree with pycalphad, fully traced) and are marked Checked. The other 811 are
marked "Check before use", each with its reasons: what could not be traced (the assessment
unpublished 138, not a journal paper 97, without a checkable DOI 64, its DOI record disagreeing 14,
none named 3; parameters from an unknown source in 332 datasets, unpublished work 158, later
adjustments 101, unchecked papers 39, compiled databases 18), or that pycalphad reads the file
differently (3) or cannot read it (3). The calculator repeats the warning when such a file loads.
`scripts/import_orchid.py` copies the files unchanged into `web/orchid/sgte-binary/` (each SHA-256
checked against ORCHID's manifest) with `web/orchid/catalog.json`.

What this does not check: whether each assessment fits the measurements it was fitted to, or
whether the file reproduces the paper's own figures. The trace establishes where every number
came from, not that the assessment is good.
