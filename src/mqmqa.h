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

/* MQMQA reference (pair) energy, J per mole of quadruplets, following Poschmann
 * 2021 / Pelton 2001:
 *
 *   G_ref = sum over MQMG pairs (a/x) of  (G_ax / stoich_ax) *
 *             sum over quadruplets q of  X[q] * n_a(q) * n_x(q) / (2 Z(a, q))
 *
 * where n_a(q) is how many of the quadruplet's two cation slots hold cation a
 * (0, 1, or 2), n_x(q) likewise for anion x, and Z(a, q) is the coordination
 * number of a in quadruplet q.
 *
 * Cations and anions are referred to by integer index. Quadruplet q holds cation
 * indices (quad_ca[q], quad_cb[q]) and anion indices (quad_ax[q], quad_ay[q]).
 * Z is a row-major [n_pairs][n_quads] table: Z[p*n_quads + q] = Z(pair_c[p], q).
 */
MQMQA_API double mqmqa_reference_energy(
    int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    int n_pairs,
    const int *pair_c, const int *pair_a,
    const double *Gax, const double *stoich,
    const double *Z);

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_H */
