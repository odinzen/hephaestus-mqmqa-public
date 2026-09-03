#include "cs_dat.h"
#include "cef.h"

#include <ctype.h>
#include <math.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ *
 * Term basis, shared by Gibbs and excess expressions.
 *
 * ChemApp numbers the temperature functions from 1; index 0 is a pad so the
 * file's 1-based coefficient indices need no shifting. Indices 7,8 are the
 * pressure terms, which the isobaric energy here evaluates to zero.
 * ------------------------------------------------------------------ */
static double term_value(int idx, double T)
{
    switch (idx) {
    case 0: return 0.0;
    case 1: return 1.0;
    case 2: return T;
    case 3: return T * log(T);
    case 4: return T * T;
    case 5: return T * T * T;
    case 6: return 1.0 / T;
    case 7: return 0.0;  /* P   */
    case 8: return 0.0;  /* P^2 */
    default: return 0.0;
    }
}

/* ------------------------------------------------------------------ *
 * In-memory model
 * ------------------------------------------------------------------ */
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
    double *stoich_el;          /* stoichiometry over pure elements */
    int n_intervals;
    Interval *intervals;
    int magnetic;               /* eq_type > 12: carries a magnetic contribution */
    /* SUBQ pair extras */
    double stoich_quad[5];
    double zeta;
    int cat_idx, an_idx;        /* 0-based sublattice indices of this pair */
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
} Mqmx;

/* --- compound-energy-formalism (SUBL) phase --- */
typedef struct {
    int subl;                   /* mixing sublattice (local) */
    int i, j;                   /* mixing constituents (local, name-sorted) */
    int order;                  /* Redlich-Kister order */
    double *coeff;              /* n_excess coefficients -> L(T) */
    int *other;                 /* [n_subl] pinned constituent on every other sublattice */
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
    Endmember *pairs;
    Mqmz *mqmz;
    int n_mqmx;
    Mqmx *mqmx;
    SublPhase *cef;             /* non-NULL when kind == 1 */
} Phase;

typedef struct {
    int n_el;
    char (*el_name)[NAME_MAX];
    double *el_mass;
    int n_gibbs, gibbs_idx[MAX_COEFFS];
    int n_excess, excess_idx[MAX_COEFFS];
    int n_phases;
    Phase *phases;
    int n_stoich;
    Endmember *stoich;
} Db;

/* ------------------------------------------------------------------ *
 * Lexer. A whitespace-tokenized view over an owned, uppercased copy of the
 * file. Parse errors longjmp back to the read entry point with a message, so
 * the recursive-descent code below stays free of error plumbing.
 * ------------------------------------------------------------------ */
typedef struct {
    char *buf;
    char *cur;
    int line;
    char *tok_end;      /* where the last tok() wrote its terminator, or NULL */
    char tok_end_ch;    /* the byte it overwrote, so a peek can restore it */
    char peekbuf[NAME_MAX];
    jmp_buf jb;
    char err[256];
} Lexer;

static _Thread_local char g_error[256] = "";

static void lex_fail(Lexer *lx, const char *what)
{
    snprintf(lx->err, sizeof lx->err, "line %d: %s", lx->line, what);
    longjmp(lx->jb, 1);
}

/* Next whitespace-delimited token, null-terminated in place. NULL only at EOF. */
static char *tok(Lexer *lx)
{
    char *p = lx->cur;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\r') p++;
        if (*p == '\n') { lx->line++; p++; continue; }
        if (*p == '\0') { lx->cur = p; return NULL; }
        break;
    }
    char *start = p;
    while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
    if (*p) { lx->tok_end = p; lx->tok_end_ch = *p; *p = '\0'; p++; }
    else { lx->tok_end = NULL; }
    lx->cur = p;
    return start;
}

static char *tok_req(Lexer *lx)
{
    char *t = tok(lx);
    if (!t) lex_fail(lx, "unexpected end of file");
    return t;
}

/* Peek the next token without consuming it. Returns a stable copy (the buffer's
 * injected terminator is undone so the stream is untouched). NULL at EOF. */
static const char *tok_peek(Lexer *lx)
{
    char *save = lx->cur;
    int saveline = lx->line;
    char *t = tok(lx);
    if (!t) { lx->cur = save; lx->line = saveline; return NULL; }
    size_t n = strlen(t);
    if (n >= sizeof lx->peekbuf) n = sizeof lx->peekbuf - 1;
    memcpy(lx->peekbuf, t, n);
    lx->peekbuf[n] = '\0';
    if (lx->tok_end) *lx->tok_end = lx->tok_end_ch;  /* undo the terminator */
    lx->cur = save;
    lx->line = saveline;
    return lx->peekbuf;
}

static int is_int_token(const char *s)
{
    if (!s) return 0;
    if (*s == '+' || *s == '-') s++;
    if (!*s) return 0;
    for (; *s; ++s)
        if (!isdigit((unsigned char)*s)) return 0;
    return 1;
}

static int tok_int(Lexer *lx)
{
    char *t = tok_req(lx);
    char *end;
    long v = strtol(t, &end, 10);
    if (*end != '\0') lex_fail(lx, "expected an integer");
    return (int)v;
}

static double tok_dbl(Lexer *lx)
{
    char *t = tok_req(lx);
    char *end;
    double v = strtod(t, &end);
    if (*end != '\0') lex_fail(lx, "expected a number");
    return v;
}

static void tok_name(Lexer *lx, char out[NAME_MAX])
{
    char *t = tok_req(lx);
    size_t n = strlen(t);
    if (n >= NAME_MAX) n = NAME_MAX - 1;
    memcpy(out, t, n);
    out[n] = '\0';
}

/* Checked allocation: longjmp on failure rather than returning NULL upward. */
static void *xalloc(Lexer *lx, size_t n)
{
    void *p = calloc(n ? n : 1, 1);
    if (!p) lex_fail(lx, "out of memory");
    return p;
}

/* ------------------------------------------------------------------ *
 * Endmember (Gibbs energy) parsing, following the ChemApp thermodynamic
 * data options. Only the plain Gibbs intervals (options 1-6) are handled;
 * heat-capacity and molar-volume options are rejected, matching the target
 * SUBQ slag/salt databases.
 * ------------------------------------------------------------------ */
static Interval parse_interval(Lexer *lx, int n_gibbs, int has_additional)
{
    Interval iv;
    memset(&iv, 0, sizeof iv);
    iv.t_max = tok_dbl(lx);
    for (int i = 0; i < n_gibbs; ++i) iv.coeff[i] = tok_dbl(lx);
    if (has_additional) {
        iv.n_add = tok_int(lx);
        if (iv.n_add < 0) lex_fail(lx, "negative additional-term count");
        iv.add_c = xalloc(lx, (size_t)iv.n_add * sizeof(double));
        iv.add_e = xalloc(lx, (size_t)iv.n_add * sizeof(double));
        for (int i = 0; i < iv.n_add; ++i) {
            iv.add_c[i] = tok_dbl(lx);
            iv.add_e[i] = tok_dbl(lx);
        }
    }
    return iv;
}

/* Parse one endmember into `em`. n_el pure-element stoichiometries are read.
 * `is_stoich` allows the trailing "#" dummy-species marker of stoichiometric
 * phases. The five quadruplet-stoichiometry values and zeta of SUBQ pairs are
 * NOT read here; parse_subq_phase does that after this returns. */
static void parse_endmember(Lexer *lx, Endmember *em, int n_el, int n_gibbs)
{
    memset(em, 0, sizeof *em);
    tok_name(lx, em->name);
    const char *pk = tok_peek(lx);
    if (pk && strcmp(pk, "#") == 0) tok_req(lx);

    /* Gibbs equation type. A species line may carry two (usually zero) floats
     * before the type; tolerate and discard them when they are zero. */
    int eq_type;
    if (is_int_token(tok_peek(lx))) {
        eq_type = tok_int(lx);
    } else {
        double f1 = tok_dbl(lx), f2 = tok_dbl(lx);
        if (f1 != 0.0 || f2 != 0.0)
            lex_fail(lx, "non-zero pre-type floats on species line not supported");
        eq_type = tok_int(lx);
    }

    int magnetic = eq_type > 12;
    em->magnetic = magnetic;
    int reduced = magnetic ? eq_type - 12 : eq_type;
    if (reduced < 1 || reduced > 6)
        lex_fail(lx, "only Gibbs-energy data options (1-6) are supported");
    int has_additional = (reduced == 4 || reduced == 5 || reduced == 6);
    if (reduced == 2 || reduced == 5)
        lex_fail(lx, "constant molar-volume options are not supported");
    if (reduced == 3 || reduced == 6)
        lex_fail(lx, "P-T molar-volume options are not supported");

    em->n_intervals = tok_int(lx);
    if (em->n_intervals < 1) lex_fail(lx, "endmember with no intervals");
    em->stoich_el = xalloc(lx, (size_t)n_el * sizeof(double));
    for (int i = 0; i < n_el; ++i) em->stoich_el[i] = tok_dbl(lx);

    em->intervals = xalloc(lx, (size_t)em->n_intervals * sizeof(Interval));
    for (int i = 0; i < em->n_intervals; ++i)
        em->intervals[i] = parse_interval(lx, n_gibbs, has_additional);

    if (magnetic) { (void)tok_dbl(lx); (void)tok_dbl(lx); } /* Tc, moment: unused */
}

static double endmember_gibbs(const Db *db, const Endmember *em, double T)
{
    /* Piecewise in T: the first interval whose upper bound exceeds T. Above the
     * last bound the ChemApp convention gives zero. */
    const Interval *iv = NULL;
    for (int i = 0; i < em->n_intervals; ++i) {
        if (T < em->intervals[i].t_max) { iv = &em->intervals[i]; break; }
    }
    if (!iv) return 0.0;

    double g = 0.0;
    for (int i = 0; i < db->n_gibbs; ++i)
        g += iv->coeff[i] * term_value(db->gibbs_idx[i], T);
    for (int i = 0; i < iv->n_add; ++i) {
        double e = iv->add_e[i];
        g += (e == 99.0) ? iv->add_c[i] * log(T) : iv->add_c[i] * pow(T, e);
    }
    return g;
}

static double excess_coeff_gibbs(const Db *db, const double *coeff, double T)
{
    double g = 0.0;
    for (int i = 0; i < db->n_excess; ++i)
        g += coeff[i] * term_value(db->excess_idx[i], T);
    return g;
}

/* ------------------------------------------------------------------ *
 * SUBQ / SUBG phase
 * ------------------------------------------------------------------ */
static void parse_subq_phase(Lexer *lx, Db *db, Phase *ph, const char *type)
{
    ph->soln_type = strcmp(type, "SUBQ") == 0 ? 1 : 0;

    if (ph->soln_type == 0) ph->subg_zeta = tok_dbl(lx); /* SUBG: one global zeta */

    ph->n_pairs = tok_int(lx);
    ph->n_quads = tok_int(lx);
    if (ph->n_pairs < 1 || ph->n_quads < 1) lex_fail(lx, "bad pair/quadruplet count");

    ph->pairs = xalloc(lx, (size_t)ph->n_pairs * sizeof(Endmember));
    for (int k = 0; k < ph->n_pairs; ++k) {
        Endmember *em = &ph->pairs[k];
        parse_endmember(lx, em, db->n_el, db->n_gibbs);
        for (int i = 0; i < 5; ++i) em->stoich_quad[i] = tok_dbl(lx);
        em->zeta = (ph->soln_type == 1) ? tok_dbl(lx) : ph->subg_zeta;
    }

    ph->n_cat = tok_int(lx);
    ph->n_an = tok_int(lx);
    if (ph->n_cat < 1 || ph->n_an < 1) lex_fail(lx, "bad sublattice size");
    if (ph->n_pairs != ph->n_cat * ph->n_an)
        lex_fail(lx, "pair count does not equal n_cat * n_an");

    ph->cat_name = xalloc(lx, (size_t)ph->n_cat * sizeof(*ph->cat_name));
    ph->an_name = xalloc(lx, (size_t)ph->n_an * sizeof(*ph->an_name));
    ph->cat_charge = xalloc(lx, (size_t)ph->n_cat * sizeof(double));
    ph->an_charge = xalloc(lx, (size_t)ph->n_an * sizeof(double));
    ph->cat_group = xalloc(lx, (size_t)ph->n_cat * sizeof(int));
    ph->an_group = xalloc(lx, (size_t)ph->n_an * sizeof(int));

    for (int i = 0; i < ph->n_cat; ++i) tok_name(lx, ph->cat_name[i]);
    for (int k = 0; k < ph->n_an; ++k) tok_name(lx, ph->an_name[k]);
    for (int i = 0; i < ph->n_cat; ++i) ph->cat_charge[i] = tok_dbl(lx);
    for (int i = 0; i < ph->n_cat; ++i) ph->cat_group[i] = tok_int(lx);
    /* anion charges are given as positive magnitudes in the file */
    for (int k = 0; k < ph->n_an; ++k) ph->an_charge[k] = tok_dbl(lx);
    for (int k = 0; k < ph->n_an; ++k) ph->an_group[k] = tok_int(lx);

    /* The pair endmembers came in the order of these (cation, anion) index
     * labels; attach them so each pair knows its sublattice position. */
    int npair = ph->n_cat * ph->n_an;
    int *cat_of = xalloc(lx, (size_t)npair * sizeof(int));
    int *an_of = xalloc(lx, (size_t)npair * sizeof(int));
    for (int k = 0; k < npair; ++k) cat_of[k] = tok_int(lx);
    for (int k = 0; k < npair; ++k) an_of[k] = tok_int(lx);
    for (int k = 0; k < ph->n_pairs; ++k) {
        ph->pairs[k].cat_idx = cat_of[k] - 1;   /* file is 1-based */
        ph->pairs[k].an_idx = an_of[k] - 1;
    }
    free(cat_of);
    free(an_of);

    /* Coordination (MQMZ) entries. The four linear indices span cations then
     * anions; convert to sublattice-local 0-based and canonicalize A<=B, X<=Y,
     * carrying the coordinations with them. */
    ph->mqmz = xalloc(lx, (size_t)ph->n_quads * sizeof(Mqmz));
    for (int q = 0; q < ph->n_quads; ++q) {
        int li[4];
        double z[4];
        for (int i = 0; i < 4; ++i) li[i] = tok_int(lx);
        for (int i = 0; i < 4; ++i) z[i] = tok_dbl(lx);
        int a = li[0] - 1, b = li[1] - 1;                 /* cation locals */
        int x = li[2] - 1 - ph->n_cat, y = li[3] - 1 - ph->n_cat; /* anion locals */
        double za = z[0], zb = z[1], zx = z[2], zy = z[3];
        if (a > b) { int t = a; a = b; b = t; double tz = za; za = zb; zb = tz; }
        if (x > y) { int t = x; x = y; y = t; double tz = zx; zx = zy; zy = tz; }
        Mqmz *m = &ph->mqmz[q];
        m->A = a; m->B = b; m->X = x; m->Y = y;
        m->Z[0] = za; m->Z[1] = zb; m->Z[2] = zx; m->Z[3] = zy;
    }

    /* Excess (MQMX) parameters, terminated by a 0 mixing type. A negative type
     * introduces chemical-group override strings, which we consume and ignore
     * (with no ternary systems in the seed databases they never fire). */
    int cap = 8, n = 0;
    ph->mqmx = xalloc(lx, (size_t)cap * sizeof(Mqmx));
    for (;;) {
        int mixing_type = tok_int(lx);
        if (mixing_type == 0) break;
        if (mixing_type < 0) {
            for (int i = 0; i < -mixing_type; ++i)
                for (int j = 0; j < 10; ++j) (void)tok_req(lx);
            break;
        }
        if (n == cap) {
            cap *= 2;
            Mqmx *grown = xalloc(lx, (size_t)cap * sizeof(Mqmx));
            memcpy(grown, ph->mqmx, (size_t)n * sizeof(Mqmx));
            free(ph->mqmx);
            ph->mqmx = grown;
        }
        Mqmx *mx = &ph->mqmx[n++];
        memset(mx, 0, sizeof *mx);
        char code[NAME_MAX];
        tok_name(lx, code);
        mx->code = code[0];
        int li[4];
        for (int i = 0; i < 4; ++i) li[i] = tok_int(lx);
        for (int i = 0; i < 4; ++i) mx->exp[i] = tok_int(lx);
        for (int i = 0; i < 12; ++i) (void)tok_dbl(lx);   /* metadata, always zero here */
        {
            /* additional (ternary) mixing constituents: a cation index is stored and
             * evaluated (Poschmann Eq 25-26); an anion one is not supported. */
            int addc = tok_int(lx);
            int adda = tok_int(lx);
            if (adda != 0) lex_fail(lx, "additional anion mixing constituent not supported");
            if (addc < 0 || addc > ph->n_cat)
                lex_fail(lx, "additional cation mixing constituent out of range");
            mx->add_cat = addc - 1;                       /* 0 -> -1 = none */
        }
        mx->coeff = xalloc(lx, (size_t)db->n_excess * sizeof(double));
        for (int i = 0; i < db->n_excess; ++i) mx->coeff[i] = tok_dbl(lx);

        int A = li[0] - 1, B = li[1] - 1;
        int X = li[2] - 1 - ph->n_cat, Y = li[3] - 1 - ph->n_cat;
        mx->A = A; mx->B = B; mx->X = X; mx->Y = Y;
        if (A != B && X == Y) mx->mix = 0;
        else if (A == B && X != Y) mx->mix = 1;
        else mx->mix = -1;
    }
    ph->n_mqmx = n;
}

