#ifndef MQMQA_TQ_H
#define MQMQA_TQ_H

/* An OCASI-compatible thermodynamic application interface for Hephaestus.
 *
 * These entry points mirror the shape and semantics of the OpenCalphad OCASI /
 * classic TQ interface (itself the de-facto embedding standard originating in
 * Thermo-Calc's TQ), so an application written against OCASI can bind Hephaestus
 * instead and run where OpenCalphad cannot: the browser (WebAssembly), and MIT- or
 * closed-licensed products. It is written clean-room from the documented interface
 * semantics; no OpenCalphad (GPL) source or headers are copied or linked.
 *
 * Model coverage is Hephaestus's own: MQMQA liquids, compound-energy-formalism
 * solids with the Inden-Hillert-Jarl magnetic term, stoichiometric compounds, and
 * the NASA-polynomial gas. Equilibrium is found by global minimization (candidate
 * generation plus the lower convex hull) so a returned assemblage is never a local
 * trap. See docs/EQUILIBRIUM_ENGINE.md.
 *
 * A tq_ctx is one stateful workspace: a database, a set of conditions, a phase
 * status mask, and the last equilibrium result. It is not thread shared.
 */

#include "mqmqa.h"   /* MQMQA_API, extern "C" */

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tq_ctx tq_ctx;

/* --- lifecycle --- */

/* Initialise an empty workspace. Release with tq_free. Returns NULL on allocation
 * failure. (OCASI: tqini) */
MQMQA_API tq_ctx *tq_init(void);

/* Read a database into the workspace, format auto-detected from the text
 * (.dat / .tdb / .utdb / .xtdb). Returns 0 on success; on failure returns non-zero
 * and tq_error() gives the reason. (OCASI: tqrfil / tqrpfil) */
MQMQA_API int tq_read_string(tq_ctx *c, const char *text);

/* Release a workspace. (OCASI: tqfree) */
MQMQA_API void tq_free(tq_ctx *c);

/* Human-readable reason for the last failure on this workspace, or "" if none. */
MQMQA_API const char *tq_error(const tq_ctx *c);

/* --- introspection (OCASI: tqgcom, tqgnp, tqgpn, tqgpi, tqgnsubl) --- */

MQMQA_API int tq_num_components(const tq_ctx *c);
MQMQA_API const char *tq_component(const tq_ctx *c, int i);
MQMQA_API int tq_num_phases(const tq_ctx *c);
MQMQA_API const char *tq_phase_name(const tq_ctx *c, int p);
MQMQA_API int tq_phase_index(const tq_ctx *c, const char *name);

/* --- conditions (OCASI: tqsetc, tqphsts) --- */

/* Set temperature (K) and pressure (Pa). */
MQMQA_API int tq_set_TP(tq_ctx *c, double T, double P);

/* Set the overall system content: amount[i] for component i in tq_component order,
 * length tq_num_components. Interpreted as mole fractions if they sum to about 1,
 * otherwise as moles. (OCASI: tqsetc with a composition condition.) */
MQMQA_API int tq_set_composition(tq_ctx *c, const double *amount);

/* Phase status: status < 0 suspended (never stable), 0 entered (default), > 0 fixed
 * stable. Stage 1 honours suspended/entered; fixed is reserved. (OCASI: tqphsts) */
MQMQA_API int tq_set_phase_status(tq_ctx *c, int p, int status);

/* --- equilibrium (OCASI: tqce) --- */

/* Compute the equilibrium at the current conditions by global minimization. Returns
 * 0 on success; results are read with the tq_get_* calls below. */
MQMQA_API int tq_compute_equilibrium(tq_ctx *c);

/* --- results (OCASI: tqgetv) --- */

/* Total Gibbs energy of the system, J per mole of atoms. NaN if no result. */
MQMQA_API double tq_G(const tq_ctx *c);

/* Number of stable phases in the last equilibrium (amount > 0). */
MQMQA_API int tq_num_stable_phases(const tq_ctx *c);

/* For the k-th stable phase (0..tq_num_stable_phases-1): its database phase index
 * (tq_phase_name), and its molar amount fraction written to *amount (may be NULL).
 * Returns -1 if k is out of range. */
MQMQA_API int tq_stable_phase(const tq_ctx *c, int k, double *amount);

/* Composition of the k-th stable phase: writes mole fractions over components
 * (length tq_num_components) to x_out. Returns 0 on success. */
MQMQA_API int tq_stable_phase_composition(const tq_ctx *c, int k, double *x_out);

/* Chemical potential of component i at equilibrium, mu_i / RT (dimensionless), from
 * the supporting hyperplane of the stable facet. Writes length tq_num_components to
 * mu_out. Returns 0 on success. */
MQMQA_API int tq_chemical_potentials(const tq_ctx *c, double *mu_out);

#ifdef __cplusplus
}
#endif

#endif
