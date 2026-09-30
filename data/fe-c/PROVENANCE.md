# Fe-C, the basic steel system

`FeC.tdb`, an own transcription for the open calculator, shipped as `web/FeC.tdb`. Licensed
CC BY-SA 4.0.

- Unaries after Dinsdale (1991, SGTE); binary after Gustafson (1985), the assessment industrial
  Fe-C work still rests on.
- Phases: liquid, ferrite BCC_A2 (Fe)(C,VA)3 interstitial, austenite FCC_A1 (Fe)(C,VA),
  cementite Fe3C, graphite.
- The BCC and FCC magnetic contributions use the Inden-Hillert-Jarl model.

Validated in `tests/test_fec_steel.py`: pycalphad parity on every phase and the measured
pure-iron transition temperatures.

It is also the steel half of `../unified/FeC-FeOMgOSiO2.utdb`.
