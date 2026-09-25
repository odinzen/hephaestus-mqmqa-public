/* XTDB (XML) reader + third-generation Gibbs-energy models for Hephaestus.
 *
 * XTDB is the open XML CALPHAD format (Sundman et al., Calphad 90 (2025) 102849). This
 * module is self-contained on purpose: it does not touch the .dat/.tdb readers in cs_dat.c,
 * so it cannot regress them (its writers only call their public API). It parses the XTDB tag set, evaluates the temperature functions
 * (including the built-in GEIN Einstein function), and assembles third-generation endmember
 * Gibbs energies:
 *
 *   endmember G(T) = [G parameter] + N_atoms * GEIN(theta),  theta = exp(LNTH parameter)
 *   two-state liquid: G = G_amorphous + G2ST,  G2ST(dG) = -R T ln(1 + exp(-dG/(R T)))
 *
 * GEIN(theta,T) = 1.5 R theta + 3 R T ln(1 - exp(-theta/T)) is one Einstein oscillator (3R at
 * high T). A formula unit of N real atoms has 3N vibrational modes, so the composition-dependent
 * LNTH term is weighted by N_atoms (site multiplicities of the non-vacancy constituents); the
 * fixed-theta GEIN terms written into the G parameter are corrections whose weights, with the
 * LNTH term, sum to N_atoms. This is the third-generation convention (element weights sum to
 * unity per atom; Sundman/Chen Einstein-Cp model). Validated against He et al., Calphad 72
 * (2021) 102250: pure-Al melting 933.47 K, the Al4C3 peritectic near 2430 K, and physical
 * heat capacities (graphite ~8.5, Al ~3R, Al4C3 approaching 7*3R).
 *
 * Clean-room from the published format and model equations; no GPL source is used.
 */
#include "xtdb.h"
#include "cs_dat.h"      /* the writers hand TDB text to the TDB reader and .dat writer */
#include "textbuf.h"
#include "mqmqa_priv.h"
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <stdio.h>

#define XCAP 256                   /* generous fixed caps; XTDB files are small */
#define XNAME 64
#define XEXPR 512

/* Attribute text the engine does not evaluate (limits, reference states, references) is
 * kept verbatim so a written file carries it unchanged. */
typedef struct {
    char id[XNAME]; char expr[8][XEXPR]; double hiT[8]; int nr;
    char lo_s[XNAME]; char hi_s[8][XNAME];
} TPfun;
typedef struct {
    char kind[8]; char phase[XNAME]; char cons[XNAME]; int deg; char expr[XEXPR];
    char id[XEXPR]; char bib[XNAME];
} Param;
typedef struct {
    char id[XNAME]; int twostate; int nsubl; double mult[8];
    int ncon[8]; char con[8][8][XNAME];   /* con[sublattice][index] */
    char config[XNAME], state[XNAME], models[XNAME];
} XPhase;

struct xtdb_db {
    char elem[XCAP][XNAME]; int nelem;
    char el_attr[XCAP][4][XNAME];        /* Refstate, Mass, H298, S298 */
    char sp_id[XCAP][XNAME], sp_st[XCAP][XNAME]; int nsp;
    char def_lo[XNAME], def_hi[XNAME], def_el[XNAME], version[XNAME];
    char note[1024];                     /* the file's opening comment (its provenance) */
    char bib_id[XCAP][XNAME], bib_text[XCAP][XEXPR]; int nbib;
    TPfun tp[XCAP]; int ntp;
    Param par[XCAP]; int npar;
    XPhase ph[XCAP]; int nph;
    /* first content read past without modeling; the writers refuse such a database */
    char lossy[256];
    RInfo R;                             /* the database's own gas constant */
};

/* the R a calculation on this database uses */
static double xr(const struct xtdb_db *db) { return rinfo_value(&db->R); }

static char g_err[256];
const char *xtdb_error(void) { return g_err; }

/* ---- tiny XML helpers: find tags and read attributes ---------------------------------- */

/* copy the value of attribute `name` inside tag body [b,e) into out; return 1 if found */
static int attr(const char *b, const char *e, const char *name, char *out, int cap) {
    size_t nl = strlen(name);
    for (const char *p = b; p + nl + 1 < e; ++p) {
        if (strncmp(p, name, nl) == 0 && (p == b || isspace((unsigned char)p[-1]))) {
            const char *q = p + nl;
            while (q < e && isspace((unsigned char)*q)) q++;
            if (q >= e || *q != '=') continue;
            q++;
            while (q < e && isspace((unsigned char)*q)) q++;
            if (q >= e || *q != '"') continue;
            q++;
            const char *r = q;
            while (r < e && *r != '"') r++;
            int n = (int)(r - q); if (n >= cap) n = cap - 1;
            memcpy(out, q, n); out[n] = 0;
            return 1;
        }
    }
    return 0;
}

/* find the next element named `tag`; sets *body to attributes region, *close to '>' or "/>",
 * returns pointer to start of tag ('<') or NULL. */
static const char *find_tag(const char *s, const char *tag, const char **body, const char **gt) {
    char open[XNAME]; snprintf(open, sizeof open, "<%s", tag);
    size_t ol = strlen(open);
    for (const char *p = strstr(s, open); p; p = strstr(p + 1, open)) {
        char after = p[ol];
        if (after == ' ' || after == '\t' || after == '\n' || after == '\r' || after == '>' || after == '/') {
            const char *b = p + ol;
            const char *end = strchr(b, '>');
            if (!end) return NULL;
            *body = b; *gt = end;
            return p;
        }
    }
    return NULL;
}

/* ---- expression evaluator (recursive descent) ----------------------------------------- */

typedef struct { const struct xtdb_db *db; double T; const char *p; int err; } Ev;
static double ev_expr(Ev *e);

static void ev_ws(Ev *e) { while (*e->p && isspace((unsigned char)*e->p)) e->p++; }

static const TPfun *find_tp(const struct xtdb_db *db, const char *name) {
    for (int i = 0; i < db->ntp; ++i) if (strcmp(db->tp[i].id, name) == 0) return &db->tp[i];
    return NULL;
}

static double eval_tp(const struct xtdb_db *db, const TPfun *f, double T, int *err);

static double ev_atom(Ev *e) {
    ev_ws(e);
    if (*e->p == '(') { e->p++; double v = ev_expr(e); ev_ws(e); if (*e->p == ')') e->p++; else e->err = 1; return v; }
    if (isdigit((unsigned char)*e->p) || *e->p == '.') {
        char *end; double v = strtod(e->p, &end); e->p = end; return v;
    }
    if (isalpha((unsigned char)*e->p) || *e->p == '_') {
        char id[XNAME]; int n = 0;
        while ((isalnum((unsigned char)*e->p) || *e->p == '_') && n < XNAME - 1) id[n++] = *e->p++;
        id[n] = 0;
        ev_ws(e);
        if (*e->p == '(') {           /* function call: LN, EXP, GEIN */
            e->p++; double a = ev_expr(e); ev_ws(e); if (*e->p == ')') e->p++; else e->err = 1;
            if (!strcmp(id, "LN"))  return log(a);
            if (!strcmp(id, "EXP")) return exp(a);
            if (!strcmp(id, "GEIN")) {
                const double R = xr(e->db);
                return 1.5 * R * a + 3.0 * R * e->T * log(1.0 - exp(-a / e->T));
            }
            e->err = 1; return 0.0;
        }
        if (*e->p == '#') e->p++;     /* tolerate TDB-style function-ref marker */
        if (!strcmp(id, "T")) return e->T;
        if (!strcmp(id, "P")) return 1.0e5;
        const TPfun *f = find_tp(e->db, id);
        /* a forced gas constant replaces the file's own TPfun R wherever it is used */
        if (f && !strcmp(id, "R") && mqmqa_gas_constant_mode() != MQMQA_R_AS_ASSESSED)
            return xr(e->db);
        if (f) { int er = 0; double v = eval_tp(e->db, f, e->T, &er); if (er) e->err = 1; return v; }
        e->err = 1; return 0.0;
    }
    e->err = 1; return 0.0;
}

