"""mqmqa: a small standalone Modified Quasichemical Model (quadruplet approximation).

C core loaded through cffi in ABI mode, so no compiler is needed at import time,
only the prebuilt shared library. Build it with scripts/build.sh.
"""

from ._abi import (
    R,
    ideal_entropy_binary,
    reference_energy,
    ideal_mixing_energy,
    excess_energy,
    coordination,
    c_equilibrate,
)
from ._database import ConversionError, Database, UnsupportedModelError, enumerate_quadruplets
from ._xtdb import XTDB

__all__ = [
    "R",
    "ideal_entropy_binary",
    "reference_energy",
    "ideal_mixing_energy",
    "excess_energy",
    "coordination",
    "c_equilibrate",
    "ConversionError",
    "Database",
    "UnsupportedModelError",
    "XTDB",
    "enumerate_quadruplets",
]
