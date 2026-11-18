# FactSage cases A, B and C: comparison run once after unsealing

Engines: {"C": {"engine_commit": "3f38162", "engine_dirty": false}, "A": {"engine_commit": "754177c", "engine_dirty": false}, "B": {"engine_commit": "754177c", "engine_dirty": false}}. Rules in compare.py.

## Case A

Class counts: agree 4, disagree 11

| id | reaction | FactSage T (K) | Hephaestus T (K) | dT (K) | FactSage x | Hephaestus x | dx | class |
|---|---|---|---|---|---|---|---|---|
| A01 | LiCl = L | 883 | 882.983 | -0.017 |  |  |  | agree |
| A02 | Li4ThCl8 = LiCl + L | 723 | 724.904 | +1.904 |  |  |  | disagree |
| A03 | Li4ThCl8 + beta-ThCl4 = L | 695 | 696.746 | +1.746 | 0.343 | 0.34287 | -0.00013 | disagree |
| A04 | alpha-ThCl4 = beta-ThCl4 | 679 | 679.142 | +0.142 |  |  |  | agree |
| A05 | beta-ThCl4 = L | 1042 | 1043.010 | +1.010 |  |  |  | disagree |
| A06 | NaCl = L | 1074 | 1074.003 | +0.003 |  |  |  | agree |
| A07 | NaCl + Na2ThCl6 = L | 657 | 659.178 | +2.178 | 0.251 | 0.24969 | -0.00131 | disagree |
| A08 | Na2ThCl6 = L | 703 | 705.233 | +2.233 |  |  |  | disagree |
| A09 | Na2ThCl6 + alpha-ThCl4 = L | 654 | 655.668 | +1.668 | 0.457 | 0.45594 | -0.00106 | disagree |
| A10 | KCl = L | 1044 | 1044.002 | +0.002 |  |  |  | agree |
| A11 | KCl + K2ThCl6 = L | 894 | 894.706 | +0.706 | 0.206 | 0.20594 | -0.00006 | disagree |
| A12 | K2ThCl6 = L | 977 | 977.966 | +0.966 |  |  |  | disagree |
| A13 | K2ThCl6 + KThCl5 = L | 697 | 697.989 | +0.989 | 0.467 | 0.4655 | -0.00150 | disagree |
| A14 | KThCl5 = L | 702 | 703.672 | +1.672 |  |  |  | disagree |
| A15 | KThCl5 + beta-ThCl4 = L | 699 | 699.486 | +0.486 | 0.536 | 0.53531 | -0.00069 | disagree |

## Case B

Class counts: agree 2, disagree 6

| id | reaction | FactSage T (K) | Hephaestus T (K) | dT (K) | FactSage x | Hephaestus x | dx | class |
|---|---|---|---|---|---|---|---|---|
| B01 | L = LiF + LaF3 | 1039 | 1038.799 | -0.201 | 0.159 | 0.15934 | +0.00034 | agree |
| B02 | L = NaF + NaLaF4 | 1006 | 1005.781 | -0.219 | 0.282 | 0.28146 | -0.00054 | disagree |
| B03 | NaLaF4 = L + LaF3 | 1055 | 1056.103 | +1.103 | 0.331 | 0.33231 | +0.00131 | disagree |
| B04 | NaLaF4 = NaF + LaF3 | 686 | 634.481 | -51.519 |  |  |  | disagree |
| B05 | L = LiF + CeF3 | 1024 | 1024.409 | +0.409 | 0.185 | 0.18472 | -0.00028 | agree |
| B06 | L = NaF + NaCeF4 | 1005 | 1005.213 | +0.213 | 0.25 | 0.2538 | +0.00380 | disagree |
| B07 | NaCeF4 = L + CeF3 | 1080 | 1088.445 | +8.445 | 0.32 | 0.33342 | +0.01342 | disagree |
| B08 | NaCeF4 = NaF + CeF3 | 226 | - | NACEF4 is already present at 298.15 K, the bottom of the data |  |  |  | disagree |

## Case C

Class counts: agree 30

| id | FactSage (read) | Hephaestus | difference | read uncertainty | class |
|---|---|---|---|---|---|
| C-G-00 | -381.328 | -381.289 | +0.039 | 1.0 | agree |
| C-G-01 | -372.891 | -372.853 | +0.038 | 1.0 | agree |
| C-G-02 | -364.315 | -363.898 | +0.417 | 1.0 | agree |
| C-G-03 | -355.325 | -354.894 | +0.431 | 1.0 | agree |
| C-G-04 | -346.473 | -345.880 | +0.593 | 1.0 | agree |
| C-G-05 | -337.206 | -336.834 | +0.372 | 1.0 | agree |
| C-G-06 | -328.078 | -327.758 | +0.320 | 1.0 | agree |
| C-G-07 | -318.949 | -318.693 | +0.256 | 1.0 | agree |
| C-G-08 | -309.82 | -309.671 | +0.149 | 1.0 | agree |
| C-G-09 | -300.968 | -300.670 | +0.298 | 1.0 | agree |
| C-H-00 | -230.617 | -230.343 | +0.274 | 0.8 | agree |
| C-H-01 | -222.998 | -222.998 | +0.000 | 0.8 | agree |
| C-H-02 | -216.437 | -216.026 | +0.411 | 0.8 | agree |
| C-H-03 | -209.453 | -209.190 | +0.263 | 0.8 | agree |
| C-H-04 | -202.892 | -202.356 | +0.536 | 0.8 | agree |
| C-H-05 | -195.803 | -195.458 | +0.345 | 0.8 | agree |
| C-H-06 | -188.818 | -188.522 | +0.296 | 0.8 | agree |
| C-H-07 | -181.729 | -181.639 | +0.090 | 0.8 | agree |
| C-H-08 | -175.274 | -174.889 | +0.385 | 0.8 | agree |
| C-H-09 | -168.395 | -168.326 | +0.069 | 0.8 | agree |
| C-S-00 | 94.256 | 94.341 | +0.085 | 0.15 | agree |
| C-S-01 | 93.565 | 93.660 | +0.095 | 0.15 | agree |
| C-S-02 | 92.406 | 92.420 | +0.014 | 0.15 | agree |
| C-S-03 | 91.024 | 91.065 | +0.041 | 0.15 | agree |
| C-S-04 | 89.663 | 89.702 | +0.039 | 0.15 | agree |
| C-S-05 | 88.28 | 88.360 | +0.080 | 0.15 | agree |
| C-S-06 | 86.98 | 87.022 | +0.042 | 0.15 | agree |
| C-S-07 | 85.598 | 85.659 | +0.061 | 0.15 | agree |
| C-S-08 | 84.195 | 84.239 | +0.044 | 0.15 | agree |
| C-S-09 | 82.711 | 82.715 | +0.004 | 0.15 | agree |
