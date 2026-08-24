#ifndef MQMQA_CS_DAT_H
#define MQMQA_CS_DAT_H

/* ChemSage .dat reader for the MQMQA core.
 *
 * Parses a ChemSage thermochemical data file into an in-memory database so the
 * engine can load pair (MQMG), coordination (MQMZ) and excess (MQMX) parameters
 * plus the SUBQ/SUBG phase structure without pycalphad at runtime. pycalphad is
 * only the validation oracle.
 *
 * Clean-room from the published format description (ChemApp documentation,
 * "The format of a ChemApp data-file") and the model papers (Pelton 2001;
 * Poschmann 2021). No FactSage or other implementation code is used.
 *
 * The database is an opaque handle. Read it with mqmqa_db_read_file/read_string,
 * query it through the accessors below, and release it with mqmqa_db_free. On a
 * read failure the read functions return NULL and mqmqa_db_error() gives the
 * reason. Species indices returned by the accessors are 0-based within their
 * sublattice (cations, anions); coordination and excess indices follow the same
 * convention so they feed the energy routines in mqmqa.h directly.
 */

#include "mqmqa.h"   /* MQMQA_API, extern "C" wrapper */

#ifdef __cplusplus
extern "C" {
#endif

typedef void mqmqa_db;

/* Read a database from a file path or an in-memory string. Return NULL on error
 * (see mqmqa_db_error). The returned handle owns all its memory. */
MQMQA_API mqmqa_db *mqmqa_db_read_file(const char *path);
MQMQA_API mqmqa_db *mqmqa_db_read_string(const char *text);
MQMQA_API void mqmqa_db_free(mqmqa_db *db);

/* Human-readable message for the most recent read failure on this thread. */
MQMQA_API const char *mqmqa_db_error(void);

/* --- Header --- */
MQMQA_API int mqmqa_db_num_elements(const mqmqa_db *db);
MQMQA_API const char *mqmqa_db_element(const mqmqa_db *db, int i);
MQMQA_API double mqmqa_db_element_mass(const mqmqa_db *db, int i);

/* --- Solution phases (the MQMQA ones the engine runs) --- */
MQMQA_API int mqmqa_db_num_phases(const mqmqa_db *db);
MQMQA_API int mqmqa_db_phase_index(const mqmqa_db *db, const char *name);
MQMQA_API const char *mqmqa_db_phase_name(const mqmqa_db *db, int p);
/* 1 for SUBQ, 0 for SUBG, -1 for any other (unsupported) phase type. */
MQMQA_API int mqmqa_db_phase_is_subq(const mqmqa_db *db, int p);

MQMQA_API int mqmqa_ph_num_cations(const mqmqa_db *db, int p);
MQMQA_API int mqmqa_ph_num_anions(const mqmqa_db *db, int p);
MQMQA_API const char *mqmqa_ph_cation(const mqmqa_db *db, int p, int i);
MQMQA_API const char *mqmqa_ph_anion(const mqmqa_db *db, int p, int k);
MQMQA_API double mqmqa_ph_cation_charge(const mqmqa_db *db, int p, int i);
MQMQA_API double mqmqa_ph_anion_charge(const mqmqa_db *db, int p, int k);
MQMQA_API int mqmqa_ph_cation_group(const mqmqa_db *db, int p, int i);
MQMQA_API int mqmqa_ph_anion_group(const mqmqa_db *db, int p, int k);

/* Pairs (MQMG endmembers). n = num_pairs = n_cat * n_an. The array fills take
 * caller-allocated buffers of length n. Gibbs and zeta come from the endmember;
 * cat/an are 0-based sublattice indices; stoich is the pair's cation stoichiometry
 * (stoichiometry_quadruplet[0]), the divisor in the reference-energy term. */
MQMQA_API int mqmqa_ph_num_pairs(const mqmqa_db *db, int p);
MQMQA_API void mqmqa_ph_pair_indices(const mqmqa_db *db, int p, int *cat, int *an);
MQMQA_API void mqmqa_ph_pair_stoich(const mqmqa_db *db, int p, double *stoich);
MQMQA_API void mqmqa_ph_pair_zeta(const mqmqa_db *db, int p, double *zeta);
MQMQA_API void mqmqa_ph_pair_gibbs(const mqmqa_db *db, int p, double T, double *G);

/* Coordination (MQMZ). n = num_quadruplets listed in the file (the pure pairs
 * plus any explicit mixed entries). Indices are canonicalized to A<=B (cations)
 * and X<=Y (anions); Z is row-major [n*4] with slots ordered [A,B,X,Y]. These
 * feed mqmqa_coordination directly. */
MQMQA_API int mqmqa_ph_num_mqmz(const mqmqa_db *db, int p);
MQMQA_API void mqmqa_ph_mqmz(const mqmqa_db *db, int p,
                             int *A, int *B, int *X, int *Y, double *Z);

/* Excess (MQMX). n = num params. mix is 0 for cation mixing (A!=B, X==Y), 1 for
 * anion mixing (A==B, X!=Y), -1 otherwise (reciprocal/unsupported by the current
 * excess routine, still reported). code is 0=Q, 1=G, 2=B, 3=R. A,B are 0-based
 * cations, X,Y 0-based anions. p_exp,q_exp are the first two mixing exponents.
 * L is the interaction coefficient evaluated at T. */
MQMQA_API int mqmqa_ph_num_mqmx(const mqmqa_db *db, int p);
MQMQA_API void mqmqa_ph_mqmx(const mqmqa_db *db, int p,
                             int *mix, int *code,
                             int *A, int *B, int *X, int *Y,
                             int *p_exp, int *q_exp);
MQMQA_API void mqmqa_ph_mqmx_L(const mqmqa_db *db, int p, double T, double *L);

/* --- CEF (SUBL / compound-energy-formalism) solution phases ---
 * kind is 0 for MQMQA (SUBQ/SUBG) phases and 1 for CEF (SUBL). The accessors below
 * apply only to CEF phases. Constituents are flattened by sublattice; site fractions
 * passed to mqmqa_ph_cef_gibbs follow that same order (query it with the accessors).
 * The excess Redlich-Kister mixing pair is name-sorted to match pycalphad. */
MQMQA_API int mqmqa_db_phase_kind(const mqmqa_db *db, int p);
MQMQA_API int mqmqa_ph_cef_num_subl(const mqmqa_db *db, int p);
MQMQA_API void mqmqa_ph_cef_subl_ncon(const mqmqa_db *db, int p, int *out);
MQMQA_API void mqmqa_ph_cef_site_ratio(const mqmqa_db *db, int p, double *out);
MQMQA_API int mqmqa_ph_cef_num_constituents(const mqmqa_db *db, int p);
MQMQA_API const char *mqmqa_ph_cef_constituent(const mqmqa_db *db, int p, int s, int i);
MQMQA_API double mqmqa_ph_cef_gibbs(const mqmqa_db *db, int p, const double *Y,
                                    double T, int per_mole_atoms);

/* --- Stoichiometric compounds (solid oxides etc., for later equilibrium) --- */
MQMQA_API int mqmqa_db_num_stoich(const mqmqa_db *db);
MQMQA_API const char *mqmqa_db_stoich_name(const mqmqa_db *db, int i);
MQMQA_API double mqmqa_db_stoich_gibbs(const mqmqa_db *db, int i, double T);

/* --- Quadruplet enumeration (engine utility, no database needed) ---
 * The full quadruplet set is every unordered cation pair {i<=j} crossed with
 * every unordered anion pair {k<=l}. This is the state space the energy routines
 * and the solver iterate over. */
MQMQA_API int mqmqa_num_quadruplets(int n_cat, int n_an);
MQMQA_API void mqmqa_enumerate_quadruplets(int n_cat, int n_an,
                                           int *ca, int *cb, int *ax, int *ay);

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_CS_DAT_H */
