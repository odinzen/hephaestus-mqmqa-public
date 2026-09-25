/* Database writers: serialize the in-memory database that the .dat, .tdb and .utdb
 * readers build (cs_dat_priv.h) as Thermo-Calc TDB, the unified uTDB dialect
 * (docs/UNIFIED_TDB_SPEC.md), ChemSage .dat, or XTDB.
 *
 * The writers see what the readers kept: TDB functions arrive already expanded into
 * per-interval polynomials, so a written TDB carries those polynomials rather than
 * the original FUNCTION calls. Energies are unchanged; every coefficient is printed
 * with enough digits to read back as the identical double.
 *
 * A model the target format cannot hold is an error naming the model and a format
 * that can hold it, never an approximation. A source the reader skipped content in
 * (Db.lossy) is refused outright, since the converted file would drop it silently.
 */
#include "cs_dat.h"
#include "cs_dat_priv.h"
#include "textbuf.h"

#include <ctype.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LICENSE_LINE \
    "Converting a database does not change its license; the license of the source data applies."
/* pycalphad's stand-in for a lower temperature limit the source never gave */
#define UNKNOWN_LO 0.01
/* the TDB reader ends an extrapolating (unbounded) interval here */
#define OPEN_T 1e12

const char *mqmqa_version(void) { return HEPHAESTUS_VERSION; }

void mqmqa_text_free(char *text) { free(text); }

/* ------------------------------------------------------------------ *
 * Writer state
 * ------------------------------------------------------------------ */
typedef struct {
    const Db *db;
    TextBuf head, body;
    int bad;
    /* conventions the header has to explain, found while writing the body */
    int used_unknown_lo, used_zero_tail, renamed_ion;
} W;

static void wfail(W *w, const char *fmt, ...)
{
    char msg[256];
    va_list ap;
    if (w->bad) return;
    w->bad = 1;
    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);
    mqmqa_db_set_error("%s", msg);
}

#define OUT(...) tb_putf(&w->body, __VA_ARGS__)

/* Phase, species and constituent names become TDB tokens; reject any character
 * the TDB grammar reserves rather than write a file that parses differently. */
static int tdb_token_ok(const char *s)
{
    if (!*s) return 0;
    for (; *s; ++s)
        if (*s <= ' ' || *s > '~' || strchr(",:;()!$%#*\"'", *s)) return 0;
    return 1;
}

static int is_element_name(const Db *db, const char *s)
{
    for (int e = 0; e < db->n_el; ++e)
        if (strcmp(db->el_name[e], s) == 0) return 1;
    return 0;
}

/* ------------------------------------------------------------------ *
 * Species compositions. A TDB source keeps its SPECIES table; a ChemSage source
 * names its constituents, so the composition is read from the name (FE+2, SIO2).
 * ------------------------------------------------------------------ */
typedef struct {
    int n_el;
    int el[8];
    double n[8];
    double charge;
} Comp;

static int elem_match(const Db *db, const char *s, size_t len)
{
    for (int e = 0; e < db->n_el; ++e)
        if (strlen(db->el_name[e]) == len && strncmp(db->el_name[e], s, len) == 0) return e;
    return -1;
}

/* Split a trailing charge off a name, in any of the spellings databases use: FE+2,
 * FE2+ (ChemSage), FE[2+] (pycalphad), K+. Returns the base length. */
static size_t split_charge(const char *name, double *charge)
{
    size_t n = strlen(name), k = n;
    *charge = 0.0;
    if (n > 2 && name[n - 1] == ']') {
        const char *lb = strrchr(name, '[');
        if (lb && (name[n - 2] == '+' || name[n - 2] == '-')) {
            double mag = (lb + 1 < name + n - 2) ? strtod(lb + 1, NULL) : 1.0;
            *charge = (name[n - 2] == '-') ? -mag : mag;
            return (size_t)(lb - name);
        }
    }
    if (n > 1 && (name[n - 1] == '+' || name[n - 1] == '-')) {
        size_t d = n - 1;
        while (d > 0 && isdigit((unsigned char)name[d - 1])) d--;
        if (d < n - 1 && d > 0) {
            double mag = strtod(name + d, NULL);
            *charge = (name[n - 1] == '-') ? -mag : mag;
            return d;
        }
    }
    while (k > 0 && (isdigit((unsigned char)name[k - 1]) || name[k - 1] == '.')) k--;
    if (k > 0 && (name[k - 1] == '+' || name[k - 1] == '-')) {
        double mag = (k < n) ? strtod(name + k, NULL) : 1.0;
        *charge = (name[k - 1] == '-') ? -mag : mag;
        return k - 1;
    }
    return n;
}

static int parse_formula(const Db *db, const char *name, Comp *c)
{
    size_t len = split_charge(name, &c->charge), i = 0;
    c->n_el = 0;
    while (i < len) {
        int e = -1;
        size_t w = 0;
        if (!isalpha((unsigned char)name[i])) return 0;
        if (i + 1 < len && isalpha((unsigned char)name[i + 1]) &&
            (e = elem_match(db, name + i, 2)) >= 0) w = 2;
        else if ((e = elem_match(db, name + i, 1)) >= 0) w = 1;
        else return 0;
        i += w;
        {
            char num[32];
            size_t k = 0;
            double amt = 1.0;
            while (i < len && k + 1 < sizeof num &&
                   (isdigit((unsigned char)name[i]) || name[i] == '.')) num[k++] = name[i++];
            num[k] = '\0';
            if (k) amt = strtod(num, NULL);
            if (c->n_el >= 8) return 0;
            c->el[c->n_el] = e;
            c->n[c->n_el] = amt;
            c->n_el++;
        }
    }
    return c->n_el > 0;
}

/* Composition of a named constituent; VA is the empty composition. 0 if unknown. */
static int species_comp(const Db *db, const char *name, Comp *c)
{
    memset(c, 0, sizeof *c);
    if (strcmp(name, "VA") == 0) return 1;
    for (int i = 0; i < db->n_sp; ++i)
        if (strcmp(db->sp[i].name, name) == 0) {
            c->n_el = db->sp[i].n_el;
            memcpy(c->el, db->sp[i].el, sizeof c->el);
            memcpy(c->n, db->sp[i].n, sizeof c->n);
            c->charge = db->sp[i].charge;
            return 1;
        }
    for (int e = 0; e < db->n_el; ++e)
        if (strcmp(db->el_name[e], name) == 0) {
            c->n_el = 1; c->el[0] = e; c->n[0] = 1.0;
            return 1;
        }
    return parse_formula(db, name, c);
}

static double comp_atoms(const Comp *c)
{
    double a = 0.0;
    for (int i = 0; i < c->n_el; ++i) a += c->n[i];
    return a;
}

/* TDB species composition string, e.g. FE1/+2 or SI1O2. */
static void comp_text(const Db *db, const Comp *c, char *out, size_t cap)
{
    char num[40];
    size_t n = 0;
    out[0] = '\0';
    for (int i = 0; i < c->n_el; ++i)
        n += (size_t)snprintf(out + n, cap - n, "%s%s", db->el_name[c->el[i]],
                              tb_num(num, c->n[i]));
    if (c->charge != 0.0)
        snprintf(out + n, cap - n, "/%c%s", c->charge < 0 ? '-' : '+', tb_num(num, fabs(c->charge)));
}

/* ------------------------------------------------------------------ *
 * Polynomial terms. ChemSage numbers its temperature functions 1..8
 * (1, T, T ln T, T^2, T^3, 1/T, P, P^2); the readers evaluate the pressure
 * terms as zero, so a nonzero one has no faithful image in TDB or XTDB.
 * ------------------------------------------------------------------ */
typedef struct {
    double c;
    int kind;        /* 0: c T^e, 1: c T ln T, 2: c ln T */
    double e;
} Term;

#define MAX_TERMS (MAX_COEFFS + 64)

static int basis_term(W *w, int idx, double c, Term *t, const char *who)
{
    t->c = c; t->kind = 0; t->e = 0.0;
    switch (idx) {
    case 1: return 1;
    case 2: t->e = 1.0; return 1;
    case 3: t->kind = 1; return 1;
    case 4: t->e = 2.0; return 1;
    case 5: t->e = 3.0; return 1;
    case 6: t->e = -1.0; return 1;
    default:
        wfail(w, "%s carries a ChemSage pressure term (index %d); Hephaestus evaluates it as "
                 "zero and only .dat keeps it verbatim", who, idx);
        return 0;
    }
}

static int interval_terms(W *w, const Interval *iv, Term *t, const char *who)
{
    const Db *db = w->db;
    int n = 0;
    for (int i = 0; i < db->n_gibbs; ++i) {
        if (iv->coeff[i] == 0.0) continue;
        if (basis_term(w, db->gibbs_idx[i], iv->coeff[i], &t[n], who)) n++;
    }
    for (int i = 0; i < iv->n_add && n < MAX_TERMS; ++i) {
        if (iv->add_c[i] == 0.0) continue;
        t[n].c = iv->add_c[i];
        if (iv->add_e[i] == 99.0) { t[n].kind = 2; t[n].e = 0.0; }
        else { t[n].kind = 0; t[n].e = iv->add_e[i]; }
        n++;
    }
    return n;
}

