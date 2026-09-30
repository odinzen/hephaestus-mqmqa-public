# Al-Zn open example database

`AlZn.tdb`, the open alloy example in Thermo-Calc .tdb form, shipped next to the calculator as
`web/AlZn.tdb`. Licensed CC BY-SA 4.0.

Authored for this repository from published parameter values only:

- Unary lattice stabilities: A.T. Dinsdale, SGTE data for pure elements, Calphad 15 (1991)
  317-425, in the variant tabulated with the assessment.
- Binary excess parameters: S. an Mey, Reevaluation of the Al-Zn system, Z. Metallkd. 84 (1993)
  451-455.

An independent transcription with its own text and layout. Verified numerically to machine
precision against pycalphad (`tests/test_tdb_reader_vs_pycalphad.py`).

It is also the alloy half of `../unified/AlZn-LiClKCl.utdb` and
`../unified/AlZn-NaClKClMgCl2.utdb`.
