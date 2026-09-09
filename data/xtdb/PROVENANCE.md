# XTDB third-generation example databases

Databases in the open XML XTDB format (Sundman et al., Calphad 90 (2025) 102849), read by the
Hephaestus XTDB engine (`src/xtdb.c`). Third-generation model: an Einstein heat capacity valid
to 0 K and, for the liquid, a two-state description. Licensed CC BY 4.0.

## AlC.xtdb (this directory)

Third-generation Al-C assessment. Parameters (facts) transcribed from the primary source:

- Z. He, B. Kaplan, H. Mao, M. Selleby, "The third generation Calphad description of Al-C
  including revisions of pure Al and C", Calphad 72 (2021) 102250.

Independent transcription: our own text and layout, only the published numerical parameters
are used; no file, text, or layout from any GPL or other implementation is copied. Phases:
LIQUID (two-state), FCC_A1, GRAPHITE, DIAMOND, AL4C3.

Verified: pure-Al melting 933.47 K (exact), Al4C3 peritectic ~2429 K (literature 2156 degC),
graphite Cp ~8.5 and Al4C3 Cp approaching 7*3R. The engine matches an independent Python
evaluator (`../xtdb-alc/xtdb_ref.py`) to < 1e-6 J/mol-atom.

## PbSn.xtdb (in `web/`, shipped next to the calculator)

Classic assessment (2nd-generation SGTE unaries + Redlich-Kister excess) written in XTDB, to
exercise the legacy path through the same reader. Parameters transcribed from:

- T.L. Ngai, Y.A. Chang, "A thermodynamic analysis of the Pb-Sn system and the calculation of
  the Pb-Sn phase diagram", Calphad 5 (1981) 267-276,

as tabulated in the open NIMS/pycalphad pbsn.tdb (Abe, Hashimoto, Sawada 2011). Reproduces the
eutectic at 456 K and x(Sn) ~ 0.74.

## Not redistributed

Bo Sundman's own AlC-database.XTDB (the reference implementation's example) is GPL-3.0 and is
kept only as a LOCAL validation reference under `../xtdb-alc/`; it is git-ignored and never
shipped from this MIT/CC-BY repository. Our AlC.xtdb is an independent transcription from the
He et al. (2021) primary source.