/* ------------------------------------------------------------------ *
 * SUBL (compound-energy-formalism) phase
 *
 * Grammar (clean-room from the ChemApp format and cross-checked against
 * pycalphad's open ChemSage reader):
 *   num_const endmembers (parse_endmember)
 *   num_subl
 *   site fraction of each sublattice          [num_subl floats]
 *   constituent count of each sublattice      [num_subl ints]
 *   constituent names, sublattice by sublattice
 *   endmember constituent index, sublattice by sublattice (num_em each, 1-based)
 *   Redlich-Kister excess block, 0-terminated
 * The number of endmembers is not in the phase block; it is the phase's species
 * count from the header (num_const), exactly as for the SUBQ pair count semantics.
 * ------------------------------------------------------------------ */
static void parse_subl_phase(Lexer *lx, Db *db, Phase *ph, int num_const)
{
    ph->kind = 1;
    ph->soln_type = -1;
    SublPhase *cf = xalloc(lx, sizeof(SublPhase));
    ph->cef = cf;

    /* number of atoms per formula unit, from an optional ":N" suffix on the phase
     * name (e.g. SIGMA:30); default 1. Site ratios = num_atoms * site fraction. */
    double num_atoms = 1.0;
    const char *colon = strchr(ph->name, ':');
    if (colon && colon[1]) num_atoms = strtod(colon + 1, NULL);

    cf->n_em = num_const;
    cf->em = xalloc(lx, (size_t)num_const * sizeof(Endmember));
    for (int e = 0; e < num_const; ++e)
        parse_endmember(lx, &cf->em[e], db->n_el, db->n_gibbs);

    cf->n_subl = tok_int(lx);
    if (cf->n_subl < 1) lex_fail(lx, "SUBL phase with no sublattices");
    cf->site_ratio = xalloc(lx, (size_t)cf->n_subl * sizeof(double));
    cf->subl_ncon = xalloc(lx, (size_t)cf->n_subl * sizeof(int));
    cf->subl_off = xalloc(lx, (size_t)cf->n_subl * sizeof(int));
    for (int s = 0; s < cf->n_subl; ++s) cf->site_ratio[s] = num_atoms * tok_dbl(lx);
    for (int s = 0; s < cf->n_subl; ++s) {
        cf->subl_ncon[s] = tok_int(lx);
        if (cf->subl_ncon[s] < 1) lex_fail(lx, "sublattice with no constituents");
    }
    cf->n_con = 0;
    for (int s = 0; s < cf->n_subl; ++s) {
        cf->subl_off[s] = cf->n_con;
        cf->n_con += cf->subl_ncon[s];
    }
    cf->con_name = xalloc(lx, (size_t)cf->n_con * sizeof(*cf->con_name));
    cf->con_atoms = xalloc(lx, (size_t)cf->n_con * sizeof(double));
    for (int s = 0; s < cf->n_subl; ++s)
        for (int i = 0; i < cf->subl_ncon[s]; ++i) {
            char *nm = cf->con_name[cf->subl_off[s] + i];
            tok_name(lx, nm);
            /* monatomic constituents (elements / single ions) contribute one atom;
             * the vacancy VA contributes none. This is the standard ionic/metallic
             * sublattice convention and matches pycalphad's per-atom GM. */
            cf->con_atoms[cf->subl_off[s] + i] = (strcmp(nm, "VA") == 0) ? 0.0 : 1.0;
        }

    /* endmember constituent indices: num_subl rows, each num_em 1-based indices */
    int n_em = cf->n_em;
    cf->em_con = xalloc(lx, (size_t)n_em * cf->n_subl * sizeof(int));
    for (int s = 0; s < cf->n_subl; ++s)
        for (int e = 0; e < n_em; ++e)
            cf->em_con[e * cf->n_subl + s] = tok_int(lx) - 1;

    /* cumulative constituent counts, for decoding the excess linear indices */
    int cum[64];
    if (cf->n_subl > 64) lex_fail(lx, "too many sublattices");
    int run = 0;
    for (int s = 0; s < cf->n_subl; ++s) { run += cf->subl_ncon[s]; cum[s] = run; }

    /* Redlich-Kister excess parameters, 0-terminated. Each entry lists the
     * interacting constituents as linear 1-based indices across all sublattices
     * (the mixing sublattice contributes two, every other sublattice one), then a
     * count of RK orders and that many coefficient rows. */
    int cap = 8;
    cf->n_ex = 0;
    cf->ex = xalloc(lx, (size_t)cap * sizeof(CefExcess));
    for (;;) {
        int n_int = tok_int(lx);
        if (n_int == 0) break;
        if (n_int < 0) lex_fail(lx, "unsupported excess mixing type in SUBL phase");

        /* decode linear indices into per-sublattice local constituent lists */
        int listed[64];             /* local constituent listed on each sublattice, or -1 */
        int mix_a[64], mix_b[64];   /* the (up to two) mixing constituents per sublattice */
        int listed_count[64];
        for (int s = 0; s < cf->n_subl; ++s) { listed[s] = -1; listed_count[s] = 0; }
        for (int t = 0; t < n_int; ++t) {
            int lin = tok_int(lx);
            int s = 0;
            while (s < cf->n_subl && cum[s] < lin) s++;
            if (s >= cf->n_subl) lex_fail(lx, "excess constituent index out of range");
            int base = (s == 0) ? 0 : cum[s - 1];
            int local = lin - base - 1;
            if (local < 0 || local >= cf->subl_ncon[s])
                lex_fail(lx, "excess constituent index out of range");
            if (listed_count[s] == 0) { mix_a[s] = local; listed[s] = local; }
            else if (listed_count[s] == 1) { mix_b[s] = local; }
            else lex_fail(lx, "more than binary mixing on one sublattice not supported");
            listed_count[s]++;
        }
        /* exactly one sublattice mixes (two constituents); the rest are pinned */
        int mix_s = -1;
        for (int s = 0; s < cf->n_subl; ++s) {
            if (listed_count[s] == 2) {
                if (mix_s >= 0) lex_fail(lx, "reciprocal excess (two mixing sublattices) not supported");
                mix_s = s;
            } else if (listed_count[s] != 1) {
                lex_fail(lx, "every sublattice must appear once in an excess parameter");
            }
        }
        if (mix_s < 0) lex_fail(lx, "excess parameter with no mixing sublattice");

        /* order the mixing pair by constituent name, matching pycalphad's sorted
         * constituent order so the (y_i - y_j)^order sign is consistent */
        int ci = mix_a[mix_s], cj = mix_b[mix_s];
        if (strcmp(cf->con_name[cf->subl_off[mix_s] + ci],
                   cf->con_name[cf->subl_off[mix_s] + cj]) > 0) {
            int t = ci; ci = cj; cj = t;
        }

        int n_terms = tok_int(lx);
        if (n_terms < 0) lex_fail(lx, "negative RK order count");
        for (int o = 0; o < n_terms; ++o) {
            if (cf->n_ex == cap) {
                cap *= 2;
                CefExcess *grown = xalloc(lx, (size_t)cap * sizeof(CefExcess));
                memcpy(grown, cf->ex, (size_t)cf->n_ex * sizeof(CefExcess));
                free(cf->ex);
                cf->ex = grown;
            }
            CefExcess *xe = &cf->ex[cf->n_ex++];
            memset(xe, 0, sizeof *xe);
            xe->subl = mix_s;
            xe->i = ci;
            xe->j = cj;
            xe->order = o;
            xe->other = xalloc(lx, (size_t)cf->n_subl * sizeof(int));
            for (int s = 0; s < cf->n_subl; ++s) xe->other[s] = (s == mix_s) ? 0 : listed[s];
            xe->coeff = xalloc(lx, (size_t)db->n_excess * sizeof(double));
            for (int i = 0; i < db->n_excess; ++i) xe->coeff[i] = tok_dbl(lx);
        }
    }
}

/* ------------------------------------------------------------------ *
 * Top-level file grammar
 * ------------------------------------------------------------------ */
static void parse_header(Lexer *lx, Db *db, int *soln_counts, int *n_soln_out)
{
    int n_el = tok_int(lx);
    int n_soln = tok_int(lx);
    if (n_el < 1 || n_el > 256) lex_fail(lx, "implausible element count");
    if (n_soln < 0 || n_soln > 256) lex_fail(lx, "implausible solution-phase count");
    for (int i = 0; i < n_soln; ++i) soln_counts[i] = tok_int(lx);
    *n_soln_out = n_soln;
    db->n_stoich = tok_int(lx);

    db->n_el = n_el;
    db->el_name = xalloc(lx, (size_t)n_el * sizeof(*db->el_name));
    db->el_mass = xalloc(lx, (size_t)n_el * sizeof(double));
    for (int i = 0; i < n_el; ++i) tok_name(lx, db->el_name[i]);
    for (int i = 0; i < n_el; ++i) db->el_mass[i] = tok_dbl(lx);

    db->n_gibbs = tok_int(lx);
    if (db->n_gibbs < 1 || db->n_gibbs > MAX_COEFFS) lex_fail(lx, "bad Gibbs-term count");
    for (int i = 0; i < db->n_gibbs; ++i) db->gibbs_idx[i] = tok_int(lx);
    db->n_excess = tok_int(lx);
    if (db->n_excess < 1 || db->n_excess > MAX_COEFFS) lex_fail(lx, "bad excess-term count");
    for (int i = 0; i < db->n_excess; ++i) db->excess_idx[i] = tok_int(lx);
}

static Db *parse_db(Lexer *lx)
{
    Db *db = xalloc(lx, sizeof(Db));

    int soln_counts[256];
    int n_soln = 0;
    parse_header(lx, db, soln_counts, &n_soln);

    /* one phase struct per non-empty solution phase */
    db->phases = xalloc(lx, (size_t)(n_soln ? n_soln : 1) * sizeof(Phase));
    db->n_phases = 0;
    for (int s = 0; s < n_soln; ++s) {
        if (soln_counts[s] == 0) continue;   /* absent (e.g. gas) phase */
        Phase *ph = &db->phases[db->n_phases];
        memset(ph, 0, sizeof *ph);
        tok_name(lx, ph->name);
        char type[NAME_MAX];
        tok_name(lx, type);
        if (strcmp(type, "SUBQ") == 0 || strcmp(type, "SUBG") == 0) {
            parse_subq_phase(lx, db, ph, type);
        } else if (strncmp(type, "SUBL", 4) == 0) {
            /* SUBL (and the magnetic SUBLM, whose two magnetic factors we skip) */
            if (strcmp(type, "SUBLM") == 0) { (void)tok_dbl(lx); (void)tok_dbl(lx); }
            parse_subl_phase(lx, db, ph, soln_counts[s]);
        } else {
            snprintf(lx->err, sizeof lx->err,
                     "phase type %s is not supported (only SUBQ/SUBG/SUBL)", type);
            longjmp(lx->jb, 1);
        }
        db->n_phases++;
    }

    db->stoich = xalloc(lx, (size_t)(db->n_stoich ? db->n_stoich : 1) * sizeof(Endmember));
    for (int i = 0; i < db->n_stoich; ++i) {
        parse_endmember(lx, &db->stoich[i], db->n_el, db->n_gibbs);
        /* magnetic stoichiometric phases carry the AFM and structure factors
         * after the endmember's Curie temperature and moment. */
        if (db->stoich[i].magnetic) { (void)tok_dbl(lx); (void)tok_dbl(lx); }
    }

    return db;
}

/* ------------------------------------------------------------------ *
 * Free
 * ------------------------------------------------------------------ */
static void free_endmember(Endmember *em)
{
    for (int i = 0; i < em->n_intervals; ++i) {
        free(em->intervals[i].add_c);
        free(em->intervals[i].add_e);
    }
    free(em->intervals);
    free(em->stoich_el);
}

