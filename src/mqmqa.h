#ifndef MQMQA_H
#define MQMQA_H

/* Public C API for the MQMQA core.
 *
 * Walking-skeleton stage: the two functions below exist only to exercise the
 * C -> DLL -> cffi -> Python -> pytest pipeline end to end. Real MQMQA energy
 * terms (reference, ideal mixing, excess) are added incrementally, each
 * validated against pycalphad and Thermochimica before landing.
 *
 * Model implemented clean-room from published papers only:
 *   Pelton, Chartrand, Eriksson, Metall. Mater. Trans. A 32 (2001) 1409.
 *   Poschmann, Bajpai, Fitzpatrick, Piro, Calphad 75 (2021) 102341.
 */

#ifdef _WIN32
#define MQMQA_API __declspec(dllexport)
#else
#define MQMQA_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Molar gas constant R (J/mol/K), CODATA 2018. */
MQMQA_API double mqmqa_R(void);

/* Ideal binary configurational entropy, -R (x ln x + (1-x) ln(1-x)), J/mol/K.
 * Placeholder quantity used to check the toolchain against a hand value. */
MQMQA_API double mqmqa_ideal_entropy_binary(double x);

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_H */