static int excess_terms(W *w, const double *coeff, Term *t, const char *who)
{
    const Db *db = w->db;
    int n = 0;
    for (int i = 0; i < db->n_excess; ++i) {
        if (coeff[i] == 0.0) continue;
        if (basis_term(w, db->excess_idx[i], coeff[i], &t[n], who)) n++;
    }
    return n;
}

/* One signed term in TDB/XTDB expression syntax (the two agree on it). */
static void term_text(const Term *t, char *out, size_t cap)
{
    char num[40], ex[40];
    char sign = t->c < 0 ? '-' : '+';
    tb_num(num, fabs(t->c));
    if (t->kind == 1) { snprintf(out, cap, "%c%s*T*LN(T)", sign, num); return; }
    if (t->kind == 2) { snprintf(out, cap, "%c%s*LN(T)", sign, num); return; }
    if (t->e == 0.0) snprintf(out, cap, "%c%s", sign, num);
    else if (t->e == 1.0) snprintf(out, cap, "%c%s*T", sign, num);
    else if (t->e > 0.0 && t->e == floor(t->e) && t->e < 100.0)
        snprintf(out, cap, "%c%s*T**%d", sign, num, (int)t->e);
    else snprintf(out, cap, "%c%s*T**(%s)", sign, num, tb_num(ex, t->e));
}

static int has_ln_term(const Term *t, int n)
{
    for (int i = 0; i < n; ++i) if (t[i].kind == 2) return 1;
    return 0;
}

/* Terms of a TDB expression, wrapped onto indented lines. */
static void tdb_terms(W *w, const Term *t, int n, int *col)
{
    char s[96];
    if (n == 0) { OUT("0"); *col += 1; return; }
    for (int i = 0; i < n; ++i) {
        size_t len;
        term_text(&t[i], s, sizeof s);
        len = strlen(s);
        if (*col + (int)len > 76 && *col > 4) { OUT("\n    "); *col = 4; }
        OUT("%s", s);
        *col += (int)len;
    }
}

/* ------------------------------------------------------------------ *
 * TDB / uTDB
 * ------------------------------------------------------------------ */

/* Lower limit and upper limit text of an interval set as the source wrote them. */
static double lo_of(W *w, double t_lo)
{
    if (isnan(t_lo)) { w->used_unknown_lo = 1; return UNKNOWN_LO; }
    return t_lo;
}

/* The piecewise tail of a G-type statement: " lo expr; t1 Y expr; ... tn N !".
 * A ChemSage endmember is zero above its last t_max, while the TDB reader extends
 * the last interval; an explicit zero interval keeps the source's value there. */
static void tdb_piecewise(W *w, const Endmember *em, const char *who)
{
    char num[40];
    Term t[MAX_TERMS];
    int col;
    OUT("  %s", tb_num(num, lo_of(w, em->t_lo)));
    for (int k = 0; k < em->n_intervals; ++k) {
        const Interval *iv = &em->intervals[k];
        int last = (k == em->n_intervals - 1);
        int n = interval_terms(w, iv, t, who);
        if (w->bad) return;
        if (has_ln_term(t, n)) {
            wfail(w, "%s has a ln(T) term (ChemSage exponent 99), which the TDB reader does "
                     "not accept; .dat or .xtdb can hold it", who);
            return;
        }
        OUT("\n    ");
        col = 4;
        tdb_terms(w, t, n, &col);
        if (!last) { OUT(";  %s Y", tb_num(num, iv->t_max)); continue; }
        if (iv->t_max >= OPEN_T) {
            double top = (!isnan(em->t_top) && em->t_top < OPEN_T) ? em->t_top : iv->t_max;
            OUT(";  %s N !\n", tb_num(num, top));
        } else {
            char top[40];
            OUT(";  %s Y\n    0;  %s N !\n", tb_num(num, iv->t_max), tb_num(top, OPEN_T));
            w->used_zero_tail = 1;
        }
    }
}

/* Single-interval statement for an excess-basis coefficient set. */
static void tdb_single(W *w, const double *coeff, double t_lo, double t_hi, const char *who)
{
    char a[40], b[40];
    Term t[MAX_TERMS];
    int col = 4;
    int n = excess_terms(w, coeff, t, who);
    if (w->bad) return;
    if (isnan(t_lo)) t_lo = isnan(w->db->lim_lo) ? lo_of(w, NAN) : w->db->lim_lo;
    if (isnan(t_hi)) t_hi = isnan(w->db->lim_hi) ? OPEN_T : w->db->lim_hi;
    OUT("  %s\n    ", tb_num(a, t_lo));
    tdb_terms(w, t, n, &col);
    OUT(";  %s N !\n", tb_num(b, t_hi));
}

static void const_limits(W *w, double *lo, double *hi)
{
    *lo = isnan(w->db->lim_lo) ? lo_of(w, NAN) : w->db->lim_lo;
    *hi = isnan(w->db->lim_hi) ? OPEN_T : w->db->lim_hi;
}

/* SPECIES statements, collected once per name. */
typedef struct {
    int n;
    char name[512][NAME_MAX];
    Comp comp[512];
} SpList;

static void sp_add(W *w, SpList *L, const char *name, const Comp *c)
{
    for (int i = 0; i < L->n; ++i)
        if (strcmp(L->name[i], name) == 0) {
            if (memcmp(&L->comp[i], c, sizeof *c) != 0)
                wfail(w, "species %s would need two different compositions", name);
            return;
        }
    if (L->n >= 512) { wfail(w, "more than 512 species"); return; }
    snprintf(L->name[L->n], NAME_MAX, "%s", name);
    L->comp[L->n] = *c;
    L->n++;
}

/* Species name for an MQMQA constituent. uTDB takes the charge from the SPECIES
 * statement, and a species cannot share its element's name, so a bare element name
 * (a ChemSage anion "O") gains its charge suffix, the convention the shipped uTDB
 * files use (O-2, CL-1). */
static void q_species(W *w, SpList *L, const char *con, double charge, int anion,
                      char out[NAME_MAX], const char *phase)
{
    Comp c;
    double q = anion ? -fabs(charge) : fabs(charge), q_name;
    size_t base = split_charge(con, &q_name);
    char num[40];
    if (!species_comp(w->db, con, &c) || c.n_el == 0) {
        wfail(w, "cannot resolve the composition of %s in %s", con, phase);
        return;
    }
    if (base < strlen(con)) {
        if (q_name != q) {
            wfail(w, "constituent %s of %s is named with charge %g but carries %g",
                  con, phase, q_name, q);
            return;
        }
        snprintf(out, NAME_MAX, "%s", con);
    } else {
        snprintf(out, NAME_MAX, "%s%c%s", con, anion ? '-' : '+', tb_num(num, fabs(q)));
        w->renamed_ion = 1;
    }
    c.charge = q;
    sp_add(w, L, out, &c);
}

typedef struct {
    int n;
    double afm[16], p[16];
    char ch[16];
    char phase[16][NAME_MAX];
} MagDefs;

static char mag_char(W *w, MagDefs *M, const SublPhase *cf, const char *phase)
{
    static const char chars[] = "&'ABCDEFGHIJKLM";
    for (int i = 0; i < M->n; ++i)
        if (M->afm[i] == cf->mag_afm && M->p[i] == cf->mag_p) return M->ch[i];
    if (M->n >= 15) {    /* the TDB reader keeps 15 magnetic type definitions */
        wfail(w, "more than 15 distinct magnetic type definitions");
        return '&';
    }
    M->afm[M->n] = cf->mag_afm;
    M->p[M->n] = cf->mag_p;
    M->ch[M->n] = chars[M->n];
    snprintf(M->phase[M->n], NAME_MAX, "%s", phase);
    return M->ch[M->n++];
}

/* Constituent array text of a CEF parameter; mixing on `subl` when >= 0. */
static void cef_array(const SublPhase *cf, const int *pick, int subl, int i, int j,
                      char *out, size_t cap)
{
    size_t n = 0;
    out[0] = '\0';
    for (int s = 0; s < cf->n_subl; ++s) {
        if (s) n += (size_t)snprintf(out + n, cap - n, ":");
        if (s == subl)
            n += (size_t)snprintf(out + n, cap - n, "%s,%s", cf->con_name[cf->subl_off[s] + i],
                                  cf->con_name[cf->subl_off[s] + j]);
        else
            n += (size_t)snprintf(out + n, cap - n, "%s", cf->con_name[cf->subl_off[s] + pick[s]]);
    }
}

static int any_nonzero(const double *v, int n)
{
    for (int i = 0; i < n; ++i) if (v[i] != 0.0) return 1;
    return 0;
}

