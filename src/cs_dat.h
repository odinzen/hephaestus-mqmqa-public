#ifndef MQMQA_CS_DAT_H
#define MQMQA_CS_DAT_H

/* ChemSage .dat reader for the MQMQA core.
 *
 * Parses a ChemSage thermochemical data file into an in-memory database so the
 * engine can load pair (MQMG), coordination (MQMZ) and excess (MQMX) parameters
 * plus the SUBQ/SUBG phase structure without pycalphad at runtime. pycalphad is
 * only the validation oracle.
 *
 * The block grammar follows pycalphad's ChemSage reader (pycalphad/io/cs_dat.py,
 * MIT; see NOTICE), which was read while writing this, together with the ChemApp
 * format description ("The format of a ChemApp data-file"). No FactSage code is used.
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

/* Human-readable message for the most recent read or write failure. */
MQMQA_API const char *mqmqa_db_error(void);

/* The database's own gas constant, the value its calculations use in the as-assessed
 * mode; pass it as R_own to the array-level energy routines. */
MQMQA_API double mqmqa_db_R_own(const mqmqa_db *db);
/* The R its calculations use now (the mode applied), and where it comes from
 * (MQMQA_R_SRC_*, OVERRIDE while a mode is forced); the source of the own value; and a
 * one-line note for the user (a static buffer, overwritten by the next note). */
MQMQA_API double mqmqa_db_R(const mqmqa_db *db);
/* Pressure (Pa) seen by the database's ideal gas phase, the first solution phase of a
 * ChemSage file when it is IDMX: each gas species gains R T ln(P / 1 atm). Condensed
 * phases carry no volume data and do not change. Default 101325 Pa; -1 if P <= 0. */
MQMQA_API int mqmqa_db_set_pressure(mqmqa_db *db, double P);
MQMQA_API double mqmqa_db_pressure(const mqmqa_db *db);
/* Species whose energy was taken above the end of their data (the last range carried on),
 * as logged since the last clear: name, where the data end, the highest T used, elements. */
MQMQA_API void mqmqa_db_beyond_clear(mqmqa_db *db);
MQMQA_API int mqmqa_db_beyond_count(const mqmqa_db *db);
MQMQA_API const char *mqmqa_db_beyond_name(const mqmqa_db *db, int i);
MQMQA_API double mqmqa_db_beyond_top(const mqmqa_db *db, int i);
MQMQA_API double mqmqa_db_beyond_T(const mqmqa_db *db, int i);
MQMQA_API int mqmqa_db_beyond_elements(const mqmqa_db *db, int i, double *out);
MQMQA_API int mqmqa_db_R_source(const mqmqa_db *db);
MQMQA_API int mqmqa_db_R_own_source(const mqmqa_db *db);
MQMQA_API const char *mqmqa_db_R_note(const mqmqa_db *db);
/* Declare which R a database that does not state one was assessed with: choice is
 * MQMQA_R_CALPHAD, _SGTE or _SI, or MQMQA_R_AS_ASSESSED to withdraw a declaration. The
 * declared value is the database's own from then on (source DECLARED) and is what the
 * writers record. Returns 0; -1 when the file states R (the error text says so); -2 for
 * an unknown choice. */
MQMQA_API int mqmqa_db_declare_R(mqmqa_db *db, int choice);

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
/* Ternary additional-constituent data per MQMX term: exponent r (exponents slot 3)
 * and the additional cation's 0-based index, -1 when none. */
MQMQA_API void mqmqa_ph_mqmx_ternary(const mqmqa_db *db, int p, double *r_exp, int *add_cat);
/* NULL when every excess term of MQMQA phase p can be evaluated; otherwise a message
 * naming the phase and the first term the engine refuses (an unsupported code, an
 * additional anion, r > 1, mixed chemical groups, chemical-group override strings).
 * The energy routines return NaN for such a phase; this says why. The text lives in
 * a static buffer overwritten by the next call. */
MQMQA_API const char *mqmqa_ph_excess_unsupported(const mqmqa_db *db, int p);

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
/* Gibbs energy along a CEF phase's composition line (y = site-weighted fraction of the
 * second constituent over its mixing sublattices). Two sublattices mixing the same pair
 * are taken at internal equilibrium (minimum over the site distribution); Y_out, when not
 * NULL, receives the site fractions. NaN (error set) for any other layout. */
