#ifndef MQMQA_GAS_H
#define MQMQA_GAS_H

/* Ideal-gas thermochemistry and equilibrium from NASA 7-coefficient polynomials.
 *
 * The combustion school ships its data as NASA/CHEMKIN thermo.dat cards, an open
 * format (NASA CEA, Burcat, GRI-Mech). This module reads those cards, evaluates the
 * standard-state Gibbs energy of each species, and finds the ideal-gas equilibrium
 * at a fixed temperature and pressure by the element-potential (RAND/CEA) method,
 * the same algorithm proven in python/mqmqa/gas.py against the Cantera oracle. It is
 * self-contained C11 with no dependencies, so it compiles to the WebAssembly engine
 * and runs in the browser exactly like the condensed-phase core.
 *
 * Standard-state reference pressure is 1 atm (101325 Pa), matching the polynomials.
 */

#include "mqmqa.h"   /* MQMQA_API, extern "C" wrapper */

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gas_db gas_db;

/* Parse a NASA/CHEMKIN thermo.dat string. Returns NULL on failure; the reason is
 * available from mqmqa_gas_error(). Release with mqmqa_gas_free. */
MQMQA_API gas_db *mqmqa_gas_read_string(const char *text);
MQMQA_API void mqmqa_gas_free(gas_db *g);
MQMQA_API const char *mqmqa_gas_error(void);

MQMQA_API int mqmqa_gas_num_species(const gas_db *g);
MQMQA_API const char *mqmqa_gas_species_name(const gas_db *g, int i);
MQMQA_API int mqmqa_gas_num_elements(const gas_db *g);
MQMQA_API const char *mqmqa_gas_element(const gas_db *g, int e);

/* Standard-state Gibbs energy over RT, G(T)/RT, of species i. */
MQMQA_API double mqmqa_gas_species_grt(const gas_db *g, int i, double T);

/* Ideal-gas equilibrium at temperature T (K) and pressure P (Pa). Element amounts
 * b are given in the database element order (mqmqa_gas_element), length
 * num_elements. Fills out_x (length num_species) with equilibrium mole fractions.
 * Returns 0 on success, non-zero on failure. */
MQMQA_API int mqmqa_gas_equilibrium(const gas_db *g, double T, double P,
                                    const double *b, double *out_x);

#ifdef __cplusplus
}
#endif

#endif
