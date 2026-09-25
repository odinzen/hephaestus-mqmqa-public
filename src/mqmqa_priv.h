#ifndef MQMQA_PRIV_H
#define MQMQA_PRIV_H

/* Internal to the C core, not part of the public ABI. */

/* Why an MQMX excess term cannot be evaluated. The energy routine returns NaN for any
 * status other than XS_OK; the database layer turns the status into a message that
 * names the phase (mqmqa_ph_excess_unsupported). */
typedef enum {
    XS_OK = 0,
    XS_CODE,          /* excess code other than Q or G (Bragg-Williams B/H, reciprocal R) */
    XS_MIX,           /* reciprocal mixing: two cations and two anions in one term */
    XS_TERN_ANION,    /* additional constituent on an anion-mixing term */
    XS_TERN_R,        /* additional-constituent exponent r other than 1 */
    XS_GROUPS         /* needs the mixed chemical-group (nu/gamma) interpolation */
} mqmqa_xs_status;

/* Status of one excess term. cat_group/an_group may be NULL, meaning every species of
 * that sublattice is in one chemical group. */
mqmqa_xs_status mqmqa_excess_term_status(int n_cat, int n_an, int mix, int code,
                                         int A, int B, int X, int Y,
                                         double r, int addcat,
                                         const int *cat_group, const int *an_group);

/* The gas-constant mode changed: databases whose expressions reference R are re-read
 * with the value R now takes (cs_dat.c). */
void mqmqa_gas_constant_changed(void);

#endif /* MQMQA_PRIV_H */