static void tdb_cef_phase(W *w, const Phase *ph, char magc)
{
    const SublPhase *cf = ph->cef;
    char num[40], arr[1024], who[256];
    int pick[64];
    OUT("\n PHASE %s %%%s  %d ", ph->name, magc ? (char[]){magc, 0} : "", cf->n_subl);
    for (int s = 0; s < cf->n_subl; ++s) OUT(" %s", tb_num(num, cf->site_ratio[s]));
    OUT(" !\n CONSTITUENT %s :", ph->name);
    for (int s = 0; s < cf->n_subl; ++s) {
        OUT(" ");
        for (int i = 0; i < cf->subl_ncon[s]; ++i)
            OUT("%s%s", i ? "," : "", cf->con_name[cf->subl_off[s] + i]);
        OUT(" :");
    }
    OUT(" !\n");
    for (int e = 0; e < cf->n_em; ++e) {
        const Endmember *em = &cf->em[e];
        for (int s = 0; s < cf->n_subl; ++s) pick[s] = cf->em_con[e * cf->n_subl + s];
        cef_array(cf, pick, -1, 0, 0, arr, sizeof arr);
        snprintf(who, sizeof who, "G(%s,%s)", ph->name, arr);
        if (em->name[0] && strcmp(em->name, ph->name) != 0 && tdb_token_ok(em->name))
            OUT(" $ %s\n", em->name);
        OUT(" PARAMETER G(%s,%s;0)", ph->name, arr);
        tdb_piecewise(w, em, who);
    }
    for (int pass = 0; pass < 3; ++pass) {
        const char *kw = pass == 0 ? "G" : pass == 1 ? "TC" : "BMAGN";
        int nk = pass == 0 ? cf->n_ex : pass == 1 ? cf->n_tcx : cf->n_bmx;
        const CefExcess *xs = pass == 0 ? cf->ex : pass == 1 ? cf->tc_ex : cf->bm_ex;
        if (pass && !cf->magnetic) break;
        if (pass) {   /* endmember TC / BMAGN rows */
            const double *rows = pass == 1 ? cf->tc_em : cf->bm_em;
            for (int e = 0; e < cf->n_em; ++e) {
                double row[MAX_COEFFS] = {0};   /* rows are 6 wide; the basis may list more */
                memcpy(row, rows + e * 6, 6 * sizeof(double));
                if (!any_nonzero(row, 6)) continue;
                for (int s = 0; s < cf->n_subl; ++s) pick[s] = cf->em_con[e * cf->n_subl + s];
                cef_array(cf, pick, -1, 0, 0, arr, sizeof arr);
                snprintf(who, sizeof who, "%s(%s,%s)", kw, ph->name, arr);
                OUT(" PARAMETER %s(%s,%s;0)", kw, ph->name, arr);
                tdb_single(w, row, NAN, NAN, who);
            }
        }
        for (int k = 0; k < nk; ++k) {
            const CefExcess *x = &xs[k];
            for (int s = 0; s < cf->n_subl; ++s) pick[s] = (s == x->subl) ? 0 : x->other[s];
            cef_array(cf, pick, x->subl, x->i, x->j, arr, sizeof arr);
            snprintf(who, sizeof who, "%s(%s,%s;%d)", kw, ph->name, arr, x->order);
            OUT(" PARAMETER %s(%s,%s;%d)", kw, ph->name, arr, x->order);
            tdb_single(w, x->coeff, x->t_lo, x->t_hi, who);
        }
    }
}

static void tdb_q_phase(W *w, const Phase *ph, char (*qc)[NAME_MAX], char (*qa)[NAME_MAX])
{
    char num[40], a[40], b[40], who[256];
    double lo, hi;
    const_limits(w, &lo, &hi);
    OUT("\n PHASE %s:Q %%  2  1  1 !\n CONSTITUENT %s:Q : ", ph->name, ph->name);
    for (int i = 0; i < ph->n_cat; ++i) OUT("%s%s", i ? "," : "", qc[i]);
    OUT(" : ");
    for (int k = 0; k < ph->n_an; ++k) OUT("%s%s", k ? "," : "", qa[k]);
    OUT(" : !\n");
    for (int k = 0; k < ph->n_pairs; ++k) {
        const Endmember *em = &ph->pairs[k];
        const char *c = qc[em->cat_idx], *an = qa[em->an_idx];
        snprintf(who, sizeof who, "MQG(%s,%s:%s)", ph->name, c, an);
        if (em->name[0] && tdb_token_ok(em->name)) OUT(" $ pair %s\n", em->name);
        OUT(" PARAMETER MQG(%s,%s:%s;0)", ph->name, c, an);
        tdb_piecewise(w, em, who);
        OUT(" PARAMETER MQZETA(%s,%s:%s)  %s  %s;  %s N !\n", ph->name, c, an,
            tb_num(a, lo), tb_num(num, em->zeta), tb_num(b, hi));
        OUT(" PARAMETER MQSTOI(%s,%s:%s)  %s ", ph->name, c, an, tb_num(a, lo));
        for (int v = 0; v < 5; ++v) OUT(" %s", tb_num(num, em->stoich_quad[v]));
        OUT(";  %s N !\n", tb_num(b, hi));
    }
    for (int q = 0; q < ph->n_quads; ++q) {
        const Mqmz *z = &ph->mqmz[q];
        OUT(" PARAMETER MQZ(%s,%s,%s:%s,%s)  %s ", ph->name, qc[z->A], qc[z->B],
            qa[z->X], qa[z->Y], tb_num(a, lo));
        for (int v = 0; v < 4; ++v) OUT(" %s", tb_num(num, z->Z[v]));
        OUT(";  %s N !\n", tb_num(b, hi));
    }
    for (int k = 0; k < ph->n_mqmx; ++k) {
        const Mqmx *x = &ph->mqmx[k];
        snprintf(who, sizeof who, "MQX(%s,%s,%s:%s,%s)", ph->name, qc[x->A], qc[x->B],
                 qa[x->X], qa[x->Y]);
        if (!strchr("QGBR", x->code) || !x->code) {
            wfail(w, "%s has excess code %c, which uTDB does not define", who, x->code);
            return;
        }
        if (any_nonzero(x->meta, 12)) {
            wfail(w, "%s carries nonzero ChemSage MQMX metadata, which has no uTDB slot; "
                     ".dat keeps it", who);
            return;
        }
        if (x->exp[3] != 0) {
            wfail(w, "%s has a fourth (anion ternary) exponent, which has no uTDB slot; "
                     ".dat holds it", who);
            return;
        }
        if (x->exp[2] != 0 || x->add_cat >= 0) {
            OUT(" PARAMETER MQXT%c(%s,%s,%s:%s,%s;%d,%d,%d", x->code, ph->name, qc[x->A],
                qc[x->B], qa[x->X], qa[x->Y], x->exp[0], x->exp[1], x->exp[2]);
            if (x->add_cat >= 0) OUT(":%s", qc[x->add_cat]);
            OUT(")");
        } else {
            OUT(" PARAMETER MQX%c(%s,%s,%s:%s,%s;%d,%d)", x->code, ph->name, qc[x->A],
                qc[x->B], qa[x->X], qa[x->Y], x->exp[0], x->exp[1]);
        }
        tdb_single(w, x->coeff, x->t_lo, x->t_hi, who);
    }
    for (int i = 0; i < ph->n_cat; ++i)
        OUT(" PARAMETER MQGRP(%s,%s)  %s  %d;  %s N !\n", ph->name, qc[i], tb_num(a, lo),
            ph->cat_group[i], tb_num(b, hi));
    for (int k = 0; k < ph->n_an; ++k)
        OUT(" PARAMETER MQGRP(%s,%s)  %s  %d;  %s N !\n", ph->name, qa[k], tb_num(a, lo),
            ph->an_group[k], tb_num(b, hi));
}

static void tdb_stoich(W *w, const Endmember *em)
{
    const Db *db = w->db;
    char num[40], who[256];
    int k = 0;
    for (int e = 0; e < db->n_el; ++e) if (em->stoich_el[e] != 0.0) k++;
    if (k == 0) { wfail(w, "stoichiometric phase %s has no atoms", em->name); return; }
    OUT("\n PHASE %s %%  %d ", em->name, k);
    for (int e = 0; e < db->n_el; ++e)
        if (em->stoich_el[e] != 0.0) OUT(" %s", tb_num(num, em->stoich_el[e]));
    OUT(" !\n CONSTITUENT %s :", em->name);
    for (int e = 0; e < db->n_el; ++e) if (em->stoich_el[e] != 0.0) OUT(" %s :", db->el_name[e]);
    OUT(" !\n PARAMETER G(%s,", em->name);
    k = 0;
    for (int e = 0; e < db->n_el; ++e)
        if (em->stoich_el[e] != 0.0) OUT("%s%s", k++ ? ":" : "", db->el_name[e]);
    OUT(";0)");
    snprintf(who, sizeof who, "G(%s)", em->name);
    tdb_piecewise(w, em, who);
}

static int check_lossy(W *w, const char *fmt_name)
{
    if (w->db->lossy[0]) {
        wfail(w, "cannot write %s: the source carries %s, which the reader skipped without "
                 "modeling, so a converted file would silently drop it", fmt_name, w->db->lossy);
        return 0;
    }
    return 1;
}