static void free_db(Db *db)
{
    if (!db) return;
    for (int p = 0; p < db->n_phases; ++p) {
        Phase *ph = &db->phases[p];
        for (int k = 0; k < ph->n_pairs; ++k) free_endmember(&ph->pairs[k]);
        free(ph->pairs);
        free(ph->cat_name); free(ph->an_name);
        free(ph->cat_charge); free(ph->an_charge);
        free(ph->cat_group); free(ph->an_group);
        free(ph->mqmz);
        for (int k = 0; k < ph->n_mqmx; ++k) free(ph->mqmx[k].coeff);
        free(ph->mqmx);
        if (ph->cef) {
            SublPhase *cf = ph->cef;
            for (int e = 0; e < cf->n_em; ++e) free_endmember(&cf->em[e]);
            free(cf->em);
            free(cf->site_ratio); free(cf->subl_ncon); free(cf->subl_off);
            free(cf->con_name); free(cf->con_atoms); free(cf->em_con);
            for (int k = 0; k < cf->n_ex; ++k) { free(cf->ex[k].coeff); free(cf->ex[k].other); }
            free(cf->ex);
            free(cf->tc_em); free(cf->bm_em);
            for (int k = 0; k < cf->n_tcx; ++k) { free(cf->tc_ex[k].coeff); free(cf->tc_ex[k].other); }
            for (int k = 0; k < cf->n_bmx; ++k) { free(cf->bm_ex[k].coeff); free(cf->bm_ex[k].other); }
            free(cf->tc_ex); free(cf->bm_ex);
            free(cf);
        }
    }
    free(db->phases);
    for (int i = 0; i < db->n_stoich; ++i) free_endmember(&db->stoich[i]);
    free(db->stoich);
    free(db->el_name);
    free(db->el_mass);
    free(db);
}

/* ------------------------------------------------------------------ *
 * Public entry points
 * ------------------------------------------------------------------ */
/* TDB front-end (defined at the end of this file). Detects and parses the
 * Thermo-Calc TDB dialect into the same Db the ChemSage reader builds. */
static int tdb_detect(const char *text);
static Db *read_tdb(char *text_owned);

static Db *read_from_text(char *text_owned)
{
    /* Uppercase in place, matching pycalphad's reader so species names align. */
    for (char *p = text_owned; *p; ++p) *p = (char)toupper((unsigned char)*p);

    if (tdb_detect(text_owned))
        return read_tdb(text_owned);

    Lexer lx;
    memset(&lx, 0, sizeof lx);
    lx.buf = text_owned;
    lx.line = 1;
    lx.err[0] = '\0';

    /* Skip the first line (system title / provenance), as the format's data
     * begins on line 2. */
    lx.cur = text_owned;
    while (*lx.cur && *lx.cur != '\n') lx.cur++;
    if (*lx.cur == '\n') { lx.cur++; lx.line++; }

    Db *db = NULL;
    if (setjmp(lx.jb) == 0) {
        db = parse_db(&lx);
        g_error[0] = '\0';
    } else {
        snprintf(g_error, sizeof g_error, "%s", lx.err);
        db = NULL;
    }
    free(text_owned);
    return db;
}

mqmqa_db *mqmqa_db_read_string(const char *text)
{
    if (!text) { snprintf(g_error, sizeof g_error, "null input"); return NULL; }
    char *copy = malloc(strlen(text) + 1);
    if (!copy) { snprintf(g_error, sizeof g_error, "out of memory"); return NULL; }
    strcpy(copy, text);
    return (mqmqa_db *)read_from_text(copy);
}

mqmqa_db *mqmqa_db_read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) { snprintf(g_error, sizeof g_error, "cannot open %s", path ? path : "(null)"); return NULL; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); snprintf(g_error, sizeof g_error, "seek failed"); return NULL; }
    long n = ftell(f);
    if (n < 0) { fclose(f); snprintf(g_error, sizeof g_error, "tell failed"); return NULL; }
    rewind(f);
    char *buf = malloc((size_t)n + 1);
    if (!buf) { fclose(f); snprintf(g_error, sizeof g_error, "out of memory"); return NULL; }
    size_t got = fread(buf, 1, (size_t)n, f);
    fclose(f);
    buf[got] = '\0';
    return (mqmqa_db *)read_from_text(buf);
}

void mqmqa_db_free(mqmqa_db *db) { free_db((Db *)db); }

const char *mqmqa_db_error(void) { return g_error; }

/* ------------------------------------------------------------------ *
 * Accessors
 * ------------------------------------------------------------------ */
int mqmqa_db_num_elements(const mqmqa_db *db) { return ((const Db *)db)->n_el; }
const char *mqmqa_db_element(const mqmqa_db *db, int i) { return ((const Db *)db)->el_name[i]; }
double mqmqa_db_element_mass(const mqmqa_db *db, int i) { return ((const Db *)db)->el_mass[i]; }

int mqmqa_db_num_phases(const mqmqa_db *db) { return ((const Db *)db)->n_phases; }

int mqmqa_db_phase_index(const mqmqa_db *db, const char *name)
{
    const Db *d = (const Db *)db;
    for (int p = 0; p < d->n_phases; ++p)
        if (strcmp(d->phases[p].name, name) == 0) return p;
    return -1;
}

const char *mqmqa_db_phase_name(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].name; }
int mqmqa_db_phase_is_subq(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].soln_type; }

int mqmqa_ph_num_cations(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].n_cat; }
int mqmqa_ph_num_anions(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].n_an; }
const char *mqmqa_ph_cation(const mqmqa_db *db, int p, int i) { return ((const Db *)db)->phases[p].cat_name[i]; }
const char *mqmqa_ph_anion(const mqmqa_db *db, int p, int k) { return ((const Db *)db)->phases[p].an_name[k]; }
double mqmqa_ph_cation_charge(const mqmqa_db *db, int p, int i) { return ((const Db *)db)->phases[p].cat_charge[i]; }
double mqmqa_ph_anion_charge(const mqmqa_db *db, int p, int k) { return ((const Db *)db)->phases[p].an_charge[k]; }
int mqmqa_ph_cation_group(const mqmqa_db *db, int p, int i) { return ((const Db *)db)->phases[p].cat_group[i]; }
int mqmqa_ph_anion_group(const mqmqa_db *db, int p, int k) { return ((const Db *)db)->phases[p].an_group[k]; }

int mqmqa_ph_num_pairs(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].n_pairs; }

void mqmqa_ph_pair_indices(const mqmqa_db *db, int p, int *cat, int *an)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int k = 0; k < ph->n_pairs; ++k) { cat[k] = ph->pairs[k].cat_idx; an[k] = ph->pairs[k].an_idx; }
}

void mqmqa_ph_pair_stoich(const mqmqa_db *db, int p, double *stoich)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int k = 0; k < ph->n_pairs; ++k) stoich[k] = ph->pairs[k].stoich_quad[0];
}

void mqmqa_ph_pair_zeta(const mqmqa_db *db, int p, double *zeta)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int k = 0; k < ph->n_pairs; ++k) zeta[k] = ph->pairs[k].zeta;
}

void mqmqa_ph_pair_gibbs(const mqmqa_db *db, int p, double T, double *G)
{
    const Db *d = (const Db *)db;
    const Phase *ph = &d->phases[p];
    for (int k = 0; k < ph->n_pairs; ++k) G[k] = endmember_gibbs(d, &ph->pairs[k], T);
}

int mqmqa_ph_num_mqmz(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].n_quads; }

void mqmqa_ph_mqmz(const mqmqa_db *db, int p, int *A, int *B, int *X, int *Y, double *Z)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int q = 0; q < ph->n_quads; ++q) {
        A[q] = ph->mqmz[q].A; B[q] = ph->mqmz[q].B;
        X[q] = ph->mqmz[q].X; Y[q] = ph->mqmz[q].Y;
        for (int i = 0; i < 4; ++i) Z[q * 4 + i] = ph->mqmz[q].Z[i];
    }
}

int mqmqa_ph_num_mqmx(const mqmqa_db *db, int p) { return ((const Db *)db)->phases[p].n_mqmx; }

void mqmqa_ph_mqmx(const mqmqa_db *db, int p,
                   int *mix, int *code, int *A, int *B, int *X, int *Y,
                   int *p_exp, int *q_exp)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int k = 0; k < ph->n_mqmx; ++k) {
        const Mqmx *mx = &ph->mqmx[k];
        mix[k] = mx->mix;
        code[k] = (mx->code == 'Q') ? 0 : (mx->code == 'G') ? 1
                : (mx->code == 'B') ? 2 : (mx->code == 'R') ? 3 : -1;
        A[k] = mx->A; B[k] = mx->B; X[k] = mx->X; Y[k] = mx->Y;
        p_exp[k] = mx->exp[0]; q_exp[k] = mx->exp[1];
    }
}

void mqmqa_ph_mqmx_L(const mqmqa_db *db, int p, double T, double *L)
{
    const Db *d = (const Db *)db;
    const Phase *ph = &d->phases[p];
    for (int k = 0; k < ph->n_mqmx; ++k) L[k] = excess_coeff_gibbs(d, ph->mqmx[k].coeff, T);
}

void mqmqa_ph_mqmx_ternary(const mqmqa_db *db, int p, double *r_exp, int *add_cat)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    for (int k = 0; k < ph->n_mqmx; ++k) {
        r_exp[k] = (double)ph->mqmx[k].exp[2];
        add_cat[k] = ph->mqmx[k].add_cat;
    }
}

/* ------------------------------------------------------------------ *
 * CEF (SUBL) phase accessors
 * ------------------------------------------------------------------ */
int mqmqa_db_phase_kind(const mqmqa_db *db, int p)
{
    const Db *d = (const Db *)db;
    return (p < 0 || p >= d->n_phases) ? -1 : d->phases[p].kind;
}

int mqmqa_ph_cef_num_subl(const mqmqa_db *db, int p)
{
    const Phase *ph = &((const Db *)db)->phases[p];
    return ph->cef ? ph->cef->n_subl : -1;
}

void mqmqa_ph_cef_subl_ncon(const mqmqa_db *db, int p, int *out)
{
    const SublPhase *cf = ((const Db *)db)->phases[p].cef;
    for (int s = 0; s < cf->n_subl; ++s) out[s] = cf->subl_ncon[s];
}

void mqmqa_ph_cef_site_ratio(const mqmqa_db *db, int p, double *out)
{
    const SublPhase *cf = ((const Db *)db)->phases[p].cef;
    for (int s = 0; s < cf->n_subl; ++s) out[s] = cf->site_ratio[s];
}

int mqmqa_ph_cef_num_constituents(const mqmqa_db *db, int p)
{
    const SublPhase *cf = ((const Db *)db)->phases[p].cef;
    return cf ? cf->n_con : -1;
}

const char *mqmqa_ph_cef_constituent(const mqmqa_db *db, int p, int s, int i)
{
    const SublPhase *cf = ((const Db *)db)->phases[p].cef;
    return cf->con_name[cf->subl_off[s] + i];
}

/* Molar Gibbs energy of a CEF phase at site fractions Y (flattened by sublattice,
 * in the reader's constituent order) and temperature T. Assembles the per-parameter
 * arrays the kernel needs (endmember Gibbs at T, excess L at T) and calls
 * mqmqa_cef_gibbs. Returns NaN if the phase is not CEF or on allocation failure. */
double mqmqa_ph_cef_gibbs(const mqmqa_db *db, int p, const double *Y, double T,
                          int per_mole_atoms)
{
    const Db *d = (const Db *)db;
    if (p < 0 || p >= d->n_phases) return NAN;
    const Phase *ph = &d->phases[p];
    if (!ph->cef) return NAN;
    const SublPhase *cf = ph->cef;

    double *em_G = malloc((size_t)cf->n_em * sizeof(double));
    int n_ex = cf->n_ex;
    int *ex_subl = malloc((size_t)(n_ex ? n_ex : 1) * sizeof(int));
    int *ex_i = malloc((size_t)(n_ex ? n_ex : 1) * sizeof(int));
    int *ex_j = malloc((size_t)(n_ex ? n_ex : 1) * sizeof(int));
    int *ex_order = malloc((size_t)(n_ex ? n_ex : 1) * sizeof(int));
    double *ex_L = malloc((size_t)(n_ex ? n_ex : 1) * sizeof(double));
    int *ex_other = malloc((size_t)(n_ex ? n_ex : 1) * cf->n_subl * sizeof(int));
    if (!em_G || !ex_subl || !ex_i || !ex_j || !ex_order || !ex_L || !ex_other) {
        free(em_G); free(ex_subl); free(ex_i); free(ex_j);
        free(ex_order); free(ex_L); free(ex_other);
        return NAN;
    }

    for (int e = 0; e < cf->n_em; ++e)
        em_G[e] = endmember_gibbs(d, &cf->em[e], T);
    for (int k = 0; k < n_ex; ++k) {
        const CefExcess *xe = &cf->ex[k];
        ex_subl[k] = xe->subl;
        ex_i[k] = xe->i;
        ex_j[k] = xe->j;
        ex_order[k] = xe->order;
        ex_L[k] = excess_coeff_gibbs(d, xe->coeff, T);
        for (int s = 0; s < cf->n_subl; ++s) ex_other[k * cf->n_subl + s] = xe->other[s];
    }

    double g = mqmqa_cef_gibbs(
        T, cf->n_subl, cf->site_ratio, cf->subl_ncon, cf->subl_off, Y, cf->con_atoms,
        cf->n_em, cf->em_con, em_G,
        n_ex, ex_subl, ex_i, ex_j, ex_order, ex_L, ex_other,
        0);

    /* Inden-Hillert-Jarl magnetic contribution, per mole of formula: TC(Y) and
     * beta(Y) mix exactly like the excess terms, then G_mag = R T ln(1+beta) f(tau). */
    if (cf->magnetic) {
        double TC = 0.0, B = 0.0;
        for (int e = 0; e < cf->n_em; ++e) {
            double prod = 1.0;
            for (int s = 0; s < cf->n_subl; ++s)
                prod *= Y[cf->subl_off[s] + cf->em_con[e * cf->n_subl + s]];
            TC += prod * excess_coeff_gibbs(d, cf->tc_em + e * 6, T);
            B  += prod * excess_coeff_gibbs(d, cf->bm_em + e * 6, T);
        }
        for (int pass = 0; pass < 2; ++pass) {
            int nk = pass ? cf->n_bmx : cf->n_tcx;
            const CefExcess *xs = pass ? cf->bm_ex : cf->tc_ex;
            for (int k = 0; k < nk; ++k) {
                const CefExcess *xe = &xs[k];
                int s = xe->subl;
                double yi = Y[cf->subl_off[s] + xe->i];
                double yj = Y[cf->subl_off[s] + xe->j];
                double other = 1.0;
                for (int s2 = 0; s2 < cf->n_subl; ++s2)
                    if (s2 != s) other *= Y[cf->subl_off[s2] + xe->other[s2]];
                double v = other * yi * yj * excess_coeff_gibbs(d, xe->coeff, T)
                           * pow(yi - yj, (double)xe->order);
                if (pass) B += v; else TC += v;
            }
        }
        if (TC < 0.0 && cf->mag_afm != 0.0) TC /= cf->mag_afm;
        if (B  < 0.0 && cf->mag_afm != 0.0) B  /= cf->mag_afm;
        if (TC > 1e-10 && B > -1.0 + 1e-12) {
            double pm = cf->mag_p;
            double tau = T / TC;
            double A = 518.0 / 1125.0 + (11692.0 / 15975.0) * (1.0 / pm - 1.0);
            double f;
            if (tau < 1.0)
                f = 1.0 - (79.0 / (140.0 * pm * tau)
                    + (474.0 / 497.0) * (1.0 / pm - 1.0)
                      * (pow(tau, 3) / 6.0 + pow(tau, 9) / 135.0 + pow(tau, 15) / 600.0)) / A;
            else
                f = -(pow(tau, -5) / 10.0 + pow(tau, -15) / 315.0 + pow(tau, -25) / 1500.0) / A;
            g += 8.3145 * T * log(B + 1.0) * f;
        }
    }

    if (per_mole_atoms) {
        double tot = 0.0;
        for (int s = 0; s < cf->n_subl; ++s) {
            double ssum = 0.0;
            for (int i = 0; i < cf->subl_ncon[s]; ++i)
                ssum += Y[cf->subl_off[s] + i] * cf->con_atoms[cf->subl_off[s] + i];
            tot += cf->site_ratio[s] * ssum;
        }
        if (tot > 0.0) g /= tot;
    }

    free(em_G); free(ex_subl); free(ex_i); free(ex_j);
    free(ex_order); free(ex_L); free(ex_other);
    return g;
}

