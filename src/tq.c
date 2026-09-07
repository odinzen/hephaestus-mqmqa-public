/* OCASI-compatible interface implementation (see tq.h). A thin stateful layer over
 * the validated equilibrium engine: tq_compute_equilibrium detects the MQMQA liquid,
 * the CEF solid solutions and the stoichiometric compounds, converts the component
 * (element) composition to the engine's cation basis, and calls
 * mqmqa_equilibrium_ternary. Results are read with tq_G / tq_stable_phase / ...
 *
 * Phases are presented as one unified list so stoichiometric compounds appear as
 * phases the way OCASI expects: index 0..nph-1 are database phases, nph..nph+nst-1
 * are the stoichiometric compounds.
 */
#include "tq.h"
#include "cs_dat.h"

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TQ_ELEN 8

struct tq_ctx {
    mqmqa_db *db;
    int ncomp;                 /* components = database elements */
    double T, P;
    double *amount;            /* [ncomp] set composition */
    int *status;               /* [nph+nst] phase status: <0 suspended, 0 entered */
    int have;                  /* an equilibrium has been computed */
    int nstable;
    int *stable_ph;            /* [<=8] unified phase indices */
    double *stable_amt;
    double gm;                 /* per mole cation */
    char err[256];
};

static void tq_el_of(const char *name, char *out)
{
    int j = 0;
    for (const char *p = name; *p && j < TQ_ELEN-1 && isalpha((unsigned char)*p); ++p)
        out[j++] = (char)toupper((unsigned char)*p);
    out[j] = '\0';
    if (j == 0) { strncpy(out, name, TQ_ELEN-1); out[TQ_ELEN-1] = '\0'; }
}

tq_ctx *tq_init(void)
{
    tq_ctx *c = calloc(1, sizeof(*c));
    if (c) { c->T = 1000.0; c->P = 101325.0; }
    return c;
}

void tq_free(tq_ctx *c)
{
    if (!c) return;
    if (c->db) mqmqa_db_free(c->db);
    free(c->amount); free(c->status); free(c->stable_ph); free(c->stable_amt);
    free(c);
}

const char *tq_error(const tq_ctx *c) { return c ? c->err : ""; }

static int tq_num_all_phases(const tq_ctx *c)
{
    return mqmqa_db_num_phases(c->db) + mqmqa_db_num_stoich(c->db);
}

int tq_read_string(tq_ctx *c, const char *text)
{
    if (!c) return 1;
    if (c->db) { mqmqa_db_free(c->db); c->db = NULL; }
    c->db = mqmqa_db_read_string(text);
    if (!c->db) {
        snprintf(c->err, sizeof c->err, "%s", mqmqa_db_error());
        return 1;
    }
    c->ncomp = mqmqa_db_num_elements(c->db);
    free(c->amount); c->amount = calloc((size_t)c->ncomp, sizeof(double));
    int nall = tq_num_all_phases(c);
    free(c->status); c->status = calloc((size_t)nall, sizeof(int));
    c->have = 0;
    c->err[0] = '\0';
    return 0;
}

int tq_num_components(const tq_ctx *c) { return c ? c->ncomp : 0; }
const char *tq_component(const tq_ctx *c, int i) { return mqmqa_db_element(c->db, i); }

int tq_num_phases(const tq_ctx *c) { return c ? tq_num_all_phases(c) : 0; }

const char *tq_phase_name(const tq_ctx *c, int p)
{
    int nph = mqmqa_db_num_phases(c->db);
    if (p < nph) return mqmqa_db_phase_name(c->db, p);
    return mqmqa_db_stoich_name(c->db, p - nph);
}

int tq_phase_index(const tq_ctx *c, const char *name)
{
    int nall = tq_num_all_phases(c);
    for (int p = 0; p < nall; ++p)
        if (!strcmp(tq_phase_name(c, p), name)) return p;
    return -1;
}

int tq_set_TP(tq_ctx *c, double T, double P) { c->T = T; c->P = P; c->have = 0; return 0; }

int tq_set_composition(tq_ctx *c, const double *amount)
{
    for (int i = 0; i < c->ncomp; ++i) c->amount[i] = amount[i];
    c->have = 0;
    return 0;
}

int tq_set_phase_status(tq_ctx *c, int p, int status)
{
    if (p < 0 || p >= tq_num_all_phases(c)) return 1;
    c->status[p] = status;
    c->have = 0;
    return 0;
}

