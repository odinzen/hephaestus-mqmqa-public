/* XTDB (XML) reader + third-generation Gibbs-energy models for Hephaestus.
 *
 * XTDB is the open XML CALPHAD format (Sundman et al., Calphad 90 (2025) 102849). This
 * module is self-contained on purpose: it does not touch the .dat/.tdb readers in cs_dat.c,
 * so it cannot regress them. It parses the XTDB tag set, evaluates the temperature functions
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
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <stdio.h>

#define XR 8.31451                 /* CALPHAD gas constant used by the 3rd-gen SGTE data */
#define XCAP 256                   /* generous fixed caps; XTDB files are small */
#define XNAME 64
#define XEXPR 512

typedef struct { char id[XNAME]; char expr[8][XEXPR]; double hiT[8]; int nr; } TPfun;
typedef struct { char kind[8]; char phase[XNAME]; char cons[XNAME]; int deg; char expr[XEXPR]; } Param;
typedef struct {
    char id[XNAME]; int twostate; int nsubl; double mult[8];
    int ncon[8]; char con[8][8][XNAME];   /* con[sublattice][index] */
} XPhase;

struct xtdb_db {
    char elem[XCAP][XNAME]; int nelem;
    TPfun tp[XCAP]; int ntp;
    Param par[XCAP]; int npar;
    XPhase ph[XCAP]; int nph;
};

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
            if (!strcmp(id, "GEIN")) return 1.5 * XR * a + 3.0 * XR * e->T * log(1.0 - exp(-a / e->T));
            e->err = 1; return 0.0;
        }
        if (*e->p == '#') e->p++;     /* tolerate TDB-style function-ref marker */
        if (!strcmp(id, "T")) return e->T;
        if (!strcmp(id, "P")) return 1.0e5;
        const TPfun *f = find_tp(e->db, id);
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
        G += natoms_of(db, phase, cons) * (1.5 * XR * theta + 3.0 * XR * T * log(1.0 - exp(-theta / T)));
    }
    const XPhase *ph = find_phase(db, phase);
    if (ph && ph->twostate) {
        const char *gd = find_param(db, "GD", phase, cons, 0);
        if (gd) { double dG = eval_str(db, gd, T, &err); G += -XR * T * log(1.0 + exp(-dG / (XR * T))); }
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
        G += natoms_of(db, phase, cons) * (1.5 * XR * theta + 3.0 * XR * T * log(1.0 - exp(-theta / T)));
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
            if (Y[s][i] > 0.0) ideal += XR * T * ph->mult[s] * Y[s][i] * log(Y[s][i]);

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
        G += -XR * T * log(1.0 + exp(-dG / (XR * T)));
    }
    if (ok) *ok = !err;
    return G;
}

/* ---- parsing --------------------------------------------------------------------------- */

