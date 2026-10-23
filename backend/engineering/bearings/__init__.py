"""Bearing calculators: ISO 281 life, bearing finder, required load rating. Exports CALCULATORS."""
from typing import List

from ..core import Calculator
from .calcs import CALCULATORS as _CALCS

CALCULATORS: List[Calculator] = list(_CALCS)