static double ev_unary(Ev *e) {
    ev_ws(e);
    if (*e->p == '+') { e->p++; return ev_unary(e); }
    if (*e->p == '-') { e->p++; return -ev_unary(e); }
    return ev_atom(e);
}

static double ev_power(Ev *e) {
    double base = ev_unary(e);
    ev_ws(e);
    if (e->p[0] == '*' && e->p[1] == '*') { e->p += 2; double ex = ev_power(e); return pow(base, ex); }
    return base;
}

static double ev_term(Ev *e) {
    double v = ev_power(e);
    for (;;) {
        ev_ws(e);
        if (e->p[0] == '*' && e->p[1] != '*') { e->p++; v *= ev_power(e); }
        else if (*e->p == '/') { e->p++; v /= ev_power(e); }
        else return v;
    }
}

static double ev_expr(Ev *e) {
    double v = ev_term(e);
    for (;;) {
        ev_ws(e);
        if (*e->p == '+') { e->p++; v += ev_term(e); }
        else if (*e->p == '-') { e->p++; v -= ev_term(e); }
        else return v;
    }
}

static double eval_str(const struct xtdb_db *db, const char *expr, double T, int *err) {
    Ev e = { db, T, expr, 0 };
    double v = ev_expr(&e);
    if (e.err) *err = 1;
    return v;
}

static double eval_tp(const struct xtdb_db *db, const TPfun *f, double T, int *err) {
    int r = 0;
    while (r < f->nr - 1 && T > f->hiT[r]) r++;   /* pick the range holding T */
    return eval_str(db, f->expr[r], T, err);
}

static const char *find_param(const struct xtdb_db *db, const char *kind, const char *phase,
                              const char *cons, int deg) {
    for (int i = 0; i < db->npar; ++i)
        if (!strcmp(db->par[i].kind, kind) && !strcmp(db->par[i].phase, phase) &&
            !strcmp(db->par[i].cons, cons) && db->par[i].deg == deg)
            return db->par[i].expr;
    return NULL;
}

static const XPhase *find_phase(const struct xtdb_db *db, const char *name) {
    for (int i = 0; i < db->nph; ++i) if (!strcmp(db->ph[i].id, name)) return &db->ph[i];
    return NULL;
}

/* ---- third-generation endmember Gibbs -------------------------------------------------- */

/* real atoms per formula unit of an endmember: site multiplicities of the non-VA constituents.
 * The LNTH Einstein term is weighted by this so a compound carries its full 3R-per-atom Cp. */
static double natoms_of(const struct xtdb_db *db, const char *phase, const char *cons) {
    const XPhase *ph = find_phase(db, phase);
    if (!ph) return 1.0;
    char buf[XNAME]; strncpy(buf, cons, XNAME - 1); buf[XNAME - 1] = 0;
    double n = 0.0; int s = 0;
    for (char *t = strtok(buf, ":"); t && s < ph->nsubl; t = strtok(NULL, ":"), ++s)
        if (strcmp(t, "VA") != 0) n += ph->mult[s];
    return n > 0 ? n : 1.0;
}

double xtdb_endmember_gibbs(const struct xtdb_db *db, const char *phase, const char *cons,
                            double T, int *ok) {
    int err = 0;
    const char *g = find_param(db, "G", phase, cons, 0);
    if (!g) { if (ok) *ok = 0; return NAN; }
    double G = eval_str(db, g, T, &err);
    const char *lnth = find_param(db, "LNTH", phase, cons, 0);
    if (lnth) {
        double theta = exp(eval_str(db, lnth, T, &err));
        G += natoms_of(db, phase, cons) * (1.5 * xr(db) * theta + 3.0 * xr(db) * T * log(1.0 - exp(-theta / T)));
    }
    const XPhase *ph = find_phase(db, phase);
    if (ph && ph->twostate) {
        const char *gd = find_param(db, "GD", phase, cons, 0);
        if (gd) { double dG = eval_str(db, gd, T, &err); G += -xr(db) * T * log(1.0 + exp(-dG / (xr(db) * T))); }
    }
    if (ok) *ok = !err;
    return G;
}

/* ---- phase Gibbs: CEF reference + ideal + Redlich-Kister excess + phase-level two-state -- */

static double cons_atoms(const char *name) { return strcmp(name, "VA") == 0 ? 0.0 : 1.0; }

/* amorphous endmember Gibbs (G + GEIN, WITHOUT the two-state term); the two-state term is a
 * phase-level contribution and must not be summed per endmember for a solution. */
static double endmember_am(const struct xtdb_db *db, const char *phase, const char *cons,
                           double T, int *err) {
    const char *g = find_param(db, "G", phase, cons, 0);
    if (!g) { *err = 1; return 0.0; }
    double G = eval_str(db, g, T, err);
    const char *lnth = find_param(db, "LNTH", phase, cons, 0);
    if (lnth) {
        double theta = exp(eval_str(db, lnth, T, err));
        G += natoms_of(db, phase, cons) * (1.5 * xr(db) * theta + 3.0 * xr(db) * T * log(1.0 - exp(-theta / T)));
    }
    return G;
}

/* overall mole fraction of element `B` given mixing-sublattice fraction y of its first
 * constituent (used to invert composition -> site fraction). */
static double xB_of_y(const XPhase *ph, int smix, const char *B, double y) {
    double aB = 0.0, atot = 0.0;
    for (int s = 0; s < ph->nsubl; ++s) {
        for (int i = 0; i < ph->ncon[s]; ++i) {
            double yi = (s == smix) ? (i == 0 ? y : (ph->ncon[s] == 2 ? 1.0 - y : 0.0)) : 1.0;
            double at = cons_atoms(ph->con[s][i]);
            atot += ph->mult[s] * yi * at;
            if (strcmp(ph->con[s][i], B) == 0) aB += ph->mult[s] * yi * at;
        }
    }
    return atot > 0 ? aB / atot : 0.0;
}

/* Gibbs of a phase (J/mol-atom) at overall mole fraction xB of element B, and T.
 * For a stoichiometric/pure phase xB is ignored and its fixed composition is returned in
 * *fixed (>=0). Returns NAN if the phase cannot reach xB. */