xtdb_db *xtdb_read_string(const char *text) {
    g_err[0] = 0;
    if (!strstr(text, "<XTDB")) { snprintf(g_err, sizeof g_err, "not an XTDB file (<XTDB missing)"); return NULL; }
    xtdb_db *db = calloc(1, sizeof *db);
    if (!db) { snprintf(g_err, sizeof g_err, "out of memory"); return NULL; }
    const char *b, *gt; char v[XEXPR];

    for (const char *p = find_tag(text, "Element", &b, &gt); p; p = find_tag(gt, "Element", &b, &gt))
        if (db->nelem < XCAP && attr(b, gt, "Id", v, XNAME)) strncpy(db->elem[db->nelem++], v, XNAME - 1);

    for (const char *p = find_tag(text, "TPfun", &b, &gt); p; p = find_tag(gt, "TPfun", &b, &gt)) {
        if (db->ntp >= XCAP) break;
        TPfun *f = &db->tp[db->ntp++];
        memset(f, 0, sizeof *f);
        attr(b, gt, "Id", f->id, XNAME);
        attr(b, gt, "Expr", f->expr[0], XEXPR);
        if (attr(b, gt, "HighT", v, XEXPR)) f->hiT[0] = atof(v); else f->hiT[0] = 1e30;
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
                attr(tb, tgt, "Expr", f->expr[f->nr], XEXPR);
                if (attr(tb, tgt, "HighT", v, XEXPR)) f->hiT[f->nr] = atof(v); else f->hiT[f->nr] = 1e30;
                f->nr++;
            }
            scan = tgt + 1;
        }
    }

    for (const char *p = find_tag(text, "Parameter", &b, &gt); p; p = find_tag(gt, "Parameter", &b, &gt)) {
        if (db->npar >= XCAP) break;
        char id[XEXPR]; if (!attr(b, gt, "Id", id, XEXPR)) continue;
        Param *pr = &db->par[db->npar];
        memset(pr, 0, sizeof *pr);
        /* Id = KIND(PHASE,CONS;DEG) */
        const char *lp = strchr(id, '('), *comma = lp ? strchr(lp, ',') : NULL;
        const char *semi = comma ? strchr(comma, ';') : NULL, *rp = semi ? strchr(semi, ')') : NULL;
        if (!lp || !comma || !semi || !rp) continue;
        int kn = (int)(lp - id); if (kn > 7) kn = 7; memcpy(pr->kind, id, kn); pr->kind[kn] = 0;
        int pn = (int)(comma - lp - 1); if (pn > XNAME - 1) pn = XNAME - 1; memcpy(pr->phase, lp + 1, pn); pr->phase[pn] = 0;
        int cn = (int)(semi - comma - 1); if (cn > XNAME - 1) cn = XNAME - 1; memcpy(pr->cons, comma + 1, cn); pr->cons[cn] = 0;
        pr->deg = atoi(semi + 1);
        if (!attr(b, gt, "Expr", pr->expr, XEXPR)) continue;
        db->npar++;
    }

    for (const char *p = find_tag(text, "Phase", &b, &gt); p; p = find_tag(gt, "Phase", &b, &gt)) {
        if (db->nph >= XCAP) break;
        XPhase *ph = &db->ph[db->nph++];
        memset(ph, 0, sizeof *ph);
        attr(b, gt, "Id", ph->id, XNAME);
        /* phase body ends at </Phase> */
        const char *pend = strstr(gt, "</Phase>");
        const char *sb, *sgt;
        const char *sub = find_tag(gt, "Sublattices", &sb, &sgt);
        if (sub && (!pend || sub < pend)) {
            attr(sb, sgt, "NumberOf", v, XEXPR); ph->nsubl = atoi(v);
            char mult[XEXPR]; attr(sb, sgt, "Multiplicities", mult, XEXPR);
            char *tok = strtok(mult, " "); int s = 0;
            while (tok && s < 8) { ph->mult[s++] = atof(tok); tok = strtok(NULL, " "); }
            const char *cscan = sgt;
            for (const char *cp = find_tag(cscan, "Constituents", &sb, &sgt); cp && (!pend || cp < pend);
                 cp = find_tag(sgt, "Constituents", &sb, &sgt)) {
                int sl = 0; if (attr(sb, sgt, "Sublattice", v, XEXPR)) sl = atoi(v) - 1;
                char lst[XEXPR]; attr(sb, sgt, "List", lst, XEXPR);
                char *ct = strtok(lst, " "); int ci = 0;
                while (ct && sl >= 0 && sl < 8 && ci < 8) { strncpy(ph->con[sl][ci++], ct, XNAME - 1); ct = strtok(NULL, " "); }
                if (sl >= 0 && sl < 8) ph->ncon[sl] = ci;
            }
        }
        const char *ab, *agt;
        const char *am = find_tag(gt, "AmendPhase", &ab, &agt);
        if (am && (!pend || am < pend) && attr(ab, agt, "Models", v, XEXPR) && strstr(v, "LIQ2STATE"))
            ph->twostate = 1;
    }
    return db;
}

void xtdb_free(xtdb_db *db) { free(db); }
int xtdb_n_phases(const xtdb_db *db) { return db->nph; }
const char *xtdb_phase(const xtdb_db *db, int p) { return (p >= 0 && p < db->nph) ? db->ph[p].id : ""; }
int xtdb_n_elements(const xtdb_db *db) { return db->nelem; }
const char *xtdb_element(const xtdb_db *db, int i) { return (i >= 0 && i < db->nelem) ? db->elem[i] : ""; }

#ifdef XTDB_TEST
/* standalone self-test: read AlC.xtdb, verify endmembers, mixing, and the diagram assemblage. */

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
