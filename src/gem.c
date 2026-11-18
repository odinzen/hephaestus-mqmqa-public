/* General equilibrium for any number of elements and phases. Method and sources in
 * docs/GENERAL_EQUILIBRIUM.md: candidates from every phase, a linear program for the
 * lower hull at the bulk composition (its duals are the chemical potentials), then column
 * generation from each phase's driving-force minimum until no phase lies below the hull.
 * Written from Lukas, Fries and Sundman (2007) and Dantzig and Wolfe (1960); no other
 * program's solver source was consulted. */
#include "gem.h"
#include "cs_dat_priv.h"

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GEM_GRID 6          /* default grid steps per simplex edge */
#define GEM_PASSES 120      /* default refinement passes */
#define GEM_MAX_SAMPLES 4000
#define GEM_TOL 1e-9        /* J per mole of atoms: a driving force below -GEM_TOL is a new column */
#define GEM_OBJ_TOL 1e-6    /* J per mole of atoms: a smaller hull drop is no progress (tailing
                               refinements drop it ~1e-9 a pass long after it has settled) */
#define MERGE_DX 2e-3       /* composition distance under which two columns are one set */
#define GEM_KMIN 4          /* distinct MQMQA driving-force minima taken per search */
#define GEM_AMT_MIN 1e-6    /* a basic column below this amount is folded into its phase's set */
#define GEM_DF_STOP 1e-6    /* J per mole of atoms: below the tangent plane by more, keep going.
                               1e-3 left a dilute element's potential ~10 J/mol loose (Tc in Ru)
                               at no saving in time over the Thermochimica cases */
#define GEM_STALLS_MAX 8    /* passes in a row without a hull drop before giving up on one */
#define GEM_RESUME_MAX 12   /* times the passes resume when the certificate finds a point below */
#define GEM_CERT_FAIL 1e-3  /* J/mol: a final certificate below minus this is a failed solve */

/* ------------------------------------------------------------------ *
 * Phase handlers
 * ------------------------------------------------------------------ */
typedef enum { PH_STOICH, PH_CEF, PH_MQMQA, PH_IONIC } PhKind;

typedef struct {
    PhKind kind;
    int tag;                /* solution phase index, or -(j+1) for compound j */
    int nz;                 /* internal variables (simplex-mapped) */
    int n_simp;             /* simplices: CEF sublattices, or 2 for MQMQA and SUBI */
    int simp_n[64];         /* size of each simplex */
    double *con_el;         /* CEF and SUBI: [n_con * n_el] element amounts per constituent;
                               MQMQA: [(ncat+nan) * n_el] per ion */
    double *ion_q;          /* MQMQA: |charge| per ion, cations then anions */
    int *off;               /* constituent (ion) held at zero: of an element the bulk lacks, or
                               leading off the face the bulk lies on (NULL: none) */
    int gone;               /* left out entirely by face_reduce */
    int face;               /* MQMQA: off is also the database's ion_off for this solve */
} Ph;

typedef struct {
    const Db *d;
    const mqmqa_db *db;
    double T;
    int n_el;
    Ph *ph;
    int n_ph;
    const int *active;      /* element present in the bulk */
} Sys;


/* A ChemSage file gives a phase with a miscibility gap a second copy under the same name.
 * Where no gap opens the copies have one energy, and the linear program can split an amount
 * between them at one composition (NobleMetals-Kaye's two HCPN at 2250 K); that is one set.
 * A name alone does not make a copy: FeMnCaS-1's two IONIC_LIQ differ by up to 48 kJ/mol. Two
 * phases count as one only when their energies agree to the last digit at four fixed points. */
static unsigned long long sp_rng;
static double sp_u(void)
{
    sp_rng = sp_rng * 6364136223846793005ULL + 1442695040888963407ULL;
    return (double)(sp_rng >> 11) / 9007199254740992.0 + 1e-3;
}

static int same_phase(const mqmqa_db *db, double T, int a, int b)
{
    if (a == b) return 1;
    if (a < 0 || b < 0) return 0;
    const char *na = mqmqa_db_phase_name(db, a), *nb = mqmqa_db_phase_name(db, b);
    if (!na || !nb || strcmp(na, nb)) return 0;
    const Db *d = (const Db *)db;
    const Phase *A = &d->phases[a], *B = &d->phases[b];
    if (A->kind != B->kind) return 0;
    double y[256], X[256];
    sp_rng = 0x2545F4914F6CDD1DULL;
    for (int k = 0; k < 4; ++k) {
        double ga, gb;
        if (A->kind == 1) {
            const SublPhase *ca = A->cef, *cb = B->cef;
            if (!ca || !cb || ca->n_subl != cb->n_subl || ca->n_con != cb->n_con || ca->n_con > 256) return 0;
            for (int t = 0; t < ca->n_subl; ++t) {
                double sum = 0.0;
                for (int i = 0; i < ca->subl_ncon[t]; ++i) sum += (y[ca->subl_off[t] + i] = sp_u());
                for (int i = 0; i < ca->subl_ncon[t]; ++i) y[ca->subl_off[t] + i] /= sum;
            }
            ga = mqmqa_ph_cef_gibbs(db, a, y, T, 1);
            gb = mqmqa_ph_cef_gibbs(db, b, y, T, 1);
        } else if (A->kind == 2) {
            const IonicPhase *ia = A->ion, *ib = B->ion;
            if (!ia || !ib || ia->nc != ib->nc || ia->na != ib->na || ia->nc + ia->na > 256) return 0;
            double sc = 0.0, sa = 0.0;
            for (int i = 0; i < ia->nc; ++i) sc += (y[i] = sp_u());
            for (int i = ia->nc; i < ia->nc + ia->na; ++i) sa += (y[i] = sp_u());
            for (int i = 0; i < ia->nc; ++i) y[i] /= sc;
            for (int i = ia->nc; i < ia->nc + ia->na; ++i) y[i] /= sa;
            ga = mqmqa_ph_ionic_gibbs(db, a, y, T, NULL);
            gb = mqmqa_ph_ionic_gibbs(db, b, y, T, NULL);
        } else {
            mqmqa_quad_ctx *qa = mqmqa_quad_open(db, a, T, NULL), *qb = mqmqa_quad_open(db, b, T, NULL);
            const int n = qa ? mqmqa_quad_count(qa) : 0;
            int same = qa && qb && n == mqmqa_quad_count(qb) && n <= 256;
            if (same) {
                double sum = 0.0;
                for (int q = 0; q < n; ++q) sum += (X[q] = sp_u());
                for (int q = 0; q < n; ++q) X[q] /= sum;
                ga = mqmqa_quad_gibbs(qa, X, NULL);
                gb = mqmqa_quad_gibbs(qb, X, NULL);
            }
            mqmqa_quad_close(qa);
            mqmqa_quad_close(qb);
            if (!same) return 0;
        }
        if (!(ga == gb)) return 0;
    }
    return 1;
}

static int name_to_el(const Db *d, const char *name, double *el)
{
    memset(el, 0, (size_t)d->n_el * sizeof(double));
    if (!strcmp(name, "VA") || !strcmp(name, "Va") || !strcmp(name, "va")) return 0;
    for (int s = 0; s < d->n_sp; ++s)
        if (!strcmp(d->sp[s].name, name)) {
            for (int k = 0; k < d->sp[s].n_el; ++k) el[d->sp[s].el[k]] += d->sp[s].n[k];
            return 0;
        }
    char sym[NAME_MAX];
    int j = 0;
    for (const char *p = name; *p && j < NAME_MAX - 1 && isalpha((unsigned char)*p); ++p)
        sym[j++] = (char)toupper((unsigned char)*p);
    sym[j] = '\0';
    for (int e = 0; e < d->n_el; ++e) {
        char up[NAME_MAX];
        int k = 0;
        for (; d->el_name[e][k] && k < NAME_MAX - 1; ++k)
            up[k] = (char)toupper((unsigned char)d->el_name[e][k]);
        up[k] = '\0';
        if (!strcmp(up, sym)) { el[e] = 1.0; return 0; }
    }
    return -1;
}

/* map unconstrained z onto a simplex of n entries (last logit fixed at 0) */
static void softmax(const double *z, int n, double *y)
{
    double m = 0.0;
    for (int i = 0; i < n - 1; ++i) if (z[i] > m) m = z[i];
    double s = exp(-m);
    for (int i = 0; i < n - 1; ++i) s += exp(z[i] - m);
    for (int i = 0; i < n - 1; ++i) y[i] = exp(z[i] - m) / s;
    y[n - 1] = exp(-m) / s;
}

static void logits(const double *y, int n, double *z)
{
    const double floor_ = 1e-12;
    double last = y[n - 1] > floor_ ? y[n - 1] : floor_;
    for (int i = 0; i < n - 1; ++i) z[i] = log((y[i] > floor_ ? y[i] : floor_) / last);
}

/* simplex fractions of every simplex of phase h from its internal variables z */
static void unpack(const Ph *h, const double *z, double *y)
{
    int zo = 0, yo = 0;
    for (int s = 0; s < h->n_simp; ++s) {
        int n = h->simp_n[s];
        if (n == 1) y[yo] = 1.0;
        else softmax(z + zo, n, y + yo);
        zo += n - 1;
        yo += n;
    }
}

/* Element mole fractions of an MQMQA phase from its cation fractions y[0..nc) and anion
 * fractions y[nc..nc+na), anions in the amount charge balance sets; -1 if undefined */
static int mq_x_of_y(const Ph *h, int ne, const double *y, double *x)
{
    const int nc = h->simp_n[0], na = h->simp_n[1];
    double qc = 0.0, qa = 0.0;
    for (int i = 0; i < nc; ++i) qc += y[i] * h->ion_q[i];
    for (int k = 0; k < na; ++k) qa += y[nc + k] * h->ion_q[nc + k];
    if (!(qc > 0.0 && qa > 0.0)) return -1;
    const double an_mol = qc / qa;
    memset(x, 0, (size_t)ne * sizeof(double));
    for (int i = 0; i < nc; ++i)
        for (int e = 0; e < ne; ++e) x[e] += y[i] * h->con_el[i * ne + e];
    for (int k = 0; k < na; ++k)
        for (int e = 0; e < ne; ++e) x[e] += an_mol * y[nc + k] * h->con_el[(nc + k) * ne + e];
    double atoms = 0.0;
    for (int e = 0; e < ne; ++e) atoms += x[e];
    if (!(atoms > 0.0)) return -1;
    for (int e = 0; e < ne; ++e) x[e] /= atoms;
    return 0;
}

/* Constituents of elements the bulk lacks set to zero, each sublattice renormalized;
 * -1 when a sublattice holds nothing else */
static int drop_off(const Ph *h, double *y)
{
    if (!h->off) return 0;
    for (int s = 0, o = 0; s < h->n_simp; o += h->simp_n[s], ++s) {
        double sum = 0.0;
        for (int i = o; i < o + h->simp_n[s]; ++i) {
            if (h->off[i]) y[i] = 0.0;
            sum += y[i];
        }
        if (!(sum > 0.0)) return -1;
        for (int i = o; i < o + h->simp_n[s]; ++i) y[i] /= sum;
    }
    return 0;
}

/* Gibbs energy per mole of atoms and element mole fractions x at simplex fractions y.
 * NaN when the point is not evaluable. */
static double ph_eval(const Sys *S, const Ph *h, const double *y, double *x)
{
    const int ne = S->n_el;
    if (h->kind == PH_CEF) {
        const SublPhase *cf = S->d->phases[h->tag].cef;
        double yr[256];
        if (h->off) {
            if (cf->n_con > 256) return NAN;
            memcpy(yr, y, (size_t)cf->n_con * sizeof(double));
            if (drop_off(h, yr)) return NAN;
            y = yr;
        }
        memset(x, 0, (size_t)ne * sizeof(double));
        for (int s = 0; s < cf->n_subl; ++s)
            for (int i = 0; i < cf->subl_ncon[s]; ++i) {
                int c = cf->subl_off[s] + i;
                for (int e = 0; e < ne; ++e) x[e] += cf->site_ratio[s] * y[c] * h->con_el[c * ne + e];
            }
        double atoms = 0.0;
        for (int e = 0; e < ne; ++e) atoms += x[e];
        if (!(atoms > 1e-12)) return NAN;
        for (int e = 0; e < ne; ++e) x[e] /= atoms;
        return mqmqa_ph_cef_gibbs(S->db, h->tag, y, S->T, 1);
    }
    if (h->kind == PH_IONIC) {
        /* the site numbers P and Q move with composition, so the element amounts come
         * from the phase itself */
        double yr[128];
        const int ni = h->simp_n[0] + h->simp_n[1];
        if (h->off) {
            if (ni > 128) return NAN;
            memcpy(yr, y, (size_t)ni * sizeof(double));
            if (drop_off(h, yr)) return NAN;
            y = yr;
        }
        const double g = mqmqa_ph_ionic_gibbs(S->db, h->tag, y, S->T, x);
        double atoms = 0.0;
        for (int e = 0; e < ne; ++e) atoms += x[e];
        if (!isfinite(g) || !(atoms > 1e-12)) return NAN;
        for (int e = 0; e < ne; ++e) x[e] /= atoms;
        return g / atoms;
    }
    /* A point counts only if the fixed-composition solve came close to its composition. With a
     * trace of an element (the simplex floor leaves 1e-10 of it) the solve can miss: by up to
     * 4e-7 in FeO-MgO-SiO2, harmless for a candidate, but in ClAlNa's metallic liquid (1e-12 of
     * Cl) by 0.26, returning the energy of another composition, 2 kJ/mol below the plane, which
     * the hull took as a second liquid that does not exist. A gross miss is moved onto the edge
     * without its traces, which the solve takes as a subsystem exactly, and dropped if it still
     * misses. Every sample is not moved there: columns exactly on an edge coincide with
     * compounds (liquid at SiO2 beside cristobalite) and made the basis singular. */
    double yr[128];
    const double *yy = y;
    if (h->off) {
        const int ni = h->simp_n[0] + h->simp_n[1];
        if (ni > 128) return NAN;
        memcpy(yr, y, (size_t)ni * sizeof(double));
        if (drop_off(h, yr)) return NAN;
        yy = yr;
    }
    if (mq_x_of_y(h, ne, yy, x) || ne > 64) return NAN;
    double err = 0.0;
    double g = h->off ? mqmqa_equilibrate_sub_err(S->db, h->tag, S->T, x, S->active, &err)
                      : mqmqa_equilibrate_db(S->db, h->tag, S->T, x, NULL, &err);
    if (err > 1e-5) {
        int keep[64], moved = 0;
        double sum = 0.0;
        for (int e = 0; e < ne; ++e) {
            if (x[e] > 0.0 && x[e] < 1e-6) { x[e] = 0.0; moved = 1; }
            keep[e] = S->active[e] && x[e] > 0.0;
            sum += x[e];
        }
        if (!moved || !(sum > 0.0)) return NAN;
        for (int e = 0; e < ne; ++e) x[e] /= sum;
        g = mqmqa_equilibrate_sub_err(S->db, h->tag, S->T, x, keep, &err);
    }
    return err > 1e-5 ? NAN : g;
}

/* ------------------------------------------------------------------ *
 * Candidate store
 * ------------------------------------------------------------------ */
typedef struct {
    int n, cap, ne, nzmax;
    int *ph;                /* handler index */
    double *x, *g, *z;
} Cols;

