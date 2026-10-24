"""Transmission calculators (shafts, keys & fits, gears). Exports CALCULATORS."""
from typing import List

from ..core import Calculator
from .drives import CALCULATORS as _drives
from .gears import CALCULATORS as _gears
from .keys_fits import CALCULATORS as _keys_fits
from .shafts import CALCULATORS as _shafts

CALCULATORS: List[Calculator] = [*_drives, *_shafts, *_keys_fits, *_gears]