/* The source's own header lines, each cleaned, one per output line (sep "\n") or
 * joined on one line (sep " / "). */
static void source_header(TextBuf *h, const char *text, const char *prefix, const char *sep)
{
    char line[1024], clean[1024];
    int first = 1;
    while (text && *text) {
        size_t n = strcspn(text, "\n");
        if (n >= sizeof line) n = sizeof line - 1;
        memcpy(line, text, n);
        line[n] = '\0';
        tb_clean(clean, sizeof clean, line);
        tb_putf(h, "%s%s%s", first ? "" : sep, prefix, clean);
        first = 0;
        text += strcspn(text, "\n");
        if (*text == '\n') text++;
    }
}

static void header(W *w, const char *prefix, const char *fmt_name, const char *source)
{
    char src[200];
    TextBuf *h = &w->head;
    tb_clean(src, sizeof src, source);
    tb_putf(h, "%sConverted to %s by Hephaestus %s from %s.\n", prefix, fmt_name,
            HEPHAESTUS_VERSION, src);
    tb_putf(h, "%s%s\n", prefix, LICENSE_LINE);
    if (w->db->title[0]) {
        char sub[16];
        snprintf(sub, sizeof sub, "%s  ", prefix);
        tb_putf(h, "%sSource header:\n", prefix);
        source_header(h, w->db->title, sub, "\n");
        tb_putf(h, "\n");
    }
}

/* Join head and body, or report why not. */
static char *finish(W *w)
{
    char *out = NULL;
    if (!w->bad && (w->head.oom || w->body.oom)) wfail(w, "out of memory");
    if (!w->bad) {
        out = malloc(w->head.n + w->body.n + 1);
        if (!out) wfail(w, "out of memory");
        else {
            memcpy(out, w->head.s ? w->head.s : "", w->head.n);
            memcpy(out + w->head.n, w->body.s ? w->body.s : "", w->body.n);
            out[w->head.n + w->body.n] = '\0';
        }
    }
    free(w->head.s);
    free(w->body.s);
    return out;
}

static char *write_tdb(const Db *db, const char *source, int unified)
{
    W w0, *w = &w0;
    SpList *sp = calloc(1, sizeof *sp);
    MagDefs mag;
    char (*qc)[NAME_MAX] = NULL, (*qa)[NAME_MAX] = NULL;
    char *magc = calloc((size_t)(db->n_phases > 0 ? db->n_phases : 1), 1);
    const char *fmt_name = unified ? "uTDB" : "TDB";
    char num[40], a[40], b[40], ctext[256];
    memset(w, 0, sizeof *w);
    memset(&mag, 0, sizeof mag);
    w->db = db;
    if (!sp || !magc) { free(sp); free(magc); mqmqa_db_set_error("out of memory"); return NULL; }
    if (!check_lossy(w, fmt_name)) goto done;

    /* model and name checks before any text is produced */
    for (int e = 0; e < db->n_el; ++e) {
        const char *n = db->el_name[e];
        if (strlen(n) < 1 || strlen(n) > 2 || !isalpha((unsigned char)n[0]) ||
            (n[1] && !isalpha((unsigned char)n[1])))
            wfail(w, "element %s is not a one- or two-letter TDB element name", n);
    }
    for (int p = 0; p < db->n_phases && !w->bad; ++p) {
        const Phase *ph = &db->phases[p];
        if (!tdb_token_ok(ph->name)) {
            wfail(w, "phase name %s is not a valid TDB name", ph->name);
            break;
        }
        if (ph->kind == 0) {
            if (!unified)
                wfail(w, "phase %s is an MQMQA (quadruplet) liquid, which plain TDB cannot "
                         "hold; .utdb or .dat can", ph->name);
            else if (ph->soln_type != 1)
                wfail(w, "phase %s is an MQMQA SUBG liquid; the uTDB :Q phase is SUBQ, so "
                         "only .dat holds it", ph->name);
            continue;
        }
        for (int i = 0; i < ph->cef->n_con && !w->bad; ++i) {
            const char *cn = ph->cef->con_name[i];
            Comp c;
            if (!tdb_token_ok(cn)) { wfail(w, "constituent %s of %s is not a valid TDB name", cn, ph->name); break; }
            if (strcmp(cn, "VA") == 0 || is_element_name(db, cn)) continue;
            if (!species_comp(db, cn, &c)) {
                wfail(w, "cannot resolve the composition of constituent %s of %s", cn, ph->name);
                break;
            }
            if (fabs(comp_atoms(&c) - ph->cef->con_atoms[i]) > 1e-12) {
                wfail(w, "constituent %s of %s counts %g atoms in the source but %g as a TDB "
                         "species", cn, ph->name, ph->cef->con_atoms[i], comp_atoms(&c));
                break;
            }
            sp_add(w, sp, cn, &c);
        }
        if (ph->cef->magnetic) magc[p] = mag_char(w, &mag, ph->cef, ph->name);
    }
    for (int i = 0; i < db->n_stoich && !w->bad; ++i)
        if (!tdb_token_ok(db->stoich[i].name))
            wfail(w, "phase name %s is not a valid TDB name", db->stoich[i].name);
    if (w->bad) goto done;

    for (int p = 0; p < db->n_phases && !w->bad; ++p) {
        const Phase *ph = &db->phases[p];
        if (ph->kind != 0) {
            tdb_cef_phase(w, ph, magc[p]);
            continue;
        }
        qc = calloc((size_t)ph->n_cat, NAME_MAX);
        qa = calloc((size_t)ph->n_an, NAME_MAX);
        if (!qc || !qa) { wfail(w, "out of memory"); break; }
        for (int i = 0; i < ph->n_cat; ++i)
            q_species(w, sp, ph->cat_name[i], ph->cat_charge[i], 0, qc[i], ph->name);
        for (int k = 0; k < ph->n_an; ++k)
            q_species(w, sp, ph->an_name[k], ph->an_charge[k], 1, qa[k], ph->name);
        if (!w->bad) tdb_q_phase(w, ph, qc, qa);
        free(qc); free(qa);
        qc = qa = NULL;
    }
    for (int i = 0; i < db->n_stoich && !w->bad; ++i) tdb_stoich(w, &db->stoich[i]);
    if (w->bad) goto done;

    /* declarations go ahead of the phases that use them */
    header(w, "$ ", fmt_name, source);
    if (unified)
        tb_putf(&w->head, "$ MQMQA liquids use the uTDB statements of docs/UNIFIED_TDB_SPEC.md.\n");
    tb_putf(&w->head, "$ Functions of the source appear expanded, one polynomial per interval.\n");
    if (w->used_unknown_lo)
        tb_putf(&w->head, "$ A lower limit of %s K marks one the source did not give.\n",
                tb_num(num, UNKNOWN_LO));
    if (w->used_zero_tail)
        tb_putf(&w->head, "$ A final zero interval keeps ChemSage data zero above their last limit.\n");
    if (w->renamed_ion)
        tb_putf(&w->head, "$ Ions named by element alone carry their charge here (O -> O-2).\n");
    tb_putf(&w->head, "$\n ELEMENT /-   ELECTRON_GAS  0  0  0 !\n ELEMENT VA   VACUUM  0  0  0 !\n");
    for (int e = 0; e < db->n_el; ++e) {
        const char *ref = (db->el_ref && db->el_ref[e][0]) ? db->el_ref[e] : "BLANK";
        tb_putf(&w->head, " ELEMENT %-3s  %s  %s  %s  %s !\n", db->el_name[e], ref,
                tb_num(num, db->el_mass[e]), tb_num(a, db->el_h298 ? db->el_h298[e] : 0.0),
                tb_num(b, db->el_s298 ? db->el_s298[e] : 0.0));
    }
    if (sp->n) tb_putf(&w->head, "\n");
    for (int i = 0; i < sp->n; ++i) {
        comp_text(db, &sp->comp[i], ctext, sizeof ctext);
        tb_putf(&w->head, " SPECIES %s  %s !\n", sp->name[i], ctext);
    }
    tb_putf(&w->head, "\n TYPE_DEFINITION %% SEQ * !\n");
    /* the database's own gas constant, stated so a reader need not assume one */
    tb_putf(&w->head, " FUNCTION R  0.01  %s;  1E+12 N !\n", tb_num(num, db->R.own));
    for (int i = 0; i < mag.n; ++i)
        tb_putf(&w->head, " TYPE_DEFINITION %c GES A_P_D %s MAGNETIC  %s  %s !\n", mag.ch[i],
                mag.phase[i], tb_num(a, mag.afm[i]), tb_num(b, mag.p[i]));
done:
    free(sp);
    free(magc);
    free(qc);
    free(qa);
    return finish(w);
}

/* A mode that forces the gas constant re-reads R# references with the forced value; a
 * written file records the database as assessed, so the writers use the file's own
 * reading. */
typedef char *(*db_writer)(const Db *db, const char *source_name, int arg);