static int cols_add(Cols *c, int ph, const double *x, double g, const double *z, int nz)
{
    if (!isfinite(g)) return 0;
    for (int e = 0; e < c->ne; ++e) if (!isfinite(x[e])) return 0;
    /* A point of a phase within 1e-9 of one it already has is the same point: kept once,
     * at the lower energy. Two such columns make a nearly singular basis whose prices are
     * rounding noise, and the simplex cycled on that noise. */
    for (int k = 0; k < c->n; ++k) {
        if (c->ph[k] != ph) continue;
        double dx = 0.0;
        for (int e = 0; e < c->ne && dx <= 1e-9; ++e) dx = fmax(dx, fabs(c->x[(size_t)k * c->ne + e] - x[e]));
        if (dx > 1e-9) continue;
        if (g < c->g[k]) {
            c->g[k] = g;
            memset(c->z + (size_t)k * c->nzmax, 0, (size_t)c->nzmax * sizeof(double));
            if (nz) memcpy(c->z + (size_t)k * c->nzmax, z, (size_t)nz * sizeof(double));
        }
        return 0;
    }
    if (c->n == c->cap) {
        int cap = c->cap ? 2 * c->cap : 1024;
        int *p2 = realloc(c->ph, (size_t)cap * sizeof(int));
        double *x2 = realloc(c->x, (size_t)cap * c->ne * sizeof(double));
        double *g2 = realloc(c->g, (size_t)cap * sizeof(double));
        double *z2 = realloc(c->z, (size_t)cap * c->nzmax * sizeof(double));
        if (!p2 || !x2 || !g2 || !z2) {
            if (p2) c->ph = p2;
            if (x2) c->x = x2;
            if (g2) c->g = g2;
            if (z2) c->z = z2;
            return -1;
        }
        c->ph = p2; c->x = x2; c->g = g2; c->z = z2; c->cap = cap;
    }
    c->ph[c->n] = ph;
    memcpy(c->x + (size_t)c->n * c->ne, x, (size_t)c->ne * sizeof(double));
    c->g[c->n] = g;
    memset(c->z + (size_t)c->n * c->nzmax, 0, (size_t)c->nzmax * sizeof(double));
    if (nz) memcpy(c->z + (size_t)c->n * c->nzmax, z, (size_t)nz * sizeof(double));
    c->n++;
    return 0;
}

/* ------------------------------------------------------------------ *
 * Linear program: min c.n subject to A n = b, n >= 0 (revised simplex, two phases,
 * Dantzig pricing with Bland's rule once steps stall). A is column-major, m rows.
 * ------------------------------------------------------------------ */
#define LP_PIV 1e-9         /* smallest pivot element the ratio test accepts */
#define LP_FEAS 1e-12       /* amount a basic variable may go below zero in a step */

static int invert(int m, double *M, double *inv)
{
    for (int i = 0; i < m * m; ++i) inv[i] = 0.0;
    for (int i = 0; i < m; ++i) inv[i * m + i] = 1.0;
    for (int col = 0; col < m; ++col) {
        int piv = col;
        for (int r = col + 1; r < m; ++r)
            if (fabs(M[r * m + col]) > fabs(M[piv * m + col])) piv = r;
        if (fabs(M[piv * m + col]) < 1e-14) return -1;
        if (piv != col)
            for (int k = 0; k < m; ++k) {
                double t = M[col * m + k]; M[col * m + k] = M[piv * m + k]; M[piv * m + k] = t;
                t = inv[col * m + k]; inv[col * m + k] = inv[piv * m + k]; inv[piv * m + k] = t;
            }
        double p = M[col * m + col];
        for (int k = 0; k < m; ++k) { M[col * m + k] /= p; inv[col * m + k] /= p; }
        for (int r = 0; r < m; ++r) {
            if (r == col) continue;
            double f = M[r * m + col];
            if (f == 0.0) continue;
            for (int k = 0; k < m; ++k) { M[r * m + k] -= f * M[col * m + k]; inv[r * m + k] -= f * inv[col * m + k]; }
        }
    }
    return 0;
}

typedef struct {
    int m, N;
    const double *A, *c, *b;
    int *basis;             /* m entries, index < N real, >= N artificial */
    double *Binv, *xb, *y;
} Lp;

static const double *lp_col(const Lp *L, int j, double *tmp)
{
    if (j < L->N) return L->A + (size_t)j * L->m;
    for (int i = 0; i < L->m; ++i) tmp[i] = (i == j - L->N) ? 1.0 : 0.0;
    return tmp;
}

static int lp_refactor(Lp *L, double *work, double *tmp)
{
    const int m = L->m;
    for (int i = 0; i < m; ++i) {
        const double *col = lp_col(L, L->basis[i], tmp);
        for (int r = 0; r < m; ++r) work[r * m + i] = col[r];
    }
    if (invert(m, work, L->Binv)) return -1;
    for (int r = 0; r < m; ++r) {
        double s = 0.0;
        for (int k = 0; k < m; ++k) s += L->Binv[r * m + k] * L->b[k];
        L->xb[r] = s;
    }
    return 0;
}

/* The optimum read from a fresh factorization. Amounts updated pivot by pivot carry the
 * rounding of every update since the last refactor (2e-7 in a mass balance after a long
 * run of pivots); a refactor plus one step of iterative refinement removes it, and the
 * duals are recomputed from the same inverse. */
static int lp_finish(Lp *L, double *work, double *tmp)
{
    const int m = L->m, N = L->N;
    if (lp_refactor(L, work, tmp)) return -1;
    double *res = work;                         /* the factorization is no longer needed */
    for (int i = 0; i < m; ++i) res[i] = L->b[i];
    for (int r = 0; r < m; ++r) {
        const double *col = lp_col(L, L->basis[r], tmp);
        for (int i = 0; i < m; ++i) res[i] -= col[i] * L->xb[r];
    }
    for (int r = 0; r < m; ++r) {
        double s = 0.0;
        for (int k = 0; k < m; ++k) s += L->Binv[r * m + k] * res[k];
        L->xb[r] += s;
    }
    for (int i = 0; i < m; ++i) {
        double s = 0.0;
        for (int r = 0; r < m; ++r) {
            const int j = L->basis[r];
            s += (j >= N ? 0.0 : L->c[j]) * L->Binv[r * m + i];
        }
        L->y[i] = s;
    }
    return 0;
}

/* phase 1 when phase1 != 0 (artificial cost 1, real 0), else phase 2 (artificials barred) */
static int lp_iterate(Lp *L, int phase1, double *d, double *tmp, double *work)
{
    const int m = L->m, N = L->N;
    int stall = 0;
    double obj_prev = INFINITY;
    for (int it = 0; it < 50000; ++it) {
        for (int i = 0; i < m; ++i) {
            double s = 0.0;
            for (int r = 0; r < m; ++r) {
                int j = L->basis[r];
                double cj = phase1 ? (j >= N ? 1.0 : 0.0) : (j >= N ? 0.0 : L->c[j]);
                s += cj * L->Binv[r * m + i];
            }
            L->y[i] = s;
        }
        double scale = 1.0;
        if (!phase1) for (int j = 0; j < N; ++j) if (fabs(L->c[j]) > scale) scale = fabs(L->c[j]);
        const double tol = 1e-11 * scale;
        int enter = -1;
        double best = -tol;
        for (int j = 0; j < N; ++j) {
            /* a basic column's reduced cost is zero up to drift in Binv; pricing it lets
             * it re-enter in its own place, a pivot that changes nothing, forever */
            int basic = 0;
            for (int r = 0; r < m; ++r) if (L->basis[r] == j) { basic = 1; break; }
            if (basic) continue;
            const double *a = L->A + (size_t)j * m;
            double r = (phase1 ? 0.0 : L->c[j]);
            for (int i = 0; i < m; ++i) r -= L->y[i] * a[i];
            if (stall > 30) { if (r < -tol) { enter = j; best = r; break; } }
            else if (r < best) { best = r; enter = j; }
        }
        if (enter < 0) return 0;
        const double *a = L->A + (size_t)enter * m;
        for (int r = 0; r < m; ++r) {
            double s = 0.0;
            for (int k = 0; k < m; ++k) s += L->Binv[r * m + k] * a[k];
            d[r] = s;
        }
        int leave = -1;
        /* In phase 2 an artificial left in the basis sits at zero (a row the others make
         * redundant, e.g. oxygen fixed by charge balance). It must stay at zero, so any
         * entering column that would move it, either way, pivots it out now. */
        for (int r = 0; r < m && !phase1; ++r)
            if (L->basis[r] >= N && fabs(d[r]) > LP_PIV) { leave = r; break; }
        if (leave < 0) {
            /* Harris's two-pass ratio test: the longest step that keeps every amount above
             * -LP_FEAS, then, among the rows that bound it, the largest pivot element (the
             * lowest basis index once Bland's rule is on), never one below LP_PIV. A pivot
             * of 1e-11 once wrecked the inverse until the simplex reported an unbounded
             * direction, which no set of positive columns has. */
            double theta = INFINITY;
            for (int r = 0; r < m; ++r)
                if (d[r] > LP_PIV) theta = fmin(theta, (fmax(L->xb[r], 0.0) + LP_FEAS) / d[r]);
            for (int r = 0; r < m; ++r) {
                if (!(d[r] > LP_PIV) || fmax(L->xb[r], 0.0) / d[r] > theta) continue;
                if (leave < 0 || (stall > 30 ? L->basis[r] < L->basis[leave] : d[r] > d[leave])) leave = r;
            }
        }
        if (leave < 0) return -2;           /* unbounded: cannot happen with positive columns */
        /* The basis has as many rows as elements, so a fresh inverse every pivot costs
         * little and leaves no update error to build up. */
        L->basis[leave] = enter;
        if (lp_refactor(L, work, tmp)) return -3;
        /* A pivot is progress only if the objective, read from the fresh inverse, drops
         * beyond rounding; a predicted drop can be noise. Thousands of pivots in a row
         * without one are a degenerate vertex walked in that noise, and this basis is
         * then the optimum. */
        double obj = 0.0;
        for (int r = 0; r < m; ++r) {
            const int j = L->basis[r];
            obj += (phase1 ? (j >= N ? 1.0 : 0.0) : (j >= N ? 0.0 : L->c[j])) * L->xb[r];
        }
        stall = (obj_prev - obj > 1e-12 * scale) ? 0 : stall + 1;
        obj_prev = obj;
        if (stall > 2000) return 0;
    }
    return -4;
}

static int lp_solve(Lp *L)
{
    const int m = L->m;
    double *d = malloc((size_t)m * sizeof(double));
    double *tmp = malloc((size_t)m * sizeof(double));
    double *work = malloc((size_t)m * m * sizeof(double));
    int rc = -5;
    if (!d || !tmp || !work) goto out;
    for (int i = 0; i < m; ++i) L->basis[i] = L->N + i;
    if (lp_refactor(L, work, tmp)) goto out;
    rc = lp_iterate(L, 1, d, tmp, work);
    if (rc) goto out;
    double art = 0.0;
    for (int r = 0; r < m; ++r) if (L->basis[r] >= L->N) art += L->xb[r];
    if (art > 1e-9) { rc = -6; goto out; }        /* bulk composition out of reach */
    /* pivot zero-level artificials out where a real column can take their place */
    for (int r = 0; r < m; ++r) {
        if (L->basis[r] < L->N) continue;
        for (int j = 0; j < L->N; ++j) {
            int in_basis = 0;
            for (int q = 0; q < m; ++q) if (L->basis[q] == j) in_basis = 1;
            if (in_basis) continue;
            const double *a = L->A + (size_t)j * m;
            double dr = 0.0;
            for (int k = 0; k < m; ++k) dr += L->Binv[r * m + k] * a[k];
            if (fabs(dr) > 1e-9) {
                L->basis[r] = j;
                if (lp_refactor(L, work, tmp)) { rc = -3; goto out; }
                break;
            }
        }
    }
    rc = lp_iterate(L, 0, d, tmp, work);
    if (!rc && lp_finish(L, work, tmp)) rc = -3;
out:
    free(d); free(tmp); free(work);
    return rc;
}

/* ------------------------------------------------------------------ *
 * Driving-force minimization over the simplex-mapped variables
 * ------------------------------------------------------------------ */
typedef struct {
    const Sys *S;
    const Ph *h;
    const double *mu;       /* per element, 0 for absent elements */
    const int *active;      /* element present in the bulk */
    double *y, *x;
} DfCtx;

static double df_value(DfCtx *c, const double *z)
{
    unpack(c->h, z, c->y);
    double g = ph_eval(c->S, c->h, c->y, c->x);
    if (!isfinite(g)) return INFINITY;
    double v = g;
    for (int e = 0; e < c->S->n_el; ++e) {
        if (!c->active[e]) {
            if (c->x[e] > 1e-14) return INFINITY;   /* holds an element the bulk lacks */
            continue;
        }
        v -= c->mu[e] * c->x[e];
    }
    return v;
}

/* Quasi-Newton (BFGS) descent of the driving-force function with central-difference
 * gradients. Far fewer evaluations than the simplex, which matters for the MQMQA
 * liquid where each evaluation is an internal equilibrium. Returns the final value. */
static double bfgs(DfCtx *c, double *z, int n, int max_iter)
{
    if (n == 0) return df_value(c, z);
    double *H = malloc((size_t)n * n * sizeof(double));
    double *g = malloc((size_t)n * sizeof(double));
    double *g1 = malloc((size_t)n * sizeof(double));
    double *p = malloc((size_t)n * sizeof(double));
    double *z1 = malloc((size_t)n * sizeof(double));
    double *s = malloc((size_t)n * sizeof(double));
    double *yv = malloc((size_t)n * sizeof(double));
    double f = INFINITY;
    if (!H || !g || !g1 || !p || !z1 || !s || !yv) goto out;
    const double h = 1e-6;
    f = df_value(c, z);
    if (!isfinite(f)) goto out;
#define GRAD(zz, out_) do { for (int a = 0; a < n; ++a) { double z0 = (zz)[a]; \
        (zz)[a] = z0 + h; double fp = df_value(c, (zz)); (zz)[a] = z0 - h; double fm = df_value(c, (zz)); \
        (zz)[a] = z0; (out_)[a] = (isfinite(fp) && isfinite(fm)) ? (fp - fm) / (2 * h) : 0.0; } } while (0)
    GRAD(z, g);
    for (int a = 0; a < n * n; ++a) H[a] = 0.0;
    double gn = 0.0;
    for (int a = 0; a < n; ++a) gn += g[a] * g[a];
    const double h0 = 1.0 / (sqrt(gn) + 1.0);      /* first step of unit length, roughly */
    for (int a = 0; a < n; ++a) H[a * n + a] = h0;
    for (int it = 0; it < max_iter; ++it) {
        for (int a = 0; a < n; ++a) {
            double v = 0.0;
            for (int b = 0; b < n; ++b) v -= H[a * n + b] * g[b];
            p[a] = v;
        }
        double slope = 0.0;
        for (int a = 0; a < n; ++a) slope += g[a] * p[a];
        if (!(slope < 0.0)) {                        /* not a descent direction: reset */
            for (int a = 0; a < n * n; ++a) H[a] = 0.0;
            for (int a = 0; a < n; ++a) { H[a * n + a] = h0; p[a] = -h0 * g[a]; }
            slope = 0.0;
            for (int a = 0; a < n; ++a) slope += g[a] * p[a];
            if (!(slope < 0.0)) break;
        }
        double alpha = 1.0, f1 = INFINITY;
        for (int ls = 0; ls < 30; ++ls, alpha *= 0.5) {
            for (int a = 0; a < n; ++a) z1[a] = z[a] + alpha * p[a];
            f1 = df_value(c, z1);
            if (f1 <= f + 1e-4 * alpha * slope) break;
        }
        if (!(f1 < f)) break;
        GRAD(z1, g1);
        double sy = 0.0;
        for (int a = 0; a < n; ++a) { s[a] = z1[a] - z[a]; yv[a] = g1[a] - g[a]; sy += s[a] * yv[a]; }
        memcpy(z, z1, (size_t)n * sizeof(double));
        memcpy(g, g1, (size_t)n * sizeof(double));
        double drop = f - f1;
        f = f1;
        if (drop < 1e-11 * (1.0 + fabs(f))) break;
        if (sy > 1e-16) {                            /* BFGS inverse-Hessian update */
            double *Hy = p;                          /* reuse p as scratch */
            for (int a = 0; a < n; ++a) {
                double v = 0.0;
                for (int b = 0; b < n; ++b) v += H[a * n + b] * yv[b];
                Hy[a] = v;
            }
            double yHy = 0.0;
            for (int a = 0; a < n; ++a) yHy += yv[a] * Hy[a];
            for (int a = 0; a < n; ++a)
                for (int b = 0; b < n; ++b)
                    H[a * n + b] += ((sy + yHy) * s[a] * s[b]) / (sy * sy)
                                    - (Hy[a] * s[b] + s[a] * Hy[b]) / sy;
        }
    }
#undef GRAD
out:
    free(H); free(g); free(g1); free(p); free(z1); free(s); free(yv);
    return f;
}

