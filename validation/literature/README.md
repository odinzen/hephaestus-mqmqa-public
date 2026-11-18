# Held-out literature test

A standalone module that tests the shipped databases against measured values that were not
used to fit them. It is kept apart from the engine on purpose:

- Nothing in `src/`, `python/mqmqa/` or `data/` imports from here, and nothing here imports
  engine internals. The scorer (added after sealing) calls Hephaestus only through its public
  Python API, the way an outside user would.
- Measured values live in the sealed folder outside the repository until the predictions are
  committed. This folder holds only the rules, the sealing script and the conditions.

| File | What it is |
|---|---|
| `RULES.md` | Selection and scoring rules, fixed before collection |
| `template.csv` | One row per measured point |
| `seal.py` | Strips the values, seals the full file, prints its SHA-256 |
| `USED_SOURCES.txt` | Sources the databases already cite, for the overlap check |
| `conditions_<round>.csv` | What was measured and where, without the values (after sealing) |
| `SEALED_HASH_<round>.txt` | Fingerprint of each sealed round |
| `predict.py` | Computes every row from the conditions alone, as shipped and as the baseline |
| `predictions_<round>.json` | Its output, committed before the round is unsealed |
| `score.py` | The scores of RULES.md, committed with the predictions and run once after unsealing |

Results go in Supplementary Material, not the main paper.
