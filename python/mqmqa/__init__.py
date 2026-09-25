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
    GAS_CONSTANT_MODES,
    GAS_CONSTANT_SOURCES,
    set_gas_constant,
    gas_constant_mode,
    gas_constant_choice,
    gas_constant,
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
    "GAS_CONSTANT_MODES",
    "GAS_CONSTANT_SOURCES",
    "set_gas_constant",
    "gas_constant_mode",
    "gas_constant_choice",
    "gas_constant",
    "ConversionError",
    "Database",
    "UnsupportedModelError",
    "XTDB",
    "enumerate_quadruplets",
]