static char *write_own(const mqmqa_db *h, const char *source_name, int arg, db_writer fn)
{
    if (!h) { mqmqa_db_set_error("null database"); return NULL; }
    Db *own = mqmqa_db_own_reading((const Db *)h);
    char *text = fn(own ? own : (const Db *)h, source_name, arg);
    if (own) mqmqa_db_free(own);
    return text;
}

char *mqmqa_db_write_tdb(const mqmqa_db *db, const char *source_name)
{
    return write_own(db, source_name, 0, write_tdb);
}

char *mqmqa_db_write_utdb(const mqmqa_db *db, const char *source_name)
{
    return write_own(db, source_name, 1, write_tdb);
}

/* ------------------------------------------------------------------ *
 * ChemSage .dat, in the grammar parse_db in cs_dat.c reads (and pycalphad's
 * cs_dat reader, which additionally wants every SUBL endmember listed).
 * ------------------------------------------------------------------ */

static int dat_token_ok(const char *s)
{
    if (!*s) return 0;
    for (; *s; ++s) if (*s <= ' ' || *s > '~') return 0;
    return 1;
}

/* Element amounts of a CEF endmember from its constituents, for a TDB source whose
 * endmembers carry no element row. */
static int cef_em_stoich(W *w, const SublPhase *cf, const int *pick, double *out,
                         const char *phase)
{
    const Db *db = w->db;
    for (int e = 0; e < db->n_el; ++e) out[e] = 0.0;
    for (int s = 0; s < cf->n_subl; ++s) {
        const char *cn = cf->con_name[cf->subl_off[s] + pick[s]];
        Comp c;
        if (!species_comp(db, cn, &c)) {
            wfail(w, "cannot resolve the composition of constituent %s of %s", cn, phase);
            return 0;
        }
        for (int i = 0; i < c.n_el; ++i) out[c.el[i]] += cf->site_ratio[s] * c.n[i];
    }
    return 1;
}

static void dat_endmember(W *w, const Endmember *em, const char *name, const double *stoich_el)
{
    const Db *db = w->db;
    char num[40];
    int has_add = 0;
    if (!dat_token_ok(name) || strlen(name) >= NAME_MAX) {
        wfail(w, "species name \"%s\" cannot be a ChemSage token", name);
        return;
    }
    for (int k = 0; k < em->n_intervals; ++k) if (em->intervals[k].n_add) has_add = 1;
    OUT(" %s\n   %d   %d", name, has_add ? 4 : 1, em->n_intervals);
    for (int e = 0; e < db->n_el; ++e) OUT("   %s", tb_num(num, stoich_el[e]));
    OUT("\n");
    for (int k = 0; k < em->n_intervals; ++k) {
        const Interval *iv = &em->intervals[k];
        OUT("   %s", tb_num(num, iv->t_max));
        for (int i = 0; i < db->n_gibbs; ++i) OUT("   %s", tb_num(num, iv->coeff[i]));
        OUT("\n");
        if (has_add) {
            OUT("   %d", iv->n_add);
            for (int i = 0; i < iv->n_add; ++i) {
                OUT("   %s", tb_num(num, iv->add_c[i]));
                OUT("   %s", tb_num(num, iv->add_e[i]));
            }
            OUT("\n");
        }
    }
}

/* Returns the number of endmembers written (the header's species count). */
static int dat_cef_phase(W *w, const Phase *ph)
{
    const Db *db = w->db;
    const SublPhase *cf = ph->cef;
    char num[40], nm[NAME_MAX * 4];
    double num_atoms = 1.0, *stoich = NULL;
    int total = 1, *pick = NULL, *listed = NULL, n_list = 0;
    Endmember zero;
    Interval zero_iv;
    const char *colon = strchr(ph->name, ':');

    if (cf->magnetic) {
        wfail(w, "phase %s uses the Inden magnetic model (TC, BMAGN), which the ChemSage "
                 "reader here does not evaluate; .tdb or .utdb holds it", ph->name);
        return 0;
    }
    for (int i = 0; i < cf->n_con; ++i) {
        int va = strcmp(cf->con_name[i], "VA") == 0;
        if (!dat_token_ok(cf->con_name[i])) {
            wfail(w, "constituent \"%s\" of %s cannot be a ChemSage token", cf->con_name[i], ph->name);
            return 0;
        }
        if (cf->con_atoms[i] != (va ? 0.0 : 1.0)) {
            wfail(w, "constituent %s of %s counts %g atoms; a ChemSage SUBL constituent counts "
                     "one, so only .tdb or .utdb keeps it", cf->con_name[i], ph->name,
                  cf->con_atoms[i]);
            return 0;
        }
    }
    /* the name suffix :N scales the site fractions back to site ratios on reading */
    if (colon && colon[1]) num_atoms = strtod(colon + 1, NULL);
    if (!(num_atoms > 0.0)) num_atoms = 1.0;
    for (int s = 0; s < cf->n_subl; ++s) total *= cf->subl_ncon[s];
    pick = calloc((size_t)cf->n_subl, sizeof(int));
    listed = calloc((size_t)total * (size_t)cf->n_subl, sizeof(int));
    stoich = calloc((size_t)(db->n_el > 0 ? db->n_el : 1), sizeof(double));
    if (!pick || !listed || !stoich) { wfail(w, "out of memory"); goto done; }

    OUT(" %s\n SUBL\n", ph->name);
    /* the phase's own endmembers first, in order; then any constituent combination it
     * leaves out, as a zero Gibbs energy, which is what an absent endmember contributes */
    for (int e = 0; e < cf->n_em && !w->bad; ++e) {
        const Endmember *em = &cf->em[e];
        for (int s = 0; s < cf->n_subl; ++s) pick[s] = cf->em_con[e * cf->n_subl + s];
        memcpy(listed + n_list++ * cf->n_subl, pick, (size_t)cf->n_subl * sizeof(int));
        if (em->name[0] && strcmp(em->name, ph->name) != 0) snprintf(nm, sizeof nm, "%s", em->name);
        else {
            size_t n = 0;
            for (int s = 0; s < cf->n_subl; ++s)
                n += (size_t)snprintf(nm + n, sizeof nm - n, "%s%s", s ? ":" : "",
                                      cf->con_name[cf->subl_off[s] + pick[s]]);
        }
        if (em->stoich_el) memcpy(stoich, em->stoich_el, (size_t)db->n_el * sizeof(double));
        else if (!cef_em_stoich(w, cf, pick, stoich, ph->name)) break;
        dat_endmember(w, em, nm, stoich);
    }
    memset(&zero, 0, sizeof zero);
    memset(&zero_iv, 0, sizeof zero_iv);
    zero_iv.t_max = OPEN_T;
    zero.n_intervals = 1;
    zero.intervals = &zero_iv;
    for (int c = 0; c < total && !w->bad; ++c) {
        int rem = c, seen = 0;
        for (int s = cf->n_subl - 1; s >= 0; --s) { pick[s] = rem % cf->subl_ncon[s]; rem /= cf->subl_ncon[s]; }
        for (int k = 0; k < n_list && !seen; ++k)
            seen = memcmp(listed + k * cf->n_subl, pick, (size_t)cf->n_subl * sizeof(int)) == 0;
        if (seen) continue;
        memcpy(listed + n_list++ * cf->n_subl, pick, (size_t)cf->n_subl * sizeof(int));
        {
            size_t n = 0;
            for (int s = 0; s < cf->n_subl; ++s)
                n += (size_t)snprintf(nm + n, sizeof nm - n, "%s%s", s ? ":" : "",
                                      cf->con_name[cf->subl_off[s] + pick[s]]);
        }
        if (!cef_em_stoich(w, cf, pick, stoich, ph->name)) break;
        dat_endmember(w, &zero, nm, stoich);
    }
    if (w->bad) goto done;

    OUT("   %d\n", cf->n_subl);
    for (int s = 0; s < cf->n_subl; ++s) OUT("   %s", tb_num(num, cf->site_ratio[s] / num_atoms));
    OUT("\n");
    for (int s = 0; s < cf->n_subl; ++s) OUT("   %d", cf->subl_ncon[s]);
    OUT("\n");
    for (int s = 0; s < cf->n_subl; ++s) {
        for (int i = 0; i < cf->subl_ncon[s]; ++i) OUT("   %s", cf->con_name[cf->subl_off[s] + i]);
        OUT("\n");
    }
    for (int s = 0; s < cf->n_subl; ++s) {
        for (int k = 0; k < n_list; ++k) OUT("   %d", listed[k * cf->n_subl + s] + 1);
        OUT("\n");
    }
    /* Redlich-Kister terms grouped by interaction; ChemSage lists orders 0..n-1, so a
     * gap in the source's orders is written as a zero row */
    for (int k = 0; k < cf->n_ex; ++k) {
        const CefExcess *x = &cf->ex[k];
        int first = 1, max_order = 0;
        for (int j = 0; j < k && first; ++j) {
            const CefExcess *y = &cf->ex[j];
            int same = y->subl == x->subl && y->i == x->i && y->j == x->j;
            for (int s = 0; s < cf->n_subl && same; ++s)
                if (s != x->subl && y->other[s] != x->other[s]) same = 0;
            if (same) first = 0;
        }
        if (!first) continue;
        for (int j = k; j < cf->n_ex; ++j) {
            const CefExcess *y = &cf->ex[j];
            int same = y->subl == x->subl && y->i == x->i && y->j == x->j;
            for (int s = 0; s < cf->n_subl && same; ++s)
                if (s != x->subl && y->other[s] != x->other[s]) same = 0;
            if (same && y->order > max_order) max_order = y->order;
        }
        OUT("   %d", cf->n_subl + 1);
        for (int s = 0; s < cf->n_subl; ++s) {
            if (s == x->subl) OUT("   %d   %d", cf->subl_off[s] + x->i + 1, cf->subl_off[s] + x->j + 1);
            else OUT("   %d", cf->subl_off[s] + x->other[s] + 1);
        }
        OUT("\n   %d\n", max_order + 1);
        for (int o = 0; o <= max_order; ++o) {
            double row[MAX_COEFFS] = {0};
            for (int j = k; j < cf->n_ex; ++j) {
                const CefExcess *y = &cf->ex[j];
                int same = y->subl == x->subl && y->i == x->i && y->j == x->j && y->order == o;
                for (int s = 0; s < cf->n_subl && same; ++s)
                    if (s != x->subl && y->other[s] != x->other[s]) same = 0;
                if (same)
                    for (int i = 0; i < db->n_excess; ++i) row[i] += y->coeff[i];
            }
            for (int i = 0; i < db->n_excess; ++i) OUT("   %s", tb_num(num, row[i]));
            OUT("\n");
        }
    }
    OUT("   0\n");
done:
    free(pick);
    free(listed);
    free(stoich);
    return n_list;
}