/* Search solution phase i for points below the plane mu: an MQMQA phase directly over its
 * quadruplet fractions with the composition free (which replaces a descent whose every
 * step is a fixed-composition internal equilibrium), any other phase by BFGS from its
 * lowest candidates and its basic columns. An MQMQA phase holding an element the bulk lacks
 * is searched without those ions. Lowers *worst to the most negative driving force found; with add
 * set, every point below -GEM_TOL becomes a column. Returns the number of columns added,
 * or -1 on failure. */
static int search_phase(const Sys *S, Cols *C, int i, const double *mu, const int *active,
                        const int *basis, int m, int add, double *worst)
{
    const Ph *h = &S->ph[i];
    const int ne = S->n_el;
    int ytot = 0;
    for (int s = 0; s < h->n_simp; ++s) ytot += h->simp_n[s];
    double *yy = malloc((size_t)ytot * sizeof(double));
    double *xx = malloc((size_t)ne * sizeof(double));
    double *zz = malloc((size_t)(h->nz + 1) * sizeof(double));
    double *ym = malloc((size_t)GEM_KMIN * ytot * sizeof(double));
    int added = -1;
    if (!yy || !xx || !zz || !ym) goto out;
    added = 0;
    if (h->kind == PH_MQMQA) {
        double gm[GEM_KMIN], dfm[GEM_KMIN];
        int nm = mqmqa_driving_force_db(S->db, h->tag, S->T, mu, h->off ? S->active : NULL,
                                        GEM_KMIN, ym, gm, dfm);
        if (nm < 0) { added = -1; goto out; }
        for (int k = 0; k < nm; ++k) {
            if (dfm[k] < *worst) *worst = dfm[k];
            if (!add || !(dfm[k] < -GEM_TOL)) continue;
            const double *yk = ym + (size_t)k * ytot;
            if (mq_x_of_y(h, ne, yk, xx)) continue;
            logits(yk, h->simp_n[0], zz);
            logits(yk + h->simp_n[0], h->simp_n[1], zz + h->simp_n[0] - 1);
            if (cols_add(C, i, xx, gm[k], zz, h->nz)) { added = -1; goto out; }
            added++;
        }
        goto out;
    }
    /* starts: the two lowest candidates of distinct composition, and basic columns; a
     * phase whose best point sits far above the plane is skipped */
    const double window = 0.5 * mqmqa_db_R(S->db) * S->T;
    DfCtx ctx = { S, h, mu, active, yy, xx };
    int starts[8], ns = 0;
    double v1 = INFINITY, v2 = INFINITY;
    int k1 = -1, k2 = -1;
    for (int k = 0; k < C->n; ++k) {
        if (C->ph[k] != i) continue;
        double v = C->g[k];
        for (int e = 0; e < ne; ++e) v -= mu[e] * C->x[(size_t)k * ne + e];
        if (v < v1) { v2 = v1; k2 = k1; v1 = v; k1 = k; }
        else if (v < v2) {
            double dx = 0.0;
            for (int e = 0; e < ne; ++e)
                dx = fmax(dx, fabs(C->x[(size_t)k * ne + e] - C->x[(size_t)k1 * ne + e]));
            if (dx > 0.05) { v2 = v; k2 = k; }
        }
    }
    if (k1 < 0 || v1 > window) goto out;
    starts[ns++] = k1;
    if (k2 >= 0 && v2 < window) starts[ns++] = k2;
    for (int r = 0; r < m && ns < 8; ++r) {
        int k = basis[r], dup = 0;
        if (k >= C->n || C->ph[k] != i) continue;
        for (int q = 0; q < ns; ++q) if (starts[q] == k) dup = 1;
        if (!dup) starts[ns++] = k;
    }
    for (int s = 0; s < ns; ++s) {
        memcpy(zz, C->z + (size_t)starts[s] * C->nzmax, (size_t)h->nz * sizeof(double));
        double v = bfgs(&ctx, zz, h->nz, 80);
        if (v < *worst) *worst = v;
        if (add && v < -GEM_TOL) {
            unpack(h, zz, yy);
            double g = ph_eval(S, h, yy, xx);
            if (cols_add(C, i, xx, g, zz, h->nz)) { added = -1; goto out; }
            added++;
        }
    }
out:
    free(yy); free(xx); free(zz); free(ym);
    return added;
}

/* Lowers *worst to how far the plane mu is from supporting the hull: the most negative
 * driving force of any phase against it, or the largest gap between it and a stable column
 * (a plane passing under the stable phases has nothing below it either). -1 on failure. */
static int certify(const Sys *S, Cols *C, const double *mu, const int *active,
                   const int *basis, const double *xb, int m, double *worst)
{
    const int ne = S->n_el;
    for (int i = 0; i < S->n_ph; ++i)
        if (S->ph[i].kind != PH_STOICH && search_phase(S, C, i, mu, active, basis, m, 0, worst) < 0)
            return -1;
    for (int k = 0; k < C->n; ++k) {
        if (S->ph[C->ph[k]].kind != PH_STOICH) continue;
        double v = C->g[k];
        for (int e = 0; e < ne; ++e) v -= mu[e] * C->x[(size_t)k * ne + e];
        if (v < *worst) *worst = v;
    }
    for (int r = 0; r < m; ++r) {
        if (basis[r] >= C->n || xb[r] < GEM_AMT_MIN) continue;
        double v = C->g[basis[r]];
        for (int e = 0; e < ne; ++e) v -= mu[e] * C->x[(size_t)basis[r] * ne + e];
        if (-fabs(v) < *worst) *worst = -fabs(v);
    }
    return 0;
}

/* ------------------------------------------------------------------ *
 * Sampling
 * ------------------------------------------------------------------ */
static unsigned long long rng_state = 88172645463325252ULL;
static double rng_u(void)
{
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 7; rng_state ^= rng_state << 17;
    return (double)(rng_state >> 11) / 9007199254740992.0;
}

/* all compositions of `grid` units over n parts (stars and bars), visited recursively */
static void grid_simplex(int n, int grid, int depth, int left, int *cnt, double *buf,
                         double *out, int *n_out, int cap)
{
    if (*n_out >= cap) return;
    if (depth == n - 1) {
        cnt[depth] = left;
        for (int i = 0; i < n; ++i) out[*n_out * n + i] = (double)cnt[i] / grid;
        (*n_out)++;
        return;
    }
    for (int k = 0; k <= left; ++k) {
        cnt[depth] = k;
        grid_simplex(n, grid, depth + 1, left - k, cnt, buf, out, n_out, cap);
    }
}

/* Points on one simplex of n parts, n*count of them in *out. The whole grid when it fits
 * under the cap. Past the cap the grid is not cut short: listing it in order and stopping
 * kept one corner only, and a 29-species gas never had a point near H2 (Thermochimica
 * TestThermo55). Instead the corners, points where one part holds 90, 99 or 99.9%, the
 * midpoints of every pair, then uniform random points up to the cap. Corners come first. */
static int simplex_points(int n, int grid, double **out)
{
    long long cnt = 1;
    for (int k = 1; k < n && cnt <= GEM_MAX_SAMPLES; ++k) cnt = cnt * (grid + k) / k;
    if (cnt <= GEM_MAX_SAMPLES) {
        *out = malloc((size_t)cnt * n * sizeof(double));
        int tmp[64], got = 0;
        if (!*out) return -1;
        grid_simplex(n, grid, 0, grid, tmp, NULL, *out, &got, (int)cnt);
        return got;
    }
    double *p = *out = malloc((size_t)GEM_MAX_SAMPLES * n * sizeof(double));
    if (!p) return -1;
    int m = 0;
    static const double dom[3] = { 0.9, 0.99, 0.999 };
    for (int i = 0; i < n; ++i, ++m)
        for (int k = 0; k < n; ++k) p[(size_t)m * n + k] = k == i;
    for (int d = 0; d < 3; ++d)
        for (int i = 0; i < n && m < GEM_MAX_SAMPLES; ++i, ++m)
            for (int k = 0; k < n; ++k) p[(size_t)m * n + k] = k == i ? dom[d] : (1.0 - dom[d]) / (n - 1);
    if (m + n * (n - 1) / 2 <= GEM_MAX_SAMPLES / 2)
        for (int i = 0; i < n; ++i)
            for (int j = i + 1; j < n; ++j, ++m)
                for (int k = 0; k < n; ++k) p[(size_t)m * n + k] = (k == i || k == j) ? 0.5 : 0.0;
    for (; m < GEM_MAX_SAMPLES; ++m) {
        double sum = 0.0;
        for (int k = 0; k < n; ++k) sum += p[(size_t)m * n + k] = -log(1.0 - rng_u());
        for (int k = 0; k < n; ++k) p[(size_t)m * n + k] /= sum;
    }
    return m;
}

static int sample_phase(const Sys *S, int hi, int grid, Cols *C, int *active)
{
    const Ph *h = &S->ph[hi];
    const int ne = S->n_el;
    double *x = malloc((size_t)ne * sizeof(double));
    int ytot = 0;
    for (int s = 0; s < h->n_simp; ++s) ytot += h->simp_n[s];
    double *y = malloc((size_t)(ytot + 1) * sizeof(double));
    double *z = malloc((size_t)(h->nz + 1) * sizeof(double));
    /* per-simplex point sets, combined as a product, randomized past the cap */
    double *grids[64] = {0};
    int ng[64] = {0};
    long long total = 1, corners = 1;
    int rc = 0;
    if (!x || !y || !z || h->n_simp > 64) { rc = -1; goto out; }
    for (int s = 0; s < h->n_simp; ++s) {
        int n = h->simp_n[s];
        if (n > 64) { rc = -1; goto out; }
        int got = simplex_points(n, n == 1 ? 1 : grid, &grids[s]);
        if (got < 0) { rc = -1; goto out; }
        ng[s] = got;
        if (total <= GEM_MAX_SAMPLES) total *= got;
        if (corners <= GEM_MAX_SAMPLES) corners *= n;
    }
    /* past the cap, every endmember first (when they fit in half of it), then random picks */
    const int big = total > GEM_MAX_SAMPLES;
    const long long n_corner = big && corners <= GEM_MAX_SAMPLES / 2 ? corners : 0;
    const long long want = big ? GEM_MAX_SAMPLES : total;
    for (long long t = 0; t < want; ++t) {
        long long idx = t;
        int yo = 0;
        for (int s = 0; s < h->n_simp; ++s) {
            int n = h->simp_n[s], pick;
            if (!big) { pick = (int)(idx % ng[s]); idx /= ng[s]; }
            else if (t < n_corner) { pick = -1 - (int)(idx % n); idx /= n; }
            else pick = (int)(rng_u() * ng[s]);
            for (int k = 0; k < n; ++k) {
                double v = pick < 0 ? (k == -1 - pick) : grids[s][(size_t)pick * n + k];
                y[yo + k] = v < 1e-9 ? 1e-9 : v;   /* keep logs finite, logits defined */
            }
            double sum = 0.0;
            for (int k = 0; k < n; ++k) sum += y[yo + k];
            for (int k = 0; k < n; ++k) y[yo + k] /= sum;
            yo += n;
        }
        if (h->off && drop_off(h, y)) continue;
        double g = ph_eval(S, h, y, x);
        int ok = isfinite(g);
        for (int e = 0; ok && e < ne; ++e) if (!active[e] && x[e] > 1e-12) ok = 0;
        if (!ok) continue;
        int zo = 0;
        yo = 0;
        for (int s = 0; s < h->n_simp; ++s) {
            int n = h->simp_n[s];
            if (n > 1) logits(y + yo, n, z + zo);
            zo += n - 1;
            yo += n;
        }
        if (cols_add(C, hi, x, g, z, h->nz)) { rc = -1; goto out; }
    }
out:
    for (int s = 0; s < 64; ++s) free(grids[s]);
    free(x); free(y); free(z);
    return rc;
}

/* The MQMQA phase at the bulk composition itself, added as a column when it lies below the
 * hull value `above`; 1 when added. Where a compound melts congruently the liquid and the
 * solid share one composition, so a trace element carried by the liquid alone leaves its
 * potential free; the duals picked one 3 MJ/mol off at Mg2SiO4 with 1e-4 Fe, and against that
 * plane the driving-force search missed the liquid at the bulk 77 J/mol below the liquid +
 * olivine hull. A state at the bulk is always reachable, so the hull must not end above it.
 * It is a final check, not a starting column: a column covering the bulk alone made the first
 * bases degenerate and left the search one liquid short beside cristobalite (0.4 J/mol, FeO-
 * MgO-SiO2 at 1949 K). Needs each ion to carry an element no other ion carries. */
static int bulk_column(const Sys *S, int hi, const double *bn, Cols *C, double above)
{
    const Ph *h = &S->ph[hi];
    const int ne = S->n_el, nc = h->simp_n[0], na = h->simp_n[1], ni = nc + na;
    if (h->kind != PH_MQMQA || ni > 128 || ne > 64) return 0;
    double y[128], z[128], x[64];
    for (int i = 0; i < ni; ++i) {
        int own = -1;
        for (int e = 0; e < ne && own != -2; ++e) {
            if (!(h->con_el[i * ne + e] > 0.0)) continue;
            int shared = 0;
            for (int k = 0; k < ni; ++k) if (k != i && h->con_el[k * ne + e] > 0.0) shared = 1;
            if (!shared) own = own < 0 ? e : -2;
        }
        if (own < 0) return 0;
        y[i] = bn[own] / h->con_el[i * ne + own];
    }
    for (int s = 0, o = 0; s < 2; o += h->simp_n[s], ++s) {
        double sum = 0.0;
        for (int i = o; i < o + h->simp_n[s]; ++i) sum += y[i];
        if (!(sum > 0.0)) return 0;
        for (int i = o; i < o + h->simp_n[s]; ++i) y[i] /= sum;
    }
    if (mq_x_of_y(h, ne, y, x)) return 0;
    for (int e = 0; e < ne; ++e) if (fabs(x[e] - bn[e]) > 1e-12) return 0;
    const double g = ph_eval(S, h, y, x);
    if (!isfinite(g)) return 0;
    for (int e = 0; e < ne; ++e) if (fabs(x[e] - bn[e]) > 1e-9) return 0;
    if (!(g < above)) return 0;
    logits(y, nc, z);
    logits(y + nc, na, z + nc - 1);
    return cols_add(C, hi, x, g, z, h->nz) ? -1 : 1;
}

/* ------------------------------------------------------------------ *
 * Result
 * ------------------------------------------------------------------ */
struct mqmqa_gem {
    int n_el, n_sets, passes;
    int exact;              /* 1 when the exact finish solved the conditions */
    int *phase;
    double *amount, *x, *mu;
    double G, residual;
};

static void free_sys(Sys *S)
{
    for (int i = 0; i < S->n_ph; ++i) {
        if (S->ph[i].face) ((Phase *)&S->d->phases[S->ph[i].tag])->ion_off = NULL;
        free(S->ph[i].con_el); free(S->ph[i].ion_q); free(S->ph[i].off);
    }
    free(S->ph);
}

/* Mark the constituents holding an element the bulk lacks. 1 when a sublattice is left
 * with none, so the phase cannot form here; -1 when out of memory. */
static int mark_off(Ph *h, const int *active, int ne)
{
    int n = 0;
    for (int s = 0; s < h->n_simp; ++s) n += h->simp_n[s];
    int any = 0;
    for (int s = 0, o = 0; s < h->n_simp; o += h->simp_n[s], ++s) {
        int kept = 0;
        for (int i = o; i < o + h->simp_n[s]; ++i) {
            int out = 0;
            for (int e = 0; e < ne; ++e) if (!active[e] && h->con_el[(size_t)i * ne + e] != 0.0) out = 1;
            any |= out;
            kept += !out;
        }
        if (!kept) return 1;
    }
    if (!any) return 0;
    h->off = calloc((size_t)n, sizeof(int));
    if (!h->off) return -1;
    for (int i = 0; i < n; ++i)
        for (int e = 0; e < ne; ++e)
            if (!active[e] && h->con_el[(size_t)i * ne + e] != 0.0) h->off[i] = 1;
    return 0;
}

