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
static Db *read_from_text(char *text_owned)
{
    /* Uppercase in place, matching pycalphad's reader so species names align. */
    for (char *p = text_owned; *p; ++p) *p = (char)toupper((unsigned char)*p);

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
        per_mole_atoms);

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