/* Conventional ChemSage pair name from its ions and stoichiometry: SIO2, ALO1.5. */
static void pair_name(const Phase *ph, const Endmember *em, char *out, size_t cap)
{
    char num[40];
    double q;
    const char *c = ph->cat_name[em->cat_idx], *a = ph->an_name[em->an_idx];
    size_t nc = split_charge(c, &q), na = split_charge(a, &q), n = 0;
    n += (size_t)snprintf(out + n, cap - n, "%.*s", (int)nc, c);
    if (em->stoich_quad[0] != 1.0) n += (size_t)snprintf(out + n, cap - n, "%s", tb_num(num, em->stoich_quad[0]));
    n += (size_t)snprintf(out + n, cap - n, "%.*s", (int)na, a);
    if (em->stoich_quad[1] != 1.0) snprintf(out + n, cap - n, "%s", tb_num(num, em->stoich_quad[1]));
}

static void dat_q_phase(W *w, const Phase *ph)
{
    const Db *db = w->db;
    char num[40], nm[NAME_MAX * 2];
    double *stoich = calloc((size_t)(db->n_el > 0 ? db->n_el : 1), sizeof(double));
    if (!stoich) { wfail(w, "out of memory"); return; }
    OUT(" %s\n %s\n", ph->name, ph->soln_type == 1 ? "SUBQ" : "SUBG");
    if (ph->soln_type != 1) OUT("   %s\n", tb_num(num, ph->subg_zeta));
    OUT("   %d   %d\n", ph->n_pairs, ph->n_quads);
    for (int k = 0; k < ph->n_pairs && !w->bad; ++k) {
        const Endmember *em = &ph->pairs[k];
        if (em->name[0]) snprintf(nm, sizeof nm, "%s", em->name);
        else pair_name(ph, em, nm, sizeof nm);
        if (em->stoich_el) memcpy(stoich, em->stoich_el, (size_t)db->n_el * sizeof(double));
        else {  /* a uTDB pair: the ions' compositions times the quadruplet stoichiometry */
            Comp cc, ca;
            if (!species_comp(db, ph->cat_name[em->cat_idx], &cc) ||
                !species_comp(db, ph->an_name[em->an_idx], &ca)) {
                wfail(w, "cannot resolve the composition of pair %s in %s", nm, ph->name);
                break;
            }
            for (int e = 0; e < db->n_el; ++e) stoich[e] = 0.0;
            for (int i = 0; i < cc.n_el; ++i) stoich[cc.el[i]] += em->stoich_quad[0] * cc.n[i];
            for (int i = 0; i < ca.n_el; ++i) stoich[ca.el[i]] += em->stoich_quad[1] * ca.n[i];
        }
        dat_endmember(w, em, nm, stoich);
        for (int v = 0; v < 5; ++v) OUT("   %s", tb_num(num, em->stoich_quad[v]));
        OUT("\n");
        if (ph->soln_type == 1) OUT("   %s\n", tb_num(num, em->zeta));
    }
    free(stoich);
    if (w->bad) return;
    OUT("   %d   %d\n", ph->n_cat, ph->n_an);
    for (int i = 0; i < ph->n_cat; ++i) OUT(" %s", ph->cat_name[i]);
    OUT("\n");
    for (int k = 0; k < ph->n_an; ++k) OUT(" %s", ph->an_name[k]);
    OUT("\n");
    for (int i = 0; i < ph->n_cat; ++i) OUT("   %s", tb_num(num, ph->cat_charge[i]));
    OUT("\n");
    for (int i = 0; i < ph->n_cat; ++i) OUT("   %d", ph->cat_group[i]);
    OUT("\n");
    for (int k = 0; k < ph->n_an; ++k) OUT("   %s", tb_num(num, ph->an_charge[k]));
    OUT("\n");
    for (int k = 0; k < ph->n_an; ++k) OUT("   %d", ph->an_group[k]);
    OUT("\n");
    for (int k = 0; k < ph->n_pairs; ++k) OUT("   %d", ph->pairs[k].cat_idx + 1);
    OUT("\n");
    for (int k = 0; k < ph->n_pairs; ++k) OUT("   %d", ph->pairs[k].an_idx + 1);
    OUT("\n");
    for (int q = 0; q < ph->n_quads; ++q) {
        const Mqmz *z = &ph->mqmz[q];
        OUT("   %d   %d   %d   %d", z->A + 1, z->B + 1, z->X + 1 + ph->n_cat, z->Y + 1 + ph->n_cat);
        for (int v = 0; v < 4; ++v) OUT("   %s", tb_num(num, z->Z[v]));
        OUT("\n");
    }
    for (int k = 0; k < ph->n_mqmx; ++k) {
        const Mqmx *x = &ph->mqmx[k];
        /* a uTDB source has no mixing-type integer; ChemSage files count the distinct
         * species of the term there (3 for a binary, 4 for a reciprocal one) */
        int mt = x->mix_type ? x->mix_type : (x->A != x->B ? 2 : 1) + (x->X != x->Y ? 2 : 1);
        OUT("   %d\n %c   %d   %d   %d   %d", mt, x->code, x->A + 1, x->B + 1,
            x->X + 1 + ph->n_cat, x->Y + 1 + ph->n_cat);
        for (int v = 0; v < 4; ++v) OUT("   %d", x->exp[v]);
        OUT("\n");
        for (int v = 0; v < 12; ++v) OUT("   %s%s", tb_num(num, x->meta[v]), v == 5 ? "\n" : "");
        OUT("\n   %d   0", x->add_cat + 1);
        for (int i = 0; i < db->n_excess; ++i) OUT("   %s", tb_num(num, x->coeff[i]));
        OUT("\n");
    }
    OUT("   0\n");
}