/* An ionic liquid whose cations are all absent still exists as a liquid of neutrals: with
 * only neutrals on the second sublattice P = 0, the cation sites vanish and the phase is the
 * neutrals alone (Sundman, Calphad 15 (1991) 109), pure Te in a Cs-Te liquid. The first cation
 * is kept as a placeholder holding no atoms, every anion and the vacancy are held at zero.
 * 1 when no neutral of a present element is left either; -1 when out of memory. */
static int ionic_neutrals_only(Ph *h, const IonicPhase *io, const int *active, int ne)
{
    const int ni = io->nc + io->na;
    int kept = 0;
    for (int i = io->nc; i < ni; ++i) {
        if (io->type[i] != 'B') continue;
        int out = 0;
        for (int e = 0; e < ne; ++e) if (!active[e] && h->con_el[(size_t)i * ne + e] != 0.0) out = 1;
        kept += !out;
    }
    if (!kept) return 1;
    free(h->off);
    h->off = calloc((size_t)ni, sizeof(int));
    if (!h->off) return -1;
    for (int i = 1; i < ni; ++i) {
        int out = i < io->nc || io->type[i] != 'B';
        for (int e = 0; e < ne && !out; ++e) if (!active[e] && h->con_el[(size_t)i * ne + e] != 0.0) out = 1;
        h->off[i] = out;
    }
    return 0;
}

static int setup_phases(Sys *S, const int *suspended, int *active)
{
    const Db *d = S->d;
    const int ne = d->n_el;
    S->ph = calloc((size_t)(d->n_phases + d->n_stoich), sizeof(Ph));
    if (!S->ph) return -1;
    for (int p = 0; p < d->n_phases; ++p) {
        if (suspended && suspended[p]) continue;
        const Phase *P = &d->phases[p];
        Ph *h = &S->ph[S->n_ph];
        h->tag = p;
        if (P->kind == 1 && P->cef) {
            const SublPhase *cf = P->cef;
            if (cf->n_subl > 64) { mqmqa_db_set_error("phase %s: too many sublattices", P->name); return -1; }
            h->kind = PH_CEF;
            h->n_simp = cf->n_subl;
            h->con_el = calloc((size_t)cf->n_con * ne, sizeof(double));
            if (!h->con_el) return -1;
            for (int c = 0; c < cf->n_con; ++c)
                if (name_to_el(d, cf->con_name[c], h->con_el + (size_t)c * ne)) {
                    mqmqa_db_set_error("phase %s: constituent %s is not an element or declared species",
                                       P->name, cf->con_name[c]);
                    return -1;
                }
            for (int s = 0; s < cf->n_subl; ++s) { h->simp_n[s] = cf->subl_ncon[s]; h->nz += cf->subl_ncon[s] - 1; }
            const int dead = mark_off(h, active, ne);
            if (dead < 0) return -1;
            if (dead) { free(h->con_el); memset(h, 0, sizeof(*h)); continue; }
        } else if (P->kind == 2 && P->ion) {
            const IonicPhase *io = P->ion;
            h->kind = PH_IONIC;
            h->n_simp = 2;
            h->simp_n[0] = io->nc;
            h->simp_n[1] = io->na;
            h->nz = io->nc - 1 + io->na - 1;
            h->con_el = calloc((size_t)(io->nc + io->na) * ne, sizeof(double));
            if (!h->con_el) return -1;
            memcpy(h->con_el, io->comp, (size_t)(io->nc + io->na) * ne * sizeof(double));
            int dead = mark_off(h, active, ne);
            if (dead > 0) dead = ionic_neutrals_only(h, io, active, ne);
            if (dead < 0) return -1;
            if (dead) { free(h->con_el); memset(h, 0, sizeof(*h)); continue; }
        } else if (P->kind == 0) {
            const char *why = mqmqa_ph_excess_unsupported(S->db, p);
            if (why) { mqmqa_db_set_error("%s (suspend the phase to compute without it)", why); return -1; }
            h->kind = PH_MQMQA;
            h->n_simp = 2;
            h->simp_n[0] = P->n_cat;
            h->simp_n[1] = P->n_an;
            h->nz = P->n_cat - 1 + P->n_an - 1;
            int ni = P->n_cat + P->n_an;
            h->con_el = calloc((size_t)ni * ne, sizeof(double));
            h->ion_q = calloc((size_t)ni, sizeof(double));
            if (!h->con_el || !h->ion_q) return -1;
            /* element amounts of each ion: from its name, as a vacancy, or from the pairs */
            if (mqmqa_ph_ion_comps(d, p, h->con_el)) return -1;
            for (int i = 0; i < ni; ++i)
                h->ion_q[i] = fabs(i < P->n_cat ? P->cat_charge[i] : P->an_charge[i - P->n_cat]);
            /* ions of an element the bulk lacks are taken out of the phase */
            const int dead = mark_off(h, active, ne);
            if (dead < 0) return -1;
            if (dead) { free(h->con_el); free(h->ion_q); memset(h, 0, sizeof(*h)); continue; }
        } else {
            continue;
        }
        S->n_ph++;
    }
    for (int j = 0; j < d->n_stoich; ++j) {
        if (suspended && suspended[d->n_phases + j]) continue;
        Ph *h = &S->ph[S->n_ph++];
        h->kind = PH_STOICH;
        h->tag = -(j + 1);
    }
    return 0;
}

/* Chemical potentials from the stable phases themselves. At a degenerate optimum (one
 * phase, or fewer phases than elements) the linear program's duals are only one of many
 * supporting planes. The equilibrium plane is the one tangent to every stable phase:
 * g = mu.x at each stable column, and dg = mu.dx along each internal direction of a
 * stable solution phase (central differences). Solved by least squares for a correction
 * to the duals, with a small ridge so a direction the conditions leave open (an element
 * tied to others by charge balance) keeps its dual value. */
static int polish_mu(const Sys *S, const Cols *C, const int *basis, const double *xb, int m,
                     const int *row_el, double *mu)
{
    const int ne = S->n_el;
    int cap = 0;
    for (int r = 0; r < m; ++r)
        if (basis[r] < C->n && xb[r] > 1e-12) {
            const Ph *h = &S->ph[C->ph[basis[r]]];
            cap += 1 + (h->kind == PH_MQMQA ? mqmqa_num_quadruplets(h->simp_n[0], h->simp_n[1]) : h->nz);
        }
    if (cap == 0) return 0;
    double *J = calloc((size_t)cap * m, sizeof(double));
    double *res = calloc((size_t)cap, sizeof(double));
    double *N = calloc((size_t)m * m, sizeof(double));
    double *Ninv = malloc((size_t)m * m * sizeof(double));
    double *rhs = calloc((size_t)m, sizeof(double));
    int ytot_max = 0;
    for (int i = 0; i < S->n_ph; ++i) {
        int t = 0;
        for (int s = 0; s < S->ph[i].n_simp; ++s) t += S->ph[i].simp_n[s];
        if (t > ytot_max) ytot_max = t;
    }
    double *z = malloc((size_t)(C->nzmax + 1) * sizeof(double));
    double *y = malloc((size_t)(ytot_max + 1) * sizeof(double));
    double *xp = malloc((size_t)ne * sizeof(double));
    double *xm = malloc((size_t)ne * sizeof(double));
    int rc = -1, nr = 0;
    if (!J || !res || !N || !Ninv || !rhs || !z || !y || !xp || !xm) goto out;
    for (int r = 0; r < m; ++r) {
        int k = basis[r];
        if (k >= C->n || xb[r] <= 1e-12) continue;
        /* A negligible column of a phase that also holds a real amount is a leftover of a
         * degenerate basis at another composition, not a point the plane must touch. */
        if (xb[r] < GEM_AMT_MIN) {
            int major = 0;
            for (int q = 0; q < m && !major; ++q)
                major = basis[q] < C->n && C->ph[basis[q]] == C->ph[k] && xb[q] >= GEM_AMT_MIN;
            if (major) continue;
        }
        const Ph *h = &S->ph[C->ph[k]];
        const double *xk = C->x + (size_t)k * ne;
        for (int q = 0; q < m; ++q) J[(size_t)nr * m + q] = xk[row_el[q]];
        res[nr] = C->g[k];
        for (int q = 0; q < m; ++q) res[nr] -= mu[row_el[q]] * xk[row_el[q]];
        nr++;
        if (h->kind == PH_STOICH) continue;
        /* An MQMQA phase gives its tangent exactly, from the energy gradient at its
         * internal equilibrium; differences of the nested fixed-composition solve carry
         * its tolerance divided by the step, kJ/mol in the slopes with four cations. */
        if (h->kind == PH_MQMQA) {
            const int nqh = mqmqa_num_quadruplets(h->simp_n[0], h->simp_n[1]);
            double *Ar = malloc((size_t)nqh * ne * sizeof(double));
            double *br = malloc((size_t)nqh * sizeof(double));
            int nrw = (Ar && br) ? mqmqa_tangent_rows_db(S->db, h->tag, S->T, xk,
                                                         h->off ? S->active : NULL, nqh, Ar, br) : -1;
            for (int w = 0; w < nrw; ++w) {
                for (int q = 0; q < m; ++q) J[(size_t)nr * m + q] = Ar[(size_t)w * ne + row_el[q]];
                res[nr] = br[w];
                for (int q = 0; q < m; ++q) res[nr] -= mu[row_el[q]] * J[(size_t)nr * m + q];
                nr++;
            }
            free(Ar); free(br);
            if (nrw >= 0) continue;
        }
        memcpy(z, C->z + (size_t)k * C->nzmax, (size_t)h->nz * sizeof(double));
        for (int j = 0; j < h->nz; ++j) {
            const double step = 1e-4, z0 = z[j];
            z[j] = z0 + step; unpack(h, z, y);
            double gp = ph_eval(S, h, y, xp);
            z[j] = z0 - step; unpack(h, z, y);
            double gm = ph_eval(S, h, y, xm);
            z[j] = z0;
            if (!isfinite(gp) || !isfinite(gm)) continue;
            for (int q = 0; q < m; ++q) J[(size_t)nr * m + q] = (xp[row_el[q]] - xm[row_el[q]]) / (2 * step);
            res[nr] = (gp - gm) / (2 * step);
            for (int q = 0; q < m; ++q) res[nr] -= mu[row_el[q]] * J[(size_t)nr * m + q];
            nr++;
        }
    }
    /* scale rows to unit norm so composition-sized and derivative-sized rows weigh alike */
    for (int i = 0; i < nr; ++i) {
        double s = 0.0;
        for (int q = 0; q < m; ++q) s += J[(size_t)i * m + q] * J[(size_t)i * m + q];
        s = sqrt(s);
        if (s < 1e-14) continue;
        for (int q = 0; q < m; ++q) J[(size_t)i * m + q] /= s;
        res[i] /= s;
    }
    for (int a = 0; a < m; ++a) {
        for (int b2 = 0; b2 < m; ++b2) {
            double s = 0.0;
            for (int i = 0; i < nr; ++i) s += J[(size_t)i * m + a] * J[(size_t)i * m + b2];
            N[a * m + b2] = s + (a == b2 ? 1e-10 : 0.0);
        }
        double s = 0.0;
        for (int i = 0; i < nr; ++i) s += J[(size_t)i * m + a] * res[i];
        rhs[a] = s;
    }
    if (invert(m, N, Ninv)) goto out;
    for (int a = 0; a < m; ++a) {
        double s = 0.0;
        for (int b2 = 0; b2 < m; ++b2) s += Ninv[a * m + b2] * rhs[b2];
        mu[row_el[a]] += s;
    }
    rc = 0;
out:
    free(J); free(res); free(N); free(Ninv); free(rhs); free(z); free(y); free(xp); free(xm);
    if (rc) mqmqa_db_set_error("gem: chemical potential polish failed");
    return rc;
}

/* ------------------------------------------------------------------ *
 * Exact finish
 *
 * The passes end on sampled compositions. That fixes G to about 1e-9 of its value, but the
 * chemical potentials are slopes and hang on the last digits of a dilute constituent. A CsI
 * gas at 1e-5 atm holds 4e-6 Cs and I atoms, and a composition error of 3e-8 there moves
 * mu(Cs) - mu(I) by 70 J/mol. The equilibrium conditions are therefore solved directly, by
 * Newton steps, for every stable set:
 *   a compound's Gibbs energy lies on the plane;
 *   a sublattice phase (CEF with any number of sublattices, and the SUBI ionic liquid) has,
 *     at its site fractions y, the derivative of F = G - mu.N along each constituent equal
 *     to its sublattice's multiplier, each sublattice summing to one, and F = 0 (G and the
 *     element amounts N per formula unit). The ideal part, RT m_s y ln y with m_s the
 *     sublattice's site number, is differentiated exactly and the rest by central
 *     differences;
 *   an MQMQA liquid's quadruplets are species, as Thermochimica treats SUBG and SUBQ: each
 *     quadruplet's potential, from the engine's exact gradient, lies on the plane;
 * and the amounts meet the bulk. A constituent whose own fraction would fall below e^-690 is
 * held at zero. The result is kept only if nothing lies below the new plane and G has not
 * risen above the hull it refines.
 * ------------------------------------------------------------------ */
#define RF_ITER 300
#define RF_TOL_STALL 1e-5   /* potential residual in RT accepted when Newton stalls before RF_TOL_MU:
                               0.2 J/mol at 2000 K (a pure-Al liquid beside a trace of NaCl melt
                               in ClAlNa stopped at 4e-6 RT, ill-conditioned) */
#define RF_TOL_MU 1e-7      /* potential residual in units of RT: under 1e-3 J/mol at 1000 K,
                               near the floor of the finite differences (about 3e-5 J/mol) */
#define RF_TOL_B 1e-15      /* mass balance and site sums. The potentials of a gas with 4e-13
                               of free atoms hang on the balance at that level */
#define RF_ZERO 700.0       /* log amount at which a constituent is held at zero */
#define RF_ZERO_Q 69.0      /* the same for a quadruplet, about 1e-30: the MQMQA gradient's pair
                               products of 1e-300 fractions underflow to 0 and give NaN */
#define RF_DILUTE(u) ((u) < -20.0)   /* a log amount too small to matter to the rest */

typedef enum { RF_STOICH, RF_SITES, RF_QUAD } RfKind;

typedef struct {
    RfKind kind;
    int ph;                 /* handler */
    int stoich;             /* compound index (RF_STOICH) */
    int nv, ns;             /* constituents and sublattices (RF_SITES); quadruplets (RF_QUAD) */
    int off;                /* first unknown, and first row, of this set */
    int sub[256];           /* sublattice of each constituent (RF_SITES) */
    double *qel;            /* element amounts per quadruplet, [nv * n_el] (RF_QUAD) */
    mqmqa_quad_ctx *qc;
} RfSet;

static int rf_count(const RfSet *t)
{
    return t->kind == RF_STOICH ? 1 : t->kind == RF_QUAD ? t->nv : t->nv + t->ns + 1;
}

/* G and element amounts per formula unit of a sublattice phase at y, its site numbers, and
 * the gas constant its ideal term uses. NaN when not evaluable. */
static double rf_sites_eval(const Sys *S, const Ph *h, const double *y, double *N, double *m, double *Rid)
{
    const int ne = S->n_el;
    if (h->kind == PH_IONIC) {
        const IonicPhase *io = S->d->phases[h->tag].ion;
        double Q = 0.0, P = 0.0;
        for (int c = 0; c < io->nc; ++c) Q += io->q[c] * y[c];
        for (int i = io->nc; i < io->nc + io->na; ++i) if (io->type[i] == 'A') P += io->q[i] * y[i];
        if (io->va >= 0) P += Q * y[io->va];
        if (m) { m[0] = P; m[1] = Q; }
        if (Rid) *Rid = mqmqa_db_R(S->db);
        return mqmqa_ph_ionic_gibbs(S->db, h->tag, y, S->T, N);
    }
    const SublPhase *cf = S->d->phases[h->tag].cef;
    memset(N, 0, (size_t)ne * sizeof(double));
    for (int s = 0; s < cf->n_subl; ++s) {
        if (m) m[s] = cf->site_ratio[s];
        for (int i = 0; i < cf->subl_ncon[s]; ++i) {
            const int c = cf->subl_off[s] + i;
            for (int e = 0; e < ne; ++e) N[e] += cf->site_ratio[s] * y[c] * h->con_el[c * ne + e];
        }
    }
    if (Rid) *Rid = mqmqa_gas_constant(mqmqa_db_R_own(S->db));
    return mqmqa_ph_cef_gibbs(S->db, h->tag, y, S->T, 0);
}

