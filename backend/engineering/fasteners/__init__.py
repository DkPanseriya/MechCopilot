"""Fastener calculators (ISO metric bolts, VDI 2230, EN 1993-1-8). Exports CALCULATORS."""
from typing import List

from ..core import Calculator
from .joint import BOLTED_JOINT
from .selector import FASTENER_SELECTOR
from .shear import BOLT_GROUP_ECCENTRIC, BOLT_SHEAR_JOINT, THREAD_ENGAGEMENT
from .tightening import BOLT_PRELOAD_TORQUE, FASTENER_LOOKUP

CALCULATORS: List[Calculator] = [
    FASTENER_SELECTOR,
    FASTENER_LOOKUP,
    BOLT_PRELOAD_TORQUE,
    BOLTED_JOINT,
    BOLT_SHEAR_JOINT,
    THREAD_ENGAGEMENT,
    BOLT_GROUP_ECCENTRIC,
]