double xtdb_phase_gibbs(const struct xtdb_db *db, int pidx, const char *B, double xB, double T,
                        double *fixed, int *ok) {
    int err = 0;
    if (fixed) *fixed = -1.0;
    if (pidx < 0 || pidx >= db->nph) { if (ok) *ok = 0; return NAN; }
    const XPhase *ph = &db->ph[pidx];

    int smix = -1;
    for (int s = 0; s < ph->nsubl; ++s) if (ph->ncon[s] > 1) { smix = s; break; }

    double y = 1.0;                          /* fraction of first constituent on the mixing subl */
    if (smix < 0) {                          /* stoichiometric / pure: fixed composition */
        double fx = xB_of_y(ph, -1, B, 1.0);
        if (fixed) *fixed = fx;
    } else {
        double lo = 1e-9, hi = 1.0 - 1e-9;   /* invert xB_of_y by bisection (monotone) */
        double flo = xB_of_y(ph, smix, B, lo) - xB;
        double fhi = xB_of_y(ph, smix, B, hi) - xB;
        if (flo * fhi > 0) { if (ok) *ok = 0; return NAN; }   /* xB out of this phase's range */
        for (int it = 0; it < 100; ++it) {
            double m = 0.5 * (lo + hi);
            if ((xB_of_y(ph, smix, B, m) - xB) * flo <= 0) hi = m; else lo = m;
        }
        y = 0.5 * (lo + hi);
    }

    /* site fractions per (sublattice, constituent) */
    double Y[8][8];
    for (int s = 0; s < ph->nsubl; ++s)
        for (int i = 0; i < ph->ncon[s]; ++i)
            Y[s][i] = (s == smix) ? (i == 0 ? y : 1.0 - y) : 1.0;

    /* reference: sum over endmembers (product of one constituent per sublattice) */
    double ref = 0.0;
    int idx[8] = {0};
    for (;;) {
        double prod = 1.0; char cs[XNAME] = {0};
        for (int s = 0; s < ph->nsubl; ++s) {
            prod *= Y[s][idx[s]];
            if (s) strncat(cs, ":", XNAME - strlen(cs) - 1);
            strncat(cs, ph->con[s][idx[s]], XNAME - strlen(cs) - 1);
        }
        if (prod > 0.0) ref += prod * endmember_am(db, ph->id, cs, T, &err);
        int s = ph->nsubl - 1;
        while (s >= 0) { if (++idx[s] < ph->ncon[s]) break; idx[s] = 0; s--; }
        if (s < 0) break;
    }

    /* ideal configurational entropy, per sublattice weighted by multiplicity */
    double ideal = 0.0;
    for (int s = 0; s < ph->nsubl; ++s)
        for (int i = 0; i < ph->ncon[s]; ++i)
            if (Y[s][i] > 0.0) ideal += xr(db) * T * ph->mult[s] * Y[s][i] * log(Y[s][i]);

    /* excess: Redlich-Kister interaction parameters G(phase, ...comma-list...; deg) */
    double excess = 0.0;
    for (int k = 0; k < db->npar; ++k) {
        if (strcmp(db->par[k].kind, "G") || strcmp(db->par[k].phase, ph->id)) continue;
        if (!strchr(db->par[k].cons, ',')) continue;              /* interaction only */
        /* split cons by ':' into sublattices; the one with ',' is the mixing pair */
        char c[XNAME]; strncpy(c, db->par[k].cons, XNAME - 1); c[XNAME - 1] = 0;
        char *subl[8]; int ns = 0;
        for (char *t = strtok(c, ":"); t && ns < 8; t = strtok(NULL, ":")) subl[ns++] = t;
        double L = eval_str(db, db->par[k].expr, T, &err);
        double other = 1.0; int s_mix = -1; char *ci = NULL, *cj = NULL;
        for (int s = 0; s < ns; ++s) {
            char *comma = strchr(subl[s], ',');
            if (comma) { s_mix = s; *comma = 0; ci = subl[s]; cj = comma + 1; }
        }
        if (s_mix < 0) continue;
        int ii = -1, jj = -1;
        for (int i = 0; i < ph->ncon[s_mix]; ++i) {
            if (!strcmp(ph->con[s_mix][i], ci)) ii = i;
            if (!strcmp(ph->con[s_mix][i], cj)) jj = i;
        }
        if (ii < 0 || jj < 0) continue;
        double yi = Y[s_mix][ii], yj = Y[s_mix][jj];
        excess += other * yi * yj * L * pow(yi - yj, (double)db->par[k].deg);
    }

    /* per mole of atoms */
    double atot = 0.0;
    for (int s = 0; s < ph->nsubl; ++s)
        for (int i = 0; i < ph->ncon[s]; ++i)
            atot += ph->mult[s] * Y[s][i] * cons_atoms(ph->con[s][i]);
    double G = (ref + ideal + excess) / (atot > 0 ? atot : 1.0);

    /* two-state liquid: G += G2ST(dG), dG = composition-weighted GD (single sublattice) */
    if (ph->twostate && smix >= 0) {
        double dG = 0.0;
        for (int i = 0; i < ph->ncon[smix]; ++i) {
            const char *gd = find_param(db, "GD", ph->id, ph->con[smix][i], 0);
            if (gd) dG += Y[smix][i] * eval_str(db, gd, T, &err);
        }
        G += -xr(db) * T * log(1.0 + exp(-dG / (xr(db) * T)));
    }
    if (ok) *ok = !err;
    return G;
}

/* ---- parsing --------------------------------------------------------------------------- */

static void note_lossy(struct xtdb_db *db, const char *fmt, ...) {
    va_list ap;
    if (db->lossy[0]) return;
    va_start(ap, fmt);
    vsnprintf(db->lossy, sizeof db->lossy, fmt, ap);
    va_end(ap);
}

/* attr(), noting a value too long for its buffer: the engine would use a truncated copy */
static int attr_k(struct xtdb_db *db, const char *b, const char *e, const char *name,
                  char *out, int cap) {
    int r = attr(b, e, name, out, cap);
    if (r && (int)strlen(out) >= cap - 1)
        note_lossy(db, "a %s attribute longer than %d characters", name, cap - 2);
    return r;
}