/* G less the ideal part at fixed site numbers m0, less mu.N: smooth, for differences */
static double rf_smooth(const Sys *S, const Ph *h, const RfSet *t, const double *y, const double *m0,
                        double Rid, const double *mu, const int *el, int nmu, double *N)
{
    double g = rf_sites_eval(S, h, y, N, NULL, NULL);
    for (int i = 0; i < t->nv; ++i)
        if (y[i] > 0.0) g -= Rid * S->T * m0[t->sub[i]] * y[i] * log(y[i]);
    for (int q = 0; q < nmu; ++q) g -= mu[q] * N[el[q]];
    return g;
}

typedef struct {
    double *y, *ys, *N, *m, *X, *grad;
} RfWork;

/* Rows of set t at unknowns u (potentials at u + nu), written from row t->off; its share of
 * the element balance added to bal; rest (optional) receives each constituent's row less the
 * log of its fraction. -1 if not evaluable. */
static int rf_set_rows(const Sys *S, const RfSet *t, const double *u, int nu, int nmu, const int *el,
                       const char *frz, double *res, double *bal, double *rest, RfWork *w)
{
    const int ne = S->n_el;
    const double RT = mqmqa_db_R_own(S->db) * S->T;
    const double *mu = u + nu;
    const int o = t->off;
    if (t->kind == RF_STOICH) {
        const double *a = S->d->stoich[t->stoich].stoich_el;
        double g = mqmqa_db_stoich_gibbs(S->db, t->stoich, S->T);
        for (int q = 0; q < nmu; ++q) { g -= a[el[q]] * mu[q]; bal[q] += u[o] * a[el[q]]; }
        res[o] = g / RT;
        if (rest) rest[o] = 0.0;
        return 0;
    }
    if (t->kind == RF_QUAD) {
        double tot = 0.0;
        for (int k = 0; k < t->nv; ++k) {
            if (u[o + k] > 700.0) return -1;
            w->X[k] = exp(u[o + k]);
            tot += w->X[k];
        }
        if (!(tot > 0.0)) return -1;
        for (int k = 0; k < t->nv; ++k) {
            for (int q = 0; q < nmu; ++q) bal[q] += w->X[k] * t->qel[(size_t)k * ne + el[q]];
            w->X[k] /= tot;
        }
        const double g = mqmqa_quad_gibbs(t->qc, w->X, w->grad);
        double sg = 0.0;
        for (int k = 0; k < t->nv; ++k) sg += w->X[k] * w->grad[k];
        if (!isfinite(g) || !isfinite(sg)) return -1;
        for (int k = 0; k < t->nv; ++k) {
            double v = g + w->grad[k] - sg;
            for (int q = 0; q < nmu; ++q) v -= t->qel[(size_t)k * ne + el[q]] * mu[q];
            if (rest) rest[o + k] = v / RT - log(w->X[k]);
            res[o + k] = frz[o + k] ? 0.0 : v / RT;
        }
        return 0;
    }
    const Ph *h = &S->ph[t->ph];
    const double hstep = 1e-6;
    for (int i = 0; i < t->nv; ++i) w->y[i] = frz[o + i] ? 0.0 : exp(u[o + i]);
    double Rid;
    const double g0 = rf_sites_eval(S, h, w->y, w->N, w->m, &Rid);
    if (!isfinite(g0)) return -1;
    double F0 = g0;
    for (int q = 0; q < nmu; ++q) F0 -= mu[q] * w->N[el[q]];
    const double Nf = exp(u[o + t->nv + t->ns]);
    for (int q = 0; q < nmu; ++q) bal[q] += Nf * w->N[el[q]];
    memcpy(w->ys, w->y, (size_t)t->nv * sizeof(double));
    for (int i = 0; i < t->nv; ++i) {
        if (frz[o + i]) { res[o + i] = 0.0; if (rest) rest[o + i] = 0.0; continue; }
        const double ms = w->m[t->sub[i]];
        w->ys[i] = w->y[i] + hstep;
        const double tp = rf_smooth(S, h, t, w->ys, w->m, Rid, mu, el, nmu, w->N);
        w->ys[i] = w->y[i] - hstep;
        const double tm = rf_smooth(S, h, t, w->ys, w->m, Rid, mu, el, nmu, w->N);
        w->ys[i] = w->y[i];
        if (!isfinite(tp) || !isfinite(tm)) return -1;
        const double d = (tp - tm) / (2 * hstep) + Rid * S->T * ms;
        const double lam = u[o + t->nv + t->sub[i]];
        res[o + i] = (Rid * S->T * ms * log(w->y[i]) + d) / RT - lam;
        /* the fraction it would take: ln y = -(d/RT - lam) RT / (Rid T m_s) */
        if (rest) rest[o + i] = ms > 0.0 ? (d / RT - lam) * RT / (Rid * S->T * ms) : 0.0;
    }
    for (int s = 0; s < t->ns; ++s) {
        double sum = -1.0;
        for (int i = 0; i < t->nv; ++i) if (t->sub[i] == s) sum += w->y[i];
        res[o + t->nv + s] = sum;
    }
    res[o + t->nv + t->ns] = F0 / RT;
    return 0;
}

static int rf_resid(const Sys *S, const RfSet *set, int ns, int nu, int nmu, const int *el,
                    const double *bn, const double *u, const char *frz, double *res, double *rest,
                    RfWork *w)
{
    double *bal = res + nu;
    for (int q = 0; q < nmu; ++q) bal[q] = -bn[el[q]];
    for (int s = 0; s < ns; ++s)
        if (rf_set_rows(S, &set[s], u, nu, nmu, el, frz, res, bal, rest, w)) return -1;
    return 0;
}

/* Solve A x = b in place (partial pivoting); -1 only on an exact zero pivot, since a gas with
 * 1e-13 of free atoms has true entries that small. A poor step is caught by the line search. */
static int rf_solve(int n, double *A, double *b)
{
    for (int c = 0; c < n; ++c) {
        int p = c;
        for (int r = c + 1; r < n; ++r) if (fabs(A[r * n + c]) > fabs(A[p * n + c])) p = r;
        if (!(fabs(A[p * n + c]) > 0.0) || !isfinite(A[p * n + c])) return -1;
        if (p != c) {
            for (int k = 0; k < n; ++k) { double t = A[c * n + k]; A[c * n + k] = A[p * n + k]; A[p * n + k] = t; }
            double t = b[c]; b[c] = b[p]; b[p] = t;
        }
        for (int r = c + 1; r < n; ++r) {
            double f = A[r * n + c] / A[c * n + c];
            if (f == 0.0) continue;
            for (int k = c; k < n; ++k) A[r * n + k] -= f * A[c * n + k];
            b[r] -= f * b[c];
        }
    }
    for (int r = n - 1; r >= 0; --r) {
        double s = b[r];
        for (int k = r + 1; k < n; ++k) s -= A[r * n + k] * b[k];
        b[r] = s / A[r * n + r];
    }
    return 0;
}

/* Sum of squares of the conditions in their own units (potentials in RT, amounts in mol per
 * mol of atoms). Weighting each by its tolerance instead let the balance rows, held to 1e-15,
 * turn the 1e-6 second-order change of any useful step into a rise, and the line search shrank
 * an MQMQA liquid's steps to 1% (CuFeC-Kang). The tolerances decide only when it is done. */
static double rf_norm(const double *r, int n)
{
    double s = 0.0;
    for (int i = 0; i < n; ++i) s += r[i] * r[i];
    return s;
}

/* Refine the sets of R in place. set_col[s] is the column a set was started from. Returns 1
 * when refined, 0 when Newton did not settle or the result failed its checks (R kept), -1 on
 * allocation failure. */