MQMQA_API double mqmqa_ph_cef_line_gibbs(const mqmqa_db *db, int p, double y, double T,
                                         int per_mole_atoms, double *Y_out);

/* --- Two-sublattice ionic liquid (ChemSage SUBI, phase kind 2) ---
 * Site fractions run over the cations, then the second sublattice (anions, Va, neutrals),
 * in the file's order. mqmqa_ph_ionic_gibbs gives the energy of one formula unit (P cation
 * and Q anion sites) and, when n_el is not NULL, its element amounts. */
MQMQA_API int mqmqa_ph_ionic_size(const mqmqa_db *db, int p, int *nc, int *na);
MQMQA_API const char *mqmqa_ph_ionic_constituent(const mqmqa_db *db, int p, int i);
MQMQA_API double mqmqa_ph_ionic_gibbs(const mqmqa_db *db, int p, const double *y, double T,
                                      double *n_el);

/* --- Stoichiometric compounds (solid oxides etc., for later equilibrium) --- */
MQMQA_API int mqmqa_db_num_stoich(const mqmqa_db *db);
MQMQA_API const char *mqmqa_db_stoich_name(const mqmqa_db *db, int i);
MQMQA_API double mqmqa_db_stoich_gibbs(const mqmqa_db *db, int i, double T);
/* Element stoichiometry of stoichiometric phase i, in database element order
 * (length mqmqa_db_num_elements). */
MQMQA_API void mqmqa_db_stoich_elems(const mqmqa_db *db, int i, double *out);

/* --- Excess coefficients as fit parameters ---
 * Every excess coefficient of every solution phase, numbered 0..n-1: MQMX terms of
 * MQMQA phases first, then the Redlich-Kister terms of CEF phases, each phase in order.
 * info gives the phase, kind (0 MQMX, 1 CEF Redlich-Kister), term index within that
 * phase's list, coefficient slot, and the slot's temperature function (the ChemSage
 * excess basis code: 1 constant, 2 T, ...). set changes the value in memory only; the
 * next energy evaluation uses it, and a writer then records it. Both return -1 for an
 * index out of range. */
MQMQA_API int mqmqa_db_num_params(const mqmqa_db *db);
MQMQA_API int mqmqa_db_param_info(const mqmqa_db *db, int i, int *phase, int *kind,
                                  int *term, int *slot, int *tfun);
MQMQA_API double mqmqa_db_param_get(const mqmqa_db *db, int i);
MQMQA_API int mqmqa_db_param_set(mqmqa_db *db, int i, double value);

/* --- Writers (src/db_write.c) ---
 * Serialize a loaded database in another format. Each returns the whole file as a
 * NUL-terminated string the caller releases with mqmqa_text_free, or NULL when the
 * database holds a model the target cannot represent (or the source had content the
 * reader skipped); mqmqa_db_error() then names the model and a format that can hold
 * it. Nothing partial is ever returned. source_name (may be NULL) is recorded in the
 * provenance header with the engine version and the licensing note. Every file records
 * the database's own gas constant (never a forced mode's): FUNCTION R in .tdb/.utdb, a
 * TPfun R in .xtdb, the title line of a .dat. */
MQMQA_API char *mqmqa_db_write_tdb(const mqmqa_db *db, const char *source_name);
MQMQA_API char *mqmqa_db_write_utdb(const mqmqa_db *db, const char *source_name);
MQMQA_API char *mqmqa_db_write_dat(const mqmqa_db *db, const char *source_name);
MQMQA_API char *mqmqa_db_write_xtdb(const mqmqa_db *db, const char *source_name);
MQMQA_API void mqmqa_text_free(char *text);

/* --- Quadruplet enumeration (engine utility, no database needed) ---
 * The full quadruplet set is every unordered cation pair {i<=j} crossed with
 * every unordered anion pair {k<=l}. This is the state space the energy routines
 * and the solver iterate over. */
MQMQA_API int mqmqa_num_quadruplets(int n_cat, int n_an);
MQMQA_API void mqmqa_enumerate_quadruplets(int n_cat, int n_an,
                                           int *ca, int *cb, int *ax, int *ay);

/* Convenience over mqmqa_equilibrate (src/equil.c): equilibrate MQMQA phase `phase`
 * at T and a target composition over the database elements (length
 * mqmqa_db_num_elements). Assembles all model inputs from the parsed database.
 * Writes quadruplet fractions to X_out and the max composition error to err_out
 * (may be NULL). Returns GM per mole of atoms, or NaN on failure; a phase whose excess
 * the engine refuses returns NaN with the reason in mqmqa_db_error(). */
