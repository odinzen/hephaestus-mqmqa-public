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

/* A loaded database's gas constant: its own value and where that came from. */
typedef struct {
    double own;              /* what as-assessed calculations use */
    int src;                 /* MQMQA_R_SRC_* of own (never OVERRIDE) */
    double found;            /* what the file gave: stated, inferred, or the convention */
    int found_src;
    char format[24];         /* the format named in the note, ".tdb" etc. */
    char detail[200];        /* a literal conflict, or what R# evaluates to */
} RInfo;

/* Settle a database's R from what its file says. stated: the file states R as
 * stated_value. Otherwise R is inferred from gas-constant literals in `text` (NULL for a
 * format with no expressions): kind 1 scans TDB statements, kind 2 XTDB Expr
 * attributes. Failing both, the format's convention. */
void rinfo_detect(RInfo *ri, const char *format, double convention, int stated,
                  double stated_value, const char *text, int kind);
/* 0 on success; -1 when the file states R (nothing to declare); -2 for a bad choice.
 * MQMQA_R_AS_ASSESSED withdraws a declaration. */
int rinfo_declare(RInfo *ri, int choice);
double rinfo_value(const RInfo *ri);         /* the R calculations use now */
int rinfo_source(const RInfo *ri);           /* OVERRIDE while a mode is forced */
const char *rinfo_note(const RInfo *ri);     /* one line for the user, static buffer */

#endif /* MQMQA_PRIV_H */
