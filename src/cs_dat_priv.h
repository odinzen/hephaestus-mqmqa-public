#ifndef MQMQA_CS_DAT_PRIV_H
#define MQMQA_CS_DAT_PRIV_H

/* In-memory database model shared by the readers (cs_dat.c) and the writers
 * (db_write.c). Not part of the public ABI: callers go through the accessors in
 * cs_dat.h. Fields marked "metadata" do not enter any energy; the readers keep them
 * so a written file carries what the source said (limits, reference states,
 * provenance) instead of invented defaults. */

#include "mqmqa_priv.h"   /* RInfo */

#define NAME_MAX 64
#define MAX_COEFFS 16
#define CS_GAS_P_REF 1.0e5   /* Pa: the pressure ChemSage gas data refer to, 1 bar */
/* buffer for a TDB PARAMETER descriptor, the text inside its parentheses */
#define TDB_DESC 512

typedef struct {
    double t_max;
    double coeff[MAX_COEFFS];   /* n_gibbs coefficients */
    int n_add;
    double *add_c;              /* additional coefficient/exponent pairs */
    double *add_e;
} Interval;

typedef struct {
    char name[NAME_MAX];
    double *stoich_el;          /* stoichiometry over pure elements (NULL from a TDB phase) */
    int n_intervals;
    Interval *intervals;
    int magnetic;               /* eq_type > 12: carries a magnetic contribution */
    int dummy;                  /* marked '#' in a ChemSage file: listed, never formed */
    double mag_tc, mag_beta;    /* ChemSage magnetic record: Curie/Neel T and moment */
    /* SUBQ pair extras */
    double stoich_quad[5];
    double zeta;
    int cat_idx, an_idx;        /* 0-based sublattice indices of this pair */
    /* metadata: the TDB lower limit and the last upper limit as written. NAN from a
     * ChemSage source, whose intervals start unbounded and stop at the last t_max. */
    double t_lo, t_top;
} Endmember;

typedef struct {
    int A, B, X, Y;             /* canonical: A<=B cations, X<=Y anions (0-based) */
    double Z[4];                /* slot coordinations [A,B,X,Y] */
} Mqmz;

typedef struct {
    char code;                  /* 'Q','G','B','R' */
    int mix;                    /* 0 cation, 1 anion, -1 other */
    int A, B, X, Y;             /* 0-based sublattice indices */
    int exp[4];
    int add_cat;                /* additional (ternary) cation, 0-based; -1 none */
    double *coeff;              /* n_excess coefficients */
    int mix_type;               /* metadata: the ChemSage mixing-type integer, 0 if unknown */
    double meta[12];            /* the twelve unmodeled numbers after the exponents */
    double t_lo, t_hi;          /* metadata: TDB limits as written, NAN when unknown */
} Mqmx;

/* --- compound-energy-formalism (SUBL) phase --- */
typedef struct {
    int subl;                   /* mixing sublattice (local) */
    int i, j;                   /* mixing constituents (local), in the file's order */
    int order;                  /* Redlich-Kister order */
    double *coeff;              /* n_excess coefficients -> L(T) */
    int *other;                 /* [n_subl] pinned constituent on every other sublattice */
    double t_lo, t_hi;          /* metadata: TDB limits as written, NAN when unknown */
} CefExcess;

/* A ternary or quaternary term mixing on one sublattice: L(T) times the product of the n
 * fractions, times v_w = y_w + (1 - sum of the n)/n when a weight is given (Muggianu's
 * composition-dependent ternary), else times 1, times the pinned fraction on every other
 * sublattice. A reciprocal term (subl2 >= 0) mixes a pair on each of two sublattices,
 * L(T) y_A y_B y_C y_D times the pins. */
typedef struct {
    int n;                      /* constituents in the term, 3 or 4 */
    int subl;                   /* the mixing sublattice */
    int c[4];                   /* their local constituent indices on it */
    int weight;                 /* index into c of the v-weighted one, -1 none */
    int *other;                 /* [n_subl] pinned constituent on every other sublattice, or NULL */
    int subl2, c2[2];           /* reciprocal: the second mixing sublattice and its pair; -1 none */
    double *coeff;              /* n_excess coefficients -> L(T) */
} CefHigher;

/* A Kohler polynomial term of a ChemSage QKTO phase (Pelton, Calphad 12 (1988) 127, eq. 12,
 * all species in one group): s^n L prod (Y_c / s)^p_c with s the sum of the n fractions,
 * n = 2 (a binary, eq. 7 at the Kohler point) or 3 (a ternary term). */
typedef struct {
    int n;
    int c[3];                   /* species */
    int p[3];                   /* the power of each, as the file gives it */
    double *coeff;              /* n_excess coefficients -> L(T) */
} QkTerm;