int mqmqa_db_num_stoich(const mqmqa_db *db) { return ((const Db *)db)->n_stoich; }
const char *mqmqa_db_stoich_name(const mqmqa_db *db, int i) { return ((const Db *)db)->stoich[i].name; }
void mqmqa_db_stoich_elems(const mqmqa_db *db, int i, double *out)
{
    const Db *d = (const Db *)db;
    for (int e = 0; e < d->n_el; ++e) out[e] = d->stoich[i].stoich_el[e];
}
double mqmqa_db_stoich_gibbs(const mqmqa_db *db, int i, double T)
{
    const Db *d = (const Db *)db;
    return endmember_gibbs(d, &d->stoich[i], T);
}

/* ------------------------------------------------------------------ *
 * Quadruplet enumeration
 * ------------------------------------------------------------------ */
int mqmqa_num_quadruplets(int n_cat, int n_an)
{
    int cpairs = n_cat * (n_cat + 1) / 2;
    int apairs = n_an * (n_an + 1) / 2;
    return cpairs * apairs;
}

void mqmqa_enumerate_quadruplets(int n_cat, int n_an, int *ca, int *cb, int *ax, int *ay)
{
    int n = 0;
    for (int i = 0; i < n_cat; ++i)
        for (int j = i; j < n_cat; ++j)
            for (int k = 0; k < n_an; ++k)
                for (int l = k; l < n_an; ++l) {
                    ca[n] = i; cb[n] = j; ax[n] = k; ay[n] = l;
                    ++n;
                }
}

/* ================================================================== *
 * TDB front-end
 *
 * Reads the Thermo-Calc TDB dialect (the CALPHAD lingua franca used by
 * Thermo-Calc, OpenCalphad and pycalphad) into the same in-memory Db the
 * ChemSage reader builds, so every accessor, the Python binding and the
 * WASM build work unchanged. Clean-room from the published format as
 * handled by pycalphad's open-source parser; pycalphad is the oracle.
 *
 * v1 subset: ELEMENT / SPECIES / FUNCTION (piecewise, nested references) /
 * PHASE + CONSTITUENT (compound-energy formalism) / PARAMETER G and L
 * (Redlich-Kister, single mixing pair per term). Anything outside the
 * subset (magnetic TC/BMAGN, order-disorder partitions, the ionic
 * two-sublattice liquid, ternary interactions) fails loudly with a
 * message rather than computing silently wrong energies.
 * ================================================================== */

#define TDB_MAX_SEG   24
#define TDB_MAX_TERMS 48
#define TDB_MAX_FUNCS 4096
#define TDB_MAX_SUBL  10
#define TDB_MAX_CON   64

/* one additive term: c * T^power, c * T*ln(T), or c * FUNC(T) */
typedef struct {
    double c;
    int kind;        /* 0 = T^power, 1 = T*ln(T), 2 = function reference */
    double power;
    int func;        /* kind==2: index into the function table */
    /* deferred combinations, folded at resolution when the tables are complete:
     * func2   : second function in a product (one of the two must be constant)
     * fpow_on : the function is raised to fpow (must then be constant)
     * tmul    : 0 none, 1 times T^power, 2 times T*ln(T) (function must be constant) */
    int func2;
    int fpow_on; double fpow;
    int tmul;
} TdbTerm;

typedef struct {
    double lo, hi;
    int n;
    TdbTerm t[TDB_MAX_TERMS];
} TdbSeg;

typedef struct {
    char name[NAME_MAX];
    int n_seg;
    TdbSeg *seg;     /* heap, TDB_MAX_SEG entries once defined (WASM-friendly) */
    int state;       /* 0 unresolved, 1 resolving (cycle guard), 2 resolved */
} TdbFunc;

typedef struct {
    char name[NAME_MAX];
    int n_el;                 /* element composition (indices into db element list) */
    int el[8];
    double n[8];
    double atoms;             /* total real atoms per formula (0 for VA) */
    double charge;            /* from the /+n or /-n suffix, 0 when absent */
} TdbSpecies;

typedef struct {
    char name[NAME_MAX];
    int n_subl;
    double ratio[TDB_MAX_SUBL];
    int ncon[TDB_MAX_SUBL];
    char con[TDB_MAX_SUBL][TDB_MAX_CON][NAME_MAX];
    int flags_magnetic, flags_order;
    double mag_afm, mag_p;    /* from the phase's MAGNETIC type definition */
    int is_q;                 /* :Q model suffix - the MQMQA quadruplet liquid */
} TdbPhase;

typedef struct {
    char phase[NAME_MAX];
    int con[TDB_MAX_SUBL][2]; /* up to two constituents per sublattice (local idx) */
    int ncon[TDB_MAX_SUBL];
    int order;                /* Redlich-Kister order */
    int kind;                 /* 0 G/L, 1 TC, 2 BMAGN */
    TdbSeg *expr;             /* heap, TDB_MAX_SEG entries (WASM-friendly) */
    int n_seg;
} TdbParam;

/* one MQ* statement, kept raw until the build step */
typedef struct {
    char phase[NAME_MAX];
    int  kind;                /* 0 MQG, 1 MQZETA, 2 MQSTOI, 3 MQZ, 4 MQX, 5 MQGRP */
    char names[5][NAME_MAX];  /* constituent names as written (up to A,B,X,Y,addcat) */
    int  n_names;
    char code;                /* MQX: Q/G/B/R */
    int  exp_p, exp_q, exp_r; /* MQX exponents (r = -1 when absent) */
    double vals[8];           /* MQZETA/MQSTOI/MQZ/MQGRP constant payloads */
    int  n_vals;
    TdbSeg *expr;             /* MQG / MQX piecewise payload */
    int  n_seg;
} TdbMq;

typedef struct {
    Lexer *lx;                /* shares the error longjmp */
    char *cur;                /* scan position in the uppercased text */
    int line;
    /* symbol tables */
    int n_func;  TdbFunc  *func;
    int n_el;    char (*el_name)[NAME_MAX]; double *el_mass;
    int n_sp;    TdbSpecies *sp;
    int n_ph;    TdbPhase *ph;
    int n_par;   TdbParam *par; int cap_par;
    int n_mq;    TdbMq *mq;     int cap_mq;
    char magnetic_typedefs[16]; int n_mag_td;
    double mag_td_afm[16], mag_td_p[16];
    char order_typedefs[16];    int n_ord_td;
} Tdb;

static void tdb_fail(Tdb *tb, const char *what)
{
    snprintf(tb->lx->err, sizeof tb->lx->err, "TDB line %d: %s", tb->line, what);
    longjmp(tb->lx->jb, 1);
}

static int tdb_detect(const char *text)
{
    /* First non-comment, non-blank line starting with a TDB keyword. */
    const char *p = text;
    for (int lines = 0; lines < 200 && *p; ++lines) {
        while (*p == ' ' || *p == '\t' || *p == '\r') p++;
        if (*p == '$') { while (*p && *p != '\n') p++; if (*p) p++; continue; }
        if (*p == '\n') { p++; continue; }
        {
            static const char *kw[] = { "ELEM", "SPEC", "FUNC",
                "TYPE_DEF", "PHAS", "DATABASE_INFO", "TEMP_LIM",
                "TEMPERATURE_LIMITS", "VERSION_DATE", "REFERENCE_FILE",
                "ASSESSED_SYSTEMS", NULL };
            int k;
            for (k = 0; kw[k]; ++k) {
                size_t n = strlen(kw[k]);
                if (strncmp(p, kw[k], n) == 0)
                    return 1;
            }
        }
        return 0;   /* first real line is not a TDB statement */
    }
    return 0;
}

/* ---- statement scanning: everything up to '!', with '$' comments ---- */

static char *tdb_next_statement(Tdb *tb)
{
    char *p = tb->cur;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\r') p++;
        if (*p == '\n') { tb->line++; p++; continue; }
        if (*p == '$') { while (*p && *p != '\n') p++; continue; }
        break;
    }
    if (!*p) { tb->cur = p; return NULL; }
    {
        char *start = p;
        while (*p && *p != '!') {
            if (*p == '\n') tb->line++;
            else if (*p == '$') { while (*p && *p != '\n') *p++ = ' '; continue; }
            p++;
        }
        if (*p == '!') { *p = '\0'; p++; }
        tb->cur = p;
        return start;
    }
}

/* ---- in-statement tokens: words and single punctuation characters ---- */

static char *tdb_word(char **s, char *buf, size_t bufsz)
{
    char *p = *s;
    size_t n = 0;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
    if (!*p) { *s = p; return NULL; }
    if (strchr(",:;()*", *p)) { buf[n++] = *p++; }
    else {
        while (*p && !strchr(" \t\r\n,:;()", *p)) {
            if (n + 1 < bufsz) buf[n++] = *p;
            p++;
        }
    }
    buf[n] = '\0';
    *s = p;
    return buf;
}

static char tdb_peekc(char *s)
{
    while (*s == ' ' || *s == '\t' || *s == '\r' || *s == '\n') s++;
    return *s;
}

/* ---- expression parsing ---- */

static int tdb_func_const(Tdb *tb, int fi, double *val);

static int tdb_func_index(Tdb *tb, const char *name)
{
    int i;
    for (i = 0; i < tb->n_func; ++i)
        if (strcmp(tb->func[i].name, name) == 0) return i;
    return -1;
}

static void tdb_func_segs(Tdb *tb, int fi)
{
    if (tb->func[fi].seg) return;
    tb->func[fi].seg = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
    if (!tb->func[fi].seg) tdb_fail(tb, "out of memory");
}

static void tdb_parse_expr(Tdb *tb, char **s, TdbSeg *seg)
{
    double sign = 1.0;
    seg->n = 0;
    for (;;) {
        char c = tdb_peekc(*s);
        double coeff = 1.0;
        int have_num = 0;
        int kind = 0; double power = 0.0; int func = -1;
        int power_set = 0;
        int func2 = -1, fpow_on = 0, tmul = 0; double fpow = 1.0;
        if (c == '\0' || c == ';') break;
        for (;;) {
            while (**s == ' ' || **s == '\t' || **s == '\r' || **s == '\n') (*s)++;
            c = **s;
            if (c == '+' || c == '-') {
                if (have_num || power_set || func >= 0 || kind == 1) break;
                if (c == '-') sign = -sign;
                (*s)++;
                continue;
            }
            if ((c >= '0' && c <= '9') || c == '.') {
                char *end = NULL;
                double v = strtod(*s, &end);
                if (end == *s) tdb_fail(tb, "bad number in expression");
                *s = end;
                coeff *= v; have_num = 1;
            } else if (c == 'T' && !isalnum((unsigned char)(*s)[1]) && (*s)[1] != '_') {
                (*s)++;
                if ((*s)[0] == '*' && (*s)[1] == '*') {
                    char *end = NULL; double v; int paren;
                    *s += 2;
                    while (**s == ' ') (*s)++;
                    paren = (**s == '(');
                    if (paren) (*s)++;
                    v = strtod(*s, &end);
                    if (end == *s) tdb_fail(tb, "bad exponent");
                    *s = end;
                    if (paren) { while (**s == ' ') (*s)++; if (**s == ')') (*s)++; }
                    power += v; power_set = 1;
                } else if (strncmp(*s, "*LN(T)", 6) == 0) {
                    *s += 6; kind = 1;
                } else {
                    power += 1.0; power_set = 1;
                }
            } else if (strncmp(*s, "LN(T)", 5) == 0) {
                tdb_fail(tb, "standalone LN(T) term is outside the v1 subset");
            } else if (strncmp(*s, "EXP(", 4) == 0) {
                tdb_fail(tb, "EXP(...) term is outside the v1 subset");
            } else if (isalpha((unsigned char)c) || c == '_') {
                char name[NAME_MAX]; size_t n = 0;
                int fi;
                while (**s && (isalnum((unsigned char)**s) || **s == '_')) {
                    if (n + 1 < sizeof name) name[n++] = **s;
                    (*s)++;
                }
                name[n] = '\0';
                if (**s == '#') (*s)++;
                fi = tdb_func_index(tb, name);
                if (fi < 0) {
                    if (tb->n_func >= TDB_MAX_FUNCS) tdb_fail(tb, "too many functions");
                    fi = tb->n_func++;
                    snprintf(tb->func[fi].name, NAME_MAX, "%s", name);
                    tb->func[fi].n_seg = 0;
                    tb->func[fi].seg = NULL;
                }
                /* NAME#**n : store the power, folded at resolution time */
                while (**s == ' ') (*s)++;
                if ((*s)[0] == '*' && (*s)[1] == '*') {
                    char *end = NULL; double v; int paren;
                    *s += 2;
                    while (**s == ' ') (*s)++;
                    paren = (**s == '(');
                    if (paren) (*s)++;
                    v = strtod(*s, &end);
                    if (end == *s) tdb_fail(tb, "bad exponent");
                    *s = end;
                    if (paren) { while (**s == ' ') (*s)++; if (**s == ')') (*s)++; }
                    if (func >= 0) tdb_fail(tb, "product of powered functions is outside the v1 subset");
                    func = fi; kind = 2; fpow_on = 1; fpow = v; fi = -1;
                }
                if (fi >= 0 && func >= 0) {
                    if (func2 >= 0) tdb_fail(tb, "product of three functions is outside the v1 subset");
                    func2 = fi; fi = -1;
                }
                if (fi >= 0) { func = fi; kind = 2; }
            } else {
                break;
            }
            while (**s == ' ') (*s)++;
            if (**s == '*' && (*s)[1] != '*') (*s)++;
        }
        if (!have_num && !power_set && func < 0 && kind != 1) break;
        if (seg->n >= TDB_MAX_TERMS) tdb_fail(tb, "too many terms in one segment");
        {
            TdbTerm *t = &seg->t[seg->n++];
            t->c = sign * coeff;
            if (func >= 0 && (power_set || kind == 1)) {
                tmul = power_set ? 1 : 2;
                kind = 2;
            }
            t->kind = kind; t->power = power; t->func = func;
            t->func2 = func2; t->fpow_on = fpow_on; t->fpow = fpow; t->tmul = tmul;
        }
        sign = 1.0;
    }
}

