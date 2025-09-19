# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Tuple, Optional


def _scan_last_hold_window_from_segments(segments) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Quét self.current_plan_segments (từ cuối về đầu) để tìm cặp (hold_start, hold_end).
    """
    if not segments:
        return None, None

    hold_end = None
    hold_start = None
    for seg in reversed(segments):
        tag = seg.get("tag")
        if hold_end is None and tag == "hold_end":
            hold_end = seg.get("t")
        elif tag == "hold_start":
            hold_start = seg.get("t")
            if hold_end is not None:
                break

    return hold_start, hold_end


def get_last_command_hold_window(widget) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Trả về (hold_start, hold_end) của lệnh gần nhất nếu có.
    - Nếu có command_queue: ưu tiên lấy từ last.hold_start/hold_end; nếu thiếu thì quét segments.
    - Nếu CHƯA có lệnh nối: fallback dùng cửa sổ hold ở 429 (time_reaching_429 → post_pause_time).
    """
    # Có lệnh nối → đọc từ lệnh cuối
    if getattr(widget, "command_queue", None):
        last = widget.command_queue[-1]
        h_start, h_end = getattr(last, "hold_start", None), getattr(last, "hold_end", None)
        if h_start is not None and h_end is not None:
            return h_start, h_end

        # thử quét từ segments
        segs = getattr(widget, "current_plan_segments", None)
        h_start, h_end = _scan_last_hold_window_from_segments(segs)
        if h_start is not None and h_end is not None:
            # cập nhật ngược vào last để lần sau truy vấn nhanh
            last.hold_start, last.hold_end = h_start, h_end
            return h_start, h_end

        return None, None

    # Chưa có lệnh nối → dùng cửa sổ 429
    hold_start_429 = getattr(widget, "time_reaching_429", None)
    hold_end_429 = getattr(widget, "post_pause_time", None)
    return hold_start_429, hold_end_429


def get_last_command_end_time(widget) -> datetime:
    """
    Trả về end-time của “lệnh gần nhất” để lên lịch tiếp:
    - Nếu CHƯA có lệnh nối: ưu tiên post_pause_time; nếu không có, suy từ time_reaching_429 + pause_429; cuối cùng = now().
    - Nếu ĐÃ có lệnh nối: ưu tiên last.hold_end; nếu thiếu, tìm 'hold_end' trong segments; nếu vẫn thiếu, dùng mốc cuối cùng hoặc scheduled_start/start_time.
    """
    # Chưa có lệnh nối
    if not getattr(widget, "command_queue", None):
        post_pause = getattr(widget, "post_pause_time", None)
        if post_pause:
            return post_pause

        t_429 = getattr(widget, "time_reaching_429", None)
        if t_429 is not None:
            pause_429_min = getattr(widget, "pause_time_429_min", 0) or 0
            return t_429 + timedelta(minutes=pause_429_min)

        return datetime.now()

    # Có lệnh nối
    last = widget.command_queue[-1]
    if getattr(last, "hold_end", None) is not None:
        return last.hold_end

    segs = getattr(widget, "current_plan_segments", None)
    if segs:
        for seg in reversed(segs):
            if seg.get("tag") == "hold_end":
                return seg.get("t")
        # nếu không có hold_end, trả về thời điểm cuối cùng của plan
        return segs[-1].get("t")

    # fallback cuối: scheduled_start hoặc start_time của lệnh cuối
    return getattr(last, "scheduled_start", None) or getattr(last, "start_time")
