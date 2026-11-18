#ifndef MQMQA_GEM_H
#define MQMQA_GEM_H

/* General equilibrium: any number of elements and phases (docs/GENERAL_EQUILIBRIUM.md).
 * Candidates from every phase, a linear program for the lower hull at the bulk
 * composition, and column generation from each phase's driving-force minimum. */

#include "mqmqa.h"
#include "cs_dat.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct mqmqa_gem mqmqa_gem;

/* Equilibrium of database db at temperature T (K) for bulk element amounts b (length
 * mqmqa_db_num_elements; any positive scale, normalized internally). suspended (may be
 * NULL) has one entry per solution phase followed by one per stoichiometric compound,
 * 1 to hold that phase out. grid sets the candidate density (0 for the default) and
 * max_iter the refinement passes (0 for the default). Returns NULL on failure with the
 * reason in mqmqa_db_error(); a solution phase the engine refuses fails the call unless
 * it is suspended. Release with mqmqa_gem_free. */
MQMQA_API mqmqa_gem *mqmqa_gem_equilibrium(const mqmqa_db *db, double T, const double *b,
                                           const int *suspended, int grid, int max_iter);
MQMQA_API void mqmqa_gem_free(mqmqa_gem *r);

/* Stable composition sets. phase is a solution phase index (>= 0) or a compound
 * -(j+1); amount is in moles of atoms per mole of atoms of the system; x has one entry
 * per database element (mole fractions within the set). */
MQMQA_API int mqmqa_gem_num_sets(const mqmqa_gem *r);
MQMQA_API int mqmqa_gem_set_phase(const mqmqa_gem *r, int k);
MQMQA_API double mqmqa_gem_set_amount(const mqmqa_gem *r, int k);
MQMQA_API void mqmqa_gem_set_x(const mqmqa_gem *r, int k, double *x);
/* Gibbs energy per mole of atoms of the system, element chemical potentials (J/mol, one
 * per database element; NaN for an element absent from the bulk or one whose amount the
 * others fix, such as oxygen in a fixed-valence oxide system), the most negative
 * driving force left after the last pass (J per mole of atoms; >= -tolerance at
 * convergence), and the passes used. */
MQMQA_API double mqmqa_gem_G(const mqmqa_gem *r);
MQMQA_API void mqmqa_gem_mu(const mqmqa_gem *r, double *mu);
MQMQA_API double mqmqa_gem_residual(const mqmqa_gem *r);
MQMQA_API int mqmqa_gem_passes(const mqmqa_gem *r);
/* 1 when the result was finished by solving the equilibrium conditions exactly, 0 when the
 * finish did not settle or failed its checks and the sampled result stands */
MQMQA_API int mqmqa_gem_exact(const mqmqa_gem *r);

#ifdef __cplusplus
}
#endif
#endif
