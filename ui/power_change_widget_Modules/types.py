# ui/power_change_widget_Modules/types.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Command:
    start_mw: float
    target_mw: float
    start_time: datetime
    hold_minutes: int
    scheduled_start: datetime | None = None
    hold_start: datetime | None = None
    hold_end: datetime | None = None
