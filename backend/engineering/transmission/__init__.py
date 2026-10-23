"""Transmission calculators (shafts, keys & fits, gears). Exports CALCULATORS."""
from typing import List

from ..core import Calculator
from .gears import CALCULATORS as _gears
from .keys_fits import CALCULATORS as _keys_fits
from .shafts import CALCULATORS as _shafts

CALCULATORS: List[Calculator] = [*_shafts, *_keys_fits, *_gears]
