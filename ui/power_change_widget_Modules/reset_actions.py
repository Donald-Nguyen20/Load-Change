# -*- coding: utf-8 -*-
from PySide6.QtCore import QTime


def on_reset_clicked(widget):
    """
    Khôi phục toàn bộ trạng thái UI, dữ liệu và biểu đồ về mặc định ban đầu.
    """
    # 1) Đặt lại QTimeEdit
    widget.start_time_edit.setTime(QTime.currentTime())
    widget.holding_time_edit.setTime(QTime.currentTime())

    # 2) Bật/tắt lại chế độ live mặc định
    widget._live_start_time = True
    widget._live_hold_time  = True
    widget._live_join_time  = True

    # 3) Reset cờ báo động
    widget.alarm_played_for_429 = False
    widget.alarm_played_for_post_pause = False
    widget.alarm_played_for_final_load = False
    widget.alarm_played_for_hold_complete = False
    widget.messagebox_shown = False
    widget.override_complete_time = None
    widget.alarm_played_for_override = False
    widget._cut_after_join = False

    # Reset Hold Now auto
    widget._live_holdnow_mw = True
    if hasattr(widget, "hold_now_mw_edit") and widget.hold_now_mw_edit is not None:
        widget.hold_now_mw_edit.clear()

    widget._live_holdnow_time = True
    if hasattr(widget, "hold_now_time_edit") and widget.hold_now_time_edit is not None:
        widget.hold_now_time_edit.setTime(QTime.currentTime())

    # 4) Reset panel kết quả
    widget.result_panel.reset()

    # 5) Xoá series + kết quả thời gian
    widget.times1.clear()
    widget.powers1.clear()
    widget.final_load_time = None
    widget.time_reaching_429 = None
    widget.post_pause_time = None
    widget.time_holding_462 = None
    widget.hold_complete_time = None

    # 6) Reset NỐI LỆNH (ô nhập + hàng đợi + timeline)
    if hasattr(widget, "target_mw_edit"):
        widget.target_mw_edit.clear()
    if hasattr(widget, "join_time_edit"):
        widget.join_time_edit.setTime(QTime.currentTime())
    widget.command_queue.clear()
    widget.current_plan_segments.clear()

    # 7) Làm mới đồ thị (KHÔNG tạo Figure/Canvas mới)
    widget.ax.clear()
    widget.ax.set_title('TREND: POWER DEPEND ON TIMES')
    widget.ax.set_xlabel('TIMES')
    widget.ax.set_ylabel('POWER (MW)')
    widget.canvas.draw()

    # 8) RESET HOLD NOW / ANCHOR
    widget.hard_hold_active = False
    widget.hard_hold_dt = None
    widget.hard_hold_mw = None
    widget.next_cmd_anchor_time = None
    widget.next_cmd_anchor_mw = None

    # 9) nếu trước đó có stop() trong Hold Now thì bật lại check_timer
    if hasattr(widget, "check_timer") and widget.check_timer is not None:
        try:
            if not widget.check_timer.isActive():
                widget.check_timer.start(1000)
        except Exception:
            pass