xtdb_db *xtdb_read_string(const char *text) {
    g_err[0] = 0;
    if (!strstr(text, "<XTDB")) { snprintf(g_err, sizeof g_err, "not an XTDB file (<XTDB missing)"); return NULL; }
    xtdb_db *db = calloc(1, sizeof *db);
    if (!db) { snprintf(g_err, sizeof g_err, "out of memory"); return NULL; }
    const char *b, *gt; char v[XEXPR];

    if (find_tag(text, "XTDB", &b, &gt)) {
        const char *c0 = strstr(gt, "<!--"), *c1 = c0 ? strstr(c0 + 4, "-->") : NULL;
        const char *first = strchr(gt + 1, '<');
        attr(b, gt, "version", db->version, XNAME);
        if (c0 && c1 && c0 == first) {       /* a comment opening the file body */
            size_t n = (size_t)(c1 - (c0 + 4));
            if (n >= sizeof db->note) n = sizeof db->note - 1;
            memcpy(db->note, c0 + 4, n);
            db->note[n] = 0;
        }
    }
    if (find_tag(text, "Defaults", &b, &gt)) {
        attr(b, gt, "LowT", db->def_lo, XNAME);
        attr(b, gt, "HighT", db->def_hi, XNAME);
        attr(b, gt, "Elements", db->def_el, XNAME);
    }

    for (const char *p = find_tag(text, "Element", &b, &gt); p; p = find_tag(gt, "Element", &b, &gt)) {
        if (db->nelem >= XCAP) { note_lossy(db, "more than %d elements", XCAP); break; }
        if (attr_k(db, b, gt, "Id", v, XNAME)) {
            static const char *names[4] = { "Refstate", "Mass", "H298", "S298" };
            strncpy(db->elem[db->nelem], v, XNAME - 1);
            for (int k = 0; k < 4; ++k) attr_k(db, b, gt, names[k], db->el_attr[db->nelem][k], XNAME);
            db->nelem++;
        }
    }
    for (const char *p = find_tag(text, "Species", &b, &gt); p; p = find_tag(gt, "Species", &b, &gt)) {
        if (db->nsp >= XCAP) { note_lossy(db, "more than %d species", XCAP); break; }
        if (attr_k(db, b, gt, "Id", db->sp_id[db->nsp], XNAME)) {
            attr_k(db, b, gt, "Stoichiometry", db->sp_st[db->nsp], XNAME);
            db->nsp++;
        }
    }

    for (const char *p = find_tag(text, "TPfun", &b, &gt); p; p = find_tag(gt, "TPfun", &b, &gt)) {
        if (db->ntp >= XCAP) { note_lossy(db, "more than %d TPfun functions", XCAP); break; }
        TPfun *f = &db->tp[db->ntp++];
        memset(f, 0, sizeof *f);
        attr_k(db, b, gt, "Id", f->id, XNAME);
        attr_k(db, b, gt, "Expr", f->expr[0], XEXPR);
        attr(b, gt, "LowT", f->lo_s, XNAME);
        if (attr(b, gt, "HighT", f->hi_s[0], XNAME)) f->hiT[0] = atof(f->hi_s[0]); else f->hiT[0] = 1e30;
        f->nr = 1;
        /* Trange children up to the next '<' that is not a Trange */
        const char *scan = gt + 1;
        for (;;) {
            const char *tb, *tgt;
            const char *tr = find_tag(scan, "Trange", &tb, &tgt);
            const char *nextTop = strstr(scan, "<TPfun");
            const char *nextPar = strstr(scan, "<Parameter");
            if (!tr) break;
            if ((nextTop && tr > nextTop) || (nextPar && tr > nextPar)) break;   /* belongs to a later tag */
            if (f->nr < 8) {
                attr_k(db, tb, tgt, "Expr", f->expr[f->nr], XEXPR);
                if (attr(tb, tgt, "HighT", f->hi_s[f->nr], XNAME)) f->hiT[f->nr] = atof(f->hi_s[f->nr]);
                else f->hiT[f->nr] = 1e30;
                f->nr++;
            } else {
                note_lossy(db, "more than 8 temperature ranges in TPfun %s", f->id);
            }
            scan = tgt + 1;
        }
    }

    for (const char *p = find_tag(text, "Parameter", &b, &gt); p; p = find_tag(gt, "Parameter", &b, &gt)) {
        if (db->npar >= XCAP) { note_lossy(db, "more than %d parameters", XCAP); break; }
        char id[XEXPR]; if (!attr_k(db, b, gt, "Id", id, XEXPR)) continue;
        Param *pr = &db->par[db->npar];
        memset(pr, 0, sizeof *pr);
        /* Id = KIND(PHASE,CONS;DEG) */
        const char *lp = strchr(id, '('), *comma = lp ? strchr(lp, ',') : NULL;
        const char *semi = comma ? strchr(comma, ';') : NULL, *rp = semi ? strchr(semi, ')') : NULL;
        if (!lp || !comma || !semi || !rp) { note_lossy(db, "an unparsed parameter Id %s", id); continue; }
        int kn = (int)(lp - id); if (kn > 7) kn = 7; memcpy(pr->kind, id, kn); pr->kind[kn] = 0;
        int pn = (int)(comma - lp - 1); if (pn > XNAME - 1) pn = XNAME - 1; memcpy(pr->phase, lp + 1, pn); pr->phase[pn] = 0;
        int cn = (int)(semi - comma - 1); if (cn > XNAME - 1) cn = XNAME - 1; memcpy(pr->cons, comma + 1, cn); pr->cons[cn] = 0;
        pr->deg = atoi(semi + 1);
        if (!attr_k(db, b, gt, "Expr", pr->expr, XEXPR)) continue;
        snprintf(pr->id, sizeof pr->id, "%s", id);
        attr_k(db, b, gt, "Bibref", pr->bib, XNAME);
        if (strcmp(pr->kind, "G") && strcmp(pr->kind, "LNTH") && strcmp(pr->kind, "GD"))
            note_lossy(db, "the %s parameter %s, which the engine does not evaluate", pr->kind, id);
        if (gt[-1] != '/') {                 /* a Parameter with children: ranges not read */
            const char *close = strstr(gt, "</Parameter>");
            const char *trr = strstr(gt, "<Trange");
            if (close && trr && trr < close)
                note_lossy(db, "temperature ranges inside the parameter %s", id);
        }
        db->npar++;
    }

    for (const char *p = find_tag(text, "Phase", &b, &gt); p; p = find_tag(gt, "Phase", &b, &gt)) {
        if (db->nph >= XCAP) { note_lossy(db, "more than %d phases", XCAP); break; }
        XPhase *ph = &db->ph[db->nph++];
        memset(ph, 0, sizeof *ph);
        attr_k(db, b, gt, "Id", ph->id, XNAME);
        attr(b, gt, "Configuration", ph->config, XNAME);
        attr(b, gt, "State", ph->state, XNAME);
        if (ph->config[0] && strcmp(ph->config, "CEF"))
            note_lossy(db, "the %s configuration of phase %s", ph->config, ph->id);
        /* phase body ends at </Phase> */
        const char *pend = strstr(gt, "</Phase>");
        const char *sb, *sgt;
        const char *sub = find_tag(gt, "Sublattices", &sb, &sgt);
        if (sub && (!pend || sub < pend)) {
            attr(sb, sgt, "NumberOf", v, XEXPR); ph->nsubl = atoi(v);
            if (ph->nsubl > 8) { note_lossy(db, "more than 8 sublattices in %s", ph->id); ph->nsubl = 8; }
            char mult[XEXPR]; attr(sb, sgt, "Multiplicities", mult, XEXPR);
            char *tok = strtok(mult, " "); int s = 0;
            while (tok && s < 8) { ph->mult[s++] = atof(tok); tok = strtok(NULL, " "); }
            const char *cscan = sgt;
            for (const char *cp = find_tag(cscan, "Constituents", &sb, &sgt); cp && (!pend || cp < pend);
                 cp = find_tag(sgt, "Constituents", &sb, &sgt)) {
                int sl = 0; if (attr(sb, sgt, "Sublattice", v, XEXPR)) sl = atoi(v) - 1;
                char lst[XEXPR]; attr(sb, sgt, "List", lst, XEXPR);
                char *ct = strtok(lst, " "); int ci = 0;
                while (ct && sl >= 0 && sl < 8) {
                    if (ci < 8) strncpy(ph->con[sl][ci++], ct, XNAME - 1);
                    else note_lossy(db, "more than 8 constituents on a sublattice of %s", ph->id);
                    ct = strtok(NULL, " ");
                }
                if (sl >= 0 && sl < 8) ph->ncon[sl] = ci;
            }
        }
        const char *ab, *agt;
        const char *am = find_tag(gt, "AmendPhase", &ab, &agt);
        if (am && (!pend || am < pend) && attr(ab, agt, "Models", ph->models, XNAME)) {
            char m[XNAME]; strncpy(m, ph->models, XNAME - 1); m[XNAME - 1] = 0;
            for (char *t = strtok(m, " "); t; t = strtok(NULL, " ")) {
                if (!strcmp(t, "LIQ2STATE")) ph->twostate = 1;
                else if (strcmp(t, "GEIN"))
                    note_lossy(db, "the %s model of phase %s, which the engine does not evaluate", t, ph->id);
            }
        }
    }

    for (const char *p = find_tag(text, "Bibitem", &b, &gt); p; p = find_tag(gt, "Bibitem", &b, &gt)) {
        if (db->nbib >= XCAP) { note_lossy(db, "more than %d references", XCAP); break; }
        attr_k(db, b, gt, "Id", db->bib_id[db->nbib], XNAME);
        attr_k(db, b, gt, "Text", db->bib_text[db->nbib], XEXPR);
        db->nbib++;
    }
    {   /* a TPfun R holding one number states R; otherwise literals, then the convention */
        const TPfun *f = find_tp(db, "R");
        double v = 0.0;
        int stated = 0;
        if (f && f->nr == 1) {
            char *end;
            v = strtod(f->expr[0], &end);
            while (isspace((unsigned char)*end) || *end == ';') end++;
            stated = end != f->expr[0] && *end == '\0';
        }
        rinfo_detect(&db->R, ".xtdb files", mqmqa_gas_constant_choice(MQMQA_R_SGTE), stated, v,
                     text, 2);
        if (f && !stated)
            snprintf(db->R.detail, sizeof db->R.detail, "its TPfun R is not a single number");
    }
    return db;
}