/* tag from mqmqa_equilibrium_ternary -> unified phase index */
static int tq_tag_to_phase(const tq_ctx *c, int tag)
{
    int nph = mqmqa_db_num_phases(c->db);
    return tag >= 0 ? tag : nph + (-tag - 1);
}

int tq_compute_equilibrium(tq_ctx *c)
{
    if (!c || !c->db) return 1;
    c->have = 0;
    int nph = mqmqa_db_num_phases(c->db);

    /* the MQMQA liquid: first phaseKind-0 phase not suspended */
    int liq = -1;
    for (int p = 0; p < nph; ++p)
        if (mqmqa_db_phase_kind(c->db, p) == 0 && c->status[p] >= 0) { liq = p; break; }
    if (liq < 0) { snprintf(c->err, sizeof c->err, "no MQMQA liquid phase"); return 2; }

    int ncat = mqmqa_ph_num_cations(c->db, liq);
    if (ncat != 3) { snprintf(c->err, sizeof c->err, "engine handles 3-cation systems"); return 3; }

    /* CEF solid solutions (kind 1), not suspended */
    int *cefs = malloc((size_t)nph * sizeof(int)); int ncef = 0;
    for (int p = 0; p < nph; ++p)
        if (mqmqa_db_phase_kind(c->db, p) == 1 && c->status[p] >= 0) cefs[ncef++] = p;

    /* cation elements of the liquid -> component (element) indices; axes = cations 0,1 */
    char csym[3][TQ_ELEN];
    int celem[3];
    for (int i = 0; i < 3; ++i) {
        tq_el_of(mqmqa_ph_cation(c->db, liq, i), csym[i]);
        celem[i] = -1;
        for (int e = 0; e < c->ncomp; ++e)
            if (!strcmp(mqmqa_db_element(c->db, e), csym[i])) { celem[i] = e; break; }
    }
    int elem_a = celem[0], elem_b = celem[1];

    /* convert the set composition to cation fractions of cation 0 and cation 1 */
    double catsum = 0.0;
    for (int i = 0; i < 3; ++i) catsum += (celem[i] >= 0 ? c->amount[celem[i]] : 0.0);
    if (catsum <= 0) { free(cefs); snprintf(c->err, sizeof c->err, "no cations in composition"); return 4; }
    double qa = c->amount[elem_a] / catsum;
    double qb = c->amount[elem_b] / catsum;

    /* suspended stoichiometric compounds (unified index nph + j) */
    int nst = mqmqa_db_num_stoich(c->db);
    int *ssusp = malloc((size_t)(nst ? nst : 1) * sizeof(int));
    for (int j = 0; j < nst; ++j) ssusp[j] = (c->status[nph + j] < 0) ? 1 : 0;

    int po[8]; double am[8]; double gm = NAN;
    int m = mqmqa_equilibrium_ternary_ex(c->db, liq, cefs, ncef, c->T, 120, 60,
                                         elem_a, elem_b, qa, qb, ssusp, 1,
                                         po, am, 8, &gm);
    free(cefs); free(ssusp);
    if (m < 0) { snprintf(c->err, sizeof c->err, "equilibrium failed (%d)", m); return 5; }

    free(c->stable_ph); free(c->stable_amt);
    c->stable_ph = malloc((size_t)m * sizeof(int));
    c->stable_amt = malloc((size_t)m * sizeof(double));
    for (int k = 0; k < m; ++k) {
        c->stable_ph[k] = tq_tag_to_phase(c, po[k]);
        c->stable_amt[k] = am[k];
    }
    c->nstable = m; c->gm = gm; c->have = 1;
    c->err[0] = '\0';
    return 0;
}

double tq_G(const tq_ctx *c) { return (c && c->have) ? c->gm : NAN; }
int tq_num_stable_phases(const tq_ctx *c) { return (c && c->have) ? c->nstable : 0; }

int tq_stable_phase(const tq_ctx *c, int k, double *amount)
{
    if (!c || !c->have || k < 0 || k >= c->nstable) return -1;
    if (amount) *amount = c->stable_amt[k];
    return c->stable_ph[k];
}

/* per-phase composition and chemical potentials: not yet exposed by the engine's
 * assemblage result; reserved for the mapping-refinement stage. */
int tq_stable_phase_composition(const tq_ctx *c, int k, double *x_out)
{
    (void)c; (void)k; (void)x_out; return 1;
}
int tq_chemical_potentials(const tq_ctx *c, double *mu_out)
{
    (void)c; (void)mu_out; return 1;
}
