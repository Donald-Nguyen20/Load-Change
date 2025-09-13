# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional, Dict, Tuple, Callable

def due(now: datetime, at: Optional[datetime]) -> bool:
    if not at:
        return False
    return (now.hour*3600 + now.minute*60 + now.second) >= (at.hour*3600 + at.minute*60)

def check_and_fire(
    now: datetime,
    timeline: Dict[str, Optional[datetime]],    # {"429": dt, "holding_complete": dt, ...}
    flags: Dict[str, bool],                     # {"429": False, ...}
    say: Callable[[str], None],                 # hàm phát TTS
    messages: Dict[str, str],                   # {"429": "...", ...}
) -> Dict[str, bool]:
    # Trả về flags đã cập nhật
    for key, t_alarm in timeline.items():
        if t_alarm and not flags.get(key, False):
            if due(now, t_alarm):
                say(messages.get(key, key))
                flags[key] = True
    return flags