static int refine(const Sys *S, Cols *C, mqmqa_gem *R, const int *set_col, const double *bn,
                  const int *el, int nmu, const int *basis, int m, double *mu_full)
{
    const int ne = S->n_el, ns = R->n_sets;
    if (ns == 0) return 0;
    RfSet *set = calloc((size_t)ns, sizeof(RfSet));
    if (!set) return -1;
    int nu = 0, vmax = 1, rc = 0;
    double *u = NULL, *u1 = NULL, *res = NULL, *res1 = NULL, *J = NULL, *Jc = NULL, *step = NULL;
    double *rest = NULL, *tol = NULL, *colp = NULL, *colm = NULL, *balp = NULL, *balm = NULL, *xa = NULL;
    char *frz = NULL;
    RfWork w = {0};
    for (int s = 0; s < ns; ++s) {
        RfSet *t = &set[s];
        const int k = set_col[s];
        const Ph *h = &S->ph[C->ph[k]];
        t->ph = C->ph[k];
        t->off = nu;
        if (h->kind == PH_STOICH) {
            t->kind = RF_STOICH;
            t->stoich = -h->tag - 1;
        } else if (h->kind == PH_MQMQA) {
            t->kind = RF_QUAD;
            t->qc = mqmqa_quad_open(S->db, h->tag, S->T, h->off ? S->active : NULL);
            if (!t->qc) goto out;
            t->nv = mqmqa_quad_count(t->qc);
            t->qel = malloc((size_t)t->nv * ne * sizeof(double));
            if (!t->qel) { rc = -1; goto out; }
            mqmqa_quad_elements(t->qc, t->qel);
        } else {
            t->kind = RF_SITES;
            t->ns = h->n_simp;
            for (int q = 0, i = 0; q < h->n_simp; ++q)
                for (int j = 0; j < h->simp_n[q]; ++j, ++i) {
                    if (i >= 256) goto out;
                    t->sub[i] = q;
                }
            t->nv = 0;
            for (int q = 0; q < h->n_simp; ++q) t->nv += h->simp_n[q];
        }
        if (t->nv > vmax) vmax = t->nv;
        nu += rf_count(t);
    }
    const int n = nu + nmu;
    rc = -1;
    u = malloc((size_t)n * sizeof(double)); u1 = malloc((size_t)n * sizeof(double));
    res = malloc((size_t)n * sizeof(double)); res1 = malloc((size_t)n * sizeof(double));
    J = malloc((size_t)n * n * sizeof(double)); step = malloc((size_t)n * sizeof(double));
    Jc = malloc((size_t)n * n * sizeof(double));
    rest = malloc((size_t)n * sizeof(double)); tol = malloc((size_t)n * sizeof(double));
    colp = malloc((size_t)n * sizeof(double)); colm = malloc((size_t)n * sizeof(double));
    balp = malloc((size_t)(nmu + 1) * sizeof(double)); balm = malloc((size_t)(nmu + 1) * sizeof(double));
    frz = calloc((size_t)n, 1);
    xa = malloc((size_t)ns * ne * sizeof(double));
    w.y = malloc((size_t)vmax * sizeof(double)); w.ys = malloc((size_t)vmax * sizeof(double));
    w.X = malloc((size_t)vmax * sizeof(double)); w.grad = malloc((size_t)vmax * sizeof(double));
    w.N = malloc((size_t)ne * sizeof(double)); w.m = malloc(64 * sizeof(double));
    if (!u || !u1 || !res || !res1 || !J || !Jc || !step || !rest || !tol || !colp || !colm || !balp || !balm || !frz || !xa
        || !w.y || !w.ys || !w.X || !w.grad || !w.N || !w.m) goto out;
    rc = 0;
    /* start from each set's amount and composition, and the plane the passes ended on */
    for (int s = 0; s < ns; ++s) {
        const RfSet *t = &set[s];
        const int o = t->off;
        if (t->kind == RF_STOICH) {
            const double *a = S->d->stoich[t->stoich].stoich_el;
            double atoms = 0.0;
            for (int e = 0; e < ne; ++e) atoms += a[e];
            u[o] = R->amount[s] / atoms;
            tol[o] = RF_TOL_MU;
            continue;
        }
        if (t->kind == RF_QUAD) {
            if (mqmqa_quad_start(t->qc, R->x + (size_t)s * ne, w.X)) goto out;
            double atoms = 0.0;
            for (int k = 0; k < t->nv; ++k)
                for (int e = 0; e < ne; ++e) atoms += w.X[k] * t->qel[(size_t)k * ne + e];
            for (int k = 0; k < t->nv; ++k) {
                u[o + k] = fmax(log(fmax(w.X[k], 1e-300) * R->amount[s] / atoms), -RF_ZERO_Q);
                tol[o + k] = RF_TOL_MU;
            }
            continue;
        }
        const Ph *h = &S->ph[t->ph];
        unpack(h, C->z + (size_t)set_col[s] * C->nzmax, w.y);
        if (h->off)
            for (int i = 0; i < t->nv; ++i) if (h->off[i]) w.y[i] = 0.0;
        for (int q = 0; q < t->ns; ++q) {          /* renormalized without the absent ones */
            double sum = 0.0;
            for (int i = 0; i < t->nv; ++i) if (t->sub[i] == q) sum += w.y[i];
            for (int i = 0; i < t->nv; ++i) if (t->sub[i] == q && sum > 0.0) w.y[i] /= sum;
        }
        double atoms = 0.0;
        if (!isfinite(rf_sites_eval(S, h, w.y, w.N, NULL, NULL))) goto out;
        for (int e = 0; e < ne; ++e) atoms += w.N[e];
        if (!(atoms > 0.0)) goto out;
        for (int i = 0; i < t->nv; ++i) {
            if (h->off && h->off[i]) { frz[o + i] = 1; u[o + i] = -RF_ZERO; }
            else u[o + i] = log(fmax(w.y[i], 1e-300));
            tol[o + i] = RF_TOL_MU;
        }
        for (int q = 0; q < t->ns; ++q) { u[o + t->nv + q] = 0.0; tol[o + t->nv + q] = RF_TOL_B; }
        u[o + t->nv + t->ns] = log(R->amount[s] / atoms);
        tol[o + t->nv + t->ns] = RF_TOL_MU;
    }
    for (int q = 0; q < nmu; ++q) { u[nu + q] = mu_full[el[q]]; tol[nu + q] = RF_TOL_B; }
    if (rf_resid(S, set, ns, nu, nmu, el, bn, u, frz, res, rest, &w)) goto out;
    /* the multipliers enter linearly: start them at their least-squares values */
    for (int s = 0; s < ns; ++s) {
        const RfSet *t = &set[s];
        if (t->kind != RF_SITES) continue;
        for (int q = 0; q < t->ns; ++q) {
            double sum = 0.0;
            int cnt = 0;
            for (int i = 0; i < t->nv; ++i)
                if (t->sub[i] == q && !frz[t->off + i] && u[t->off + i] > -50.0) { sum += res[t->off + i]; cnt++; }
            if (cnt) u[t->off + t->nv + q] = sum / cnt;
        }
    }
    if (rf_resid(S, set, ns, nu, nmu, el, bn, u, frz, res, rest, &w)) goto out;
    double f = rf_norm(res, n);
    double lm = 1e-4;               /* Levenberg-Marquardt damping, kept between iterations */
    double floor2 = 0.0;           /* below this every row is near its tolerance */
    for (int i = 0; i < n; ++i) floor2 += 100.0 * tol[i] * tol[i];
    const double RT = mqmqa_db_R_own(S->db) * S->T;
    int done = 0;
    for (int it = 0; it < RF_ITER && !done; ++it) {
        /* Hold at zero any constituent whose own fraction would be below e^-690: Newton
         * would otherwise walk its log amount down 2 a step toward -5800 (Au in TestThermo33's
         * QUATERNARY). Its row becomes zero and stays satisfied. */
        int changed = 0;
        for (int s = 0; s < ns; ++s) {
            const RfSet *t = &set[s];
            if (t->kind == RF_STOICH) continue;
            const double zero = t->kind == RF_QUAD ? RF_ZERO_Q : RF_ZERO;
            for (int i = 0; i < t->nv; ++i) {
                const int k = t->off + i;
                if (!frz[k] && u[k] < -zero + (t->kind == RF_QUAD ? 9.0 : 50.0) && rest[k] > zero - 10.0) {
                    frz[k] = 1;
                    u[k] = -zero;
                    changed = 1;
                }
            }
        }
        if (changed) {
            if (rf_resid(S, set, ns, nu, nmu, el, bn, u, frz, res, rest, &w)) goto out;
            f = rf_norm(res, n);
        }
        /* Jacobian by central differences, set by set (a set's rows and its share of the
         * balance move only with its own unknowns and the potentials) */
        memset(J, 0, (size_t)n * n * sizeof(double));
        for (int s = 0; s < ns; ++s) {
            const RfSet *t = &set[s];
            const int o = t->off, cnt = rf_count(t);
            for (int j = 0; j < cnt + nmu; ++j) {
                const int col = j < cnt ? o + j : nu + (j - cnt);
                if (j < cnt && frz[col]) { J[col * n + col] = 1.0; continue; }
                const double d = j >= cnt ? RT
                                 : (t->kind == RF_SITES && j >= t->nv && j < t->nv + t->ns) ? 1.0 : 1e-5;
                memcpy(u1, u, (size_t)n * sizeof(double));
                u1[col] = u[col] + d;
                memset(balp, 0, (size_t)nmu * sizeof(double));
                if (rf_set_rows(S, t, u1, nu, nmu, el, frz, colp, balp, NULL, &w)) goto out;
                u1[col] = u[col] - d;
                memset(balm, 0, (size_t)nmu * sizeof(double));
                if (rf_set_rows(S, t, u1, nu, nmu, el, frz, colm, balm, NULL, &w)) goto out;
                for (int r = o; r < o + cnt; ++r)
                    if (!frz[r]) J[r * n + col] = (colp[r] - colm[r]) / (2 * d);
                if (j < cnt)
                    for (int q = 0; q < nmu; ++q) J[(nu + q) * n + col] += (balp[q] - balm[q]) / (2 * d);
            }
        }
        /* potentials solved in units of RT, so their columns are of order one like the rest */
        for (int i = 0; i < n; ++i)
            for (int q = 0; q < nmu; ++q) J[i * n + nu + q] *= RT;
        memcpy(Jc, J, (size_t)n * n * sizeof(double));
        for (int i = 0; i < n; ++i) step[i] = -res[i];
        const int singular = rf_solve(n, J, step);
        for (int q = 0; q < nmu; ++q) step[nu + q] *= RT;
        /* Damped, so no log amount that matters moves by more than 2 per step. A constituent
         * below e^-20 moves on its own, up to 60 a step and never above e^-15 in one: the CO2
         * gas over graphite starts its CO at the sampling floor, 1e-12, and needs it near
         * 1e-160, a CsTe liquid starts one constituent at e^-545 and needs it at e^-34, and
         * scaling the whole step to such a move held everything else to 0.5% of a step for all
         * 80 iterations. */
        double big = 0.0;
        for (int s = 0; s < ns; ++s) {
            const RfSet *t = &set[s];
            if (t->kind == RF_STOICH) continue;
            for (int i = 0; i < t->nv; ++i) {
                const int k = t->off + i;
                if (!frz[k] && !RF_DILUTE(u[k])) big = fmax(big, fabs(step[k]));
            }
            if (t->kind == RF_SITES) big = fmax(big, fabs(step[t->off + t->nv + t->ns]));
        }
        /* At each length the dilute ones first take their whole (capped) move, which the CO2 gas
         * needs, then shrink with the rest (beta), which a strongly coupled melt needs (a bad
         * full move of a dilute Al2 quadruplet in ClAlNa defeats every shorter step). */
        const double alpha0 = big > 2.0 ? 2.0 / big : 1.0;
        double alpha = alpha0, f1 = INFINITY;
        int ok = 0;
        /* a Newton step that would move a log amount by more than a million is the mark of a
         * nearly singular system (two sets at one composition trading amount freely); the
         * damped least-squares step below takes over at once */
        for (int ls = 0; ls < 30 && !ok && !singular && alpha0 > 2e-6; ++ls, alpha *= 0.5) {
            for (int pass = 0; pass < 2 && !ok; ++pass) {
                const double beta = pass ? alpha / alpha0 : 1.0;
                if (pass && ls == 0) continue;          /* the same trial as the first */
                for (int i = 0; i < n; ++i) u1[i] = u[i] + alpha * step[i];
                for (int s = 0; s < ns; ++s) {
                    const RfSet *t = &set[s];
                    if (t->kind == RF_STOICH) continue;
                    for (int i = 0; i < t->nv; ++i) {
                        const int k = t->off + i;
                        if (frz[k]) continue;
                        if (RF_DILUTE(u[k])) u1[k] = fmin(u[k] + beta * fmax(fmin(step[k], 60.0), -60.0), fmax(u[k], -15.0));
                        const double zero = t->kind == RF_QUAD ? RF_ZERO_Q : RF_ZERO;
                        if (u1[k] < -zero) u1[k] = -zero;
                    }
                }
                ok = !rf_resid(S, set, ns, nu, nmu, el, bn, u1, frz, res1, rest, &w)
                     && ((f1 = rf_norm(res1, n)) < f * (1.0 - 1e-4 * alpha) || f1 < floor2);
            }
        }
        /* Levenberg-Marquardt when the Newton direction fails: in ClAlNa's Al2 melt a dilute
         * quadruplet's potential hardly answers its own amount, so the linear model asks for a
         * log move of 68 against a residual of 6 and no shorter Newton step helps. The damped
         * least-squares step is a descent direction for any damping, and becomes Newton's as the
         * damping falls. */
        for (int k = 0; k < 14 && !ok; ++k, lm *= 10.0) {
            for (int a = 0; a < n; ++a) {
                double g = 0.0;
                for (int i = 0; i < n; ++i) g += Jc[i * n + a] * res[i];
                step[a] = -g;
                for (int b = 0; b <= a; ++b) {
                    double v = 0.0;
                    for (int i = 0; i < n; ++i) v += Jc[i * n + a] * Jc[i * n + b];
                    J[a * n + b] = J[b * n + a] = v;
                }
            }
            for (int a = 0; a < n; ++a) J[a * n + a] += lm * (J[a * n + a] + 1e-12);
            if (rf_solve(n, J, step)) continue;
            for (int q = 0; q < nmu; ++q) step[nu + q] *= RT;
            for (int i = 0; i < n; ++i) u1[i] = u[i] + step[i];
            for (int s = 0; s < ns; ++s) {
                const RfSet *t = &set[s];
                if (t->kind == RF_STOICH) continue;
                const double zero = t->kind == RF_QUAD ? RF_ZERO_Q : RF_ZERO;
                for (int i = 0; i < t->nv; ++i) {
                    const int kk = t->off + i;
                    if (frz[kk]) u1[kk] = u[kk];
                    else if (u1[kk] < -zero) u1[kk] = -zero;
                }
            }
            ok = !rf_resid(S, set, ns, nu, nmu, el, bn, u1, frz, res1, rest, &w)
                 && ((f1 = rf_norm(res1, n)) < f * (1.0 - 1e-8) || f1 < floor2);
            if (ok) lm = fmax(lm / 100.0, 1e-8);
        }
        if (!ok) break;
        memcpy(u, u1, (size_t)n * sizeof(double));
        memcpy(res, res1, (size_t)n * sizeof(double));
        f = f1;
        done = 1;
        for (int i = 0; i < n && done; ++i) if (fabs(res[i]) > tol[i]) done = 0;
    }
    if (!done) {
        done = 1;
        for (int i = 0; i < n && done; ++i)
            if (fabs(res[i]) > (tol[i] == RF_TOL_MU ? RF_TOL_STALL : 1e3 * tol[i])) done = 0;
    }
    if (!done) goto out;
    for (int s = 0; s < ns; ++s) if (set[s].kind == RF_STOICH && u[set[s].off] < 0.0) goto out;
    /* nothing may lie below the refined plane */
    double *mur = calloc((size_t)ne, sizeof(double));
    if (!mur) { rc = -1; goto out; }
    for (int q = 0; q < nmu; ++q) mur[el[q]] = u[nu + q];
    double worst = 0.0;
    for (int i = 0; i < S->n_ph; ++i)
        if (S->ph[i].kind != PH_STOICH && search_phase(S, C, i, mur, S->active, basis, m, 0, &worst) < 0) {
            free(mur); rc = -1; goto out;
        }
    for (int k = 0; k < C->n; ++k) {
        if (S->ph[C->ph[k]].kind != PH_STOICH) continue;
        double v = C->g[k];
        for (int e = 0; e < ne; ++e) v -= mur[e] * C->x[(size_t)k * ne + e];
        if (v < worst) worst = v;
    }
    /* The energy from the phases at their refined amounts, not mu.b, which carries the
     * potentials' tolerance. It may not rise above the hull it refines, beyond the hull's own
     * accuracy. The linear program meets each element's amount to 1e-9, so its value is good to
     * about 1e-9 of the potentials' sizes (5e-5 J/mol below the phase itself for Ru-1% Tc at
     * 1234 K; 1.6e-4 J/mol for a W-Au-Ar-O gap where G is 2.6e4 J/mol and the potentials 4e5). */
    double G = 0.0;
    for (int s = 0; s < ns; ++s) {
        const RfSet *t = &set[s];
        const int o = t->off;
        double *x = xa + (size_t)s * ne;        /* element amounts of the set */
        memset(x, 0, (size_t)ne * sizeof(double));
        if (t->kind == RF_STOICH) {
            const double *a = S->d->stoich[t->stoich].stoich_el;
            G += u[o] * mqmqa_db_stoich_gibbs(S->db, t->stoich, S->T);
            for (int e = 0; e < ne; ++e) x[e] = u[o] * a[e];
        } else if (t->kind == RF_QUAD) {
            double tot = 0.0;
            for (int k = 0; k < t->nv; ++k) { w.X[k] = exp(u[o + k]); tot += w.X[k]; }
            for (int k = 0; k < t->nv; ++k)
                for (int e = 0; e < ne; ++e) x[e] += w.X[k] * t->qel[(size_t)k * ne + e];
            for (int k = 0; k < t->nv; ++k) w.X[k] /= tot;
            G += tot * mqmqa_quad_gibbs(t->qc, w.X, NULL);
        } else {
            const Ph *h = &S->ph[t->ph];
            for (int i = 0; i < t->nv; ++i) w.y[i] = frz[o + i] ? 0.0 : exp(u[o + i]);
            const double Nf = exp(u[o + t->nv + t->ns]);
            G += Nf * rf_sites_eval(S, h, w.y, w.N, NULL, NULL);
            for (int e = 0; e < ne; ++e) x[e] = Nf * w.N[e];
        }
    }
    double musize = fabs(R->G);
    for (int q = 0; q < nmu; ++q) musize += fabs(mur[el[q]]);
    if (!isfinite(G) || worst < fmin(R->residual, 0.0) - 1e-9 || G > R->G + 1e-9 * musize) {
        free(mur);
        goto out;
    }
    for (int s = 0; s < ns; ++s) {
        const double *x = xa + (size_t)s * ne;
        double atoms = 0.0;
        for (int e = 0; e < ne; ++e) atoms += x[e];
        for (int e = 0; e < ne; ++e) R->x[(size_t)s * ne + e] = x[e] / atoms;
        R->amount[s] = atoms;
    }
    for (int q = 0; q < nmu; ++q) { R->mu[el[q]] = mur[el[q]]; mu_full[el[q]] = mur[el[q]]; }
    R->G = G;
    R->residual = worst;
    free(mur);
    rc = 1;
out:
    for (int s = 0; s < ns; ++s) { mqmqa_quad_close(set[s].qc); free(set[s].qel); }
    free(set); free(u); free(u1); free(res); free(res1); free(J); free(Jc); free(step); free(rest); free(tol);
    free(colp); free(colm); free(balp); free(balm); free(frz); free(xa);
    free(w.y); free(w.ys); free(w.X); free(w.grad); free(w.N); free(w.m);
    return rc;
}

/* ------------------------------------------------------------------ *
 * A bulk on a face of what the phases can reach
 * ------------------------------------------------------------------ */
/* NaAlCl4 or NaCl at exactly their formulas, in a file whose only chlorine-rich species beyond
 * the salts is a dummy: every phase lies on the side Cl <= Na + 3 Al, and the bulk on the plane
 * itself. A state holding any metal (Na vapour, the liquid's vacancy, the metals) then has zero
 * amount at equilibrium, but its samples lie a hair off the plane, and bases mixing them with the
 * salts were singular in exact arithmetic (the mass balance missed by 3e-5, or the linear program
 * failed). The bulk b lies on a face of the cone of the phases' endmember compositions e_k
 * exactly when the largest t with sum lambda_k e_k = b, every lambda_k >= t, is zero; the optimal
 * duals w are then a supporting plane, w.e_k <= 0 for every k with w.b = 0, and an endmember
 * with w.e_k < 0 has zero amount in every state reaching b. Its constituents are held at zero
 * as an absent element's are, and this repeats until b is inside the cone of what is left. A
 * bulk already inside is left as it was. (Linear-programming duality, Gordan's alternative.) */
#define FACE_T 1e-13        /* t at or below this: the bulk is on a face */
#define FACE_V 1e-7         /* off the face: below -FACE_V of the largest |w.e| per atom */
#define FACE_MAX_GEN 200000

typedef struct { int n, cap, ne; double *x; } Gens;

static int gens_push(Gens *G, const double *x, const int *active)
{
    double atoms = 0.0;
    for (int e = 0; e < G->ne; ++e) {
        if (x[e] != 0.0 && !active[e]) return 0;
        atoms += x[e];
    }
    if (!(atoms > 0.0)) return 0;
    if (G->n >= FACE_MAX_GEN) return -2;
    if (G->n == G->cap) {
        const int cap = G->cap ? 2 * G->cap : 256;
        double *nx = realloc(G->x, (size_t)cap * G->ne * sizeof(double));
        if (!nx) return -1;
        G->x = nx; G->cap = cap;
    }
    for (int e = 0; e < G->ne; ++e) G->x[(size_t)G->n * G->ne + e] = x[e] / atoms;
    G->n++;
    return 0;
}

/* The composition of each endmember of every phase still in, over its constituents not off */
static int face_gens(const Sys *S, Gens *G, const int *active)
{
    const int ne = S->n_el;
    double x[64];
    if (ne > 64) return -1;
    G->n = 0;
    for (int i = 0; i < S->n_ph; ++i) {
        const Ph *h = &S->ph[i];
        if (h->gone) continue;
        int rc = 0;
        if (h->kind == PH_STOICH) {
            const Endmember *em = &S->d->stoich[-h->tag - 1];
            if (em->dummy) continue;
            rc = gens_push(G, em->stoich_el, active);
        } else if (h->kind == PH_CEF) {
            const SublPhase *cf = S->d->phases[h->tag].cef;
            int idx[64] = {0};
            for (;;) {
                int ok = 1;
                memset(x, 0, (size_t)ne * sizeof(double));
                for (int s = 0; s < cf->n_subl; ++s) {
                    const int c = cf->subl_off[s] + idx[s];
                    if (h->off && h->off[c]) { ok = 0; break; }
                    for (int e = 0; e < ne; ++e) x[e] += cf->site_ratio[s] * h->con_el[(size_t)c * ne + e];
                }
                if (ok && (rc = gens_push(G, x, active)) != 0) break;
                int s = 0;
                while (s < cf->n_subl && ++idx[s] == cf->subl_ncon[s]) idx[s++] = 0;
                if (s == cf->n_subl) break;
            }
        } else if (h->kind == PH_MQMQA) {
            const int nc = h->simp_n[0], na = h->simp_n[1];
            for (int c = 0; c < nc && !rc; ++c)
                for (int a = nc; a < nc + na && !rc; ++a) {
                    if (h->off && (h->off[c] || h->off[a])) continue;
                    for (int e = 0; e < ne; ++e)
                        x[e] = h->con_el[(size_t)c * ne + e] / fmax(h->ion_q[c], 1e-300)
                             + h->con_el[(size_t)a * ne + e] / fmax(h->ion_q[a], 1e-300);
                    rc = gens_push(G, x, active);
                }
        } else {
            const IonicPhase *io = S->d->phases[h->tag].ion;
            for (int c = 0; c < io->nc && !rc; ++c)
                for (int a = io->nc; a < io->nc + io->na && !rc; ++a) {
                    if (h->off && (h->off[c] || h->off[a])) continue;
                    const double qc = io->q[c], qa = io->q[a];
                    for (int e = 0; e < ne; ++e) {
                        const double ce = h->con_el[(size_t)c * ne + e], ae = h->con_el[(size_t)a * ne + e];
                        x[e] = io->type[a] == 'A' ? qa * ce + qc * ae
                             : io->type[a] == 'V' ? qc * ce : qc * ae;
                    }
                    rc = gens_push(G, x, active);
                }
        }
        if (rc) return rc;
    }
    return 0;
}

