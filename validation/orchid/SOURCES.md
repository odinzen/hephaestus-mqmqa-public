# ORCHID shelf: sources and how to reproduce

**Data.** The SGTE collection of binary datasets, B. Hallstedt, Calphad 89 (2025) 102833,
doi:10.1016/j.calphad.2025.102833, CC BY 4.0, as distributed by ORCHID
(github.com/orchid-calphad/orchid-project.org, `data/databases/`), checkout pinned at commit
786f64f438eed115d6528874c45a06ff551c57eb (1 November 2026). The other ORCHID families (MatCalc
via pycalphad's binder, Mendeley Data, OpenIEC, pycalphad, scheil, Zenodo; 20 files) were loaded
and compared too but are not shelved: they carry other licences, and their sources are not traced
here.

**The files are Hallstedt's.** ORCHID's 2,773 binary datasets were compared byte for byte with the
journal's supplementary archive `1-s2.0-S0364591625000367-mmc3.zip` (SHA-256 6a0d53de...747d, the
value ORCHID records): all 2,773 are identical. `check_source.py` repeats this.

**Reference list.** Hallstedt's own reference list (the paper's 1,895 references, 1,726 with a DOI)
was read from the paper's text to resolve the citations in each dataset to DOIs. Fifteen of those
DOIs, all Z. Metallkd. papers given as 10.3139/ijmr-..., are unknown to doi.org (handle lookup
response code 100, 16 November 2026); the papers they name are counted as not checkable, not as
verified, unless a Crossref search on their volume, page, year and author found the real record.

## Reproduce

From the repository root, with a checkout of ORCHID at the commit above beside it:

```
python validation/orchid/check_source.py mmc3.zip ../orchid-project.org/data/databases/sgte-binary
python validation/orchid/load_test.py ../orchid-project.org/data/databases python results/load.jsonl
python validation/orchid/compare.py ../orchid-project.org/data/databases python list.txt results/compare.jsonl
python validation/orchid/trace.py ../orchid-project.org/data/databases/sgte-binary hallstedt2025.txt validation/orchid/results
python validation/orchid/verdict.py validation/orchid/results
python scripts/import_orchid.py ../orchid-project.org
```

`list.txt` holds the files `load.jsonl` marks as read. `hallstedt2025.txt` is the paper's text
(PyMuPDF, `page.get_text()` of every page). `trace.py` queries Crossref and doi.org; its
`registry_cache.json` is not committed. Every script reads the downloaded files as data and runs
nothing from them.
