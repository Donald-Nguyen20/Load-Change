# -*- coding: utf-8 -*-
from datetime import datetime
from PySide6.QtCore import QTime
from modules.Hold_module import get_mw_at


def tick_time_edits(widget):
    """Cập nhật thời gian & MW theo thời gian thực nếu đang bật chế độ live."""
    now = QTime.currentTime()

    # Cập nhật nếu đang ở chế độ live và không có focus (tránh ghi đè khi người dùng đang gõ)
    if getattr(widget, "_live_start_time", False) and widget.start_time_edit is not None \
            and not widget.start_time_edit.hasFocus():
        widget.start_time_edit.setTime(now)

    if getattr(widget, "_live_hold_time", False) and widget.holding_time_edit is not None \
            and not widget.holding_time_edit.hasFocus():
        widget.holding_time_edit.setTime(now)

    if getattr(widget, "_live_join_time", False) and getattr(widget, "join_time_edit", None) is not None \
            and not widget.join_time_edit.hasFocus():
        widget.join_time_edit.setTime(now)

    # Auto-update Edit Time (Hold Now) nếu đang bật auto & không focus
    if getattr(widget, "_live_holdnow_time", False) and hasattr(widget, "hold_now_time_edit") \
            and widget.hold_now_time_edit is not None and not widget.hold_now_time_edit.hasFocus():
        widget.hold_now_time_edit.setTime(QTime.currentTime())

    # Auto-update Hold MW nếu đang bật auto & ô không focus
    try:
        if getattr(widget, "_live_holdnow_mw", False) and hasattr(widget, "hold_now_mw_edit") \
                and (widget.hold_now_mw_edit is not None) and (not widget.hold_now_mw_edit.hasFocus()):
            # Lấy MW tức thời từ series (ưu tiên joined nếu có)
            profile_now = widget.build_current_profile()
            top_xy = profile_now.get("joined_xy") or profile_now.get("main_xy")
            if top_xy:
                mw_now = get_mw_at(top_xy, datetime.now())
                if mw_now is not None:
                    widget.hold_now_mw_edit.setText(f"{mw_now:.1f}")
    except Exception:
        pass

    # Refresh vạch PREVIEW theo thời gian thực khi chưa Hold Now
    try:
        if not widget.hard_hold_active:
            widget.update_plot()
    except Exception:
        pass
