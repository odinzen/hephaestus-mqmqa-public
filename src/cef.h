#ifndef MQMQA_CEF_H
#define MQMQA_CEF_H

/* Compound-energy-formalism (CEF / sublattice-model) Gibbs energy.
 *
 * The standard CALPHAD solid-solution model. A phase has one or more sublattices,
 * each with a site multiplicity a_s and a set of constituents mixing on it. The molar
 * Gibbs energy is
 *
 *   G = sum_endmembers ( prod_s y_{i_s}^s ) G_endmember(T)                 (reference)
 *     + R T sum_s a_s sum_i y_i^s ln y_i^s                                (ideal config)
 *     + sum_interactions ( prod_{other s} y ) y_i y_j L (y_i - y_j)^order  (excess, RK)
 *
 * A clean-room port of the validated Python prototype (cef/cef.py), for the engine and
 * the in-browser WASM build. It reads the SUBL (compound-energy) phases the ChemSage
 * reader now parses; the reference oracle is pycalphad's Model.GM.
 *
 * per_mole_atoms divides by the moles of REAL atoms, sum_s a_s sum_i y_i^s atoms_i, so
 * vacancies (atoms = 0) reduce the divisor exactly as pycalphad's GM does. With no
 * vacancies and monatomic constituents this is the constant sum of site multiplicities.
 *
 * Layout of the flattened arrays (Y, em_con, ex_other) uses a per-sublattice offset
 * table subl_off[s] = sum of subl_ncon[0..s-1], so Y[subl_off[s] + i] is the site
 * fraction of constituent i on sublattice s.
 */

#include "mqmqa.h"   /* MQMQA_API */

#ifdef __cplusplus
extern "C" {
#endif

MQMQA_API double mqmqa_cef_gibbs(
    double T,
    int n_subl,
    const double *site_ratio,   /* [n_subl] site multiplicity a_s */
    const int *subl_ncon,       /* [n_subl] constituents per sublattice */
    const int *subl_off,        /* [n_subl] offset of each sublattice into Y */
    const double *Y,            /* [sum subl_ncon] site fractions */
    const double *atoms,        /* [sum subl_ncon] real atoms per constituent (0 for VA);
                                   NULL treats every constituent as one atom */
    int n_em,
    const int *em_con,          /* [n_em*n_subl] constituent index of each endmember per sublattice */
    const double *em_G,         /* [n_em] endmember Gibbs energy evaluated at T */
    int n_ex,
    const int *ex_subl,         /* [n_ex] mixing sublattice of each excess term */
    const int *ex_i,            /* [n_ex] first mixing constituent (local index) */
    const int *ex_j,            /* [n_ex] second mixing constituent (local index) */
    const int *ex_order,        /* [n_ex] Redlich-Kister order */
    const double *ex_L,         /* [n_ex] interaction coefficient at T */
    const int *ex_other,        /* [n_ex*n_subl] pinned constituent on each non-mixing sublattice */
    int per_mole_atoms);        /* 1: divide by sum(site_ratio); 0: per formula unit */

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_CEF_H */