/* max t over sum lambda_k e_k = b, lambda_k >= t (t free, as t+ - t-), or with feas_only just
 * whether b is reached. 0 with t and the duals w over the rows; -6 when b is out of reach. */
static int face_lp(const Gens *G, const double *bn, const int *row_el, int m, int feas_only,
                   double *t_out, double *w)
{
    const int n = G->n, N = n + (feas_only ? 0 : 2);
    double *A = malloc((size_t)(N ? N : 1) * m * sizeof(double));
    double *c = calloc((size_t)(N ? N : 1), sizeof(double));
    double *Binv = malloc((size_t)m * m * sizeof(double)), *xb = malloc((size_t)m * sizeof(double));
    double *y = malloc((size_t)m * sizeof(double)), rb[64];
    int *basis = malloc((size_t)m * sizeof(int)), rc = -5;
    if (!A || !c || !Binv || !xb || !y || !basis || m > 64) goto out;
    for (int r = 0; r < m; ++r) rb[r] = bn[row_el[r]];
    for (int k = 0; k < n; ++k)
        for (int r = 0; r < m; ++r) A[(size_t)k * m + r] = G->x[(size_t)k * G->ne + row_el[r]];
    if (!feas_only) {
        for (int r = 0; r < m; ++r) {
            double s = 0.0;
            for (int k = 0; k < n; ++k) s += A[(size_t)k * m + r];
            A[(size_t)n * m + r] = s;
            A[(size_t)(n + 1) * m + r] = -s;
        }
        c[n] = -1.0;
        c[n + 1] = 1.0;
    }
    Lp L = { m, N, A, c, rb, basis, Binv, xb, y };
    rc = lp_solve(&L);
    if (!rc && !feas_only) {
        double t = 0.0;
        for (int r = 0; r < m; ++r) t += basis[r] == n ? xb[r] : basis[r] == n + 1 ? -xb[r] : 0.0;
        *t_out = t;
        memcpy(w, y, (size_t)m * sizeof(double));
    }
out:
    free(A); free(c); free(Binv); free(xb); free(y); free(basis);
    return rc;
}

static double wdot(const double *w, int ne, double *atoms, const double *p)
{
    double s = 0.0, a = 0.0;
    for (int e = 0; e < ne; ++e) { s += w[e] * p[e]; a += p[e]; }
    *atoms = a;
    return s;
}

/* Hold out what leads off the plane w (over the database elements). 1 if anything changed. */
static int face_mark(Sys *S, const double *wel, double tol)
{
    const int ne = S->n_el;
    int changed = 0;
    for (int i = 0; i < S->n_ph; ++i) {
        Ph *h = &S->ph[i];
        if (h->gone) continue;
        int nk = 0;
        for (int s = 0; s < h->n_simp; ++s) nk += h->simp_n[s];
        if (h->kind == PH_STOICH) {
            const Endmember *em = &S->d->stoich[-h->tag - 1];
            double v_atoms;
            const double v = wdot(wel, ne, &v_atoms, em->stoich_el);
            if (v < -tol * v_atoms) { h->gone = 1; changed = 1; }
            continue;
        }
        if (h->kind == PH_IONIC) continue;      /* left whole: no case has needed its cut */
        int *off = h->off ? h->off : calloc((size_t)nk, sizeof(int));
        if (!off) return -1;
        int now = 0;
        if (h->kind == PH_CEF) {
            /* w.x is linear in the site fractions: on the face only the constituents with the
             * largest w per site of each sublattice, and the phase only if those sum to zero */
            const SublPhase *cf = S->d->phases[h->tag].cef;
            double vmax_tot = 0.0, atoms_tot = 0.0, best[64];
            for (int s = 0; s < cf->n_subl; ++s) {
                best[s] = -INFINITY;
                double at = 0.0;
                for (int k = cf->subl_off[s]; k < cf->subl_off[s] + cf->subl_ncon[s]; ++k) {
                    if (off[k]) continue;
                    double v_atoms;
                    const double v = cf->site_ratio[s] * wdot(wel, ne, &v_atoms, h->con_el + (size_t)k * ne);
                    if (v > best[s]) { best[s] = v; at = cf->site_ratio[s] * v_atoms; }
                }
                vmax_tot += best[s];
                atoms_tot += at;
            }
            if (vmax_tot < -tol * atoms_tot) { h->gone = 1; changed = 1; }
            else
                for (int s = 0; s < cf->n_subl; ++s)
                    for (int k = cf->subl_off[s]; k < cf->subl_off[s] + cf->subl_ncon[s]; ++k) {
                        if (off[k]) continue;
                        double v_atoms;
                        const double v = cf->site_ratio[s] * wdot(wel, ne, &v_atoms, h->con_el + (size_t)k * ne);
                        if (best[s] - v > tol * atoms_tot) { off[k] = 1; now = 1; }
                    }
        } else {
            /* MQMQA: a quadruplet is on the face only if all its pairs are; an ion goes when
             * every pair it still makes leads off */
            const int nc = h->simp_n[0], na = h->simp_n[1];
            double px[64];
            int again = 1;
            while (again) {
                again = 0;
                for (int i2 = 0; i2 < nc + na; ++i2) {
                    if (off[i2]) continue;
                    int any_on = 0;
                    const int lo = i2 < nc ? nc : 0, hi = i2 < nc ? nc + na : nc;
                    for (int j = lo; j < hi && !any_on; ++j) {
                        if (off[j]) continue;
                        const int c = i2 < nc ? i2 : j, a = i2 < nc ? j : i2;
                        for (int e = 0; e < ne; ++e)
                            px[e] = h->con_el[(size_t)c * ne + e] / fmax(h->ion_q[c], 1e-300)
                                  + h->con_el[(size_t)a * ne + e] / fmax(h->ion_q[a], 1e-300);
                        double v_atoms;
                        const double v = wdot(wel, ne, &v_atoms, px);
                        if (!(v < -tol * v_atoms)) any_on = 1;
                    }
                    if (!any_on) { off[i2] = 1; now = again = 1; }
                }
            }
            int kc = 0, ka = 0;
            for (int k = 0; k < nc; ++k) kc += !off[k];
            for (int k = nc; k < nc + na; ++k) ka += !off[k];
            if (!kc || !ka) { h->gone = 1; changed = 1; }
            else if (now) h->face = 1;
        }
        if (h->gone) { if (off != h->off) free(off); continue; }
        if (now) { h->off = off; changed = 1; }
        else if (off != h->off) free(off);
    }
    return changed;
}

static int face_reduce(Sys *S, const double *bn, const int *active, const int *row_el, int m)
{
    const int ne = S->n_el;
    Gens G = { 0, 0, ne, NULL };
    double w[64], wel[64];
    int rc = 0;
    /* snapshot, to undo a cut that would leave the bulk out of reach */
    const int n0 = S->n_ph;
    int **save = calloc((size_t)n0, sizeof(int *));
    int *had = calloc((size_t)S->n_ph * 3, sizeof(int));
    if (!save || !had || ne > 64) { rc = -1; goto out; }
    for (int i = 0; i < S->n_ph; ++i) {
        const Ph *h = &S->ph[i];
        int nk = 0;
        for (int s = 0; s < h->n_simp; ++s) nk += h->simp_n[s];
        had[3 * i] = h->off != NULL; had[3 * i + 1] = h->gone; had[3 * i + 2] = h->face;
        if (h->off) {
            save[i] = malloc((size_t)nk * sizeof(int));
            if (!save[i]) { rc = -1; goto out; }
            memcpy(save[i], h->off, (size_t)nk * sizeof(int));
        }
    }
    for (int round = 0; round <= ne; ++round) {
        double t = 0.0;
        int r = face_gens(S, &G, active);
        if (r == -2) break;                     /* too many endmembers to judge: left as is */
        if (r) { rc = -1; goto out; }
        if (face_lp(&G, bn, row_el, m, 0, &t, w) || t > FACE_T) break;
        memset(wel, 0, sizeof wel);
        for (int k = 0; k < m; ++k) wel[row_el[k]] = w[k];
        double vmax = 0.0;
        for (int k = 0; k < G.n; ++k) {
            double v = 0.0;
            for (int e = 0; e < ne; ++e) v += wel[e] * G.x[(size_t)k * ne + e];
            vmax = fmax(vmax, fabs(v));
        }
        if (!(vmax > 0.0)) break;
        const int ch = face_mark(S, wel, FACE_V * vmax);
        if (ch < 0) { rc = -1; goto out; }
        if (!ch) break;
    }
    /* the cut must leave the bulk reachable; otherwise everything goes back as it was */
    if (face_gens(S, &G, active) == 0 && face_lp(&G, bn, row_el, m, 1, NULL, NULL) == -6) {
        for (int i = 0; i < S->n_ph; ++i) {
            Ph *h = &S->ph[i];
            if (!had[3 * i]) { free(h->off); h->off = NULL; }
            else { int nk = 0; for (int s = 0; s < h->n_simp; ++s) nk += h->simp_n[s];
                   memcpy(h->off, save[i], (size_t)nk * sizeof(int)); }
            h->gone = had[3 * i + 1]; h->face = had[3 * i + 2];
        }
    }
    /* drop the phases left out; MQMQA cuts go to the database for the equilibrium routines */
    int k = 0;
    for (int i = 0; i < S->n_ph; ++i) {
        Ph *h = &S->ph[i];
        if (h->gone) { free(h->con_el); free(h->ion_q); free(h->off); continue; }
        if (h->face) ((Phase *)&S->d->phases[h->tag])->ion_off = h->off;
        S->ph[k++] = *h;
    }
    S->n_ph = k;
out:
    if (save) for (int i = 0; i < n0; ++i) free(save[i]);
    free(save); free(had); free(G.x);
    return rc;
}

