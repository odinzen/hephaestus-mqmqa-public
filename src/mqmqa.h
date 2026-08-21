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

/* Molar gas constant R (J/mol/K): the CALPHAD/SGTE conventional value 8.3145 that
 * the databases are assessed with, matching pycalphad. Not CODATA 2018. */
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

/* MQMQA ideal-mixing (configurational entropy) energy, J per mole of quadruplets,
 * following Poschmann 2021 eqs 5-14. Returns Sid * T * R.
 *
 * Za,Zb,Zx,Zy give the coordination number of each of quadruplet q's four
 * constituents (cation a, cation b, anion x, anion y). zeta is the row-major
 * [n_cat*n_an] table of pair coordination-equivalence factors. soln_type is
 * 0 for SUBG, 1 for SUBQ (which uses the 0.75 / 0.5 exponents and starred pairs).
 */
MQMQA_API double mqmqa_ideal_mixing_energy(
    double T,
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    const double *zeta,
    int soln_type);

/* MQMQA excess energy for a set of MQMX interaction parameters, J per mole of
 * quadruplets (Poschmann eqs 19,20,24 mixing term, eq 17 assembly). Handles the Q
 * code (Xi, any exponents) and the G code (Chi, any exponents) for cation and anion
 * mixing, assuming a single chemical group per sublattice (empty nu/gamma).
 * Unsupported cases return NaN rather than a wrong number: Bragg-Williams B/H,
 * reciprocal R, ternary (additional mixing constituent), and the multi-group
 * nu/gamma expansion.
 *
 * Per parameter k: par_mix 0 = cation mixing (A != B, X = Y), 1 = anion mixing
 * (A = B, X != Y). par_code 0 = Q, 1 = G. par_A,par_B cations; par_X,par_Y anions;
 * par_p,par_q exponents; par_L interaction coefficient at T. Za..Zy are the
 * per-quadruplet slot coordination numbers, as in mqmqa_ideal_mixing_energy. */
MQMQA_API double mqmqa_excess_energy(
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    int n_params,
    const int *par_mix, const int *par_code,
    const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
    const double *par_p, const double *par_q, const double *par_L);

/* Coordination number Z of a species in a quadruplet (Pelton 2001 eqs 23-24).
 * sp_is_cation selects the sublattice; sp_idx, A, B, X, Y are cation/anion indices
 * (A,B cations; X,Y anions). Pure-pair coordinations come from the MQMZ table:
 * n_mqmz entries with canonical indices mz_A<=mz_B, mz_X<=mz_Y and mz_Z holding the
 * four slot coordinations [A,B,X,Y] per entry. q_cat/q_an are absolute charges. */
MQMQA_API double mqmqa_coordination(
    int sp_is_cation, int sp_idx,
    int A, int B, int X, int Y,
    int n_cat, int n_an,
    const double *q_cat, const double *q_an,
    int n_mqmz,
    const int *mz_A, const int *mz_B, const int *mz_X, const int *mz_Y,
    const double *mz_Z);

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_H */
