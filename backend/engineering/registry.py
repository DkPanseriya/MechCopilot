"""Calculator catalog: every domain module contributes its CALCULATORS list."""
from typing import Dict, List

from .core import Calculator
from .general import CALCULATORS as _general
from .fasteners import CALCULATORS as _fasteners
from .bearings import CALCULATORS as _bearings
from .beams import CALCULATORS as _beams
from .transmission import CALCULATORS as _transmission
from .structural import CALCULATORS as _structural

CATEGORY_ORDER = ["Fasteners", "Bearings", "Beams", "Shafts", "Keys & Fits", "Gears",
                  "Springs", "Welds", "Columns", "Pressure Vessels", "Fatigue", "Stress",
                  "Formulas"]

ALL: List[Calculator] = [*_fasteners, *_bearings, *_beams, *_transmission, *_structural,
                         *_general]

CATALOG: Dict[str, Calculator] = {}
for _c in ALL:
    if _c.id in CATALOG:
        raise RuntimeError(f"Duplicate calculator id: {_c.id}")
    CATALOG[_c.id] = _c


def _category_rank(cat: str) -> int:
    return CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)


def ordered() -> List[Calculator]:
    return sorted(CATALOG.values(), key=lambda c: (_category_rank(c.category), c.title))


def register(calcs: List[Calculator]) -> None:
    """Late registration (e.g. auto-generated formula calculators)."""
    for c in calcs:
        if c.id in CATALOG:
            raise RuntimeError(f"Duplicate calculator id: {c.id}")
        CATALOG[c.id] = c
        ALL.append(c)