double xtdb_R_own(const xtdb_db *db) { return db->R.own; }
double xtdb_R(const xtdb_db *db) { return rinfo_value(&db->R); }
int xtdb_R_source(const xtdb_db *db) { return rinfo_source(&db->R); }
int xtdb_R_own_source(const xtdb_db *db) { return db->R.src; }
const char *xtdb_R_note(const xtdb_db *db) { return rinfo_note(&db->R); }

int xtdb_declare_R(xtdb_db *db, int choice)
{
    const int rc = rinfo_declare(&db->R, choice);
    if (rc == -1)
        snprintf(g_err, sizeof g_err, "the file states R = %.10g; a stated value cannot be "
                 "declared otherwise", db->R.own);
    else if (rc == -2)
        snprintf(g_err, sizeof g_err, "unknown gas-constant choice %d", choice);
    return rc;
}

void xtdb_free(xtdb_db *db) { free(db); }
int xtdb_n_phases(const xtdb_db *db) { return db->nph; }
const char *xtdb_phase(const xtdb_db *db, int p) { return (p >= 0 && p < db->nph) ? db->ph[p].id : ""; }
int xtdb_n_elements(const xtdb_db *db) { return db->nelem; }
const char *xtdb_element(const xtdb_db *db, int i) { return (i >= 0 && i < db->nelem) ? db->elem[i] : ""; }

/* ---- writers ---------------------------------------------------------------------------
 * XTDB back to XTDB keeps every expression and attribute as read. XTDB to TDB carries the
 * TPfun and Parameter expressions over as FUNCTION and PARAMETER statements (the syntax is
 * shared), then reads the result with the TDB reader and checks every endmember against
 * this engine before handing it back. The .dat writer serializes that checked database.
 * The third-generation models (the Einstein LNTH term, GEIN, the two-state liquid) have no
 * TDB or ChemSage form and are refused. */

#define XLICENSE \
    "Converting a database does not change its license; the license of the source data applies."

static void xfail(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(g_err, sizeof g_err, fmt, ap);
    va_end(ap);
}

static char *xfinish(TextBuf *b) {
    if (b->oom) { free(b->s); xfail("out of memory"); return NULL; }
    return b->s ? b->s : calloc(1, 1);
}

static void xml_attr(TextBuf *b, const char *name, const char *v) {
    if (v && v[0]) tb_putf(b, " %s=\"%s\"", name, v);
}

/* the source's opening comment, one cleaned and trimmed line per output line */
static void put_note(TextBuf *b, const char *note, const char *prefix) {
    char line[1024], clean[1024];
    while (note && *note) {
        size_t n = strcspn(note, "\n");
        const char *t = note;
        while (n && (*t == ' ' || *t == '\t' || *t == '\r')) { t++; n--; }
        while (n && (t[n - 1] == ' ' || t[n - 1] == '\r' || t[n - 1] == '\t')) n--;
        if (n) {
            if (n >= sizeof line) n = sizeof line - 1;
            memcpy(line, t, n);
            line[n] = 0;
            tb_clean(clean, sizeof clean, line);
            tb_putf(b, "%s%s\n", prefix, clean);
        }
        note += strcspn(note, "\n");
        if (*note == '\n') note++;
    }
}

char *xtdb_write_xtdb(const xtdb_db *db, const char *source_name) {
    TextBuf b = { 0 };
    char src[200], num[40];
    if (!db) { xfail("null database"); return NULL; }
    if (db->lossy[0]) {
        xfail("cannot write XTDB: the source carries %s, so a converted file would silently "
              "drop it", db->lossy);
        return NULL;
    }
    tb_clean(src, sizeof src, source_name);
    tb_putf(&b, "<XTDB version=\"%s\">\n", db->version[0] ? db->version : "0.1.5");
    tb_putf(&b, "<!-- Converted to XTDB by Hephaestus %s from %s.\n     %s\n", HEPHAESTUS_VERSION,
            src, XLICENSE);
    if (db->note[0]) {
        tb_putf(&b, "     Source header:\n");
        put_note(&b, db->note, "       ");
    }
    tb_putf(&b, "-->\n");
    if (db->def_lo[0] || db->def_hi[0] || db->def_el[0]) {
        tb_putf(&b, "<Defaults");
        xml_attr(&b, "LowT", db->def_lo);
        xml_attr(&b, "HighT", db->def_hi);
        xml_attr(&b, "Elements", db->def_el);
        tb_putf(&b, " />\n");
    }
    for (int e = 0; e < db->nelem; ++e) {
        tb_putf(&b, "<Element Id=\"%s\"", db->elem[e]);
        xml_attr(&b, "Refstate", db->el_attr[e][0]);
        xml_attr(&b, "Mass", db->el_attr[e][1]);
        xml_attr(&b, "H298", db->el_attr[e][2]);
        xml_attr(&b, "S298", db->el_attr[e][3]);
        tb_putf(&b, " />\n");
    }
    for (int i = 0; i < db->nsp; ++i) {
        tb_putf(&b, "<Species Id=\"%s\"", db->sp_id[i]);
        xml_attr(&b, "Stoichiometry", db->sp_st[i]);
        tb_putf(&b, " />\n");
    }
    for (int p = 0; p < db->nph; ++p) {
        const XPhase *ph = &db->ph[p];
        tb_putf(&b, "<Phase Id=\"%s\"", ph->id);
        xml_attr(&b, "Configuration", ph->config);
        xml_attr(&b, "State", ph->state);
        tb_putf(&b, " >\n  <Sublattices NumberOf=\"%d\" Multiplicities=\"", ph->nsubl);
        for (int s = 0; s < ph->nsubl; ++s) tb_putf(&b, "%s%s", s ? " " : "", tb_num(num, ph->mult[s]));
        tb_putf(&b, "\" >\n");
        for (int s = 0; s < ph->nsubl; ++s) {
            tb_putf(&b, "    <Constituents Sublattice=\"%d\" List=\"", s + 1);
            for (int i = 0; i < ph->ncon[s]; ++i) tb_putf(&b, "%s%s", i ? " " : "", ph->con[s][i]);
            tb_putf(&b, "\" />\n");
        }
        tb_putf(&b, "  </Sublattices>\n");
        if (ph->models[0]) tb_putf(&b, "  <AmendPhase Models=\"%s\" />\n", ph->models);
        tb_putf(&b, "</Phase>\n");
    }
    for (int k = 0; k < db->ntp; ++k) {
        const TPfun *f = &db->tp[k];
        tb_putf(&b, "<TPfun Id=\"%s\"", f->id);
        xml_attr(&b, "LowT", f->lo_s);
        xml_attr(&b, "Expr", f->expr[0]);
        xml_attr(&b, "HighT", f->hi_s[0]);
        if (f->nr == 1) { tb_putf(&b, " />\n"); continue; }
        tb_putf(&b, " >\n");
        for (int r = 1; r < f->nr; ++r) {
            tb_putf(&b, "  <Trange");
            xml_attr(&b, "Expr", f->expr[r]);
            xml_attr(&b, "HighT", f->hi_s[r]);
            tb_putf(&b, " />\n");
        }
        tb_putf(&b, "</TPfun>\n");
    }
    if (!find_tp(db, "R")) {
        char num[40];
        tb_putf(&b, "<TPfun Id=\"R\" Expr=\"%s;\" />\n", tb_num(num, db->R.own));
    }
    for (int k = 0; k < db->npar; ++k) {
        const Param *pr = &db->par[k];
        tb_putf(&b, "<Parameter Id=\"%s\" Expr=\"%s\"", pr->id, pr->expr);
        xml_attr(&b, "Bibref", pr->bib);
        tb_putf(&b, " />\n");
    }
    if (db->nbib) {
        tb_putf(&b, "<Bibliography>\n");
        for (int i = 0; i < db->nbib; ++i) {
            tb_putf(&b, "<Bibitem Id=\"%s\"", db->bib_id[i]);
            xml_attr(&b, "Text", db->bib_text[i]);
            tb_putf(&b, " />\n");
        }
        tb_putf(&b, "</Bibliography>\n");
    }
    tb_putf(&b, "</XTDB>\n");
    return xfinish(&b);
}

