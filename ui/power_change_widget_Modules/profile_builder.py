# -*- coding: utf-8 -*-
# modules/profile_builder.py
from __future__ import annotations
from typing import Any, Dict



def build_current_profile_from_widget(w: Any) -> Dict[str, Any]:
    """
    Đọc state từ widget (w) và trả về:
      {
        "main_xy":   {"x": [dt...], "y": [mw...]} | None,
        "joined_xy": {"x": [dt...], "y": [mw...]} | None,
        "markers":   {name: datetime, ...}
      }
    Dùng getattr để an toàn khi thiếu thuộc tính.
    """
    # main
    main_xy = None
    times1 = getattr(w, "times1", None)
    powers1 = getattr(w, "powers1", None)
    if times1 and powers1:
        main_xy = {"x": list(times1), "y": list(powers1)}

    # joined (từ kế hoạch nối lệnh)
    joined_xy = None
    segs = getattr(w, "current_plan_segments", None) or []
    if segs:
        jx = [seg["t"] for seg in segs]
        jy = [seg["mw"] for seg in segs]
        joined_xy = {"x": jx, "y": jy}

    # markers
    markers = {
        "t_429":          getattr(w, "time_reaching_429", None),
        "post_pause":     getattr(w, "post_pause_time", None),
        "hold_start_462": getattr(w, "time_holding_462", None),
        "hold_end_462":   getattr(w, "hold_complete_time", None),
        "final":          getattr(w, "final_load_time", None),
        "override_done":  getattr(w, "override_complete_time", None),
    }
    markers = {k: v for k, v in markers.items() if v is not None}

    return {"main_xy": main_xy, "joined_xy": joined_xy, "markers": markers}