typedef struct {
    int n_subl;
    int magnetic;               /* Inden-Hillert-Jarl contribution active */
    double mag_afm, mag_p;      /* antiferromagnetic factor, structure p */
    double *tc_em, *bm_em;      /* [n_em*6] TC / BMAGN endmember coeffs (excess basis) */
    int n_tcx; CefExcess *tc_ex;    /* TC Redlich-Kister interactions */
    int n_bmx; CefExcess *bm_ex;    /* BMAGN Redlich-Kister interactions */
    double *site_ratio;         /* [n_subl] site multiplicity a_s */
    int *subl_ncon;             /* [n_subl] constituents per sublattice */
    int *subl_off;              /* [n_subl] offset of each sublattice into the flat arrays */
    int n_con;                  /* total constituents = sum(subl_ncon) */
    char (*con_name)[NAME_MAX]; /* [n_con] constituent names, flattened by sublattice */
    double *con_atoms;          /* [n_con] real atoms per constituent (0 for VA) */
    int n_em;
    Endmember *em;              /* [n_em] endmember Gibbs energies */
    int *em_con;                /* [n_em*n_subl] constituent index of each endmember per sublattice */
    int n_ex;
    CefExcess *ex;              /* [n_ex] Redlich-Kister interactions */
    int n_hx;
    CefHigher *hx;              /* [n_hx] ternary and quaternary terms (RKMP) */
    int n_qk;
    QkTerm *qk;                 /* [n_qk] Kohler polynomial terms (QKTO) */
    char cs_type[8];            /* ChemSage type when not SUBL (IDMX, RKMP), else empty */
    int gas;                    /* the ideal gas: G gains R T ln(P / 1 bar) per mole of species */
} SublPhase;

/* --- two-sublattice ionic liquid (ChemSage SUBI), Sundman, Calphad 15 (1991) 109 ---
 * (C)_P (A, Va, B)_Q with P = sum |v_A| y_A + Q y_Va and Q = sum v_C y_C. Constituents are
 * numbered cations first, then the second sublattice. Each excess term is one of the sums
 * of Sundman's eqs. 24 and 27; IonKind names which. */
typedef enum {
    ION_CC_A,       /* y_C1 y_C2 y_A (y_C1 - y_C2)^k L */
    ION_CC_VA,      /* Q y_Va^2 y_C1 y_C2 (y_Va y_C1 - y_Va y_C2)^k L (rule of pairs) */
    ION_C_AD,       /* y_C y_D1 y_D2 (y_D1 - y_D2)^k L, an anion among the D */
    ION_C_VAB,      /* Q y_Va y_C y_B (w_1 - w_2)^k L, w = y_Va y_C for Va, y_B for B (eq. 26) */
    ION_C_BB,       /* Q y_B1 y_B2 (y_B1 - y_B2)^k L */
    ION_CC_DD,      /* reciprocal y_C1 y_C2 y_D1 y_D2 L, an anion among the D (eq. 37) */
    ION_CC_VAB,     /* Q y_Va^2 y_C1 y_C2 y_B L (eq. 29) */
    ION_CCC_A,      /* y_C1 y_C2 y_C3 y_A v L, v_i = y_Ci + f */
    ION_CCC_VA,     /* Q y_Va^3 y_C1 y_C2 y_C3 v L, v_i = y_Va y_Ci + f (eqs. 32, 33) */
    ION_C_DDD,      /* y_C y_D1 y_D2 y_D3 v L, an anion among the D, v_i = y_Di + f */
    ION_C_VABB,     /* Q y_Va y_C y_B1 y_B2 v L, v = y_Va y_C + f for Va, y_B + f for B (eq. 36) */
    ION_C_BBB       /* Q y_B1 y_B2 y_B3 v L, v_i = y_Bi + f */
} IonKind;

typedef struct {
    IonKind kind;
    int c[4];                   /* constituents in file order, numbered as above */
    int order;                  /* Redlich-Kister order; for a ternary, the weighted one (-1 none) */
    double *coeff;              /* n_excess coefficients -> L(T) */
} IonTerm;

typedef struct {
    int nc, na;                 /* cations; constituents of the second sublattice */
    char (*name)[NAME_MAX];     /* [nc + na] */
    double *q;                  /* [nc + na] cation charge, |anion charge|; 0 for Va and neutrals */
    char *type;                 /* [nc + na] 'C', 'A', 'V' (vacancy) or 'B' (neutral) */
    int va;                     /* the vacancy, -1 when there is none */
    int n_em;
    Endmember *em;              /* records as the file lists them */
    int *em_of;                 /* [nc * na] record of cation c with constituent d */
    double *comp;               /* [(nc + na) * n_el] element amounts per constituent */
    int n_t;
    IonTerm *t;
} IonicPhase;

typedef struct {
    char name[NAME_MAX];
    int kind;                   /* 0 MQMQA (SUBQ/SUBG), 1 CEF (SUBL), 2 ionic liquid (SUBI) */
    int soln_type;              /* 1 SUBQ, 0 SUBG, -1 other */
    double subg_zeta;           /* single global zeta for SUBG */
    int n_cat, n_an, n_pairs, n_quads;
    char (*cat_name)[NAME_MAX];
    char (*an_name)[NAME_MAX];
    double *cat_charge, *an_charge;
    int *cat_group, *an_group;
    int n_group_override;       /* ChemSage chemical-group override strings read (not modeled) */
    Endmember *pairs;
    Mqmz *mqmz;
    int n_mqmx;
    Mqmx *mqmx;
    SublPhase *cef;             /* non-NULL when kind == 1 */
    IonicPhase *ion;            /* non-NULL when kind == 2 */
    const int *ion_off;         /* MQMQA ions (cations, then anions) held at zero for the solve
                                   that set it, the general solver's face reduction; NULL else */
} Phase;