/* ---- XTDB to TDB ---- */

static int is_tpfun(const struct xtdb_db *db, const char *id) {
    for (int i = 0; i < db->ntp; ++i) if (!strcmp(db->tp[i].id, id)) return 1;
    return 0;
}

/* An XTDB expression in TDB syntax: the trailing ';' dropped and '#' after each function
 * reference. Returns 0 with *why naming a function TDB does not have. */
static int tdb_expr(const struct xtdb_db *db, const char *in, TextBuf *out, const char **why) {
    const char *p = in, *end = in + strlen(in);
    while (end > p && (end[-1] == ';' || isspace((unsigned char)end[-1]))) end--;
    while (p < end) {
        if (isdigit((unsigned char)*p) || (*p == '.' && isdigit((unsigned char)p[1]))) {
            const char *q = p;           /* a number, exponent included (805.644E23) */
            while (q < end && (isdigit((unsigned char)*q) || *q == '.')) q++;
            if (q < end && (*q == 'E' || *q == 'e') &&
                (isdigit((unsigned char)q[1]) || ((q[1] == '+' || q[1] == '-') && isdigit((unsigned char)q[2])))) {
                q += (q[1] == '+' || q[1] == '-') ? 2 : 1;
                while (q < end && isdigit((unsigned char)*q)) q++;
            }
            tb_putf(out, "%.*s", (int)(q - p), p);
            p = q;
        } else if (isalpha((unsigned char)*p) || *p == '_') {
            char id[XNAME]; int n = 0;
            while (p < end && (isalnum((unsigned char)*p) || *p == '_')) { if (n < XNAME - 1) id[n++] = *p; p++; }
            id[n] = 0;
            if (!strcmp(id, "GEIN")) { *why = "the third-generation Einstein function GEIN"; return 0; }
            if (!strcmp(id, "EXP")) { *why = "an EXP() term"; return 0; }
            tb_putf(out, "%s", id);
            if (is_tpfun(db, id) && *p != '#') tb_putf(out, "#");
        } else {
            tb_putf(out, "%c", *p);
            p++;
        }
    }
    return 1;
}

/* real atoms of a phase's endmember as this engine counts them (non-VA site multiplicity) */
static double engine_atoms(const XPhase *ph, const int *pick) {
    double n = 0.0;
    for (int s = 0; s < ph->nsubl; ++s) if (strcmp(ph->con[s][pick[s]], "VA")) n += ph->mult[s];
    return n;
}

static int upper_eq(const char *a, const char *b) {
    for (; *a && *b; ++a, ++b) if (toupper((unsigned char)*a) != toupper((unsigned char)*b)) return 0;
    return *a == *b;
}

/* Every endmember of the TDB reading must match this engine's value, per formula unit and
 * in atoms, over 300-3000 K; anything else means the text did not carry the model. */
static int check_against_tdb(const struct xtdb_db *db, const mqmqa_db *d) {
    for (int p = 0; p < db->nph; ++p) {
        const XPhase *ph = &db->ph[p];
        int pick[8] = { 0 }, dp = -1, st = -1;
        for (int i = 0; i < mqmqa_db_num_phases(d); ++i)
            if (upper_eq(mqmqa_db_phase_name(d, i), ph->id)) dp = i;
        for (int i = 0; i < mqmqa_db_num_stoich(d); ++i)
            if (upper_eq(mqmqa_db_stoich_name(d, i), ph->id)) st = i;
        for (;;) {
            char cs[XNAME * 2] = { 0 };
            for (int s = 0; s < ph->nsubl; ++s) {
                if (s) strncat(cs, ":", sizeof cs - strlen(cs) - 1);
                strncat(cs, ph->con[s][pick[s]], sizeof cs - strlen(cs) - 1);
            }
            if (find_param(db, "G", ph->id, cs, 0)) {
                double atoms_d = 0.0, Y[64] = { 0 };
                int ny = 0;
                if (dp >= 0) {
                    int ns = mqmqa_ph_cef_num_subl(d, dp), nc[16];
                    if (ns != ph->nsubl || ns > 16) { xfail("phase %s changed shape in TDB", ph->id); return 0; }
                    mqmqa_ph_cef_subl_ncon(d, dp, nc);
                    for (int s = 0; s < ns; ++s)
                        for (int i = 0; i < nc[s] && ny < 64; ++i)
                            Y[ny++] = upper_eq(mqmqa_ph_cef_constituent(d, dp, s, i), ph->con[s][pick[s]]) ? 1.0 : 0.0;
                } else if (st < 0) {
                    xfail("phase %s is missing from the TDB reading", ph->id);
                    return 0;
                }
                for (int k = 0; k <= 12; ++k) {
                    double T = 300.37 + 225.0 * k, gx, gd;
                    int okx = 1;
                    gx = xtdb_endmember_gibbs(db, ph->id, cs, T, &okx);
                    if (dp >= 0) {
                        gd = mqmqa_ph_cef_gibbs(d, dp, Y, T, 0);
                        atoms_d = gd / mqmqa_ph_cef_gibbs(d, dp, Y, T, 1);
                    } else {
                        double el[64];
                        gd = mqmqa_db_stoich_gibbs(d, st, T);
                        atoms_d = 0.0;
                        if (mqmqa_db_num_elements(d) <= 64) {
                            mqmqa_db_stoich_elems(d, st, el);
                            for (int e = 0; e < mqmqa_db_num_elements(d); ++e) atoms_d += el[e];
                        }
                    }
                    if (!okx || !(fabs(gx - gd) <= 1e-9 * fmax(1.0, fabs(gx)))) {
                        xfail("endmember %s of %s reads back as %.17g instead of %.17g at %.2f K",
                              cs, ph->id, gd, gx, T);
                        return 0;
                    }
                    if (gd != 0.0 && fabs(atoms_d - engine_atoms(ph, pick)) > 1e-9 * engine_atoms(ph, pick)) {
                        xfail("endmember %s of %s counts %g atoms in TDB but %g here: a molecular "
                              "species, which this engine counts as one atom", cs, ph->id, atoms_d,
                              engine_atoms(ph, pick));
                        return 0;
                    }
                }
            }
            int s = ph->nsubl - 1;
            while (s >= 0) { if (++pick[s] < ph->ncon[s]) break; pick[s] = 0; s--; }
            if (s < 0) break;
        }
    }
    return 1;
}