/* Parse "lowT expr ; T Y expr ; ... T N [ref]" into segments. */
static int tdb_parse_piecewise(Tdb *tb, char **s, TdbSeg *seg, int max_seg)
{
    char buf[NAME_MAX];
    char *end = NULL;
    double lo;
    int n = 0;
    if (!tdb_word(s, buf, sizeof buf)) tdb_fail(tb, "missing lower temperature limit");
    lo = strtod(buf, &end);
    if (end == buf) tdb_fail(tb, "bad lower temperature limit");
    for (;;) {
        double hi;
        if (n >= max_seg) tdb_fail(tb, "too many temperature intervals");
        seg[n].lo = lo;
        tdb_parse_expr(tb, s, &seg[n]);
        while (**s == ' ' || **s == '\t' || **s == '\r' || **s == '\n') (*s)++;
        if (**s == ';') (*s)++;
        if (!tdb_word(s, buf, sizeof buf)) { seg[n].hi = 6000.0; n++; break; }
        hi = strtod(buf, &end);
        if (end == buf) { seg[n].hi = 6000.0; n++; break; }  /* trailing ref name */
        seg[n].hi = hi; n++;
        if (!tdb_word(s, buf, sizeof buf)) break;
        if (buf[0] == 'Y') { lo = hi; continue; }
        break;   /* 'N': the rest of the statement is the reference */
    }
    return n;
}

/* ---- resolution: inline function references, splitting at breakpoints ---- */

static void tdb_resolve_func(Tdb *tb, int fi);

static void tdb_collect_breaks(Tdb *tb, const TdbSeg *seg, double lo, double hi,
                               double *br, int *n_br, int max_br)
{
    int i;
    for (i = 0; i < seg->n; ++i) {
        int fi, k;
        TdbFunc *f;
        if (seg->t[i].kind != 2) continue;
        if (seg->t[i].fpow_on || seg->t[i].tmul) continue;   /* folds to a constant */
        fi = seg->t[i].func;
        if (seg->t[i].func2 >= 0) {
            double cv;
            if (tdb_func_const(tb, fi, &cv)) fi = seg->t[i].func2;
        }
        tdb_resolve_func(tb, fi);
        f = &tb->func[fi];
        for (k = 0; k < f->n_seg; ++k) {
            double b[2]; int j;
            b[0] = f->seg[k].lo; b[1] = f->seg[k].hi;
            for (j = 0; j < 2; ++j) {
                int seen = 0, m;
                if (b[j] <= lo + 1e-9 || b[j] >= hi - 1e-9) continue;
                for (m = 0; m < *n_br; ++m)
                    if (fabs(br[m] - b[j]) < 1e-9) { seen = 1; break; }
                if (!seen) {
                    if (*n_br >= max_br) tdb_fail(tb, "too many interval breakpoints");
                    br[(*n_br)++] = b[j];
                }
            }
        }
    }
}

static void tdb_add_term(Tdb *tb, TdbSeg *dst, double c, int kind, double power)
{
    int i;
    if (fabs(c) < 1e-300) return;
    for (i = 0; i < dst->n; ++i) {
        if (dst->t[i].kind == kind &&
            (kind == 1 || fabs(dst->t[i].power - power) < 1e-12)) {
            dst->t[i].c += c;
            return;
        }
    }
    if (dst->n >= TDB_MAX_TERMS) tdb_fail(tb, "too many terms after expansion");
    dst->t[dst->n].c = c;
    dst->t[dst->n].kind = kind;
    dst->t[dst->n].power = power;
    dst->t[dst->n].func = -1;
    dst->t[dst->n].func2 = -1;
    dst->t[dst->n].fpow_on = 0; dst->t[dst->n].fpow = 1.0;
    dst->t[dst->n].tmul = 0;
    dst->n++;
}

static void tdb_expand_into(Tdb *tb, const TdbSeg *seg, double lo, double hi,
                            double scale, TdbSeg *out, int *n_out, int max_out)
{
    double br[TDB_MAX_SEG * 4]; int n_br = 0;
    double a;
    int piece, i;
    tdb_collect_breaks(tb, seg, lo, hi, br, &n_br, (int)(sizeof br / sizeof br[0]));
    for (i = 1; i < n_br; ++i) {
        double v = br[i]; int j = i - 1;
        while (j >= 0 && br[j] > v) { br[j + 1] = br[j]; j--; }
        br[j + 1] = v;
    }
    a = lo;
    for (piece = 0; piece <= n_br; ++piece) {
        double b = (piece < n_br) ? br[piece] : hi;
        TdbSeg *dst = NULL;
        if (b <= a + 1e-9) { a = b; continue; }
        for (i = 0; i < *n_out; ++i)
            if (fabs(out[i].lo - a) < 1e-9 && fabs(out[i].hi - b) < 1e-9) { dst = &out[i]; break; }
        if (!dst) {
            if (*n_out >= max_out) tdb_fail(tb, "too many intervals after expansion");
            dst = &out[(*n_out)++];
            dst->lo = a; dst->hi = b; dst->n = 0;
        }
        for (i = 0; i < seg->n; ++i) {
            const TdbTerm *t = &seg->t[i];
            TdbFunc *f;
            const TdbSeg *src = NULL;
            int k;
            if (t->kind != 2) {
                tdb_add_term(tb, dst, scale * t->c, t->kind, t->power);
                continue;
            }
            {
                double cmul = scale * t->c;
                int fmain = t->func;
                if (t->func2 >= 0) {
                    double cv;
                    if (tdb_func_const(tb, t->func2, &cv)) cmul *= cv;
                    else if (tdb_func_const(tb, fmain, &cv)) { cmul *= cv; fmain = t->func2; }
                    else tdb_fail(tb, "product of two non-constant functions is outside the v1 subset");
                }
                if (t->fpow_on) {
                    double cv;
                    if (!tdb_func_const(tb, fmain, &cv))
                        tdb_fail(tb, "power of a non-constant function is outside the v1 subset");
                    tdb_add_term(tb, dst, cmul * pow(cv, t->fpow), 0, 0.0);
                    continue;
                }
                if (t->tmul) {
                    double cv;
                    if (!tdb_func_const(tb, fmain, &cv))
                        tdb_fail(tb, "function times T-power is outside the v1 subset");
                    tdb_add_term(tb, dst, cmul * cv, t->tmul == 2 ? 1 : 0, t->power);
                    continue;
                }
                tdb_resolve_func(tb, fmain);
                f = &tb->func[fmain];
                for (k = 0; k < f->n_seg; ++k)
                    if (a >= f->seg[k].lo - 1e-9 && b <= f->seg[k].hi + 1e-9) { src = &f->seg[k]; break; }
                if (!src && f->n_seg > 0)
                    src = (a < f->seg[0].lo) ? &f->seg[0] : &f->seg[f->n_seg - 1];
                if (!src) tdb_fail(tb, "reference to an empty function");
                for (k = 0; k < src->n; ++k) {
                    if (src->t[k].kind == 2) tdb_fail(tb, "unresolved nested reference");
                    tdb_add_term(tb, dst, cmul * src->t[k].c,
                                 src->t[k].kind, src->t[k].power);
                }
            }
        }
        a = b;
    }
}

static void tdb_resolve_func(Tdb *tb, int fi)
{
    TdbFunc *f = &tb->func[fi];
    TdbSeg *out; int n_out = 0;
    int k, i;
    out = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
    if (!out) tdb_fail(tb, "out of memory");
    if (f->state == 2) return;
    if (f->state == 1) tdb_fail(tb, "circular function reference");
    if (f->n_seg == 0) {
        snprintf(tb->lx->err, sizeof tb->lx->err,
                 "TDB: function %s referenced but never defined", f->name);
        longjmp(tb->lx->jb, 1);
    }
    f->state = 1;
    for (k = 0; k < f->n_seg; ++k)
        tdb_expand_into(tb, &f->seg[k], f->seg[k].lo, f->seg[k].hi, 1.0,
                        out, &n_out, TDB_MAX_SEG);
    for (i = 1; i < n_out; ++i) {
        TdbSeg v = out[i]; int j = i - 1;
        while (j >= 0 && out[j].lo > v.lo) { out[j + 1] = out[j]; j--; }
        out[j + 1] = v;
    }
    f->n_seg = n_out;
    memcpy(f->seg, out, (size_t)n_out * sizeof(TdbSeg));
    free(out);
    f->state = 2;
}

/* If the function resolves to a pure constant (the SGTE UNTIER/TROIS idiom),
 * return 1 and the value; used to fold products and powers of such refs. */
static int tdb_func_const(Tdb *tb, int fi, double *val)
{
    TdbFunc *f;
    int k;
    tdb_resolve_func(tb, fi);
    f = &tb->func[fi];
    if (f->n_seg < 1) return 0;
    if (f->seg[0].n == 0) { *val = 0.0; }
    else if (f->seg[0].n == 1 && f->seg[0].t[0].kind == 0 &&
             fabs(f->seg[0].t[0].power) < 1e-12) *val = f->seg[0].t[0].c;
    else return 0;
    for (k = 1; k < f->n_seg; ++k) {
        if (f->seg[k].n == 0) { if (fabs(*val) > 1e-300) return 0; continue; }
        if (!(f->seg[k].n == 1 && f->seg[k].t[0].kind == 0 &&
              fabs(f->seg[k].t[0].power) < 1e-12 &&
              fabs(f->seg[k].t[0].c - *val) < 1e-9 * (1.0 + fabs(*val)))) return 0;
    }
    return 1;
}

static int tdb_resolve_param(Tdb *tb, TdbSeg *raw, int n_raw, TdbSeg *out, int max_out)
{
    int n_out = 0, k, i;
    for (k = 0; k < n_raw; ++k)
        tdb_expand_into(tb, &raw[k], raw[k].lo, raw[k].hi, 1.0, out, &n_out, max_out);
    for (i = 1; i < n_out; ++i) {
        TdbSeg v = out[i]; int j = i - 1;
        while (j >= 0 && out[j].lo > v.lo) { out[j + 1] = out[j]; j--; }
        out[j + 1] = v;
    }
    return n_out;
}

/* ---- conversion into the shared Db representation ---- */

static void *tdb_alloc(Tdb *tb, size_t n)
{
    void *p = calloc(1, n);
    if (!p) tdb_fail(tb, "out of memory");
    return p;
}

/* Basis terms map onto the ChemSage coefficient slots (1, T, T ln T, T^2,
 * T^3, 1/T); every other power becomes an additional (coeff, exponent) pair. */
static void tdb_fill_endmember(Tdb *tb, Endmember *em, const TdbSeg *seg, int n_seg)
{
    int k;
    em->n_intervals = n_seg > 0 ? n_seg : 1;
    em->intervals = tdb_alloc(tb, (size_t)em->n_intervals * sizeof(Interval));
    if (n_seg == 0) { em->intervals[0].t_max = 1e12; return; }
    for (k = 0; k < n_seg; ++k) {
        Interval *iv = &em->intervals[k];
        int n_add = 0, i, j;
        iv->t_max = seg[k].hi;
        for (i = 0; i < seg[k].n; ++i) {
            const TdbTerm *t = &seg[k].t[i];
            double p;
            if (t->kind == 1) { iv->coeff[2] += t->c; continue; }   /* T ln T */
            p = t->power;
            if      (fabs(p - 0.0) < 1e-12) iv->coeff[0] += t->c;
            else if (fabs(p - 1.0) < 1e-12) iv->coeff[1] += t->c;
            else if (fabs(p - 2.0) < 1e-12) iv->coeff[3] += t->c;
            else if (fabs(p - 3.0) < 1e-12) iv->coeff[4] += t->c;
            else if (fabs(p + 1.0) < 1e-12) iv->coeff[5] += t->c;
            else n_add++;
        }
        if (n_add) {
            iv->n_add = n_add;
            iv->add_c = tdb_alloc(tb, (size_t)n_add * sizeof(double));
            iv->add_e = tdb_alloc(tb, (size_t)n_add * sizeof(double));
            j = 0;
            for (i = 0; i < seg[k].n; ++i) {
                const TdbTerm *t = &seg[k].t[i];
                double p;
                if (t->kind != 0) continue;
                p = t->power;
                if (fabs(p) < 1e-12 || fabs(p - 1.0) < 1e-12 || fabs(p - 2.0) < 1e-12 ||
                    fabs(p - 3.0) < 1e-12 || fabs(p + 1.0) < 1e-12) continue;
                iv->add_c[j] = t->c; iv->add_e[j] = p; j++;
            }
        }
    }
    /* TDB convention (matching pycalphad): the last interval extrapolates above
     * its upper bound instead of dropping to zero as ChemSage data do. */
    em->intervals[em->n_intervals - 1].t_max = 1e12;
}

static void tdb_fill_excess(Tdb *tb, double *coeff6, const TdbSeg *seg, int n_seg)
{
    int i;
    if (n_seg > 1) tdb_fail(tb, "piecewise interaction parameter is outside the v1 subset");
    if (n_seg == 0) return;
    for (i = 0; i < seg[0].n; ++i) {
        const TdbTerm *t = &seg[0].t[i];
        double p;
        if (t->kind == 1) { coeff6[2] += t->c; continue; }
        p = t->power;
        if      (fabs(p - 0.0) < 1e-12) coeff6[0] += t->c;
        else if (fabs(p - 1.0) < 1e-12) coeff6[1] += t->c;
        else if (fabs(p - 2.0) < 1e-12) coeff6[3] += t->c;
        else if (fabs(p - 3.0) < 1e-12) coeff6[4] += t->c;
        else if (fabs(p + 1.0) < 1e-12) coeff6[5] += t->c;
        else tdb_fail(tb, "interaction parameter with a non-polynomial term is outside the v1 subset");
    }
}

