#ifndef MQMQA_TEXTBUF_H
#define MQMQA_TEXTBUF_H

/* Growable text buffer for the database writers. Header-only and internal: each
 * writer builds the whole file in memory and hands it back only when every model
 * in the database was representable, so a failed conversion never leaves a
 * partial file behind. */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char *s;
    size_t n, cap;
    int oom;
} TextBuf;

static inline void tb_putf(TextBuf *b, const char *fmt, ...)
{
    va_list ap;
    int need;
    if (b->oom) return;
    va_start(ap, fmt);
    need = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (need < 0) { b->oom = 1; return; }
    if (b->n + (size_t)need + 1 > b->cap) {
        size_t cap = b->cap ? b->cap : 4096;
        char *grown;
        while (b->n + (size_t)need + 1 > cap) cap *= 2;
        grown = realloc(b->s, cap);
        if (!grown) { b->oom = 1; return; }
        b->s = grown;
        b->cap = cap;
    }
    va_start(ap, fmt);
    vsnprintf(b->s + b->n, b->cap - b->n, fmt, ap);
    va_end(ap);
    b->n += (size_t)need;
}

/* Shortest %G text that reads back to exactly v, so a written coefficient is
 * the stored double, not a rounding of it. */
static inline const char *tb_num(char out[40], double v)
{
    int prec;
    if (v == 0.0) { strcpy(out, "0"); return out; }
    for (prec = 15; prec <= 17; ++prec) {
        snprintf(out, 40, "%.*G", prec, v);
        if (strtod(out, NULL) == v) break;
    }
    {   /* some C runtimes print three exponent digits (E-008); drop the padding */
        char *e = strchr(out, 'E');
        if (e && (e[1] == '+' || e[1] == '-'))
            while (e[2] == '0' && e[3] >= '0' && e[3] <= '9')
                memmove(e + 2, e + 3, strlen(e + 3) + 1);
    }
    return out;
}

#endif /* MQMQA_TEXTBUF_H */