static char *write_dat(const Db *db, const char *source_name, int unused)
{
    (void)unused;
    W w0, *w = &w0;
    char num[40], src[200];
    int *count;
    if (!db) { mqmqa_db_set_error("null database"); return NULL; }
    count = calloc((size_t)(db->n_phases > 0 ? db->n_phases : 1), sizeof(int));
    if (!count) { mqmqa_db_set_error("out of memory"); return NULL; }
    memset(w, 0, sizeof *w);
    w->db = db;
    if (!check_lossy(w, "ChemSage .dat")) { free(count); return finish(w); }
    for (int e = 0; e < db->n_el; ++e)
        if (!dat_token_ok(db->el_name[e])) wfail(w, "element \"%s\" cannot be a ChemSage token", db->el_name[e]);
    for (int p = 0; p < db->n_phases && !w->bad; ++p) {
        const Phase *ph = &db->phases[p];
        if (!dat_token_ok(ph->name)) { wfail(w, "phase \"%s\" cannot be a ChemSage token", ph->name); break; }
        if (ph->kind == 1) count[p] = dat_cef_phase(w, ph);
        else { dat_q_phase(w, ph); count[p] = ph->n_pairs; }
    }
    for (int i = 0; i < db->n_stoich && !w->bad; ++i)
        dat_endmember(w, &db->stoich[i], db->stoich[i].name, db->stoich[i].stoich_el);
    if (w->bad) { free(count); return finish(w); }

    /* the title line is the one place a ChemSage file has for provenance */
    tb_clean(src, sizeof src, source_name);
    tb_putf(&w->head, " Converted to ChemSage .dat by Hephaestus %s from %s. %s", HEPHAESTUS_VERSION,
            src, LICENSE_LINE);
    /* ChemSage has no field for R; the reader takes it from this sentence */
    tb_putf(&w->head, " Gas constant R = %s J/(mol K).", tb_num(num, db->R.own));
    if (db->title[0]) {
        tb_putf(&w->head, " Source header: ");
        source_header(&w->head, db->title, "", " / ");
    }
    tb_putf(&w->head, "\n   %d   %d", db->n_el, db->n_phases);
    for (int p = 0; p < db->n_phases; ++p) tb_putf(&w->head, "   %d", count[p]);
    free(count);
    tb_putf(&w->head, "   %d\n", db->n_stoich);
    for (int e = 0; e < db->n_el; ++e) tb_putf(&w->head, " %s", db->el_name[e]);
    tb_putf(&w->head, "\n");
    for (int e = 0; e < db->n_el; ++e) tb_putf(&w->head, "   %s", tb_num(num, db->el_mass[e]));
    tb_putf(&w->head, "\n   %d", db->n_gibbs);
    for (int i = 0; i < db->n_gibbs; ++i) tb_putf(&w->head, "   %d", db->gibbs_idx[i]);
    tb_putf(&w->head, "\n   %d", db->n_excess);
    for (int i = 0; i < db->n_excess; ++i) tb_putf(&w->head, "   %d", db->excess_idx[i]);
    tb_putf(&w->head, "\n");
    return finish(w);
}
/* ------------------------------------------------------------------ *
 * XTDB. The file is written for the XTDB engine in src/xtdb.c, so the checks
 * follow what that engine evaluates: CEF phases with at most one mixing
 * sublattice of two constituents, monatomic constituents, no magnetic model and
 * no MQMQA. Its tables are fixed-size (256 entries, 511-character expressions,
 * 8 ranges per function), and a file that overflows them is refused rather than
 * read back truncated.
 * ------------------------------------------------------------------ */
#define XTDB_CAP 256
#define XTDB_EXPR 511
#define XTDB_NAME 63

typedef struct {
    W *w;
    TextBuf tp, par;
    int n_tp, n_par;
} XW;

/* One XTDB expression ("...;") from a term list; 0 when it would not fit. */
static int xtdb_expr_text(W *w, const Term *t, int n, char *out, size_t cap, const char *who)
{
    size_t len = 0;
    char s[96];
    out[0] = '\0';
    if (n == 0) { snprintf(out, cap, "0;"); return 1; }
    for (int i = 0; i < n; ++i) {
        term_text(&t[i], s, sizeof s);
        if (len + strlen(s) + 2 > XTDB_EXPR || len + strlen(s) + 2 > cap) {
            wfail(w, "%s needs an expression longer than the %d characters the XTDB engine "
                     "reads; .tdb or .dat holds it", who, XTDB_EXPR);
            return 0;
        }
        len += (size_t)snprintf(out + len, cap - len, "%s", s);
    }
    snprintf(out + len, cap - len, ";");
    return 1;
}

static void xtdb_param(XW *x, const char *id, const char *expr)
{
    if (++x->n_par > XTDB_CAP)
        wfail(x->w, "more than %d parameters, the XTDB engine's table size", XTDB_CAP);
    tb_putf(&x->par, "<Parameter Id=\"%s\" Expr=\"%s\" />\n", id, expr);
}

/* A Gibbs energy as the Expr of parameter `id`: inline for one extrapolating
 * interval, otherwise through a TPfun holding the ranges. */
static void xtdb_gibbs(XW *x, const Endmember *em, const char *id, const char *phase, const char *who)
{
    W *w = x->w;
    Term t[MAX_TERMS];
    char e[XTDB_EXPR + 8], num[40], fid[XTDB_NAME + 1];
    int last_open = em->intervals[em->n_intervals - 1].t_max >= OPEN_T;
    int n_ranges = em->n_intervals + (last_open ? 0 : 1);
    if (em->n_intervals == 1 && last_open) {
        int n = interval_terms(w, &em->intervals[0], t, who);
        if (w->bad || !xtdb_expr_text(w, t, n, e, sizeof e, who)) return;
        xtdb_param(x, id, e);
        return;
    }
    if (n_ranges > 8) {
        wfail(w, "%s has %d temperature ranges; the XTDB engine reads 8 per function; .tdb or "
                 ".dat holds it", who, n_ranges);
        return;
    }
    if (++x->n_tp > XTDB_CAP) {
        wfail(w, "more than %d functions, the XTDB engine's table size", XTDB_CAP);
        return;
    }
    {   /* a function name from the phase, kept to the reader's identifier characters */
        size_t k = 0;
        k += (size_t)snprintf(fid, sizeof fid, "G");
        for (const char *c = phase; *c && k < 40; ++c) fid[k++] = isalnum((unsigned char)*c) ? *c : '_';
        snprintf(fid + k, sizeof fid - k, "_%d", x->n_tp);
    }
    for (int k = 0; k < em->n_intervals; ++k) {
        const Interval *iv = &em->intervals[k];
        int n = interval_terms(w, iv, t, who);
        int last = (k == em->n_intervals - 1);
        if (w->bad || !xtdb_expr_text(w, t, n, e, sizeof e, who)) return;
        if (k == 0) tb_putf(&x->tp, "<TPfun Id=\"%s\" LowT=\"%s\" Expr=\"%s\"", fid,
                            tb_num(num, lo_of(w, em->t_lo)), e);
        else tb_putf(&x->tp, "  <Trange Expr=\"%s\"", e);
        if (!last || !last_open) tb_putf(&x->tp, " HighT=\"%s\"", tb_num(num, iv->t_max));
        else if (!isnan(em->t_top) && em->t_top < OPEN_T)
            tb_putf(&x->tp, " HighT=\"%s\"", tb_num(num, em->t_top));
        tb_putf(&x->tp, k == 0 ? " >\n" : " />\n");
    }
    if (!last_open) {   /* ChemSage data are zero above their last limit */
        tb_putf(&x->tp, "  <Trange Expr=\"0;\" HighT=\"%s\" />\n", tb_num(num, OPEN_T));
        w->used_zero_tail = 1;
    }
    tb_putf(&x->tp, "</TPfun>\n");
    snprintf(e, sizeof e, "+%s;", fid);
    xtdb_param(x, id, e);
}

static void xtdb_cef_phase(XW *x, const Phase *ph)
{
    W *w = x->w;
    const SublPhase *cf = ph->cef;
    char num[40], arr[512], id[640], who[640], e[XTDB_EXPR + 8];
    int pick[8], mixing = 0;
    if (cf->magnetic) {
        wfail(w, "phase %s uses the Inden magnetic model (TC, BMAGN), which the XTDB engine does "
                 "not evaluate; .tdb or .utdb holds it", ph->name);
        return;
    }
    if (cf->n_subl > 8) {
        wfail(w, "phase %s has %d sublattices; the XTDB engine reads 8", ph->name, cf->n_subl);
        return;
    }
    for (int s = 0; s < cf->n_subl; ++s) {
        if (cf->subl_ncon[s] > 1) mixing++;
        if (cf->subl_ncon[s] > 2 || mixing > 1) {
            wfail(w, "phase %s mixes on more than one sublattice or more than two constituents; "
                     "the XTDB engine evaluates one binary mixing sublattice, so .tdb or .dat "
                     "holds it", ph->name);
            return;
        }
    }
    for (int i = 0; i < cf->n_con; ++i) {
        int va = strcmp(cf->con_name[i], "VA") == 0;
        if (cf->con_atoms[i] != (va ? 0.0 : 1.0)) {
            wfail(w, "constituent %s of %s counts %g atoms; the XTDB engine counts one per "
                     "constituent, so .tdb or .utdb keeps it", cf->con_name[i], ph->name,
                  cf->con_atoms[i]);
            return;
        }
    }
    OUT("<Phase Id=\"%s\" Configuration=\"CEF\" >\n  <Sublattices NumberOf=\"%d\" Multiplicities=\"",
        ph->name, cf->n_subl);
    for (int s = 0; s < cf->n_subl; ++s) OUT("%s%s", s ? " " : "", tb_num(num, cf->site_ratio[s]));
    OUT("\" >\n");
    for (int s = 0; s < cf->n_subl; ++s) {
        OUT("    <Constituents Sublattice=\"%d\" List=\"", s + 1);
        for (int i = 0; i < cf->subl_ncon[s]; ++i) OUT("%s%s", i ? " " : "", cf->con_name[cf->subl_off[s] + i]);
        OUT("\" />\n");
    }
    OUT("  </Sublattices>\n</Phase>\n");

    /* every endmember: the engine sums over all of them, and an absent one is zero */
    memset(pick, 0, sizeof pick);
    for (;;) {
        int found = -1;
        for (int e2 = 0; e2 < cf->n_em && found < 0; ++e2) {
            int same = 1;
            for (int s = 0; s < cf->n_subl; ++s)
                if (cf->em_con[e2 * cf->n_subl + s] != pick[s]) same = 0;
            if (same) found = e2;
        }
        cef_array(cf, pick, -1, 0, 0, arr, sizeof arr);
        if (strlen(arr) > XTDB_NAME) {
            wfail(w, "endmember %s of %s is longer than the XTDB engine's %d characters",
                  arr, ph->name, XTDB_NAME);
            return;
        }
        snprintf(id, sizeof id, "G(%s,%s;0)", ph->name, arr);
        snprintf(who, sizeof who, "G(%s,%s)", ph->name, arr);
        if (found >= 0) xtdb_gibbs(x, &cf->em[found], id, ph->name, who);
        else xtdb_param(x, id, "0;");
        if (w->bad) return;
        {
            int s = cf->n_subl - 1;
            while (s >= 0) { if (++pick[s] < cf->subl_ncon[s]) break; pick[s] = 0; s--; }
            if (s < 0) break;
        }
    }
    for (int k = 0; k < cf->n_ex; ++k) {
        const CefExcess *xe = &cf->ex[k];
        Term t[MAX_TERMS];
        int n;
        for (int s = 0; s < cf->n_subl; ++s) pick[s] = (s == xe->subl) ? 0 : xe->other[s];
        cef_array(cf, pick, xe->subl, xe->i, xe->j, arr, sizeof arr);
        snprintf(id, sizeof id, "G(%s,%s;%d)", ph->name, arr, xe->order);
        n = excess_terms(w, xe->coeff, t, id);
        if (w->bad || !xtdb_expr_text(w, t, n, e, sizeof e, id)) return;
        xtdb_param(x, id, e);
    }
}