static const TdbSpecies *tdb_species(Tdb *tb, const char *name)
{
    int i;
    for (i = 0; i < tb->n_sp; ++i)
        if (strcmp(tb->sp[i].name, name) == 0) return &tb->sp[i];
    return NULL;
}

static int tdb_element_index(Tdb *tb, const char *name)
{
    int i;
    for (i = 0; i < tb->n_el; ++i)
        if (strcmp(tb->el_name[i], name) == 0) return i;
    return -1;
}

/* parse a species stoichiometry string like AL2O3 or NA1CL1 or O1/-2 */
static void tdb_parse_composition(Tdb *tb, const char *s, TdbSpecies *sp)
{
    const char *p = s;
    sp->n_el = 0; sp->atoms = 0.0; sp->charge = 0.0;
    while (*p && *p != '/') {
        char el[3];
        char *end = NULL;
        double n;
        el[0] = el[1] = el[2] = '\0';
        if (!isalpha((unsigned char)*p)) tdb_fail(tb, "bad species stoichiometry");
        el[0] = *p++;
        if (isalpha((unsigned char)*p)) {
            char two[3];
            two[0] = el[0]; two[1] = *p; two[2] = '\0';
            if (tdb_element_index(tb, two) >= 0) { el[1] = *p; p++; }
        }
        n = strtod(p, &end);
        if (end == p) n = 1.0; else p = end;
        if (strcmp(el, "VA") != 0) {
            int ei = tdb_element_index(tb, el);
            if (ei < 0) tdb_fail(tb, "species uses an element not declared");
            if (sp->n_el >= 8) tdb_fail(tb, "species with too many elements");
            sp->el[sp->n_el] = ei; sp->n[sp->n_el] = n; sp->n_el++;
            sp->atoms += n;
        }
        if (*p == '/') break;
    }
    if (*p == '/') sp->charge = strtod(p + 1, NULL);
}

/* ---- assemble a :Q (MQMQA / SUBQ) phase from the MQ* records ---- */

static int tdb_q_name_index(char (*names)[NAME_MAX], int n, const char *want)
{
    int i;
    for (i = 0; i < n; ++i)
        if (strcmp(names[i], want) == 0) return i;
    return -1;
}

static void tdb_build_q_phase(Tdb *tb, Db *db, TdbPhase *tp)
{
    Phase *ph = &db->phases[db->n_phases++];
    int ncat, nan, i, k, q;
    TdbSeg *out = calloc(TDB_MAX_SEG, sizeof(TdbSeg));   /* heap: WASM stacks are small */
    if (!out) tdb_fail(tb, "out of memory");
    memset(ph, 0, sizeof *ph);
    snprintf(ph->name, NAME_MAX, "%s", tp->name);
    ph->kind = 0;
    ph->soln_type = 1;   /* SUBQ */
    if (tp->n_subl != 2) tdb_fail(tb, ":Q phase must have two sublattices (cations : anions)");
    ncat = tp->ncon[0]; nan = tp->ncon[1];
    if (ncat < 1 || nan < 1) tdb_fail(tb, ":Q phase with an empty sublattice");
    ph->n_cat = ncat; ph->n_an = nan;
    ph->cat_name = calloc((size_t)ncat, NAME_MAX);
    ph->an_name = calloc((size_t)nan, NAME_MAX);
    ph->cat_charge = calloc((size_t)ncat, sizeof(double));
    ph->an_charge = calloc((size_t)nan, sizeof(double));
    ph->cat_group = calloc((size_t)ncat, sizeof(int));
    ph->an_group = calloc((size_t)nan, sizeof(int));
    if (!ph->cat_name || !ph->an_name || !ph->cat_charge || !ph->an_charge ||
        !ph->cat_group || !ph->an_group) tdb_fail(tb, "out of memory");
    for (i = 0; i < ncat; ++i) {
        const TdbSpecies *sp = tdb_species(tb, tp->con[0][i]);
        snprintf(ph->cat_name[i], NAME_MAX, "%s", tp->con[0][i]);
        ph->cat_charge[i] = sp ? fabs(sp->charge) : 0.0;
        if (ph->cat_charge[i] <= 0.0) tdb_fail(tb, ":Q cation without a declared charge (SPECIES .../+n)");
        ph->cat_group[i] = 1;
    }
    for (k = 0; k < nan; ++k) {
        const TdbSpecies *sp = tdb_species(tb, tp->con[1][k]);
        snprintf(ph->an_name[k], NAME_MAX, "%s", tp->con[1][k]);
        ph->an_charge[k] = sp ? fabs(sp->charge) : 0.0;
        if (ph->an_charge[k] <= 0.0) tdb_fail(tb, ":Q anion without a declared charge (SPECIES .../-n)");
        ph->an_group[k] = 1;
    }
    /* pairs, cation-major over the constituent lists */
    ph->n_pairs = ncat * nan;
    ph->pairs = calloc((size_t)ph->n_pairs, sizeof(Endmember));
    if (!ph->pairs) tdb_fail(tb, "out of memory");
    for (i = 0; i < ncat; ++i) for (k = 0; k < nan; ++k) {
        Endmember *em = &ph->pairs[i * nan + k];
        em->cat_idx = i; em->an_idx = k;
        em->zeta = 0.0;
        em->stoich_quad[0] = 1.0;
    }
    /* walk the MQ records for this phase */
    ph->n_quads = 0;
    { int nz = 0, nx = 0;
      for (q = 0; q < tb->n_mq; ++q) {
          if (strcmp(tb->mq[q].phase, tp->name) != 0) continue;
          if (tb->mq[q].kind == 3) nz++;
          if (tb->mq[q].kind == 4) nx++;
      }
      ph->mqmz = calloc((size_t)(nz > 0 ? nz : 1), sizeof(Mqmz));
      ph->mqmx = calloc((size_t)(nx > 0 ? nx : 1), sizeof(Mqmx));
      if (!ph->mqmz || !ph->mqmx) tdb_fail(tb, "out of memory");
    }
    for (q = 0; q < tb->n_mq; ++q) {
        TdbMq *mq = &tb->mq[q];
        if (strcmp(mq->phase, tp->name) != 0) continue;
        if (mq->kind == 0 || mq->kind == 1 || mq->kind == 2) {
            int ci, ai;
            Endmember *em;
            if (mq->n_names < 2) tdb_fail(tb, "MQ pair statement needs cation and anion");
            ci = tdb_q_name_index(tp->con[0], ncat, mq->names[0]);
            ai = tdb_q_name_index(tp->con[1], nan, mq->names[1]);
            if (ci < 0 || ai < 0) tdb_fail(tb, "MQ pair names a constituent not in the phase");
            em = &ph->pairs[ci * nan + ai];
            if (mq->kind == 0) {
                int n;
                memset(out, 0, TDB_MAX_SEG * sizeof(TdbSeg));
                n = tdb_resolve_param(tb, mq->expr, mq->n_seg, out, TDB_MAX_SEG);
                tdb_fill_endmember(tb, em, out, n);
            } else if (mq->kind == 1) {
                if (mq->n_vals >= 1) em->zeta = mq->vals[0];
            } else {
                int v;
                for (v = 0; v < mq->n_vals && v < 5; ++v) em->stoich_quad[v] = mq->vals[v];
            }
        } else if (mq->kind == 3) {
            Mqmz *z = &ph->mqmz[ph->n_quads];
            int A, B, X, Y, v;
            if (mq->n_names < 4) tdb_fail(tb, "MQZ needs four constituent names");
            A = tdb_q_name_index(tp->con[0], ncat, mq->names[0]);
            B = tdb_q_name_index(tp->con[0], ncat, mq->names[1]);
            X = tdb_q_name_index(tp->con[1], nan, mq->names[2]);
            Y = tdb_q_name_index(tp->con[1], nan, mq->names[3]);
            if (A < 0 || B < 0 || X < 0 || Y < 0) tdb_fail(tb, "MQZ names a constituent not in the phase");
            if (mq->n_vals < 4) tdb_fail(tb, "MQZ needs four coordination numbers");
            if (A <= B) { z->A = A; z->B = B; z->Z[0] = mq->vals[0]; z->Z[1] = mq->vals[1]; }
            else        { z->A = B; z->B = A; z->Z[0] = mq->vals[1]; z->Z[1] = mq->vals[0]; }
            if (X <= Y) { z->X = X; z->Y = Y; z->Z[2] = mq->vals[2]; z->Z[3] = mq->vals[3]; }
            else        { z->X = Y; z->Y = X; z->Z[2] = mq->vals[3]; z->Z[3] = mq->vals[2]; }
            (void)v;
            ph->n_quads++;
        } else if (mq->kind == 4) {
            Mqmx *x = &ph->mqmx[ph->n_mqmx];
            int n, A, B, X, Y, t;
            memset(out, 0, TDB_MAX_SEG * sizeof(TdbSeg));
            if (mq->n_names < 4) tdb_fail(tb, "MQX needs four constituent names");
            A = tdb_q_name_index(tp->con[0], ncat, mq->names[0]);
            B = tdb_q_name_index(tp->con[0], ncat, mq->names[1]);
            X = tdb_q_name_index(tp->con[1], nan, mq->names[2]);
            Y = tdb_q_name_index(tp->con[1], nan, mq->names[3]);
            if (A < 0 || B < 0 || X < 0 || Y < 0) tdb_fail(tb, "MQX names a constituent not in the phase");
            x->code = mq->code;
            x->A = A; x->B = B; x->X = X; x->Y = Y;
            x->mix = (A != B && X == Y) ? 0 : (A == B && X != Y) ? 1 : -1;
            x->exp[0] = mq->exp_p; x->exp[1] = mq->exp_q;
            /* the ternary exponent lives in exp[2] (see mqmqa_ph_mqmx_ternary) */
            x->exp[2] = (mq->exp_r >= 0) ? mq->exp_r : 0; x->exp[3] = 0;
            x->add_cat = -1;
            if (mq->exp_r >= 0 && mq->n_names >= 5) {
                t = tdb_q_name_index(tp->con[0], ncat, mq->names[4]);
                if (t < 0) tdb_fail(tb, "MQX ternary cation not in the phase");
                x->add_cat = t;
            }
            x->coeff = calloc((size_t)db->n_excess, sizeof(double));
            if (!x->coeff) tdb_fail(tb, "out of memory");
            n = tdb_resolve_param(tb, mq->expr, mq->n_seg, out, TDB_MAX_SEG);
            tdb_fill_excess(tb, x->coeff, out, n);
            ph->n_mqmx++;
        } else if (mq->kind == 5) {
            int t = tdb_q_name_index(tp->con[0], ncat, mq->names[0]);
            if (t >= 0) { if (mq->n_vals >= 1) ph->cat_group[t] = (int)mq->vals[0]; }
            else {
                t = tdb_q_name_index(tp->con[1], nan, mq->names[0]);
                if (t >= 0 && mq->n_vals >= 1) ph->an_group[t] = (int)mq->vals[0];
            }
        }
    }
    /* every pair needs a Gibbs function */
    for (i = 0; i < ph->n_pairs; ++i)
        if (!ph->pairs[i].intervals)
            tdb_fail(tb, ":Q phase pair without an MQG parameter");
    free(out);
}

/* ---- assemble the Db ---- */

