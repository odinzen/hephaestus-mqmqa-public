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

/* As above, with nonideal=1 selecting the Peng-Robinson real-gas fugacity model
 * (species that carry critical constants); nonideal=0 is the ideal-gas result. */
MQMQA_API int mqmqa_gas_equilibrium_ex(const gas_db *g, double T, double P,
                                       const double *b, int nonideal, double *out_x);

/* Coupled ideal-gas + pure-condensed equilibrium at fixed T, P and element feed. The gas
 * and every condensed species share one set of element potentials, so they settle to a
 * common oxygen potential; the stable assemblage is the set of lowest total Gibbs energy.
 *
 * Elements are a caller-supplied combined list of length n_elem whose first
 * mqmqa_gas_num_elements(g) entries ARE the gas elements in the database's own order (so a
 * gas species' element indices are combined indices directly); any further entries are
 * condensed-only elements. b[e] is the feed of element e. Condensed species i has molar
 * Gibbs over RT cond_grt[i] at T and stoichiometry cond_stoich[i*n_elem + e] (atoms of
 * element e). Fills out_x (gas mole fractions, length num_species), out_cond (moles of each
 * condensed species, 0 when absent, length n_cond) and out_pi (element potentials mu_e/RT,
 * length n_elem). Returns 0 on success, non-zero on failure. Mirrors and is validated
 * against python/mqmqa/gas.py:gas_condensed_equilibrium. */
MQMQA_API int mqmqa_gas_condensed_equilibrium(
    const gas_db *g, int n_elem, const double *b, double T, double P,
    int n_cond, const double *cond_grt, const double *cond_stoich,
    double *out_x, double *out_cond, double *out_pi);

#ifdef __cplusplus
}
#endif

#endif
