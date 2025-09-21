# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTimeEdit,
    QPushButton, QComboBox, QMessageBox, QFrame
)
from PySide6.QtGui import QDoubleValidator
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# modules (anh đã tách sẵn)

from ui.result_panel import ResultPanel
from modules.plotting import draw_main_and_joined 
import os  # nếu anh dùng đường dẫn ghi file
from modules.Hold_module import get_mw_at, trim_xy_until
from ui.power_change_widget_modules.profile_builder import build_current_profile_from_widget
from ui.power_change_widget_modules.hold_refresh import refresh_after_hold  # thêm ở đầu file
from ui.power_change_widget_modules.hold_actions import hold_now_clicked as _hold_now_clicked
from ui.power_change_widget_modules.join_inputs import build_join_inputs as _build_join_inputs
from ui.power_change_widget_modules.plan_timing import (get_last_command_hold_window as _get_last_command_hold_window, get_last_command_end_time as _get_last_command_end_time,)
from ui.power_change_widget_modules.enter_flow import on_enter_clicked as _on_enter_clicked
from ui.power_change_widget_modules.queue_plan import (
    on_add_command_via_enter as _on_add_command_via_enter,
    _validate_and_schedule_next_command as _validate_and_schedule_next_command_impl,
    _build_segments_for_one_command as _build_segments_for_one_command_impl,
    rebuild_joined_plan as _rebuild_joined_plan,
    render_plan as _render_plan,
)
from ui.power_change_widget_modules.plot_update import update_plot as _update_plot
from ui.power_change_widget_modules.alarms_runtime import check_and_alarm as _check_and_alarm
from ui.power_change_widget_modules.ui_builders import (
    build_ui as _build_ui_impl,
    labeled_edit as _labeled_edit_impl,
    labeled_timeedit as _labeled_timeedit_impl,
    toggle_hidden_layout as _toggle_hidden_layout_impl,
)
from ui.power_change_widget_modules.types import Command
from ui.power_change_widget_modules.live_updates import tick_time_edits as _tick_time_edits
from ui.power_change_widget_modules.reset_actions import on_reset_clicked as _on_reset_clicked