static Db *tdb_build_db(Tdb *tb)
{
    Db *db = calloc(1, sizeof(Db));
    int i, p, q, s;
    if (!db) tdb_fail(tb, "out of memory");
    db->n_el = tb->n_el;
    db->el_name = calloc((size_t)tb->n_el, NAME_MAX);
    db->el_mass = calloc((size_t)tb->n_el, sizeof(double));
    if (!db->el_name || !db->el_mass) tdb_fail(tb, "out of memory");
    for (i = 0; i < tb->n_el; ++i) {
        snprintf(db->el_name[i], NAME_MAX, "%s", tb->el_name[i]);
        db->el_mass[i] = tb->el_mass[i];
    }
    db->n_gibbs = 6;
    for (i = 0; i < 6; ++i) db->gibbs_idx[i] = i + 1;
    db->n_excess = 6;
    for (i = 0; i < 6; ++i) db->excess_idx[i] = i + 1;

    db->phases = calloc((size_t)(tb->n_ph > 0 ? tb->n_ph : 1), sizeof(Phase));
    db->stoich = calloc((size_t)(tb->n_ph > 0 ? tb->n_ph : 1), sizeof(Endmember));
    if (!db->phases || !db->stoich) tdb_fail(tb, "out of memory");

    for (p = 0; p < tb->n_ph; ++p) {
        TdbPhase *tp = &tb->ph[p];
        int is_stoich = 1;
        if (tp->is_q) { tdb_build_q_phase(tb, db, tp); continue; }
        if (tp->flags_order)
            tdb_fail(tb, "order-disorder phase model is outside the v1 subset");
        for (s = 0; s < tp->n_subl; ++s)
            if (tp->ncon[s] == 0) tdb_fail(tb, "phase with an empty sublattice");
        for (s = 0; s < tp->n_subl; ++s)
            if (tp->ncon[s] != 1) { is_stoich = 0; break; }

        if (is_stoich) {
            Endmember *em = &db->stoich[db->n_stoich];
            TdbSeg *out = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
            int found = 0, has_atoms = 0;
            if (!out) tdb_fail(tb, "out of memory");
            memset(em, 0, sizeof *em);
            snprintf(em->name, NAME_MAX, "%s", tp->name);
            em->stoich_el = calloc((size_t)tb->n_el, sizeof(double));
            if (!em->stoich_el) tdb_fail(tb, "out of memory");
            for (s = 0; s < tp->n_subl; ++s) {
                const TdbSpecies *sp = tdb_species(tb, tp->con[s][0]);
                int e;
                if (!sp) {
                    if (strcmp(tp->con[s][0], "VA") == 0) continue;
                    tdb_fail(tb, "constituent is not a declared species");
                }
                for (e = 0; e < sp->n_el; ++e) {
                    em->stoich_el[sp->el[e]] += tp->ratio[s] * sp->n[e];
                    has_atoms = 1;
                }
            }
            for (q = 0; q < tb->n_par; ++q) {
                int n;
                if (strcmp(tb->par[q].phase, tp->name) != 0) continue;
                if (tb->par[q].kind != 0) continue;
                n = tdb_resolve_param(tb, tb->par[q].expr, tb->par[q].n_seg,
                                      out, TDB_MAX_SEG);
                tdb_fill_endmember(tb, em, out, n);
                found = 1;
                break;
            }
            free(out);
            if (!found || !has_atoms) { free(em->stoich_el); em->stoich_el = NULL; continue; }
            db->n_stoich++;
            continue;
        }

        /* CEF solution phase */
        {
        Phase *ph = &db->phases[db->n_phases++];
        SublPhase *cf;
        int n_con = 0, n_em = 0, n_ex = 0;
        TdbSeg *out = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
        if (!out) tdb_fail(tb, "out of memory");
        memset(ph, 0, sizeof *ph);
        snprintf(ph->name, NAME_MAX, "%s", tp->name);
        ph->kind = 1;
        ph->soln_type = -1;
        cf = calloc(1, sizeof(SublPhase));
        if (!cf) tdb_fail(tb, "out of memory");
        ph->cef = cf;
        cf->n_subl = tp->n_subl;
        cf->site_ratio = calloc((size_t)tp->n_subl, sizeof(double));
        cf->subl_ncon = calloc((size_t)tp->n_subl, sizeof(int));
        cf->subl_off = calloc((size_t)tp->n_subl, sizeof(int));
        if (!cf->site_ratio || !cf->subl_ncon || !cf->subl_off) tdb_fail(tb, "out of memory");
        for (s = 0; s < tp->n_subl; ++s) {
            cf->site_ratio[s] = tp->ratio[s];
            cf->subl_ncon[s] = tp->ncon[s];
            cf->subl_off[s] = n_con;
            n_con += tp->ncon[s];
        }
        cf->n_con = n_con;
        cf->con_name = calloc((size_t)n_con, NAME_MAX);
        cf->con_atoms = calloc((size_t)n_con, sizeof(double));
        if (!cf->con_name || !cf->con_atoms) tdb_fail(tb, "out of memory");
        for (s = 0; s < tp->n_subl; ++s) {
            for (i = 0; i < tp->ncon[s]; ++i) {
                int fi = cf->subl_off[s] + i;
                const TdbSpecies *sp;
                snprintf(cf->con_name[fi], NAME_MAX, "%s", tp->con[s][i]);
                if (strcmp(tp->con[s][i], "VA") == 0) { cf->con_atoms[fi] = 0.0; continue; }
                sp = tdb_species(tb, tp->con[s][i]);
                if (!sp) tdb_fail(tb, "constituent is not a declared species");
                cf->con_atoms[fi] = sp->atoms;
            }
        }
        {
        int n_tcx = 0, n_bmx = 0;
        for (q = 0; q < tb->n_par; ++q) {
            int mixing = 0;
            if (strcmp(tb->par[q].phase, tp->name) != 0) continue;
            for (s = 0; s < tp->n_subl; ++s)
                if (tb->par[q].ncon[s] == 2) mixing++;
            if (mixing > 1) tdb_fail(tb, "interaction on two sublattices at once is outside the v1 subset");
            if (tb->par[q].kind == 0) { if (mixing == 0) n_em++; else n_ex++; }
            else if (mixing == 1) { if (tb->par[q].kind == 1) n_tcx++; else n_bmx++; }
        }
        cf->em = calloc((size_t)(n_em > 0 ? n_em : 1), sizeof(Endmember));
        cf->em_con = calloc((size_t)(n_em > 0 ? n_em : 1) * (size_t)tp->n_subl, sizeof(int));
        cf->ex = calloc((size_t)(n_ex > 0 ? n_ex : 1), sizeof(CefExcess));
        cf->tc_em = calloc((size_t)(n_em > 0 ? n_em : 1) * 6, sizeof(double));
        cf->bm_em = calloc((size_t)(n_em > 0 ? n_em : 1) * 6, sizeof(double));
        cf->tc_ex = calloc((size_t)(n_tcx > 0 ? n_tcx : 1), sizeof(CefExcess));
        cf->bm_ex = calloc((size_t)(n_bmx > 0 ? n_bmx : 1), sizeof(CefExcess));
        if (!cf->em || !cf->em_con || !cf->ex || !cf->tc_em || !cf->bm_em ||
            !cf->tc_ex || !cf->bm_ex) tdb_fail(tb, "out of memory");
        cf->magnetic = tp->flags_magnetic;
        cf->mag_afm = tp->flags_magnetic ? (tp->mag_afm != 0.0 ? tp->mag_afm : -1.0) : -1.0;
        cf->mag_p = tp->flags_magnetic ? (tp->mag_p > 0.0 ? tp->mag_p : 0.4) : 0.4;
        }
        for (q = 0; q < tb->n_par; ++q) {
            TdbParam *pa = &tb->par[q];
            int mixing_subl = -1, n;
            if (strcmp(pa->phase, tp->name) != 0) continue;
            if (pa->kind != 0) continue;   /* TC / BMAGN routed in the second pass */
            for (s = 0; s < tp->n_subl; ++s)
                if (pa->ncon[s] == 2) { mixing_subl = s; break; }
            n = tdb_resolve_param(tb, pa->expr, pa->n_seg, out, TDB_MAX_SEG);
            if (mixing_subl < 0) {
                Endmember *em = &cf->em[cf->n_em];
                memset(em, 0, sizeof *em);
                snprintf(em->name, NAME_MAX, "%s", tp->name);
                tdb_fill_endmember(tb, em, out, n);
                for (s = 0; s < tp->n_subl; ++s)
                    cf->em_con[cf->n_em * tp->n_subl + s] = pa->con[s][0];
                cf->n_em++;
            } else {
                CefExcess *ex = &cf->ex[cf->n_ex];
                int ci = pa->con[mixing_subl][0], cj = pa->con[mixing_subl][1];
                memset(ex, 0, sizeof *ex);
                ex->subl = mixing_subl;
                if (strcmp(tp->con[mixing_subl][ci], tp->con[mixing_subl][cj]) > 0) {
                    int t2 = ci; int k2, m2;
                    ci = cj; cj = t2;
                    if (pa->order % 2 == 1) {
                        /* odd RK order: swapping the pair flips the sign */
                        for (k2 = 0; k2 < pa->n_seg; ++k2)
                            for (m2 = 0; m2 < pa->expr[k2].n; ++m2)
                                pa->expr[k2].t[m2].c = -pa->expr[k2].t[m2].c;
                        n = tdb_resolve_param(tb, pa->expr, pa->n_seg, out, TDB_MAX_SEG);
                    }
                }
                ex->i = ci; ex->j = cj;
                ex->order = pa->order;
                ex->coeff = calloc(6, sizeof(double));
                ex->other = calloc((size_t)tp->n_subl, sizeof(int));
                if (!ex->coeff || !ex->other) tdb_fail(tb, "out of memory");
                tdb_fill_excess(tb, ex->coeff, out, n);
                for (s = 0; s < tp->n_subl; ++s)
                    ex->other[s] = (s == mixing_subl) ? -1 : pa->con[s][0];
                cf->n_ex++;
            }
        }
        /* second pass: TC and BMAGN parameters onto the built endmember/excess frame */
        for (q = 0; q < tb->n_par; ++q) {
            TdbParam *pa = &tb->par[q];
            int mixing_subl = -1, n, e;
            double *slot6 = NULL;
            if (strcmp(pa->phase, tp->name) != 0 || pa->kind == 0) continue;
            for (s = 0; s < tp->n_subl; ++s)
                if (pa->ncon[s] == 2) { mixing_subl = s; break; }
            n = tdb_resolve_param(tb, pa->expr, pa->n_seg, out, TDB_MAX_SEG);
            if (mixing_subl < 0) {
                for (e = 0; e < cf->n_em; ++e) {
                    int match = 1;
                    for (s = 0; s < tp->n_subl; ++s)
                        if (cf->em_con[e * tp->n_subl + s] != pa->con[s][0]) { match = 0; break; }
                    if (match) { slot6 = (pa->kind == 1 ? cf->tc_em : cf->bm_em) + e * 6; break; }
                }
                if (!slot6) continue;   /* TC/BMAGN for an endmember with no G: inert */
                tdb_fill_excess(tb, slot6, out, n);
            } else {
                CefExcess *ex = (pa->kind == 1) ? &cf->tc_ex[cf->n_tcx] : &cf->bm_ex[cf->n_bmx];
                int ci = pa->con[mixing_subl][0], cj = pa->con[mixing_subl][1];
                memset(ex, 0, sizeof *ex);
                ex->subl = mixing_subl;
                if (strcmp(tp->con[mixing_subl][ci], tp->con[mixing_subl][cj]) > 0) {
                    int t2 = ci; int k2, m2;
                    ci = cj; cj = t2;
                    if (pa->order % 2 == 1) {
                        for (k2 = 0; k2 < pa->n_seg; ++k2)
                            for (m2 = 0; m2 < pa->expr[k2].n; ++m2)
                                pa->expr[k2].t[m2].c = -pa->expr[k2].t[m2].c;
                        n = tdb_resolve_param(tb, pa->expr, pa->n_seg, out, TDB_MAX_SEG);
                    }
                }
                ex->i = ci; ex->j = cj;
                ex->order = pa->order;
                ex->coeff = calloc(6, sizeof(double));
                ex->other = calloc((size_t)tp->n_subl, sizeof(int));
                if (!ex->coeff || !ex->other) tdb_fail(tb, "out of memory");
                tdb_fill_excess(tb, ex->coeff, out, n);
                for (s = 0; s < tp->n_subl; ++s)
                    ex->other[s] = (s == mixing_subl) ? -1 : pa->con[s][0];
                if (pa->kind == 1) cf->n_tcx++; else cf->n_bmx++;
            }
        }
        free(out);
        if (cf->n_em == 0)
            tdb_fail(tb, "solution phase with no G parameters");
        }
    }
    return db;
}

/* ---- the parse driver ---- */

