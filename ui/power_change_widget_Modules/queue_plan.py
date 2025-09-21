# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, timedelta
from PySide6.QtWidgets import QMessageBox

from modules.power_logic import CalcConfig, compute_power_change_and_pauses
from modules.Hold_module import get_mw_at
from ui.power_change_widget_modules.types import Command

# -------------------------- API CHÍNH (5 HÀM) --------------------------

def on_add_command_via_enter(widget):
    """Thêm lệnh vào queue + rebuild timeline (mặc định hold @429 khi chưa có lệnh trước)."""
    try:
        target_mw = float(widget.target_mw_edit.text())
    except ValueError:
        QMessageBox.warning(widget, "Lỗi", "Target MW (nối lệnh) phải là số.")
        return

    t = widget.join_time_edit.time()
    user_dt = datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)

    # FORCE START FROM HARD HOLD ANCHOR (nếu có)
    if widget.next_cmd_anchor_time is not None and widget.next_cmd_anchor_mw is not None:
        user_dt = widget.next_cmd_anchor_time
        start_mw_current = widget.next_cmd_anchor_mw
    else:
        start_mw_current = widget.threshold_429

    from types import SimpleNamespace
    new_cmd = SimpleNamespace(
        start_mw=start_mw_current,
        target_mw=target_mw,
        start_time=user_dt,
        hold_minutes=0,
        scheduled_start=None,
        hold_start=None,
        hold_end=None,
    )

    # Lịch: nếu đã có lệnh trước → validate; nếu chưa có → chạy đúng giờ nhập
    ok, scheduled_dt, msg = _validate_and_schedule_next_command(widget, new_cmd)
    if not ok and msg:
        QMessageBox.information(
            widget, "Điều chỉnh thời điểm",
            f"{msg}\n\nHệ thống sẽ tự dời sang: {scheduled_dt.strftime('%H:%M')}"
        )
    new_cmd.scheduled_start = scheduled_dt

    # LẤY MW THẬT TẠI THỜI ĐIỂM BẮT ĐẦU (ưu tiên joined nếu có)
    profile_now = widget.build_current_profile()
    top_xy = profile_now.get("joined_xy") or profile_now.get("main_xy")
    if top_xy:
        start_mw_at_sched = get_mw_at(top_xy, scheduled_dt)
    else:
        start_mw_at_sched = widget.next_cmd_anchor_mw if (widget.next_cmd_anchor_mw is not None) else widget.threshold_429
    new_cmd.start_mw = start_mw_at_sched

    # Cập nhật queue và plan
    widget.command_queue.append(new_cmd)
    rebuild_joined_plan(widget)

    # Từ bây giờ mới cắt main trên plot
    widget._cut_after_join = True
    widget.update_plot()

    # mốc hoàn thành lệnh nối = ramp end của lệnh nối (đã set vào hold_start)
    widget.override_complete_time = new_cmd.hold_start
    widget.alarm_played_for_override = False  # cho phép chuông

    # DEBUG PRINT + cập nhật panel
    def _fmt(dt): return dt.strftime("%H:%M") if dt else "—"
    pivot = widget.threshold_429
    direction = "TĂNG" if new_cmd.target_mw > pivot else "GIẢM"
    print(
        f"[JOIN] {direction} {new_cmd.start_mw:.0f}→{new_cmd.target_mw:.0f} MW | "
        f"Start: {_fmt(new_cmd.scheduled_start)} | "
        f"Completed (reach target): {_fmt(new_cmd.hold_start)}"
    )
    if new_cmd.hold_start:
        widget.result_panel.set_override_complete(new_cmd.hold_start.strftime("%H:%M"))
    else:
        widget.result_panel.set_override_complete(None)

    # clear neo sau khi thêm
    widget.next_cmd_anchor_time = None
    widget.next_cmd_anchor_mw = None

    # vẽ lại cho chắc
    widget.update_plot()