class PowerChangeWidget(QWidget):
    def __init__(self, parent=None, *, excel_file: str = "abc.xlsx"):
        super().__init__(parent)

        # --- services/state ---
        self.alarm_played_for_429 = False
        self.alarm_played_for_post_pause = False
        self.alarm_played_for_final_load = False
        self.alarm_played_for_hold_complete = False
        self.alarm_played_for_override = False
        self._cut_after_join = False

        self.messagebox_shown = False

        # thresholds + alarm texts
        self.threshold_429 = 429.0
        self.holding_complete_mw = 462.0
        self.final_load_mw = 560.0

        self.alarm_texts = {
            "429": "Reached 429 MW",
            "holding_complete": "Holding complete at 462 MW",
            "final_load": "Final target load achieved, To pay Attention to check control mode and SCC Speed mode",
            "hold_10_min": "Holding 10 minutes completed",
            "override": "Override load completed",
        }

        # users’ pause config + pulverizer mode
        self.pause_time_429_min = 0
        self.pause_time_hold_min = 30
        self.pulverizer_mode_default = "3 Puls"  # default

        # data series for plotting
        self.times1: List[datetime] = []
        self.powers1: List[float] = []
        # self.times2: List[datetime] = []   # reserved (hidden layout 2)
        # self.powers2: List[float] = []

        # result times
        self.final_load_time: Optional[datetime] = None
        self.time_reaching_429: Optional[datetime] = None
        self.post_pause_time: Optional[datetime] = None
        self.time_holding_462: Optional[datetime] = None
        self.hold_complete_time: Optional[datetime] = None
        self.override_complete_time: Optional[datetime] = None
                # --- HARD HOLD state ---
        self.hard_hold_active: bool = False
        self.hard_hold_dt: datetime | None = None
        self.hard_hold_mw: float | None = None

        # Điểm neo cho lệnh thêm tiếp theo
        self.next_cmd_anchor_time: datetime | None = None
        self.next_cmd_anchor_mw: float | None = None

        # ---------------- UI: nút Hold ----------------
        self.btn_hold_now = QPushButton("Hold Now")
        self.btn_hold_now.setToolTip("Dừng tại thời điểm bấm; MW hiện tại sẽ là điểm bắt đầu cho lệnh kế tiếp")
        self.btn_hold_now.clicked.connect(self.on_hold_now_clicked)
        # --- UI ---
        self._build_ui()
        # --- live time for QTimeEdit ---
        self._live_start_time = True    # Start Time auto-run ban đầu
        self._live_hold_time  = True    # True để chạy lifetime
        self._live_join_time  = True
        self._live_holdnow_time = True  # auto-update ô Edit Time của Hold Now
        self._live_holdnow_mw = True  # auto-update ô Hold MW khi chưa bị người dùng chỉnh
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._tick_time_edits)
        self._time_timer.start(1000)    # tick mỗi giây


        # Timer kiểm tra mốc báo động (không hiển thị đồng hồ)
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_and_alarm)
        self.check_timer.start(1000)
        # --- Command queue và kế hoạch ---
        self.command_queue: list[Command] = []
        self.current_plan_segments: list[dict] = []
        self.default_hold_minutes = 10  # hoặc lấy từ cấu hình của anh
        self._cut_after_join = False




    # ----------------------
    # UI construction
    # ----------------------
    def _build_ui(self):
        return _build_ui_impl(self)

    def _labeled_edit(self, *a, **kw):
        return _labeled_edit_impl(self, *a, **kw)

    def _labeled_timeedit(self, *a, **kw):
        return _labeled_timeedit_impl(self, *a, **kw)

    def toggle_hidden_layout(self):
        return _toggle_hidden_layout_impl(self)


    def on_enter_clicked(self):
        return _on_enter_clicked(self)


    def on_hold_clicked(self):
        try:
            holding_load = float(self.holding_load_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Holding Load (MW) phải là số.")
            return

        holding_time = self.holding_time_edit.time().toString("HH:mm")
        QMessageBox.information(self, "Holding Information",
                                f"Holding Load: {holding_load}\nHolding Time: {holding_time}")

        data1 = {
            'time_now_hold': datetime.now(),
            'holding_time': holding_time,
            'holding_load': f"Hold the load at {holding_load} MW/ Giữ tải tại {holding_load} MW",
        }


    def on_reset_clicked(self):
        return _on_reset_clicked(self)


    def update_plot(self):
        return _update_plot(self)

    def _tick_time_edits(self):
        return _tick_time_edits(self)

    def check_and_alarm(self):
        return _check_and_alarm(self)

    def on_add_command_via_enter(self):
        return _on_add_command_via_enter(self)

    def _validate_and_schedule_next_command(self, new_cmd):
        return _validate_and_schedule_next_command_impl(self, new_cmd)

    def _build_segments_for_one_command(self, start_mw, target_mw, start_dt, hold_minutes):
        return _build_segments_for_one_command_impl(self, start_mw, target_mw, start_dt, hold_minutes)

    def rebuild_joined_plan(self):
        return _rebuild_joined_plan(self)

    def render_plan(self):
        return _render_plan(self)

    def _compute_last_command_hold_window(self) -> tuple[datetime | None, datetime | None]:
        return _get_last_command_hold_window(self)

    def _compute_last_command_end_time(self) -> datetime:
        return _get_last_command_end_time(self)


    def _build_join_inputs(self, parent_layout: QVBoxLayout):
        return _build_join_inputs(self, parent_layout)


    def on_hold_now_clicked(self):
        return _hold_now_clicked(self)


    def refresh_after_hold(self, profile: dict | None = None):
        return refresh_after_hold(self, profile)

    # Thêm vào trong class PowerChangeWidget:
    def build_current_profile(self) -> dict:
        # wrapper để giữ API cũ
        return build_current_profile_from_widget(self)



