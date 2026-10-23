"""Structural calculators: springs, welds, columns, pressure vessels, fatigue. Exports CALCULATORS."""
from typing import List

from ..core import Calculator
from .columns import CALCULATORS as _columns
from .fatigue import CALCULATORS as _fatigue
from .springs import CALCULATORS as _springs
from .vessels import CALCULATORS as _vessels
from .welds import CALCULATORS as _welds

CALCULATORS: List[Calculator] = [*_springs, *_welds, *_columns, *_vessels, *_fatigue]