static mqmqa_gem *gem_solve(const mqmqa_db *db, double T, const double *b,
                            const int *suspended, int grid, int max_iter)
{
    const Db *d = (const Db *)db;
    if (!d || !b || !(T > 0.0)) { mqmqa_db_set_error("gem: bad arguments"); return NULL; }
    const int ne = d->n_el;
    if (grid <= 0) grid = GEM_GRID;
    if (max_iter <= 0) max_iter = GEM_PASSES;

    Sys S = { d, db, T, ne, NULL, 0, NULL };
    rng_state = 88172645463325252ULL;      /* same samples on every call */
    Cols C = {0};
    mqmqa_gem *R = NULL;
    int *active = calloc((size_t)ne, sizeof(int));
    int *row_el = malloc((size_t)ne * sizeof(int));
    double *bn = malloc((size_t)ne * sizeof(double));
    double *mu = calloc((size_t)ne, sizeof(double));
    double *mu_pol = calloc((size_t)ne, sizeof(double));
    double *shift = calloc((size_t)ne, sizeof(double));
    double *A = NULL, *cvec = NULL, *x = NULL;
    double *Binv = NULL, *xb = NULL, *y = NULL, *yb = NULL;
    int *basis = NULL;
    if (!active || !row_el || !bn || !mu || !mu_pol || !shift) goto fail;

    double btot = 0.0;
    for (int e = 0; e < ne; ++e) { if (b[e] < 0 || !isfinite(b[e])) { mqmqa_db_set_error("gem: negative or non-finite amount"); goto fail; } btot += b[e]; }
    if (!(btot > 0.0)) { mqmqa_db_set_error("gem: empty bulk composition"); goto fail; }
    int m = 0;
    for (int e = 0; e < ne; ++e) {
        bn[e] = b[e] / btot;
        if (bn[e] > 1e-14) { active[e] = 1; row_el[m++] = e; }
    }
    S.active = active;
    if (setup_phases(&S, suspended, active)) goto fail;
    if (face_reduce(&S, bn, active, row_el, m)) goto fail;

    int nzmax = 1;
    for (int i = 0; i < S.n_ph; ++i) if (S.ph[i].nz > nzmax) nzmax = S.ph[i].nz;
    C.ne = ne;
    C.nzmax = nzmax;
    x = malloc((size_t)ne * sizeof(double));
    if (!x) goto fail;
    for (int i = 0; i < S.n_ph; ++i) {
        Ph *h = &S.ph[i];
        if (h->kind == PH_STOICH) {
            int j = -h->tag - 1;
            if (d->stoich[j].dummy) continue;      /* listed for reference, never formed */
            double atoms = 0.0;
            for (int e = 0; e < ne; ++e) atoms += d->stoich[j].stoich_el[e];
            if (!(atoms > 0.0)) continue;
            int ok = 1;
            for (int e = 0; e < ne; ++e) {
                x[e] = d->stoich[j].stoich_el[e] / atoms;
                if (!active[e] && x[e] > 1e-14) ok = 0;
            }
            if (ok && cols_add(&C, i, x, mqmqa_db_stoich_gibbs(db, j, T) / atoms, NULL, 0)) goto fail;
        } else if (sample_phase(&S, i, grid, &C, active)) {
            goto fail;
        }
    }

    basis = malloc((size_t)m * sizeof(int));
    Binv = malloc((size_t)m * m * sizeof(double));
    xb = malloc((size_t)m * sizeof(double));
    y = malloc((size_t)m * sizeof(double));
    yb = malloc((size_t)(nzmax + 1) * 64 * sizeof(double));
    if (!basis || !Binv || !xb || !y || !yb) goto fail;
    double rb[64];
    if (m > 64) { mqmqa_db_set_error("gem: more than 64 elements"); goto fail; }
    const int m_full = m;
    int el_full[64];
    memcpy(el_full, row_el, (size_t)m_full * sizeof(int));

    int pass = 0, resumes = 0, bulk_tried = 0;
    double worst = 0.0, prev_obj = INFINITY;
    int stalls = 0;
resume:
    for (;;) {
        /* Drop element rows that the candidates make redundant (oxygen fixed by charge
         * balance in every phase of a fixed-valence oxide system). Gram-Schmidt on the
         * rows keeps the first independent set. Such an element has no chemical potential
         * of its own, and the full balance is checked after the solve. */
        free(A); free(cvec);
        A = malloc((size_t)C.n * m_full * sizeof(double));
        cvec = malloc((size_t)C.n * sizeof(double));
        if (!A || !cvec) goto fail;
        {
            double *Q = malloc((size_t)m_full * C.n * sizeof(double));
            if (!Q) goto fail;
            m = 0;
            for (int r = 0; r < m_full; ++r) {
                double *q = Q + (size_t)m * C.n, n0 = 0.0, n1 = 0.0;
                for (int k = 0; k < C.n; ++k) { q[k] = C.x[(size_t)k * ne + el_full[r]]; n0 += q[k] * q[k]; }
                for (int s = 0; s < m; ++s) {
                    const double *qs = Q + (size_t)s * C.n;
                    double dot = 0.0;
                    for (int k = 0; k < C.n; ++k) dot += q[k] * qs[k];
                    for (int k = 0; k < C.n; ++k) q[k] -= dot * qs[k];
                }
                for (int k = 0; k < C.n; ++k) n1 += q[k] * q[k];
                if (!(n1 > 1e-18 * n0) || n1 <= 0.0) continue;
                n1 = sqrt(n1);
                for (int k = 0; k < C.n; ++k) q[k] /= n1;
                row_el[m++] = el_full[r];
            }
            free(Q);
        }
        for (int r = 0; r < m; ++r) rb[r] = bn[row_el[r]];
        /* Costs measured from the last pass's plane, each one a driving force. The optimum
         * is the same (mass balance fixes the plane's share), but reduced costs are then
         * differences of J-sized numbers rather than of 4e5 J/mol ones, which a basis of
         * near-collinear columns cannot resolve: two bases 0.005 J/mol apart each priced
         * better than the other, and the simplex flipped between them until its cap. */
        for (int e = 0; e < ne; ++e) shift[e] = 0.0;
        for (int r = 0; r < m; ++r) shift[row_el[r]] = mu[row_el[r]];
        for (int k = 0; k < C.n; ++k) {
            cvec[k] = C.g[k];
            for (int r = 0; r < m; ++r) {
                A[(size_t)k * m + r] = C.x[(size_t)k * ne + row_el[r]];
                cvec[k] -= shift[row_el[r]] * A[(size_t)k * m + r];
            }
        }
        Lp L = { m, C.n, A, cvec, rb, basis, Binv, xb, y };
        int rc = lp_solve(&L);
        if (rc) {
            mqmqa_db_set_error(rc == -6 ? "gem: no phase combination reaches this bulk composition"
                                        : "gem: linear program failed (%d)", rc);
            goto fail;
        }
        for (int e = 0; e < m_full; ++e) {
            double s = -bn[el_full[e]];
            for (int r = 0; r < m; ++r)
                if (basis[r] < C.n) s += xb[r] * C.x[(size_t)basis[r] * ne + el_full[e]];
            if (fabs(s) > 1e-9) {
                mqmqa_db_set_error("gem: no phase combination reaches this bulk composition");
                goto fail;
            }
        }
        for (int e = 0; e < ne; ++e) mu[e] = 0.0;
        for (int r = 0; r < m; ++r) mu[row_el[r]] = y[r] + shift[row_el[r]];
        double obj = 0.0;
        for (int r = 0; r < m; ++r) if (basis[r] < C.n) obj += C.g[basis[r]] * xb[r];
        /* Stop once the hull has not dropped for two passes and, at this basis, nothing lies
         * more than GEM_DF_STOP below one of the two planes (tested after the search
         * below). A stalled pass alone is not enough: at a degenerate optimum the supporting
         * plane is not unique, so a refined point can lie below one plane yet leave the
         * hull where it is for a pass or two. */
        stalls = (pass > 0 && prev_obj - obj < GEM_OBJ_TOL) ? stalls + 1 : 0;
        if (pass >= max_iter || stalls >= GEM_STALLS_MAX) break;
        prev_obj = obj;
        /* A stalled pass means the duals are one of many supporting planes (zero-amount
         * columns in the basis fix them). Points below one such plane may not move the
         * hull while points below another do. Below the duals a point can enter the linear
         * program; below the plane tangent to the stable phases it moves the stable
         * compositions. After a stall each phase is searched against both. */
        const double *planes[2] = { mu, mu_pol };
        int nplanes = 1;
        if (stalls > 0) {
            memcpy(mu_pol, mu, (size_t)ne * sizeof(double));
            if (!polish_mu(&S, &C, basis, xb, m, row_el, mu_pol)) nplanes = 2;
        }

        worst = 0.0;
        double wtan = 0.0;                         /* the same against the tangent plane */
        int added = 0;
        for (int i = 0; i < S.n_ph; ++i) {
            Ph *h = &S.ph[i];
            if (h->kind == PH_STOICH) continue;
            /* The phase at the weighted centre of each cluster of its basic columns. On a
             * convex stretch of the phase this lies below their chord, so the hull drops
             * toward the phase's own energy at that composition; inside a miscibility gap
             * it lies above the chord and the linear program ignores it. */
            {
                int ytot = 0;
                for (int s = 0; s < h->n_simp; ++s) ytot += h->simp_n[s];
                int cl[64], ncl = 0;
                for (int r = 0; r < m; ++r)
                    if (basis[r] < C.n && C.ph[basis[r]] == i && xb[r] > 1e-12 && ncl < 64) cl[ncl++] = r;
                int used[64] = {0};
                double *yc = malloc((size_t)ytot * sizeof(double));
                double *yy = malloc((size_t)ytot * sizeof(double));
                double *xx = malloc((size_t)ne * sizeof(double));
                double *zz = malloc((size_t)(h->nz + 1) * sizeof(double));
                int bad = !yc || !yy || !xx || !zz;
                for (int a = 0; a < ncl && !bad; ++a) {
                    if (used[a]) continue;
                    double wsum = 0.0;
                    int members = 0;
                    memset(yc, 0, (size_t)ytot * sizeof(double));
                    for (int q = a; q < ncl; ++q) {
                        if (used[q]) continue;
                        int ka = basis[cl[a]], kq = basis[cl[q]];
                        double dx = 0.0;
                        for (int e = 0; e < ne; ++e)
                            dx = fmax(dx, fabs(C.x[(size_t)ka * ne + e] - C.x[(size_t)kq * ne + e]));
                        if (dx > 0.15) continue;
                        used[q] = 1;
                        members++;
                        unpack(h, C.z + (size_t)kq * C.nzmax, yy);
                        for (int t = 0; t < ytot; ++t) yc[t] += xb[cl[q]] * yy[t];
                        wsum += xb[cl[q]];
                    }
                    if (members < 2) continue;
                    for (int t = 0; t < ytot; ++t) yc[t] /= wsum;
                    double g = ph_eval(&S, h, yc, xx);
                    if (!isfinite(g)) continue;
                    int zo = 0, yo = 0;
                    for (int s = 0; s < h->n_simp; ++s) {
                        int n = h->simp_n[s];
                        if (n > 1) logits(yc + yo, n, zz + zo);
                        zo += n - 1;
                        yo += n;
                    }
                    if (cols_add(&C, i, xx, g, zz, h->nz)) bad = 1;
                    else added++;
                }
                free(yc); free(yy); free(xx); free(zz);
                if (bad) goto fail;
            }
            for (int pl = 0; pl < nplanes; ++pl) {
                int got = search_phase(&S, &C, i, planes[pl], active, basis, m, 1, pl ? &wtan : &worst);
                if (got < 0) goto fail;
                added += got;
            }
        }
        const double settled = nplanes == 2 ? fmax(worst, wtan) : worst;
        if (wtan < worst) worst = wtan;
        pass++;
        if (!added || (stalls >= 2 && settled > -GEM_DF_STOP)) break;
    }

    {
        double art = 0.0;
        for (int r = 0; r < m; ++r) if (basis[r] >= C.n) art += fabs(xb[r]);
        if (art > 1e-9) {
            mqmqa_db_set_error("gem: %.3g of the bulk left unassigned to any phase", art);
            goto fail;
        }
    }
    /* Certificate. Every phase is searched once more against a plane; at an equilibrium
     * nothing lies below it. With fewer stable phases than elements many planes support
     * the hull, and the one fitted tangent to the stable phases can cut under a phase the
     * duals keep above (orthopyroxene 2.9 J/mol below it beside olivine + wollastonite,
     * where pycalphad agrees on the assemblage). Both are tried, and the potentials
     * reported are those of the plane with the smaller violation, with that violation as
     * the residual. */
    memcpy(mu_pol, mu, (size_t)ne * sizeof(double));             /* the duals */
    if (polish_mu(&S, &C, basis, xb, m, row_el, mu)) goto fail;
    double worst_pol = 0.0, worst_dual = 0.0;
    if (certify(&S, &C, mu, active, basis, xb, m, &worst_pol) ||
        certify(&S, &C, mu_pol, active, basis, xb, m, &worst_dual)) goto fail;
    worst = worst_pol;
    if (worst_dual > worst_pol) {
        memcpy(mu, mu_pol, (size_t)ne * sizeof(double));
        worst = worst_dual;
    }
    /* The passes stop when a pass adds nothing below the plane it searched, but the
     * certificate searches again from the final basis and can find what they missed (a
     * CsI gas at 1e-5 atm left 26 J/mol above its own minimum). What it finds goes in as
     * candidates and the passes resume. */
    if (worst < -GEM_DF_STOP && resumes < GEM_RESUME_MAX) {
        int added = 0;
        double w = 0.0;
        const double *planes[2] = { mu, mu_pol };
        for (int i = 0; i < S.n_ph; ++i) {
            if (S.ph[i].kind == PH_STOICH) continue;
            for (int pl = 0; pl < 2; ++pl) {
                const int got = search_phase(&S, &C, i, planes[pl], active, basis, m, 1, &w);
                if (got < 0) goto fail;
                added += got;
            }
        }
        if (added) {
            resumes++;
            stalls = 0;
            prev_obj = INFINITY;
            goto resume;
        }
    }
    if (!bulk_tried) {
        bulk_tried = 1;
        double hull = 0.0;
        for (int r = 0; r < m; ++r) if (basis[r] < C.n) hull += C.g[basis[r]] * xb[r];
        int added = 0;
        for (int i = 0; i < S.n_ph; ++i) {
            const int got = bulk_column(&S, i, bn, &C, hull - GEM_DF_STOP);
            if (got < 0) goto fail;
            added += got;
        }
        if (added) {                 /* a new start: the resumes it may need are its own */
            resumes = 0;
            stalls = 0;
            prev_obj = INFINITY;
            goto resume;
        }
    }
    /* A certificate that still finds a state below the result means the result is not the
     * equilibrium; it is refused, never returned (NaCl at 1200 K in ClAlNa came back as the
     * solid with the liquid 1463 J/mol below it). */
    if (worst < -GEM_CERT_FAIL) {
        mqmqa_db_set_error("gem: no equilibrium found, a state lies %.3g J/mol below the best result "
                           "after %d resumes", -worst, resumes);
        goto fail;
    }

    /* composition sets: merge basic columns of one phase that lie close together */
    R = calloc(1, sizeof(*R));
    if (!R) goto fail;
    R->n_el = ne;
    R->passes = pass;
    R->residual = worst;
    R->phase = malloc((size_t)m * sizeof(int));
    R->amount = calloc((size_t)m, sizeof(double));
    R->x = calloc((size_t)m * ne, sizeof(double));
    R->mu = malloc((size_t)ne * sizeof(double));
    if (!R->phase || !R->amount || !R->x || !R->mu) goto fail;
    for (int e = 0; e < ne; ++e) R->mu[e] = NAN;     /* absent, or fixed by the others */
    for (int r = 0; r < m; ++r) R->mu[row_el[r]] = mu[row_el[r]];
    R->G = 0.0;                            /* the hull value, not mu.b after the polish */
    for (int r = 0; r < m; ++r) if (basis[r] < C.n) R->G += C.g[basis[r]] * xb[r];
    int set_col[64];
    double set_big[64] = {0};
    for (int round = 0; round < 2; ++round)
    for (int r = 0; r < m; ++r) {
        int k = basis[r];
        if (k >= C.n || xb[r] <= 1e-12) continue;
        const int small = xb[r] < GEM_AMT_MIN;
        if (small != round) continue;              /* real amounts first, then the rest */
        int tag = S.ph[C.ph[k]].tag;
        const double *xk = C.x + (size_t)k * ne;
        int into = -1;
        double best = INFINITY;
        for (int s = 0; s < R->n_sets; ++s) {
            if (!same_phase(db, T, R->phase[s], tag)) continue;
            double dx = 0.0;
            for (int e = 0; e < ne; ++e) dx = fmax(dx, fabs(R->x[(size_t)s * ne + e] - xk[e]));
            if (small ? dx < best : dx < MERGE_DX) { into = s; best = dx; if (!small) break; }
        }
        if (into < 0) { into = R->n_sets++; R->phase[into] = tag; set_col[into] = k; }
        if (xb[r] > set_big[into]) { set_big[into] = xb[r]; set_col[into] = k; }
        double a0 = R->amount[into], a1 = a0 + xb[r];
        for (int e = 0; e < ne; ++e)
            R->x[(size_t)into * ne + e] = (R->x[(size_t)into * ne + e] * a0 + xk[e] * xb[r]) / a1;
        R->amount[into] = a1;
    }
    /* With an element fixed by the others (oxygen by charge balance in every phase of a
     * fixed-valence oxide system, all of Hephaestus's slags) the finish works in the same
     * reduced space as the passes: the independent elements' potentials, the dropped one's
     * taken as zero, which every phase's own charge balance makes exact. */
    {
        const int rf = refine(&S, &C, R, set_col, bn, row_el, m, basis, m, mu);
        if (rf < 0) goto fail;
        R->exact = rf == 1;
    }

    free_sys(&S);
    free(C.ph); free(C.x); free(C.g); free(C.z);
    free(active); free(row_el); free(bn); free(mu); free(mu_pol); free(shift); free(A); free(cvec); free(x);
    free(basis); free(Binv); free(xb); free(y); free(yb);
    return R;

fail:
    mqmqa_gem_free(R);
    free_sys(&S);
    free(C.ph); free(C.x); free(C.g); free(C.z);
    free(active); free(row_el); free(bn); free(mu); free(mu_pol); free(shift); free(A); free(cvec); free(x);
    free(basis); free(Binv); free(xb); free(y); free(yb);
    return NULL;
}

/* The fixed-composition liquid solve that supplies the MQMQA candidates is finished exactly
 * for this solve only (mqmqa_exact_finish), so the shipped path elsewhere is unchanged.
 *
 * With the default grid, no result, or one holding an MQMQA liquid that the exact finish could
 * not solve, is tried again on coarser grids. Beside a liquid miscibility gap the samples of one
 * grid can leave the search short (1.9 J/mol at 1974 K in FeO-MgO-SiO2 on grid 6, 19 J/mol at
 * 1958 K on grid 3). Every column is a real state, so each result's G is an upper bound on the
 * equilibrium: the lowest is kept, an exact one preferred at equal G. A result of solids alone
 * is not retried; olivine alone, for one, is never finished exactly and is right as it is. */
static int gem_unsure(const mqmqa_db *db, const mqmqa_gem *r)
{
    if (!r) return 1;
    if (r->exact) return 0;
    const Db *d = (const Db *)db;
    for (int s = 0; s < r->n_sets; ++s)
        if (r->phase[s] >= 0 && d->phases[r->phase[s]].kind == 0) return 1;
    return 0;
}

static int gem_better(const mqmqa_gem *a, const mqmqa_gem *b)
{
    if (!b) return 1;
    const double tol = 1e-6 * fmax(1.0, fabs(b->G));
    if (a->G < b->G - tol) return 1;
    return a->G <= b->G + tol && a->exact && !b->exact;
}

mqmqa_gem *mqmqa_gem_equilibrium(const mqmqa_db *db, double T, const double *b,
                                 const int *suspended, int grid, int max_iter)
{
    const int was = mqmqa_exact_finish(1);
    mqmqa_gem *R = gem_solve(db, T, b, suspended, grid, max_iter);
    if (grid <= 0 && gem_unsure(db, R)) {
        char err[512] = "";
        if (!R) snprintf(err, sizeof err, "%s", mqmqa_db_error());
        static const int retry[] = { 3, 2 };
        for (int k = 0; k < 2 && gem_unsure(db, R); ++k) {
            mqmqa_gem *Q = gem_solve(db, T, b, suspended, retry[k], max_iter);
            if (Q && gem_better(Q, R)) { mqmqa_gem_free(R); R = Q; }
            else mqmqa_gem_free(Q);
        }
        if (!R) mqmqa_db_set_error("%s", err);
    }
    mqmqa_exact_finish(was);
    return R;
}

void mqmqa_gem_free(mqmqa_gem *r)
{
    if (!r) return;
    free(r->phase); free(r->amount); free(r->x); free(r->mu);
    free(r);
}

int mqmqa_gem_num_sets(const mqmqa_gem *r) { return r ? r->n_sets : 0; }
int mqmqa_gem_set_phase(const mqmqa_gem *r, int k) { return (r && k >= 0 && k < r->n_sets) ? r->phase[k] : 0; }
double mqmqa_gem_set_amount(const mqmqa_gem *r, int k) { return (r && k >= 0 && k < r->n_sets) ? r->amount[k] : NAN; }
void mqmqa_gem_set_x(const mqmqa_gem *r, int k, double *x)
{
    if (!r || k < 0 || k >= r->n_sets || !x) return;
    memcpy(x, r->x + (size_t)k * r->n_el, (size_t)r->n_el * sizeof(double));
}
double mqmqa_gem_G(const mqmqa_gem *r) { return r ? r->G : NAN; }
void mqmqa_gem_mu(const mqmqa_gem *r, double *mu)
{
    if (r && mu) memcpy(mu, r->mu, (size_t)r->n_el * sizeof(double));
}
double mqmqa_gem_residual(const mqmqa_gem *r) { return r ? r->residual : NAN; }
int mqmqa_gem_passes(const mqmqa_gem *r) { return r ? r->passes : 0; }
int mqmqa_gem_exact(const mqmqa_gem *r) { return r ? r->exact : 0; }
