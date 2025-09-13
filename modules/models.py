# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class UIConfig:
    threshold_429: float = 429.0
    hold_power: float = 462.0
    final_load_mw: float = 560.0
    pause_time_429_min: int = 0
    pause_time_hold_min: int = 30
    pulverizer_mode_default: str = "3 Puls"

@dataclass
class CalcResultSimple:
    times: List[datetime]
    powers: List[float]
    final_load_time: Optional[datetime]
    time_reaching_429: Optional[datetime]
    post_pause_time: Optional[datetime]
    time_holding_462: Optional[datetime]
    hold_complete_time: Optional[datetime]