def _validate_and_schedule_next_command(widget, new_cmd) -> tuple[bool, datetime, str]:
    """
    Chuẩn hoá thời điểm bắt đầu lệnh nối:
    - Nếu lệnh mới NẰM TRONG vùng FLAT (hold) của lệnh trước: dời tới CUỐI FLAT.
    - Nếu lệnh mới NẰM SAU FLAT: bắt đầu NGAY (không chờ 45' cho lệnh giảm).
    Trả về: (ok, scheduled_start, msg). ok=False nếu có dịch chuyển để UI hiển thị dialog.
    """
    prev_hold_start, prev_hold_end = widget._compute_last_command_hold_window()
    if prev_hold_start is None or prev_hold_end is None:
        prev_hold_end = widget._compute_last_command_end_time()

    user_dt = new_cmd.start_time

    # Trong FLAT → dời tới cuối FLAT
    in_flat = (prev_hold_start is not None and prev_hold_end is not None
               and prev_hold_start <= user_dt <= prev_hold_end)
    if in_flat:
        scheduled_start = prev_hold_end
        msg = (
            "Lệnh mới đang NẰM TRONG vùng FLAT (hold), hệ thống sẽ dời tới CUỐI FLAT.\n"
            f"Giờ người nhập/neo: {user_dt.strftime('%H:%M')}\n"
            f"Cuối FLAT:          {scheduled_start.strftime('%H:%M')}"
        )
        return False, scheduled_start, msg

    # Sau FLAT → bắt đầu ngay (cả tăng lẫn giảm)
    scheduled_start = user_dt
    return True, scheduled_start, ""


def _build_segments_for_one_command(widget, start_mw: float, target_mw: float,
                                    start_dt: datetime, hold_minutes: int):
    """
    Kết quả: (segments, hold_start, hold_end)
    segments: list[{"t": datetime, "mw": float, "tag": str}]
    """
    pulverizer_mode = widget.pulverizer_combo.currentText() if hasattr(widget, "pulverizer_combo") else "3 Puls"
    cfg = CalcConfig(
        threshold_429=widget.threshold_429,
        hold_power=widget.holding_complete_mw,
        pause_time_429_min=widget.pause_time_429_min,
        pause_time_hold_min=hold_minutes,
        pulverizer_mode=pulverizer_mode,
    )

    result = compute_power_change_and_pauses(
        start_power=start_mw,
        target_power=target_mw,
        start_time=start_dt,
        cfg=cfg,
    )

    times = result.times
    mw_values = result.powers

    segs = []
    if times and mw_values:
        segs = [{"t": t, "mw": mw, "tag": "ramp"} for t, mw in zip(times, mw_values)]

    ramp_end  = times[-1] if times else None
    hold_start = ramp_end
    hold_end   = None

    if ramp_end is not None and hold_minutes > 0:
        hold_end = ramp_end + timedelta(minutes=hold_minutes)
        segs.append({"t": hold_start, "mw": target_mw, "tag": "hold_start"})
        segs.append({"t": hold_end,  "mw": target_mw, "tag": "hold_end"})

    return segs, hold_start, hold_end


def rebuild_joined_plan(widget):
    """Rebuild timeline (joined) từ command_queue."""
    if not widget.command_queue:
        widget.current_plan_segments = []
        return

    plan_segments = []
    for idx, cmd in enumerate(widget.command_queue):
        if idx == 0:
            scheduled = cmd.scheduled_start or cmd.start_time
        else:
            scheduled = cmd.scheduled_start

        segs, h_start, h_end = _build_segments_for_one_command(
            widget,
            start_mw=cmd.start_mw,
            target_mw=cmd.target_mw,
            start_dt=scheduled,
            hold_minutes=cmd.hold_minutes
        )

        # cập nhật lại vào command để truy vấn sau
        cmd.hold_start = h_start
        cmd.hold_end = h_end

        plan_segments.extend(segs)

    widget.current_plan_segments = plan_segments
    widget.update_plot()


def render_plan(widget):
    """Vẽ timeline của queue nối lệnh từ widget.current_plan_segments."""
    if not widget.current_plan_segments:
        widget.ax.clear()
        widget.ax.set_title('TREND: POWER DEPEND ON TIMES (Joined Plan)')
        widget.ax.set_xlabel('TIMES')
        widget.ax.set_ylabel('POWER (MW)')
        widget.canvas.draw_idle()
        return

    # nếu sau này cần vẽ riêng bằng draw_main_and_joined thì bổ sung ở đây.
    widget.ax.clear()
    widget.ax.set_title('TREND: POWER DEPEND ON TIMES (Joined Plan)')
    widget.ax.set_xlabel('TIMES')
    widget.ax.set_ylabel('POWER (MW)')
    widget.figure.autofmt_xdate()
    widget.canvas.draw_idle()
