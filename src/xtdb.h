#ifndef MQMQA_XTDB_H
#define MQMQA_XTDB_H

/* XTDB (XML CALPHAD) reader with third-generation Einstein + two-state models. Self-contained;
 * see xtdb.c. Clean-room from the published XTDB format and model equations. */

#include "mqmqa.h"   /* MQMQA_API, extern "C" */

#ifdef __cplusplus
extern "C" {
#endif

typedef struct xtdb_db xtdb_db;

MQMQA_API xtdb_db *xtdb_read_string(const char *text);   /* NULL on error, see xtdb_error() */
MQMQA_API void xtdb_free(xtdb_db *db);
MQMQA_API const char *xtdb_error(void);

MQMQA_API int xtdb_n_elements(const xtdb_db *db);
MQMQA_API const char *xtdb_element(const xtdb_db *db, int i);
MQMQA_API int xtdb_n_phases(const xtdb_db *db);
MQMQA_API const char *xtdb_phase(const xtdb_db *db, int p);

/* Third-generation endmember Gibbs energy (J/mol-formula) for a phase and a colon-separated
 * constituent set (e.g. "AL:VA"), including the Einstein GEIN(theta) term and, for a two-state
 * phase, the -R T ln(1+exp(-GD/RT)) contribution. Sets *ok to 0 on an expression error. */
MQMQA_API double xtdb_endmember_gibbs(const xtdb_db *db, const char *phase, const char *cons,
                                      double T, int *ok);

/* Gibbs energy per mole of atoms for phase index `p` at overall mole fraction `xB` of element
 * `B`, and temperature T. Assembles the CEF reference, ideal configurational entropy,
 * Redlich-Kister excess, and (for a two-state liquid) the -R T ln(1+exp(-GD/RT)) term. For a
 * stoichiometric phase, xB is ignored and its fixed composition is written to *fixed (else -1).
 * Returns NAN and clears *ok when xB is outside the phase's composition range. */
MQMQA_API double xtdb_phase_gibbs(const xtdb_db *db, int p, const char *B, double xB, double T,
                                  double *fixed, int *ok);

#ifdef __cplusplus
}
#endif

#endif
