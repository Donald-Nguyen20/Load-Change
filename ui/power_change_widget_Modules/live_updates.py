# -*- coding: utf-8 -*-
from datetime import datetime
from PySide6.QtCore import QTime
from modules.Hold_module import get_mw_at


def tick_time_edits(widget):
    """Cập nhật thời gian & MW theo thời gian thực nếu đang bật chế độ live."""
    now_qt = QTime.currentTime()
    now_dt = datetime.now()

    # --- NEW: luôn tính MW live để theo dõi & làm start cho lệnh tiếp theo ---
    
    try:
        # build_current_profile() là method có sẵn trên widget (đã dùng bên dưới)
        profile_now = widget.build_current_profile() if hasattr(widget, "build_current_profile") else {}
        top_xy = profile_now.get("joined_xy") or profile_now.get("main_xy")
        if top_xy:
            mw_live = get_mw_at(top_xy, now_dt)
            if mw_live is not None:
                # 1) Lưu MW "live" chạy xuyên suốt theo thời gian (kể cả khi Hold)
                widget.current_power_live_value = float(mw_live)

                # 2) Khi KHÔNG Hold, setpoint (current_power_value) = live
                if not getattr(widget, "_current_power_frozen", False):
                    widget.current_power_value = float(mw_live)
    except Exception:
        # Không để rơi lỗi ở tick ui
        pass

    # --- Auto update các ô thời gian khi bật live & ô không focus ---
    if getattr(widget, "_live_start_time", False) and widget.start_time_edit is not None \
            and not widget.start_time_edit.hasFocus():
        widget.start_time_edit.setTime(now_qt)

    if getattr(widget, "_live_hold_time", False) and widget.holding_time_edit is not None \
            and not widget.holding_time_edit.hasFocus():
        widget.holding_time_edit.setTime(now_qt)

    if getattr(widget, "_live_join_time", False) and getattr(widget, "join_time_edit", None) is not None \
            and not widget.join_time_edit.hasFocus():
        widget.join_time_edit.setTime(now_qt)

    # Auto-update Edit Time (Hold Now) nếu đang bật auto & không focus
    if getattr(widget, "_live_holdnow_time", False) and hasattr(widget, "hold_now_time_edit") \
            and widget.hold_now_time_edit is not None and not widget.hold_now_time_edit.hasFocus():
        widget.hold_now_time_edit.setTime(now_qt)

    # --- Auto-fill Hold MW: ƯU TIÊN MW "live" ---
    try:
        if getattr(widget, "_live_holdnow_mw", False) and hasattr(widget, "hold_now_mw_edit") \
                and (widget.hold_now_mw_edit is not None) and (not widget.hold_now_mw_edit.hasFocus()):
            # ưu tiên giá trị live đã tính ở trên
            mw_src = getattr(widget, "current_power_live_value", None)
            if mw_src is None:
                # fallback: nội suy trực tiếp (hiếm khi cần, lần tick đầu)
                profile_now = widget.build_current_profile() if hasattr(widget, "build_current_profile") else {}
                top_xy = profile_now.get("joined_xy") or profile_now.get("main_xy")
                if top_xy:
                    mw_src = get_mw_at(top_xy, now_dt)
            if mw_src is not None:
                widget.hold_now_mw_edit.setText(f"{float(mw_src):.1f}")
    except Exception:
        pass

    # --- Refresh vạch PREVIEW theo thời gian thực khi chưa Hard Hold ---
    try:
        widget.update_plot()
    except Exception:
        pass