static void xtdb_stoich(XW *x, const Endmember *em)
{
    W *w = x->w;
    const Db *db = w->db;
    char num[40], arr[512], id[640];
    int k = 0;
    size_t n = 0;
    for (int e = 0; e < db->n_el; ++e) if (em->stoich_el[e] != 0.0) k++;
    if (k == 0 || k > 8) {
        wfail(w, "stoichiometric phase %s has %d elements; the XTDB engine reads 1 to 8",
              em->name, k);
        return;
    }
    OUT("<Phase Id=\"%s\" Configuration=\"CEF\" >\n  <Sublattices NumberOf=\"%d\" Multiplicities=\"",
        em->name, k);
    k = 0;
    for (int e = 0; e < db->n_el; ++e)
        if (em->stoich_el[e] != 0.0) OUT("%s%s", k++ ? " " : "", tb_num(num, em->stoich_el[e]));
    OUT("\" >\n");
    k = 0;
    arr[0] = '\0';
    for (int e = 0; e < db->n_el; ++e) {
        if (em->stoich_el[e] == 0.0) continue;
        OUT("    <Constituents Sublattice=\"%d\" List=\"%s\" />\n", ++k, db->el_name[e]);
        n += (size_t)snprintf(arr + n, sizeof arr - n, "%s%s", k > 1 ? ":" : "", db->el_name[e]);
    }
    OUT("  </Sublattices>\n</Phase>\n");
    snprintf(id, sizeof id, "G(%s,%s;0)", em->name, arr);
    xtdb_gibbs(x, em, id, em->name, id);
}

static char *write_xtdb(const Db *db, const char *source_name, int unused)
{
    (void)unused;
    W w0, *w = &w0;
    XW x;
    char num[40], a[40], src[200], ctext[256];
    if (!db) { mqmqa_db_set_error("null database"); return NULL; }
    memset(w, 0, sizeof *w);
    memset(&x, 0, sizeof x);
    w->db = db;
    x.w = w;
    if (!check_lossy(w, "XTDB")) return finish(w);
    if (db->n_el > XTDB_CAP || db->n_phases + db->n_stoich > XTDB_CAP)
        wfail(w, "more elements or phases than the XTDB engine's %d", XTDB_CAP);
    for (int p = 0; p < db->n_phases && !w->bad; ++p) {
        const Phase *ph = &db->phases[p];
        if (strlen(ph->name) > XTDB_NAME || strpbrk(ph->name, ",;()\"<>&")) {
            wfail(w, "phase name %s cannot be an XTDB phase Id", ph->name);
            break;
        }
        if (ph->kind == 0) {
            wfail(w, "phase %s is an MQMQA (quadruplet) liquid, which the XTDB engine does not "
                     "read; .utdb or .dat holds it", ph->name);
            break;
        }
        xtdb_cef_phase(&x, ph);
    }
    for (int i = 0; i < db->n_stoich && !w->bad; ++i) {
        if (strlen(db->stoich[i].name) > XTDB_NAME || strpbrk(db->stoich[i].name, ",;()\"<>&")) {
            wfail(w, "phase name %s cannot be an XTDB phase Id", db->stoich[i].name);
            break;
        }
        xtdb_stoich(&x, &db->stoich[i]);
    }
    if (!w->bad) {
        /* the body so far holds the phases; functions and parameters follow them */
        tb_putf(&w->body, "%s%s", x.tp.s ? x.tp.s : "", x.par.s ? x.par.s : "");
        tb_putf(&w->body, "</XTDB>\n");
        if (x.tp.oom || x.par.oom) wfail(w, "out of memory");
    }
    free(x.tp.s);
    free(x.par.s);
    if (w->bad) return finish(w);

    tb_clean(src, sizeof src, source_name);
    tb_putf(&w->head, "<XTDB version=\"0.1.5\">\n<!-- Converted to XTDB by Hephaestus %s from %s.\n"
            "     %s\n", HEPHAESTUS_VERSION, src, LICENSE_LINE);
    if (db->title[0]) {
        tb_putf(&w->head, "     Source header:\n");
        source_header(&w->head, db->title, "       ", "\n");
        tb_putf(&w->head, "\n");
    }
    tb_putf(&w->head, "     Functions of the source appear expanded, one polynomial per range.\n");
    if (w->used_unknown_lo)
        tb_putf(&w->head, "     A LowT of %s K marks a limit the source did not give.\n",
                tb_num(num, UNKNOWN_LO));
    if (w->used_zero_tail)
        tb_putf(&w->head, "     A final zero range keeps ChemSage data zero above their last limit.\n");
    tb_putf(&w->head, "-->\n<Defaults LowT=\"%s\"",
            tb_num(num, isnan(db->lim_lo) ? UNKNOWN_LO : db->lim_lo));
    if (!isnan(db->lim_hi)) tb_putf(&w->head, " HighT=\"%s\"", tb_num(a, db->lim_hi));
    tb_putf(&w->head, " Elements=\"VA /-\" />\n");
    for (int e = 0; e < db->n_el; ++e) {
        tb_putf(&w->head, "<Element Id=\"%s\"", db->el_name[e]);
        if (db->el_ref && db->el_ref[e][0]) tb_putf(&w->head, " Refstate=\"%s\"", db->el_ref[e]);
        tb_putf(&w->head, " Mass=\"%s\"", tb_num(num, db->el_mass[e]));
        if (db->el_h298) tb_putf(&w->head, " H298=\"%s\" S298=\"%s\"", tb_num(num, db->el_h298[e]),
                                 tb_num(a, db->el_s298[e]));
        tb_putf(&w->head, " />\n");
    }
    tb_putf(&w->head, "<Species Id=\"VA\" Stoichiometry=\"VA\" />\n");
    for (int e = 0; e < db->n_el; ++e)
        tb_putf(&w->head, "<Species Id=\"%s\" Stoichiometry=\"%s\" />\n", db->el_name[e], db->el_name[e]);
    tb_putf(&w->head, "<TPfun Id=\"R\" Expr=\"%s;\" />\n", tb_num(num, db->R.own));
    {   /* named (non-element) constituents: their composition, for other readers */
        SpList *sp = calloc(1, sizeof *sp);
        if (!sp) { wfail(w, "out of memory"); return finish(w); }
        for (int p = 0; p < db->n_phases; ++p) {
            const SublPhase *cf = db->phases[p].cef;
            for (int i = 0; cf && i < cf->n_con; ++i) {
                Comp c;
                const char *cn = cf->con_name[i];
                if (!strcmp(cn, "VA") || is_element_name(db, cn)) continue;
                if (species_comp(db, cn, &c)) sp_add(w, sp, cn, &c);
            }
        }
        for (int i = 0; i < sp->n; ++i) {
            comp_text(db, &sp->comp[i], ctext, sizeof ctext);
            tb_putf(&w->head, "<Species Id=\"%s\" Stoichiometry=\"%s\" />\n", sp->name[i], ctext);
        }
        free(sp);
    }
    return finish(w);
}

char *mqmqa_db_write_dat(const mqmqa_db *db, const char *source_name)
{
    return write_own(db, source_name, 0, write_dat);
}

char *mqmqa_db_write_xtdb(const mqmqa_db *db, const char *source_name)
{
    return write_own(db, source_name, 0, write_xtdb);
}
