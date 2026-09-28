#ifndef MQMQA_FMTBUF_H
#define MQMQA_FMTBUF_H

/* Formatted text into fixed-size buffers, the same on every C runtime. The release
 * DLL links the mingw-w64 5.3 msvcrt, whose snprintf and vsnprintf return -1 when the
 * text does not fit and then leave the buffer unterminated (also when the text fills
 * it exactly). These always terminate and report a cut instead of a length, so no
 * caller adds a return value to an offset. Header-only and internal. */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#if defined(__GNUC__) || defined(__clang__)
#define FMT_PRINTF(f, a) __attribute__((format(printf, f, a)))
#else
#define FMT_PRINTF(f, a)
#endif

/* 0 when the whole text fit in dst[cap], 1 when it was cut to the prefix that fit. */
static inline int fmt_vto(char *dst, size_t cap, const char *fmt, va_list ap)
{
    int n;
    if (cap == 0) return 1;
    n = vsnprintf(dst, cap, fmt, ap);
    dst[cap - 1] = '\0';
    return n < 0 || (size_t)n >= cap;
}

static inline int fmt_to(char *dst, size_t cap, const char *fmt, ...) FMT_PRINTF(3, 4);
static inline int fmt_to(char *dst, size_t cap, const char *fmt, ...)
{
    va_list ap;
    int cut;
    va_start(ap, fmt);
    cut = fmt_vto(dst, cap, fmt, ap);
    va_end(ap);
    return cut;
}

/* Append to the terminated text already in dst[cap]; same result as fmt_to. */
static inline int fmt_cat(char *dst, size_t cap, const char *fmt, ...) FMT_PRINTF(3, 4);
static inline int fmt_cat(char *dst, size_t cap, const char *fmt, ...)
{
    va_list ap;
    size_t n = strlen(dst);
    int cut;
    if (n >= cap) return 1;
    va_start(ap, fmt);
    cut = fmt_vto(dst + n, cap - n, fmt, ap);
    va_end(ap);
    return cut;
}

/* A message cut to fit ends in "..." so the reader can tell. */
static inline void fmt_mark_cut(char *dst, size_t cap)
{
    if (cap > 4) memcpy(dst + cap - 4, "...", 4);
}

static inline void fmt_vmsg(char *dst, size_t cap, const char *fmt, va_list ap)
{
    if (fmt_vto(dst, cap, fmt, ap)) fmt_mark_cut(dst, cap);
}

static inline void fmt_msg(char *dst, size_t cap, const char *fmt, ...) FMT_PRINTF(3, 4);
static inline void fmt_msg(char *dst, size_t cap, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fmt_vmsg(dst, cap, fmt, ap);
    va_end(ap);
}

#endif /* MQMQA_FMTBUF_H */
