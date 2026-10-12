/* Expression reading in the TDB and XTDB readers, driven through the C API.
 *
 * Built and run by tests/test_tdb_expressions_c.py, which compiles it with every file in
 * src/ (no DLL involved). Prints one line per failed check and exits non-zero on any. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "cs_dat.h"
#include "xtdb.h"

static int failures = 0;

static mqmqa_db *read_gx(const char *expr)
{
    char text[1024];
    snprintf(text, sizeof text,
             "ELEMENT X BLANK 1 0 0 !\n"
             "FUNCTION GC 298.15 4; 3000 N !\n"
             "FUNCTION GX 298.15 %s; 3000 N !\n"
             "PHASE A %% 1 1 !\n"
             "CONSTITUENT A :X: !\n"
             "PARAMETER G(A,X;0) 298.15 GX#; 3000 N !\n", expr);
    return mqmqa_db_read_string(text);
}

/* the one-endmember phase A is read as stoichiometric compound 0 */
static void expect_value(const char *expr, double want)
{
    mqmqa_db *db = read_gx(expr);
    double got;
    if (!db) {
        printf("FAIL %s: read error %s\n", expr, mqmqa_db_error());
        failures++;
        return;
    }
    got = mqmqa_db_stoich_gibbs(db, 0, 400.0);
    if (!(fabs(got - want) <= 1e-12 * fmax(1.0, fabs(want)))) {
        printf("FAIL %s: %.17g, expected %.17g\n", expr, got, want);
        failures++;
    }
    mqmqa_db_free(db);
}

static void expect_error(const char *expr, const char *needle)
{
    mqmqa_db *db = read_gx(expr);
    if (db) {
        printf("FAIL %s: read without error\n", expr);
        failures++;
        mqmqa_db_free(db);
        return;
    }
    if (!strstr(mqmqa_db_error(), needle)) {
        printf("FAIL %s: error '%s' does not mention '%s'\n", expr, mqmqa_db_error(), needle);
        failures++;
    }
}

static const char *xtdb_text(char *buf, size_t cap, const char *expr)
{
    snprintf(buf, cap,
             "<XTDB version=\"0.1\"><Defaults LowT=\"298.15\" HighT=\"3000\" Elements=\"VA\"/>\n"
             "<Element Id=\"X\" Refstate=\"A\" Mass=\"1\" H298=\"0\" S298=\"0\"/>\n"
             "<Phase Id=\"A\" Configuration=\"CEF\"><Sublattices NumberOf=\"1\" Multiplicities=\"1\"/>"
             "<Constituents Sublattice=\"1\" List=\"X\"/></Phase>\n"
             "<Parameter Id=\"G(A,X;0)\" Expr=\"%s\"/>\n</XTDB>\n", expr);
    return buf;
}

static void expect_xtdb(const char *expr, double want)
{
    char buf[1024];
    int ok = 0;
    xtdb_db *db = xtdb_read_string(xtdb_text(buf, sizeof buf, expr));
    double got;
    if (!db) {
        printf("FAIL xtdb %s: read error %s\n", expr, xtdb_error());
        failures++;
        return;
    }
    got = xtdb_endmember_gibbs(db, "A", "X", 400.0, &ok);
    if (!ok || !(fabs(got - want) <= 1e-12 * fmax(1.0, fabs(want)))) {
        printf("FAIL xtdb %s: %.17g (ok %d), expected %.17g\n", expr, got, ok, want);
        failures++;
    }
    xtdb_free(db);
}

static void expect_xtdb_error(const char *expr)
{
    char buf[1024];
    xtdb_db *db = xtdb_read_string(xtdb_text(buf, sizeof buf, expr));
    if (db) {
        printf("FAIL xtdb %s: read without error\n", expr);
        failures++;
        xtdb_free(db);
    }
}

int main(void)
{
    const double T = 400.0;

    expect_value("1000*T**(-1)", 1000.0 / T);
    expect_value("1000/T", 1000.0 / T);
    expect_value("1000/T**2", 1000.0 / (T * T));
    expect_value("1000/T**0.5", 1000.0 / sqrt(T));
    expect_value("5+1000/T", 5.0 + 1000.0 / T);
    expect_value("1000/(T)", 1000.0 / T);
    expect_value("1000/T/2", 1000.0 / T / 2.0);
    expect_value("1000/(2*T)", 1000.0 / (2.0 * T));
    expect_value("-T**2", -T * T);
    expect_value("2**3**2", 512.0);
    expect_value("T**-1*1000", 1000.0 / T);
    expect_value("(T+1)*2/T", (T + 1.0) * 2.0 / T);
    expect_value("GC#/8", 0.5);
    expect_value("1000/GC#", 250.0);
    expect_value("GC#**(-1)*T", T / 4.0);
    expect_value("-24.3671976*T*LN(T)+74092/T", -24.3671976 * T * log(T) + 74092.0 / T);

    expect_error("1000 @ 5", "unexpected text");
    expect_error("2T", "unexpected text");
    expect_error("1000/", "expected a number");
    expect_error("(1000/T", "missing ')'");
    expect_error("1000/0", "division by zero");
    expect_error("1000/(T+1)", "division by a sum");
    expect_error("LOG(T)", "LOG(...)");
    expect_error("T*LN(T)*T", "LN(T) other than");

    expect_xtdb("1000/T;", 1000.0 / T);
    expect_xtdb("-T**2;", -T * T);
    expect_xtdb("1000/T**2/5;", 1000.0 / (T * T) / 5.0);
    expect_xtdb_error("1000 @ 5;");
    expect_xtdb_error("2*NOPE;");

    if (failures) printf("%d failure(s)\n", failures);
    else printf("all passed\n");
    return failures ? 1 : 0;
}