/* TDB text for the database; header_fmt NULL gives the internal form used on the way to
 * .dat, whose only comments are the source's own. On success *checked (if given) receives
 * the verified TDB reading. */
static char *to_tdb(const struct xtdb_db *db, const char *source_name, const char *header_fmt,
                    mqmqa_db **checked) {
    TextBuf b = { 0 }, ex = { 0 };
    char src[200];
    const char *why = NULL, *lo = db->def_lo[0] ? db->def_lo : "0.01";
    const char *hi = db->def_hi[0] ? db->def_hi : "1E+12";
    if (checked) *checked = NULL;
    if (db->lossy[0]) {
        xfail("cannot write %s: the source carries %s, so a converted file would silently drop it",
              header_fmt ? header_fmt : "ChemSage .dat", db->lossy);
        return NULL;
    }
    for (int p = 0; p < db->nph; ++p)
        if (db->ph[p].twostate) {
            xfail("phase %s uses the third-generation two-state liquid (LIQ2STATE), which TDB and "
                  "ChemSage .dat cannot hold; .xtdb can", db->ph[p].id);
            return NULL;
        }
    for (int k = 0; k < db->npar; ++k) {
        const Param *pr = &db->par[k];
        if (!strcmp(pr->kind, "LNTH")) {
            xfail("%s is a third-generation Einstein heat capacity (LNTH), which TDB and ChemSage "
                  ".dat cannot hold; .xtdb can", pr->id);
            return NULL;
        }
        if (!strcmp(pr->kind, "GD")) {
            xfail("%s is a two-state liquid parameter (GD), which TDB and ChemSage .dat cannot "
                  "hold; .xtdb can", pr->id);
            return NULL;
        }
    }
    tb_clean(src, sizeof src, source_name);
    if (header_fmt) {
        tb_putf(&b, "$ Converted to %s by Hephaestus %s from %s.\n$ %s\n", header_fmt,
                HEPHAESTUS_VERSION, src, XLICENSE);
        if (db->note[0]) { tb_putf(&b, "$ Source header:\n"); put_note(&b, db->note, "$   "); }
        for (int i = 0; i < db->nbib; ++i) {
            char t[XEXPR];
            tb_clean(t, sizeof t, db->bib_text[i]);
            tb_putf(&b, "$ Reference %s: %s\n", db->bib_id[i], t);
        }
    } else if (db->note[0]) {
        put_note(&b, db->note, "$ ");
    }
    tb_putf(&b, "$\n ELEMENT /-   ELECTRON_GAS  0  0  0 !\n ELEMENT VA   VACUUM  0  0  0 !\n");
    for (int e = 0; e < db->nelem; ++e)
        tb_putf(&b, " ELEMENT %-3s  %s  %s  %s  %s !\n", db->elem[e],
                db->el_attr[e][0][0] ? db->el_attr[e][0] : "BLANK",
                db->el_attr[e][1][0] ? db->el_attr[e][1] : "0",
                db->el_attr[e][2][0] ? db->el_attr[e][2] : "0",
                db->el_attr[e][3][0] ? db->el_attr[e][3] : "0");
    for (int i = 0; i < db->nsp; ++i) {
        int is_el = !strcmp(db->sp_id[i], "VA");
        for (int e = 0; e < db->nelem && !is_el; ++e) is_el = !strcmp(db->elem[e], db->sp_id[i]);
        if (!is_el && db->sp_st[i][0]) tb_putf(&b, " SPECIES %s  %s !\n", db->sp_id[i], db->sp_st[i]);
    }
    tb_putf(&b, "\n TYPE_DEFINITION %% SEQ * !\n");
    for (int k = 0; k < db->ntp; ++k) {
        const TPfun *f = &db->tp[k];
        tb_putf(&b, "\n FUNCTION %s  %s\n    ", f->id, f->lo_s[0] ? f->lo_s : lo);
        for (int r = 0; r < f->nr; ++r) {
            ex.n = 0;
            if (!tdb_expr(db, f->expr[r], &ex, &why)) {
                xfail("TPfun %s uses %s, which TDB and ChemSage .dat cannot hold; .xtdb can", f->id, why);
                free(b.s); free(ex.s);
                return NULL;
            }
            tb_putf(&b, "%.*s;  %s %s", (int)ex.n, ex.s ? ex.s : "",
                    f->hi_s[r][0] ? f->hi_s[r] : hi, r + 1 < f->nr ? "Y\n    " : "N !\n");
        }
    }
    if (!find_tp(db, "R")) {
        char num[40];
        tb_putf(&b, "\n FUNCTION R  %s  %s;  %s N !\n", lo, tb_num(num, db->R.own), hi);
    }
    for (int p = 0; p < db->nph; ++p) {
        const XPhase *ph = &db->ph[p];
        char num[40];
        tb_putf(&b, "\n PHASE %s %%  %d ", ph->id, ph->nsubl);
        for (int s = 0; s < ph->nsubl; ++s) tb_putf(&b, " %s", tb_num(num, ph->mult[s]));
        tb_putf(&b, " !\n CONSTITUENT %s :", ph->id);
        for (int s = 0; s < ph->nsubl; ++s) {
            tb_putf(&b, " ");
            for (int i = 0; i < ph->ncon[s]; ++i) tb_putf(&b, "%s%s", i ? "," : "", ph->con[s][i]);
            tb_putf(&b, " :");
        }
        tb_putf(&b, " !\n");
        for (int k = 0; k < db->npar; ++k) {
            const Param *pr = &db->par[k];
            if (strcmp(pr->phase, ph->id)) continue;
            ex.n = 0;
            if (!tdb_expr(db, pr->expr, &ex, &why)) {
                xfail("%s uses %s, which TDB and ChemSage .dat cannot hold; .xtdb can", pr->id, why);
                free(b.s); free(ex.s);
                return NULL;
            }
            tb_putf(&b, " PARAMETER %s(%s,%s;%d)  %s\n    %.*s;  %s N%s%s !\n", pr->kind, pr->phase,
                    pr->cons, pr->deg, lo, (int)ex.n, ex.s ? ex.s : "", hi,
                    pr->bib[0] ? " " : "", pr->bib);
        }
    }
    free(ex.s);
    if (b.oom) { free(b.s); xfail("out of memory"); return NULL; }
    {
        mqmqa_db *d = mqmqa_db_read_string(b.s);
        if (!d) {
            xfail("the TDB reader rejects the converted text (%s): the XTDB expressions use "
                  "syntax outside the TDB subset", mqmqa_db_error());
            free(b.s);
            return NULL;
        }
        if (!check_against_tdb(db, d)) { mqmqa_db_free(d); free(b.s); return NULL; }
        if (checked) *checked = d; else mqmqa_db_free(d);
    }
    return b.s;
}

char *xtdb_write_tdb(const xtdb_db *db, const char *source_name) {
    if (!db) { xfail("null database"); return NULL; }
    return to_tdb(db, source_name, "TDB", NULL);
}

char *xtdb_write_utdb(const xtdb_db *db, const char *source_name) {
    if (!db) { xfail("null database"); return NULL; }
    return to_tdb(db, source_name, "uTDB", NULL);
}