/* A declared TDB species: element composition (indices into the element list) and
 * charge. The ChemSage reader has no species table; its constituents are named. */
typedef struct {
    char name[NAME_MAX];
    int n_el;
    int el[8];
    double n[8];
    double charge;
} DbSpecies;

/* Species evaluated above the end of their data, each with the highest T it was asked at */
typedef struct BeyondLog {
    int n, cap;
    const Endmember **em;
    double *T;
} BeyondLog;

typedef struct Db {
    int n_el;
    char (*el_name)[NAME_MAX];
    double *el_mass;
    int n_gibbs, gibbs_idx[MAX_COEFFS];
    int n_excess, excess_idx[MAX_COEFFS];
    int n_phases;
    Phase *phases;
    int n_stoich;
    Endmember *stoich;
    /* metadata */
    /* the source's own header: a ChemSage title line, or the leading comment lines
     * of a TDB file (newline-separated), carried into a converted file's header */
    char title[1024];
    char (*el_ref)[NAME_MAX];   /* TDB element reference phase, NULL when unknown */
    double *el_h298, *el_s298;
    int n_sp;
    DbSpecies *sp;
    /* limits of the first TDB parameter, standing in for statements whose own limits
     * are not kept (TC/BMAGN endmember rows, MQ constants); NAN from ChemSage */
    double lim_lo, lim_hi;
    /* First source content the reader skipped without modeling (a magnetic ChemSage
     * record, an unread TDB parameter type, ...). Empty when the model is complete.
     * The writers refuse such a database: re-serializing it would drop that content
     * with no trace. */
    char lossy[256];
    /* gas constant */
    RInfo R;                    /* the database's own R and where it came from */
    int R_ref;                  /* TDB expressions reference the function R (R#) */
    double R_force;             /* value R# was forced to when the expressions were read,
                                 * NAN when the file's own (or the built-in) R stood */
    char *src_text;             /* the source as given, kept only when R_ref: a change of the
                                 * R the expressions need re-reads it */
    struct Db *next_live;       /* registry of databases to re-read on such a change */
    double P;                   /* pressure (Pa) for the gas phase, 0 standing for 1 atm */
    /* species whose energy was taken past the end of its data, the last range carried
     * on: logged as they are evaluated, cleared and read by the caller */
    struct BeyondLog *beyond;
} Db;

/* The database as its own gas constant has it, for the writers: NULL when d already is
 * (no R# references, or none re-read under a forced mode), else a fresh reading the
 * caller frees with mqmqa_db_free. */
Db *mqmqa_db_own_reading(const Db *d);

/* Record a write failure for mqmqa_db_error(). */
void mqmqa_db_set_error(const char *fmt, ...);

/* Element amounts of every ion of MQMQA phase p, cations then anions, n_el per ion, into
 * comp. An ion is one atom of the element it names (Fe+2), nothing for a vacancy (Va), its
 * declared species (TDB), or else read from the pair records: a pair is the neutral unit
 * of its two ions, q_a/g cations and q_c/g anions (g their charges' common divisor), so
 * Al2Cl6 with Cl known gives Al2 two Al. Every pair is then checked against the result.
 * Returns 0, or -1 with the reason in mqmqa_db_error(). */
int mqmqa_ph_ion_comps(const Db *db, int p, double *comp);

/* An MQMQA phase opened once at temperature T for repeated evaluation over its quadruplet
 * fractions (the exact finish in gem.c treats quadruplets as species). el_keep as for
 * mqmqa_equilibrate_sub_db, NULL for every element. */
typedef struct mqmqa_quad_ctx mqmqa_quad_ctx;
mqmqa_quad_ctx *mqmqa_quad_open(const mqmqa_db *db, int phase, double T, const int *el_keep);
void mqmqa_quad_close(mqmqa_quad_ctx *c);
int mqmqa_quad_count(const mqmqa_quad_ctx *c);
/* element amounts of each quadruplet over the database elements, [count * n_el] */
void mqmqa_quad_elements(const mqmqa_quad_ctx *c, double *comp);
/* Gibbs energy per mole of quadruplets at fractions X (all positive), and its exact
 * gradient when grad is not NULL */
double mqmqa_quad_gibbs(const mqmqa_quad_ctx *c, const double *X, double *grad);
/* the internal equilibrium at an element composition over the database elements; 0 or -1 */
int mqmqa_quad_start(mqmqa_quad_ctx *c, const double *target_elem, double *X_out);

/* mqmqa_equilibrate_sub_db, also reporting the largest element mole-fraction error */
double mqmqa_equilibrate_sub_err(const mqmqa_db *db, int phase, double T,
                                 const double *target_elem, const int *el_keep, double *err_out);

#endif /* MQMQA_CS_DAT_PRIV_H */
