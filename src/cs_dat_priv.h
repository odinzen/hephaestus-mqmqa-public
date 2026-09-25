#ifndef MQMQA_CS_DAT_PRIV_H
#define MQMQA_CS_DAT_PRIV_H

/* In-memory database model shared by the readers (cs_dat.c) and the writers
 * (db_write.c). Not part of the public ABI: callers go through the accessors in
 * cs_dat.h. Fields marked "metadata" do not enter any energy; the readers keep them
 * so a written file carries what the source said (limits, reference states,
 * provenance) instead of invented defaults. */

#define NAME_MAX 64
#define MAX_COEFFS 16

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
    int i, j;                   /* mixing constituents (local, name-sorted) */
    int order;                  /* Redlich-Kister order */
    double *coeff;              /* n_excess coefficients -> L(T) */
    int *other;                 /* [n_subl] pinned constituent on every other sublattice */
    double t_lo, t_hi;          /* metadata: TDB limits as written, NAN when unknown */
} CefExcess;

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
} SublPhase;

typedef struct {
    char name[NAME_MAX];
    int kind;                   /* 0 MQMQA (SUBQ/SUBG), 1 CEF (SUBL) */
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
    double R_own;               /* the database's own R, what as-assessed calculations use */
    int R_ref;                  /* TDB expressions reference the function R (R#) */
    double R_force;             /* value R# was forced to when the expressions were read,
                                 * NAN when the file's own (or the built-in) R stood */
    char *src_text;             /* the source as given, kept only when R_ref: a change of the
                                 * R the expressions need re-reads it */
    struct Db *next_live;       /* registry of databases to re-read on such a change */
} Db;

/* The database as its own gas constant has it, for the writers: NULL when d already is
 * (no R# references, or none re-read under a forced mode), else a fresh reading the
 * caller frees with mqmqa_db_free. */
Db *mqmqa_db_own_reading(const Db *d);

/* Record a write failure for mqmqa_db_error(). */
void mqmqa_db_set_error(const char *fmt, ...);

#endif /* MQMQA_CS_DAT_PRIV_H */