char *xtdb_write_dat(const xtdb_db *db, const char *source_name) {
    mqmqa_db *d = NULL;
    char *tdb, *dat;
    if (!db) { xfail("null database"); return NULL; }
    tdb = to_tdb(db, source_name, NULL, &d);
    if (!tdb) return NULL;
    free(tdb);
    dat = mqmqa_db_write_dat(d, source_name);
    if (!dat) xfail("%s", mqmqa_db_error());
    mqmqa_db_free(d);
    return dat;
}

#ifdef XTDB_TEST
/* standalone self-test: read AlC.xtdb, verify endmembers, mixing, and the diagram assemblage.
 * Link it with the rest of src/: the writers above call the database API. */

/* lower convex hull of G(x) over all phases at temperature T. Fills seg[] with the stable
 * vertices (x, G, phase index) left to right; returns the count. Solution phases are sampled
 * on a grid; stoichiometric phases contribute one point. */
static int hull_at_T(const struct xtdb_db *db, double T, double *hx, double *hg, int *hp, int cap) {
    double px[4096], pg[4096]; int pp[4096], np = 0;
    for (int p = 0; p < db->nph && np < 4000; ++p) {
        int ok = 1; double fixed;
        double g0 = xtdb_phase_gibbs(db, p, "C", 1e-6, T, &fixed, &ok);
        if (fixed >= 0) {                       /* stoichiometric: single point */
            int okk = 1; double g = xtdb_phase_gibbs(db, p, "C", fixed, T, &fixed, &okk);
            if (okk) { px[np] = fixed; pg[np] = g; pp[np] = p; np++; }
            continue;
        }
        for (int i = 0; i <= 300; ++i) {        /* solution phase: sample composition */
            double x = i / 300.0; if (x < 1e-6) x = 1e-6; if (x > 1 - 1e-6) x = 1 - 1e-6;
            int okk = 1; double g = xtdb_phase_gibbs(db, p, "C", x, T, &fixed, &okk);
            if (okk && isfinite(g)) { px[np] = x; pg[np] = g; pp[np] = p; np++; if (np >= 4000) break; }
        }
        (void)g0;
    }
    /* sort by x (simple insertion; np is a few hundred) */
    for (int i = 1; i < np; ++i) {
        double kx = px[i], kg = pg[i]; int kp = pp[i], j = i - 1;
        while (j >= 0 && px[j] > kx) { px[j+1]=px[j]; pg[j+1]=pg[j]; pp[j+1]=pp[j]; j--; }
        px[j+1]=kx; pg[j+1]=kg; pp[j+1]=kp;
    }
    /* collapse duplicate compositions to their lowest-G phase (drops metastable endpoints
     * like diamond, which is degenerate with graphite only at pure C) */
    int w = 0;
    for (int i = 0; i < np; ++i) {
        if (w > 0 && fabs(px[i] - px[w-1]) < 1e-9) { if (pg[i] < pg[w-1]) { pg[w-1]=pg[i]; pp[w-1]=pp[i]; } }
        else { px[w]=px[i]; pg[w]=pg[i]; pp[w]=pp[i]; w++; }
    }
    np = w;
    /* monotone-chain lower hull */
    int m = 0; int idx[4096];
    for (int i = 0; i < np; ++i) {
        while (m >= 2) {
            double ax = px[idx[m-2]], ay = pg[idx[m-2]], bx = px[idx[m-1]], by = pg[idx[m-1]];
            double cx = px[i], cy = pg[i];
            double cross = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax);
            if (cross <= 1e-6) m--; else break;   /* pop points not on the lower hull */
        }
        idx[m++] = i;
    }
    int out = 0;
    for (int i = 0; i < m && out < cap; ++i) { hx[out]=px[idx[i]]; hg[out]=pg[idx[i]]; hp[out]=pp[idx[i]]; out++; }
    return out;
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "data/xtdb/AlC.xtdb";
    FILE *f = fopen(path, "rb"); if (!f) { fprintf(stderr, "cannot open %s\n", path); return 1; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = malloc(n + 1); fread(buf, 1, n, f); buf[n] = 0; fclose(f);
    xtdb_db *db = xtdb_read_string(buf);
    if (!db) { fprintf(stderr, "parse error: %s\n", xtdb_error()); return 1; }
    printf("parsed %d elements, %d TPfuns, %d parameters, %d phases\n",
           db->nelem, db->ntp, db->npar, db->nph);
    int ok = 1;
    #define G(ph, c, T) xtdb_endmember_gibbs(db, ph, c, T, &ok)
    double lo = 700, hi = 1100;
    for (int i = 0; i < 80; ++i) {
        double m = 0.5 * (lo + hi);
        double flo = G("LIQUID", "AL", lo) - G("FCC_A1", "AL:VA", lo);
        double fm  = G("LIQUID", "AL", m)  - G("FCC_A1", "AL:VA", m);
        if (flo * fm <= 0) hi = m; else lo = m;
    }
    printf("C engine: pure-Al melting = %.2f K  (literature 933.47)\n", 0.5 * (lo + hi));

    puts("\n-- endmember Gibbs (J/mol-formula) --");
    struct { const char *ph, *c; double T; } pts[] = {
        {"FCC_A1","AL:VA",300},{"FCC_A1","AL:VA",933.47},{"LIQUID","AL",933.47},
        {"LIQUID","AL",1500},{"GRAPHITE","C",298.15},{"AL4C3","AL:C",1000},{"DIAMOND","C",500}};
    for (int i = 0; i < 7; ++i)
        printf("%-8s %-6s %8.2f  %.6f\n", pts[i].ph, pts[i].c, pts[i].T, G(pts[i].ph, pts[i].c, pts[i].T));

    /* phase Gibbs per mole-atom at intermediate compositions (validates mixing/excess/two-state) */
    puts("\n-- phase Gibbs per mole-atom (J) at intermediate x_C --");
    struct { const char *ph; double x, T; } mix[] = {
        {"LIQUID",0.25,2000},{"LIQUID",0.50,2000},{"LIQUID",0.75,2500},
        {"FCC_A1",0.10,1200},{"FCC_A1",0.30,1500},{"AL4C3",0.42857142857,1500}};
    for (int i = 0; i < 6; ++i) {
        int p = -1; for (int q = 0; q < db->nph; ++q) if (!strcmp(xtdb_phase(db, q), mix[i].ph)) p = q;
        int okk = 1; double fx; double g = xtdb_phase_gibbs(db, p, "C", mix[i].x, mix[i].T, &fx, &okk);
        printf("%-8s x_C=%.5f  T=%.0f  G=%.6f\n", mix[i].ph, mix[i].x, mix[i].T, g);
    }

    /* stable-phase assemblage on the lower hull at representative temperatures */
    puts("\n-- Al-C stable assemblage (lower convex hull) --");
    double Ts[] = {800, 933.47, 1000, 1500, 2000, 2500, 3000};
    for (int t = 0; t < 7; ++t) {
        double hx[512], hg[512]; int hp[512];
        int m = hull_at_T(db, Ts[t], hx, hg, hp, 512);
        printf("T=%6.1f K :", Ts[t]);
        for (int i = 0; i < m; ) {           /* collapse a run of one phase into an x-range */
            int j = i; while (j + 1 < m && hp[j+1] == hp[i]) j++;
            if (j > i) printf(" [%s x_C=%.4f..%.4f]", xtdb_phase(db, hp[i]), hx[i], hx[j]);
            else       printf(" [%s x_C=%.4f]", xtdb_phase(db, hp[i]), hx[i]);
            i = j + 1;
        }
        printf("\n");
    }
    xtdb_free(db); free(buf);
    return 0;
}
#endif
