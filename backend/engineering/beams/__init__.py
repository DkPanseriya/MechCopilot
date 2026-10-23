"""Beam calculators: FE beam analysis, section properties, standard profile selection."""
from typing import List

from ..core import Calculator
from .calcs import CALCULATORS as _CALCS

CALCULATORS: List[Calculator] = list(_CALCS)
