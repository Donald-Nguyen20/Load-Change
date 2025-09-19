# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime
from PySide6.QtWidgets import QMessageBox

from modules.Hold_module import get_mw_at
from ui.power_change_widget_Modules.hold_refresh import refresh_after_hold  # đã tách ở bước trước

# --- Helpers cục bộ (tránh lặp logic) ----------------------------------------
def _get_preview_dt(widget) -> datetime:
    """Mốc thời gian PREVIEW: ưu tiên Edit Time (hold_now_time_edit), fallback = now."""
    if getattr(widget, "_live_holdnow_time", True) is True or not hasattr(widget, "hold_now_time_edit"):
        return datetime.now()
    t = widget.hold_now_time_edit.time()
    return datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)

def _top_xy(profile: dict) -> dict | None:
    """Ưu tiên joined_xy, nếu không có thì main_xy."""
    return profile.get("joined_xy") or profile.get("main_xy")

def _resolve_hold_mw(widget, top_xy: dict, hold_dt: datetime) -> float | None:
    """
    Xác định MW tại thời điểm hold:
    - Nếu người dùng nhập ở ô Hold MW: dùng luôn và tắt auto.
    - Ngược lại: lấy từ đường top_xy tại hold_dt (có thể thay bằng clamp nếu muốn).
    """
    mw_now = None
    try:
        txt = widget.hold_now_mw_edit.text().strip() if hasattr(widget, "hold_now_mw_edit") else ""
        if txt != "":
            mw_now = float(txt)
            widget._live_holdnow_mw = False  # không ghi đè nữa
    except Exception:
        mw_now = None

    if mw_now is None:
        # Nếu anh có get_mw_at(..., clamp=True) thì đổi dòng dưới cho gọn.
        mw_now = get_mw_at(top_xy, hold_dt)
        if mw_now is None:
            xs = top_xy.get("x") or []
            ys = top_xy.get("y") or []
            if xs and ys:
                if hold_dt <= xs[0]:
                    mw_now = ys[0]
                elif hold_dt >= xs[-1]:
                    mw_now = ys[-1]
    return mw_now

def _compute_next_anchor(widget, profile: dict, hold_dt: datetime, mw_now: float | None):
    """
    Xác lập neo cho lệnh thêm kế tiếp theo luật 'trong/ngoài hold'.
    """
    prev_hold_start, prev_hold_end = widget._compute_last_command_hold_window()
    if (prev_hold_start is not None) and (prev_hold_end is not None) and (prev_hold_start <= hold_dt <= prev_hold_end):
        widget.next_cmd_anchor_time = prev_hold_end
        top_xy = _top_xy(profile)
        widget.next_cmd_anchor_mw = get_mw_at(top_xy, prev_hold_end) if top_xy else widget.threshold_429
    else:
        widget.next_cmd_anchor_time = hold_dt
        widget.next_cmd_anchor_mw = mw_now if mw_now is not None else widget.threshold_429

# --- API chính: tách hàm on_hold_now_clicked ---------------------------------
def hold_now_clicked(widget):
    """
    Bản tách rời của PowerChangeWidget.on_hold_now_clicked(self)
    """
    # 1) Xác định thời điểm hold
    hold_dt = _get_preview_dt(widget)
    widget.hard_hold_dt = hold_dt
    widget.hard_hold_active = True

    # 2) Lấy profile hiện tại
    profile = widget.build_current_profile()
    top_xy = _top_xy(profile)
    if not top_xy:
        QMessageBox.warning(widget, "Hold", "Chưa có profile để Hold.")
        return

    # 3) Xác định MW tại hold_dt (ưu tiên người dùng nhập)
    mw_now = _resolve_hold_mw(widget, top_xy, hold_dt)
    widget.hard_hold_mw = mw_now

    # 4) Tính neo cho lệnh tiếp theo
    _compute_next_anchor(widget, profile, hold_dt, mw_now)

    # 5) Cắt profile và vẽ lại (dùng module đã tách)
    refresh_after_hold(widget, profile)

    # 6) Thông báo
    try:
        if mw_now is not None:
            QMessageBox.information(
                widget, "HOLD",
                f"Đã dừng tại {widget.hard_hold_dt:%H:%M:%S}, MW hiện tại: {mw_now:.1f}. "
                "Lệnh thêm kế tiếp sẽ bắt đầu từ mốc này."
            )
        else:
            QMessageBox.information(
                widget, "HOLD",
                f"Đã dừng tại {widget.hard_hold_dt:%H:%M:%S}. "
                "Lệnh thêm kế tiếp sẽ bắt đầu từ mốc này."
            )
    except Exception:
        pass
