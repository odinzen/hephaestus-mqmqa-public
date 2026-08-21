#include "mqmqa.h"
#include <math.h>

/* CODATA 2018 exact value. */
#define MQMQA_R_CONST 8.314462618

double mqmqa_R(void)
{
    return MQMQA_R_CONST;
}

double mqmqa_ideal_entropy_binary(double x)
{
    if (x <= 0.0 || x >= 1.0) {
        return 0.0; /* endpoints: pure, zero configurational entropy */
    }
    return -MQMQA_R_CONST * (x * log(x) + (1.0 - x) * log(1.0 - x));
}