static Db *read_tdb(char *text_owned)
{
    Lexer lx;
    Tdb tb;
    Db *db = NULL;
    memset(&lx, 0, sizeof lx);
    lx.buf = text_owned;
    lx.line = 1;
    memset(&tb, 0, sizeof tb);
    tb.lx = &lx;
    tb.cur = text_owned;
    tb.line = 1;

    if (setjmp(lx.jb) == 0) {
        char *st;
        tb.func = calloc(TDB_MAX_FUNCS, sizeof(TdbFunc));
        tb.el_name = calloc(64, NAME_MAX);
        tb.el_mass = calloc(64, sizeof(double));
        tb.sp = calloc(4096, sizeof(TdbSpecies));
        tb.ph = calloc(512, sizeof(TdbPhase));
        tb.cap_par = 32768;
        tb.par = calloc((size_t)tb.cap_par, sizeof(TdbParam));
        tb.cap_mq = 8192;
        tb.mq = calloc((size_t)tb.cap_mq, sizeof(TdbMq));
        if (!tb.func || !tb.el_name || !tb.el_mass || !tb.sp || !tb.ph || !tb.par || !tb.mq)
            tdb_fail(&tb, "out of memory");

        /* built-in: the gas constant, referenced as R# in some files */
        {
            int fi = tb.n_func++;
            snprintf(tb.func[fi].name, NAME_MAX, "R");
            tb.func[fi].seg = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
            if (!tb.func[fi].seg) tdb_fail(&tb, "out of memory");
            tb.func[fi].n_seg = 1;
            tb.func[fi].seg[0].lo = 0.01; tb.func[fi].seg[0].hi = 1e12;
            tb.func[fi].seg[0].n = 1;
            tb.func[fi].seg[0].t[0].c = 8.31451;
            tb.func[fi].seg[0].t[0].kind = 0;
            tb.func[fi].seg[0].t[0].power = 0.0;
            tb.func[fi].seg[0].t[0].func = -1;
        }
        /* pass 0: register every FUNCTION from a scratch copy, so forward
         * references (including constant folding) resolve during pass 1 */
        {
            size_t len = strlen(text_owned);
            char *copy = malloc(len + 1);
            if (!copy) tdb_fail(&tb, "out of memory");
            memcpy(copy, text_owned, len + 1);
            {
                Tdb pre = tb;
                pre.cur = copy; pre.line = 1;
                while ((st = tdb_next_statement(&pre)) != NULL) {
                    char *s = st;
                    char kw[NAME_MAX], name[NAME_MAX];
                    if (!tdb_word(&s, kw, sizeof kw)) continue;
                    if (strncmp(kw, "FUN", 3) != 0) continue;
                    if (!tdb_word(&s, name, sizeof name)) continue;
                    {
                        int fi = tdb_func_index(&pre, name);
                        if (fi < 0) {
                            if (pre.n_func >= TDB_MAX_FUNCS) tdb_fail(&pre, "too many functions");
                            fi = pre.n_func++;
                            snprintf(pre.func[fi].name, NAME_MAX, "%s", name);
                            pre.func[fi].seg = NULL;
                        }
                        tdb_func_segs(&pre, fi);
                        pre.func[fi].n_seg = tdb_parse_piecewise(&pre, &s, pre.func[fi].seg, TDB_MAX_SEG);
                        pre.func[fi].state = 0;
                    }
                }
                tb.n_func = pre.n_func;   /* the table itself is shared storage */
            }
            free(copy);
        }

        while ((st = tdb_next_statement(&tb)) != NULL) {
            char *s = st;
            char kw[NAME_MAX];
            if (!tdb_word(&s, kw, sizeof kw)) continue;

            if (strncmp(kw, "ELEM", 4) == 0) {
                char name[NAME_MAX], ref[NAME_MAX], w[NAME_MAX];
                double mass = 0.0;
                TdbSpecies *sp;
                if (!tdb_word(&s, name, sizeof name)) tdb_fail(&tb, "ELEMENT without a name");
                tdb_word(&s, ref, sizeof ref);
                if (tdb_word(&s, w, sizeof w)) mass = atof(w);
                if (strcmp(name, "/-") == 0 || strcmp(name, "VA") == 0) continue;
                if (tb.n_el >= 64) tdb_fail(&tb, "too many elements");
                snprintf(tb.el_name[tb.n_el], NAME_MAX, "%s", name);
                tb.el_mass[tb.n_el] = mass;
                sp = &tb.sp[tb.n_sp++];
                snprintf(sp->name, NAME_MAX, "%s", name);
                sp->n_el = 1; sp->el[0] = tb.n_el; sp->n[0] = 1.0; sp->atoms = 1.0;
                tb.n_el++;
            } else if (strncmp(kw, "SPEC", 4) == 0) {
                char name[NAME_MAX], comp[NAME_MAX];
                TdbSpecies *sp;
                if (!tdb_word(&s, name, sizeof name) || !tdb_word(&s, comp, sizeof comp))
                    tdb_fail(&tb, "malformed SPECIES");
                if (strcmp(name, "VA") == 0) continue;
                if (tb.n_sp >= 4096) tdb_fail(&tb, "too many species");
                sp = &tb.sp[tb.n_sp++];
                snprintf(sp->name, NAME_MAX, "%s", name);
                tdb_parse_composition(&tb, comp, sp);
            } else if (strncmp(kw, "FUN", 3) == 0) {
                char name[NAME_MAX];
                int fi;
                if (!tdb_word(&s, name, sizeof name)) tdb_fail(&tb, "FUNCTION without a name");
                fi = tdb_func_index(&tb, name);
                if (fi < 0) {
                    if (tb.n_func >= TDB_MAX_FUNCS) tdb_fail(&tb, "too many functions");
                    fi = tb.n_func++;
                    snprintf(tb.func[fi].name, NAME_MAX, "%s", name);
                    tb.func[fi].seg = NULL;
                }
                tdb_func_segs(&tb, fi);
                tb.func[fi].n_seg = tdb_parse_piecewise(&tb, &s, tb.func[fi].seg, TDB_MAX_SEG);
                tb.func[fi].state = 0;
            } else if (strncmp(kw, "TYPE_DEF", 8) == 0) {
                char ch[NAME_MAX];
                if (!tdb_word(&s, ch, sizeof ch)) continue;
                if (strstr(s, "MAGNETIC")) {
                    if (tb.n_mag_td < 15) {
                        double afm = -1.0, pv = 0.4;
                        sscanf(strstr(s, "MAGNETIC") + 8, "%lf %lf", &afm, &pv);
                        tb.magnetic_typedefs[tb.n_mag_td] = ch[0];
                        tb.mag_td_afm[tb.n_mag_td] = afm;
                        tb.mag_td_p[tb.n_mag_td] = pv;
                        tb.n_mag_td++;
                    }
                } else if (strstr(s, "DISORD") || strstr(s, "DIS_PART")) {
                    if (tb.n_ord_td < 15) tb.order_typedefs[tb.n_ord_td++] = ch[0];
                }
            } else if (strncmp(kw, "PHAS", 4) == 0) {
                char name[NAME_MAX], code[NAME_MAX], w[NAME_MAX];
                char *colon;
                TdbPhase *ph;
                char *c;
                int m;
                if (!tdb_word(&s, name, sizeof name)) tdb_fail(&tb, "PHASE without a name");
                colon = strchr(name, ':');
                if (colon) *colon = '\0';
                {
                    int q_suffix = 0;
                    if (*s == ':') {      /* attached :L / :Y / :Q model-type suffix */
                        char sfx[NAME_MAX];
                        tdb_word(&s, sfx, sizeof sfx);  /* the colon */
                        if (tdb_word(&s, sfx, sizeof sfx)) {
                            if (sfx[0] == 'Y')
                                tdb_fail(&tb, "ionic two-sublattice liquid (:Y) is outside the v1 subset");
                            if (sfx[0] == 'Q') q_suffix = 1;
                        }
                    }
                    tb.ph[tb.n_ph].is_q = q_suffix;   /* the slot about to be filled */
                }
                if (tb.n_ph >= 512) tdb_fail(&tb, "too many phases");
                ph = &tb.ph[tb.n_ph++];
                snprintf(ph->name, NAME_MAX, "%s", name);
                if (!tdb_word(&s, code, sizeof code)) tdb_fail(&tb, "PHASE without a model code");
                for (c = code; *c; ++c) {
                    for (m = 0; m < tb.n_mag_td; ++m)
                        if (*c == tb.magnetic_typedefs[m]) {
                            ph->flags_magnetic = 1;
                            ph->mag_afm = tb.mag_td_afm[m];
                            ph->mag_p = tb.mag_td_p[m];
                        }
                    for (m = 0; m < tb.n_ord_td; ++m)
                        if (*c == tb.order_typedefs[m]) ph->flags_order = 1;
                }
                if (!tdb_word(&s, w, sizeof w)) tdb_fail(&tb, "PHASE without sublattice count");
                ph->n_subl = atoi(w);
                if (ph->n_subl < 1 || ph->n_subl > TDB_MAX_SUBL)
                    tdb_fail(&tb, "unsupported sublattice count");
                for (m = 0; m < ph->n_subl; ++m) {
                    if (!tdb_word(&s, w, sizeof w)) tdb_fail(&tb, "missing site ratio");
                    ph->ratio[m] = atof(w);
                }
            } else if (strncmp(kw, "CONS", 4) == 0) {
                char name[NAME_MAX], w[NAME_MAX];
                char *colon;
                TdbPhase *ph = NULL;
                int i2, subl = -1;
                if (!tdb_word(&s, name, sizeof name)) tdb_fail(&tb, "CONSTITUENT without a phase");
                colon = strchr(name, ':');
                if (colon) *colon = '\0';
                if (*s == ':') {          /* attached :L suffix: colon + short suffix, only
                                           * when the real list starts at a later colon */
                    char *save = s;
                    char sfx[NAME_MAX];
                    tdb_word(&s, sfx, sizeof sfx);      /* the colon */
                    if (!(tdb_word(&s, sfx, sizeof sfx) && sfx[0] != ':' &&
                          strlen(sfx) <= 2 && tdb_peekc(s) == ':'))
                        s = save;
                }
                for (i2 = 0; i2 < tb.n_ph; ++i2)
                    if (strcmp(tb.ph[i2].name, name) == 0) { ph = &tb.ph[i2]; break; }
                if (!ph) tdb_fail(&tb, "CONSTITUENT for an undeclared phase");
                while (tdb_word(&s, w, sizeof w)) {
                    size_t len;
                    if (w[0] == ':') { subl++; if (subl >= ph->n_subl) break; continue; }
                    if (w[0] == ',') continue;
                    if (subl < 0) continue;
                    len = strlen(w);
                    if (len && w[len - 1] == '%') w[len - 1] = '\0';
                    if (!w[0]) continue;
                    if (ph->ncon[subl] >= TDB_MAX_CON) tdb_fail(&tb, "too many constituents");
                    snprintf(ph->con[subl][ph->ncon[subl]++], NAME_MAX, "%s", w);
                }
            } else if (strncmp(kw, "PARA", 4) == 0) {
                char type[NAME_MAX]; size_t tn = 0;
                char desc[512]; size_t dn = 0;
                int depth;
                char *comma, *phname, *pcolon, *arr, *semi, *tokp;
                int order = 0, subl;
                int pending_kind = 0;
                TdbPhase *ph = NULL;
                TdbParam *pa;
                int i2;
                while (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r') s++;
                while (*s && *s != '(' && tn + 1 < sizeof type) type[tn++] = *s++;
                type[tn] = '\0';
                while (tn && type[tn - 1] == ' ') type[--tn] = '\0';
                if (*s != '(') tdb_fail(&tb, "malformed PARAMETER descriptor");
                s++;
                depth = 1;
                while (*s && depth > 0) {
                    if (*s == '(') depth++;
                    else if (*s == ')') { depth--; if (!depth) { s++; break; } }
                    if (depth > 0 && dn + 1 < sizeof desc) desc[dn++] = *s;
                    s++;
                }
                desc[dn] = '\0';
                if (strncmp(type, "MQ", 2) == 0) {
                    /* uTDB extension statements (docs/UNIFIED_TDB_SPEC.md) */
                    TdbMq *mq;
                    char *arr2, *seg2, *mem2;
                    int ni = 0;
                    if (tb.n_mq >= tb.cap_mq) tdb_fail(&tb, "too many MQ parameters");
                    mq = &tb.mq[tb.n_mq];
                    memset(mq, 0, sizeof *mq);
                    mq->exp_r = -1;
                    if      (strcmp(type, "MQG") == 0)    mq->kind = 0;
                    else if (strcmp(type, "MQZETA") == 0) mq->kind = 1;
                    else if (strcmp(type, "MQSTOI") == 0) mq->kind = 2;
                    else if (strcmp(type, "MQZ") == 0)    mq->kind = 3;
                    else if (strcmp(type, "MQGRP") == 0)  mq->kind = 5;
                    else if (type[2] == 'X') {
                        mq->kind = 4;
                        mq->code = (type[3] == 'T') ? type[4] : type[3];
                        if (type[3] == 'T') mq->exp_r = 0;   /* ternary form, r read below */
                    } else continue;
                    /* descriptor: PHASE , names (comma/colon separated) ; exponents [: addcat] */
                    {
                        char *dcomma = strchr(desc, ',');
                        if (!dcomma) tdb_fail(&tb, "MQ parameter without a constituent array");
                        *dcomma = '\0';
                        snprintf(mq->phase, NAME_MAX, "%s", desc);
                        { char *pc = strchr(mq->phase, ':'); if (pc) *pc = '\0'; }
                        arr2 = dcomma + 1;
                    }
                    seg2 = strchr(arr2, ';');
                    if (seg2) { *seg2 = '\0'; seg2++; }
                    /* addcat rides after a colon in the exponent tail (MQXT) */
                    mem2 = arr2;
                    while (mem2 && *mem2 && ni < 5) {
                        char *nx = mem2 + strcspn(mem2, ",:");
                        char sep = *nx;
                        *nx = '\0';
                        while (*mem2 == ' ') mem2++;
                        { char *e2 = mem2 + strlen(mem2);
                          while (e2 > mem2 && e2[-1] == ' ') *--e2 = '\0'; }
                        if (*mem2) snprintf(mq->names[ni++], NAME_MAX, "%s", mem2);
                        mem2 = sep ? nx + 1 : NULL;
                    }
                    mq->n_names = ni;
                    if (seg2 && mq->kind == 4) {
                        char *colon2 = strchr(seg2, ':');
                        if (colon2) {
                            *colon2 = '\0';
                            if (ni < 5) snprintf(mq->names[mq->n_names++], NAME_MAX, "%s", colon2 + 1);
                        }
                        {
                            char *q2 = strchr(seg2, ',');
                            mq->exp_p = atoi(seg2);
                            if (q2) {
                                char *r2 = strchr(q2 + 1, ',');
                                mq->exp_q = atoi(q2 + 1);
                                if (r2) mq->exp_r = atoi(r2 + 1);
                            }
                        }
                    }
                    if (mq->kind == 0 || mq->kind == 4) {
                        mq->expr = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
                        if (!mq->expr) tdb_fail(&tb, "out of memory");
                        mq->n_seg = tdb_parse_piecewise(&tb, &s, mq->expr, TDB_MAX_SEG);
                    } else {
                        /* constant payload row: lowT v1 v2 ... ; T N */
                        char w2[NAME_MAX];
                        int after_semi = 0;
                        if (!tdb_word(&s, w2, sizeof w2)) tdb_fail(&tb, "MQ constants missing");
                        while (tdb_word(&s, w2, sizeof w2)) {
                            char *e3 = NULL;
                            double v3;
                            if (w2[0] == ';') { after_semi = 1; continue; }
                            v3 = strtod(w2, &e3);
                            if (e3 == w2) break;        /* hit the trailing N / ref */
                            if (after_semi) continue;   /* upper temperature limit */
                            if (mq->n_vals < 8) mq->vals[mq->n_vals++] = v3;
                        }
                    }
                    tb.n_mq++;
                    continue;
                }
                if (strcmp(type, "G") == 0 || strcmp(type, "L") == 0) pending_kind = 0;
                else if (strcmp(type, "TC") == 0) pending_kind = 1;
                else if (strcmp(type, "BMAGN") == 0 || strcmp(type, "BM") == 0) pending_kind = 2;
                else continue;   /* VS, diffusion etc.: ignored, energies unaffected */
                comma = strchr(desc, ',');
                if (!comma) tdb_fail(&tb, "PARAMETER without a constituent array");
                *comma = '\0';
                phname = desc;
                pcolon = strchr(phname, ':');
                if (pcolon) *pcolon = '\0';
                arr = comma + 1;
                semi = strrchr(arr, ';');
                if (semi) { order = atoi(semi + 1); *semi = '\0'; }
                for (i2 = 0; i2 < tb.n_ph; ++i2)
                    if (strcmp(tb.ph[i2].name, phname) == 0) { ph = &tb.ph[i2]; break; }
                if (!ph) continue;
                if (tb.n_par >= tb.cap_par) tdb_fail(&tb, "too many parameters");
                pa = &tb.par[tb.n_par];
                memset(pa, 0, sizeof *pa);
                snprintf(pa->phase, NAME_MAX, "%s", phname);
                pa->order = order;
                pa->kind = pending_kind;
                pa->expr = calloc(TDB_MAX_SEG, sizeof(TdbSeg));
                if (!pa->expr) tdb_fail(&tb, "out of memory");
                subl = 0;
                tokp = arr;
                while (subl < ph->n_subl && tokp) {
                    char *next = strchr(tokp, ':');
                    char *mem;
                    int m = 0;
                    if (next) *next = '\0';
                    mem = tokp;
                    while (mem && *mem) {
                        char *mc = strchr(mem, ',');
                        char *e;
                        int li = -1, i3;
                        if (mc) *mc = '\0';
                        while (*mem == ' ') mem++;
                        e = mem + strlen(mem);
                        while (e > mem && e[-1] == ' ') *--e = '\0';
                        for (i3 = 0; i3 < ph->ncon[subl]; ++i3)
                            if (strcmp(ph->con[subl][i3], mem) == 0) { li = i3; break; }
                        if (li < 0) tdb_fail(&tb, "parameter constituent not in CONSTITUENT list");
                        if (m >= 2) tdb_fail(&tb, "three-constituent interaction is outside the v1 subset");
                        pa->con[subl][m++] = li;
                        mem = mc ? mc + 1 : NULL;
                    }
                    if (m == 0) tdb_fail(&tb, "empty sublattice in parameter array");
                    pa->ncon[subl] = m;
                    subl++;
                    tokp = next ? next + 1 : NULL;
                }
                if (subl != ph->n_subl) tdb_fail(&tb, "parameter array does not match sublattice count");
                pa->n_seg = tdb_parse_piecewise(&tb, &s, pa->expr, TDB_MAX_SEG);
                tb.n_par++;
            } else {
                continue;   /* DATABASE_INFO, LIST_OF_REFERENCES, DEFAULT_COMMAND, ... */
            }
        }
        db = tdb_build_db(&tb);
        g_error[0] = '\0';
    } else {
        snprintf(g_error, sizeof g_error, "%s", lx.err);
        db = NULL;
    }
    {
        int i;
        for (i = 0; i < tb.n_func; ++i) free(tb.func[i].seg);
        for (i = 0; i < tb.n_par; ++i) free(tb.par[i].expr);
        for (i = 0; i < tb.n_mq; ++i) free(tb.mq[i].expr);
    }
    free(tb.func); free(tb.el_name); free(tb.el_mass);
    free(tb.sp); free(tb.ph); free(tb.par); free(tb.mq);
    free(text_owned);
    return db;
}