MQMQA_API double mqmqa_equilibrate_db(const mqmqa_db *db, int phase, double T,
                                      const double *target_elem,
                                      double *X_out, double *err_out);

/* The calls below take el_keep, a flag per database element (NULL: all present). An ion
 * whose element is not flagged is taken out of the phase, with every quadruplet, pair and
 * excess term naming it; its weight is zero then, so the energy of what remains is the
 * same. A subsystem of a larger database can so use its liquid. They fail (NaN or -1) if
 * a sublattice would be left empty. */

/* mqmqa_equilibrate_db restricted to the elements el_keep flags; returns GM per mole of
 * atoms, or NaN. */
MQMQA_API double mqmqa_equilibrate_sub_db(const mqmqa_db *db, int phase, double T,
                                          const double *target_elem, const int *el_keep);

/* Convenience over mqmqa_driving_force_minima (src/equil.c): the lowest points of
 * G - mu.n for MQMQA phase `phase` at T, the composition free, with mu over the database
 * elements. For each of up to max_out minima, lowest first, writes the ion fractions on
 * each sublattice to y_out (all ions of the phase, cations then anions, max_out rows; a
 * removed ion at 0), G per mole of atoms to g_out and the driving force G - mu.x per mole
 * of atoms to df_out. Returns how many, or -1 with the reason in mqmqa_db_error(). */
MQMQA_API int mqmqa_driving_force_db(const mqmqa_db *db, int phase, double T,
                                     const double *mu_elem, const int *el_keep, int max_out,
                                     double *y_out, double *g_out, double *df_out);

/* Tangent conditions of MQMQA phase `phase` at T and a composition over the database
 * elements. At its internal equilibrium every quadruplet present satisfies
 * dG/dX_q - dG/dX_q0 = sum_e mu_e (n_e(q) - n_e(q0)), q0 the most abundant. Writes up to
 * max_rows rows, the element amount differences to A_out (rows of mqmqa_db_num_elements)
 * and the gradient differences to b_out. Returns the row count, or -1 on failure. */
MQMQA_API int mqmqa_tangent_rows_db(const mqmqa_db *db, int phase, double T,
                                    const double *target_elem, const int *el_keep, int max_rows,
                                    double *A_out, double *b_out);

/* Self-contained multiphase equilibrium (src/equilibrium.c) for a 3-cation MQMQA
 * system: generates candidates from the liquid (`liq_phase`), the CEF solid solutions
 * `cef_phases`, and all stoichiometric compounds, then reads the stable assemblage
 * under the bulk cation composition (qa, qb) - the cation fractions of elements
 * elem_a, elem_b (database element indices). nliq/ncef set grid density. Writes stable
 * phase tags to phase_out (>=0 a database phase index; <0 the compound -(j+1)) and
 * their molar amounts to amt_out; *gm_out is the Gibbs energy per mole cation.
 * Returns the number of stable phases, or negative on failure (-3 when the liquid's
 * excess is refused, -4 when a CEF phase is not a line solution; the reason is in
 * mqmqa_db_error()). */
MQMQA_API int mqmqa_equilibrium_ternary(const mqmqa_db *db, int liq_phase,
                                        const int *cef_phases, int n_cef, double T,
                                        int nliq, int ncef, int elem_a, int elem_b,
                                        double qa, double qb, int *phase_out,
                                        double *amt_out, int max_out, double *gm_out);

/* As above with two conditions: stoich_suspend (may be NULL) is a per-compound mask,
 * 1 = that stoichiometric phase is suspended and excluded from the hull, giving the
 * metastable equilibrium without it; refine (>=0) runs that many adaptive passes that
 * densify the liquid sampling around the liquid hull vertices, sharpening the liquid
 * boundaries from grid resolution toward the true tie-line endpoints. */
MQMQA_API int mqmqa_equilibrium_ternary_ex(const mqmqa_db *db, int liq_phase,
                                           const int *cef_phases, int n_cef, double T,
                                           int nliq, int ncef, int elem_a, int elem_b,
                                           double qa, double qb, const int *stoich_suspend,
                                           int refine, int *phase_out, double *amt_out,
                                           int max_out, double *gm_out);

#ifdef __cplusplus
}
#endif

#endif /* MQMQA_CS_DAT_H */
