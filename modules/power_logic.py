# power_logic.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Union
from datetime import datetime, timedelta

PulsMode = Literal["3 Puls", "4 Puls"]

@dataclass
class CalcConfig:
    threshold_429: float = 429.0
    hold_power: float = 462.0
    pause_time_429_min: int = 0      # dừng tại 429 MW (phút)
    pause_time_hold_min: int = 30    # giữ tại holding MW (phút)
    pulverizer_mode: PulsMode = "4 Puls"

@dataclass
class CalcResult:
    times: List[datetime]
    powers: List[float]
    final_load_time: datetime
    time_reaching_429: Optional[datetime]
    post_pause_time: Optional[datetime]
    time_holding_462: Optional[datetime]
    hold_complete_time: Optional[datetime]

def _parse_time_flex(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%H:%M:%S")
    except ValueError:
        return datetime.strptime(s, "%H:%M")

def compute_power_change_and_pauses(
    start_power: float,
    target_power: float,
    start_time: Union[str, datetime],
    cfg: CalcConfig,
) -> CalcResult:
    """
    Tính timeline tăng/giảm tải theo GIÂY, áp dụng pause tại mốc 429 MW và holding MW.
    Quy ước ramp mới:
      <330 MW: 0.11 MW/giây   (tương đương 6.6 MW/phút)
      >=330 MW: 0.22 MW/giây  (tương đương 13.2 MW/phút)
    """
    if isinstance(start_time, str):
        start_time = _parse_time_flex(start_time)

    current_power = float(start_power)
    increasing = start_power < target_power

    times = [start_time]
    powers = [start_power]

    time_reaching_429: Optional[datetime] = None
    post_pause_time:   Optional[datetime] = None
    time_holding_462:  Optional[datetime] = None
    hold_complete_time:Optional[datetime] = None
    pause_time_added = False

    t = start_time

    # Bước thời gian theo giây
    STEP = timedelta(seconds=1)
    # Tránh vòng lặp vô hạn (1 ngày = 86400 bước)
    MAX_SECONDS = 24 * 60 * 60
    EPS = 1e-9

    for _ in range(MAX_SECONDS):
        # tốc độ theo ngưỡng 330 MW (đơn vị MW/giây)
        power_rate = 0.11 if current_power < 330 else 0.22

        if increasing:
            # chạm 429 khi đang tăng
            if (start_power < cfg.threshold_429
                and current_power >= cfg.threshold_429
                and time_reaching_429 is None):
                time_reaching_429 = t
                if not pause_time_added:
                    if cfg.pulverizer_mode == "3 Puls":
                        t += timedelta(minutes=15)
                    else:  # 4 Puls
                        t += timedelta(minutes=0)
                    post_pause_time = t
                    pause_time_added = True

            # clamp bước cuối
            if current_power + power_rate > target_power:
                power_rate = max(0.0, target_power - current_power)

            current_power += power_rate

        else:
            # Giữ tại holding MW khi đang GIẢM
            if (target_power < cfg.hold_power
                and current_power <= cfg.hold_power
                and start_power > cfg.hold_power
                and time_holding_462 is None):
                time_holding_462 = t
                if cfg.pulverizer_mode == "3 Puls":
                    t += timedelta(minutes=15)
                else:
                    t += timedelta(minutes=cfg.pause_time_hold_min)
                hold_complete_time = t

            # đạt 429 khi giảm tải
            if (start_power > cfg.threshold_429
                and current_power <= cfg.threshold_429
                and time_reaching_429 is None):
                time_reaching_429 = t
                if not pause_time_added:
                    if cfg.pulverizer_mode == "3 Puls":
                        t += timedelta(minutes=25)
                    else:
                        t += timedelta(minutes=cfg.pause_time_429_min)
                    post_pause_time = t
                    pause_time_added = True

            # clamp bước cuối
            if current_power - power_rate < target_power:
                power_rate = max(0.0, current_power - target_power)

            current_power -= power_rate

        # tiến thời gian 1 giây + lưu điểm
        t += STEP
        times.append(t)
        powers.append(current_power)

        # dừng khi đạt target
        if abs(current_power - target_power) < EPS:
            break

    final_load_time = t

    return CalcResult(
        times=times,
        powers=powers,
        final_load_time=final_load_time,
        time_reaching_429=time_reaching_429,
        post_pause_time=post_pause_time,
        time_holding_462=time_holding_462,
        hold_complete_time=hold_complete_time,
    )
