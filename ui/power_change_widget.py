# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional
from unittest import result

from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTimeEdit,
    QPushButton, QComboBox, QMessageBox, QFrame
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# modules (anh đã tách sẵn)
from modules.power_logic import CalcConfig, compute_power_change_and_pauses
from modules.excel_io import ExcelUpdater
from modules.audio_tts import tts_and_play
from modules.plotting import draw_series
from modules.alarms import check_and_fire
from ui.result_panel import ResultPanel

from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Command:
    start_mw: float
    target_mw: float
    start_time: datetime        # thời điểm người dùng nhập (ý định ban đầu)
    hold_minutes: int           # thời gian hold sau khi đạt target (vd: 10’)
    # các trường tính sau (điền khi lên timeline)
    scheduled_start: datetime | None = None
    hold_start: datetime | None = None
    hold_end: datetime | None = None


class PowerChangeWidget(QWidget):
    def __init__(self, parent=None, *, excel_file: str = "abc.xlsx"):
        super().__init__(parent)

        # --- services/state ---
        self.excel_updater = ExcelUpdater(excel_file)
        self.alarm_played_for_429 = False
        self.alarm_played_for_post_pause = False
        self.alarm_played_for_final_load = False
        self.alarm_played_for_hold_complete = False
        self.alarm_played_for_override = False
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
        self.times2: List[datetime] = []   # reserved (hidden layout 2)
        self.powers2: List[float] = []

        # result times
        self.final_load_time: Optional[datetime] = None
        self.time_reaching_429: Optional[datetime] = None
        self.post_pause_time: Optional[datetime] = None
        self.time_holding_462: Optional[datetime] = None
        self.hold_complete_time: Optional[datetime] = None
        self.override_complete_time: Optional[datetime] = None

        # --- UI ---
        self._build_ui()
        # --- live time for QTimeEdit ---
        self._live_start_time = True    # Start Time auto-run ban đầu
        self._live_hold_time  = False   # Holding Time mặc định nhập tay

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




    # ----------------------
    # UI construction
    # ----------------------
    def _build_ui(self):
        # Layout ngang tổng thể
        master_layout = QHBoxLayout(self)
        master_layout.setContentsMargins(10, 10, 10, 10)
        master_layout.setSpacing(12)

        # --- BÊN TRÁI: root layout (UI chính) ---
        root = QVBoxLayout()
        root.setSpacing(8)
        master_layout.addLayout(root, 4)

        # --- BÊN PHẢI: result_column (kết quả) ---
        self.result_panel = ResultPanel()
        master_layout.addWidget(self.result_panel, 1)

        # Các nhãn kết quả
        

        # --- Khung nhập chính (trong root) ---
        input_row = QHBoxLayout()
        self.start_power_edit = self._labeled_edit(input_row, "Start Power (MW):")
        self.target_power_edit = self._labeled_edit(input_row, "Target Power (MW):")
        self.start_time_edit  = self._labeled_timeedit(input_row, "Start Time (HH:MM):", width=90, default_now=True)


        self.enter_btn  = QPushButton("Enter")
        self.reset_btn  = QPushButton("Reset")
        self.toggle_btn = QPushButton("⚙")

        self.enter_btn.clicked.connect(self.on_enter_clicked)
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        self.toggle_btn.clicked.connect(self.toggle_hidden_layout)

        input_row.addWidget(self.enter_btn, 0, Qt.AlignLeft)
        input_row.addWidget(self.reset_btn, 0, Qt.AlignLeft)
        input_row.addWidget(self.toggle_btn, 0, Qt.AlignLeft)
        input_row.addStretch(1)          # ép trái
        root.addLayout(input_row)
        self._build_join_inputs(root)

        # Khung nhập bổ sung (Hold)
        hold_row = QHBoxLayout()
        self.holding_load_edit = self._labeled_edit(hold_row, "Holding Load (MW):")
        self.holding_time_edit = self._labeled_timeedit(hold_row, "Holding Time (HH:MM):", width=90, default_now=False)
        self.hold_btn = QPushButton("Hold")
        self.hold_btn.clicked.connect(self.on_hold_clicked)   # (SỬA) nút Hold được connect
        hold_row.addWidget(self.hold_btn, 0, Qt.AlignLeft)
        hold_row.addStretch(1)
        root.addLayout(hold_row)

        # Matplotlib Figure (giữ 1 canvas suốt vòng đời widget)
        self.figure = Figure(figsize=(6, 4), dpi=120)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title('TREND: POWER DEPEND ON TIMES')
        self.ax.set_xlabel('TIMES')
        self.ax.set_ylabel('POWER (MW)')
        self.canvas = FigureCanvas(self.figure)
        root.addWidget(self.canvas, 1)

        # Layout ẩn (tuỳ biến cảnh báo + pause + pulverizer)
        self.hidden_frame = QFrame()
        self.hidden_frame.setFrameShape(QFrame.StyledPanel)
        hidden_layout = QVBoxLayout(self.hidden_frame)

        title = QLabel("Custom Alarm Messages")
        title.setStyleSheet("font-weight:700;")
        hidden_layout.addWidget(title)

        self.edit_alarm_429 = self._labeled_edit(hidden_layout, "429 MW Alert:", default=self.alarm_texts["429"], width=500)
        self.edit_alarm_hold_comp = self._labeled_edit(hidden_layout, "Holding Complete Alert:", default=self.alarm_texts["holding_complete"], width=500)
        self.edit_alarm_final = self._labeled_edit(hidden_layout, "Final Load Alert:", default=self.alarm_texts["final_load"], width=500)
        self.edit_alarm_hold10 = self._labeled_edit(hidden_layout, "Hold 10 Min Alert:", default=self.alarm_texts["hold_10_min"], width=500)
        self.edit_alarm_override = self._labeled_edit(hidden_layout, "Override Alert:", default=self.alarm_texts["override"], width=500)


        # pause + pulverizer
        pause_row = QHBoxLayout()
        self.pause_429_edit = self._labeled_edit(pause_row, "Pause at 429 MW (min):",
                                                 default=str(self.pause_time_429_min), width=60)
        self.pause_hold_edit = self._labeled_edit(pause_row, "Hold duration at holding MW (min):",
                                                  default=str(self.pause_time_hold_min), width=60)

        label = QLabel("Pulverizer Mode:")
        self.pulverizer_combo = QComboBox()
        self.pulverizer_combo.addItems(["3 Puls", "4 Puls"])
        self.pulverizer_combo.setCurrentText(self.pulverizer_mode_default)

        pause_row.addWidget(label, 0, Qt.AlignLeft)
        pause_row.addWidget(self.pulverizer_combo, 0, Qt.AlignLeft)
        pause_row.addStretch(1)
        hidden_layout.addLayout(pause_row)

        # Ẩn ngay từ đầu
        self.hidden_frame.setVisible(False)
        root.addWidget(self.hidden_frame)

    def _labeled_edit(self, parent_layout_or_widget, label: str, default: str = "", width: int = 100) -> QLineEdit:
        if isinstance(parent_layout_or_widget, QVBoxLayout):
            row = QHBoxLayout()
            parent_layout_or_widget.addLayout(row)
        else:
            row = parent_layout_or_widget
        lab = QLabel(label)
        edit = QLineEdit()
        if default:
            edit.setText(default)
        if width:
            edit.setFixedWidth(width)
        row.addWidget(lab)
        row.addWidget(edit)
        return edit
    def _labeled_timeedit(self, parent_layout_or_widget, label: str, *, width: int = 100,
                      default_now: bool = True) -> QTimeEdit:
        if isinstance(parent_layout_or_widget, QVBoxLayout):
            row = QHBoxLayout()
            parent_layout_or_widget.addLayout(row)
        else:
            row = parent_layout_or_widget
        lab = QLabel(label)
        te  = QTimeEdit()
        te.setDisplayFormat("HH:mm")
        te.setFixedWidth(width)
        if default_now:
            te.setTime(QTime.currentTime())

        # Khi người dùng chỉnh tay -> tắt live của ô tương ứng
        def stop_live():
            if te is self.start_time_edit:
                self._live_start_time = False
            elif te is self.holding_time_edit:
                self._live_hold_time = False

        te.editingFinished.connect(stop_live)

        row.addWidget(lab)
        row.addWidget(te)
        return te

    # ----------------------
    # Event handlers
    # ----------------------
    def toggle_hidden_layout(self):
        self.hidden_frame.setVisible(not self.hidden_frame.isVisible())

    def on_enter_clicked(self):
        try:
            start_power = float(self.start_power_edit.text())
            target_power = float(self.target_power_edit.text())
            t = self.start_time_edit.time()
            start_dt = datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Vui lòng nhập đúng định dạng số/giờ.")
            return

        # cập nhật cấu hình từ UI ẩn (nếu người dùng đã mở và chỉnh)
        self.alarm_texts["429"] = self.edit_alarm_429.text()
        self.alarm_texts["holding_complete"] = self.edit_alarm_hold_comp.text()
        self.alarm_texts["final_load"] = self.edit_alarm_final.text()
        self.alarm_texts["hold_10_min"] = self.edit_alarm_hold10.text()
        self.alarm_texts["override"] = self.edit_alarm_override.text() 

        try:
            self.pause_time_429_min = int(self.pause_429_edit.text() or "0")
            self.pause_time_hold_min = int(self.pause_hold_edit.text() or "30")
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Thời gian pause/hold phải là số phút.")
            return

        pulverizer_mode = self.pulverizer_combo.currentText()

        # Tính toán bằng modules.power_logic
        try:
            cfg = CalcConfig(
                threshold_429=self.threshold_429,
                hold_power=self.holding_complete_mw,
                pause_time_429_min=self.pause_time_429_min,
                pause_time_hold_min=self.pause_time_hold_min,
                pulverizer_mode=pulverizer_mode,
            )
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Lỗi cấu hình: {e}")
            return

        # --- TÍNH TOÁN ---
        result = compute_power_change_and_pauses(
            start_power=start_power,
            target_power=target_power,
            start_time=start_dt,  # dùng datetime cùng ngày
            cfg=cfg,
        )

        # Gán cho vẽ/logic
        self.times1 = result.times
        self.powers1 = result.powers
        self.final_load_time    = result.final_load_time
        self.time_reaching_429  = result.time_reaching_429
        self.post_pause_time    = result.post_pause_time
        self.time_holding_462   = result.time_holding_462
        self.hold_complete_time = result.hold_complete_time

        # Cập nhật nhãn
        self.result_panel.set_total_load_time(
            self.final_load_time.strftime("%H:%M") if self.final_load_time else None
        )
        if self.time_reaching_429:
            self.result_panel.set_429_time(self.time_reaching_429.strftime("%H:%M"))
            self.result_panel.set_post_pause_time(
                self.post_pause_time.strftime("%H:%M") if self.post_pause_time else None
            )
        else:
            self.result_panel.set_429_time(None)
            self.result_panel.set_post_pause_time(None)

        self.result_panel.set_hold_complete(
            self.hold_complete_time.strftime("%H:%M") if self.hold_complete_time else None,
            minutes=self.pause_time_hold_min
        )

        # Vẽ đồ thị
        self.update_plot()

        # --- GHI EXCEL ---
        copy_text = (
            f"Decrease Unit load to {target_power} MW/Giảm tải xuống {target_power} MW"
            if start_power > target_power else
            f"Increase Unit load to {target_power} MW/Tăng tải lên {target_power} MW"
        )
        data = {
            "time_now": datetime.now(),
            "start_power": start_power,
            "target_power": target_power,
            "start_time_str": start_dt.strftime("%H:%M"),  # thay vì biến cũ
            "copy_text": copy_text,
        }
        self.excel_updater.append_data(data)


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
        # (SỬA) dùng hàm đúng tên trong ExcelUpdater đã tách
        if hasattr(self.excel_updater, "append_data_hold"):
            self.excel_updater.append_data_hold(data1)
        else:
            # fallback nếu class cũ
            self.excel_updater.append_data1(data1)

    def on_reset_clicked(self):
        # 1) Xoá inputs
        # self.start_power_edit.clear()
        # self.target_power_edit.clear()
        # self.start_time_edit.clear()
        # self.holding_load_edit.clear()
        # self.holding_time_edit.clear()
        # Đặt lại QTimeEdit
        self.start_time_edit.setTime(QTime.currentTime())
        self.holding_time_edit.setTime(QTime(0, 0))

        # Bật/tắt lại chế độ live mặc định
        self._live_start_time = True
        self._live_hold_time  = False


        # 2) Reset cờ báo động
        self.alarm_played_for_429 = False
        self.alarm_played_for_post_pause = False
        self.alarm_played_for_final_load = False
        self.alarm_played_for_hold_complete = False
        self.messagebox_shown = False
        self.override_complete_time = None
        self.alarm_played_for_override = False


        # 3) Reset panel kết quả (DÙNG API ResultPanel)
        self.result_panel.reset()

        # 4) Xoá series + kết quả thời gian
        self.times1.clear(); self.powers1.clear()
        self.times2.clear(); self.powers2.clear()
        self.final_load_time = None
        self.time_reaching_429 = None
        self.post_pause_time = None
        self.time_holding_462 = None
        self.hold_complete_time = None
        # 4b) Reset NỐI LỆNH (ô nhập + hàng đợi + timeline)
        if hasattr(self, "target_mw_edit"):
            self.target_mw_edit.clear()
        if hasattr(self, "join_time_edit"):
            self.join_time_edit.setTime(QTime.currentTime())
        self.command_queue.clear()
        self.current_plan_segments.clear()
        # 5) Làm mới đồ thị (KHÔNG tạo Figure/Canvas mới)
        self.ax.clear()
        self.ax.set_title('TREND: POWER DEPEND ON TIMES')
        self.ax.set_xlabel('TIMES')
        self.ax.set_ylabel('POWER (MW)')
        self.canvas.draw()


    # ----------------------
    # Plotting
    # ----------------------
    def update_plot(self):
        series = [
            {"x": self.times1, "y": self.powers1, "label": "Main Load Change"},
            {"x": self.times2, "y": self.powers2, "label": "Hidden Layout 2"},
        ]
        self.ax.clear()
        self.ax.set_title('TREND: POWER DEPEND ON TIMES')
        self.ax.set_xlabel('TIMES')
        self.ax.set_ylabel('POWER (MW)')
        draw_series(self.ax, series)
        self.figure.autofmt_xdate()
        self.canvas.draw()
    def _tick_time_edits(self):
        now = QTime.currentTime()
        # Cập nhật nếu đang ở chế độ live và không có focus (tránh ghi đè khi người dùng đang gõ)
        if self._live_start_time and self.start_time_edit is not None and not self.start_time_edit.hasFocus():
            self.start_time_edit.setTime(now)
        if self._live_hold_time and self.holding_time_edit is not None and not self.holding_time_edit.hasFocus():
            self.holding_time_edit.setTime(now)

    # ----------------------
    # Alarm checking (no clock UI)
    # ----------------------
    def check_and_alarm(self):
        now = datetime.now()
        timeline = {
            "429": self.time_reaching_429,
            "holding_complete": self.post_pause_time,
            "final_load": self.final_load_time,
            "hold_10_min": self.hold_complete_time,
            "override": self.override_complete_time,  # ⬅️ NEW
        }
        flags = {
            "429": self.alarm_played_for_429,
            "holding_complete": self.alarm_played_for_post_pause,
            "final_load": self.alarm_played_for_final_load,
            "hold_10_min": self.alarm_played_for_hold_complete,
            "override": self.alarm_played_for_override,  # ⬅️ NEW
        }
        flags = check_and_fire(now, timeline, flags, tts_and_play, self.alarm_texts)

        # cập nhật cờ
        self.alarm_played_for_429 = flags["429"]
        self.alarm_played_for_post_pause = flags["holding_complete"]
        self.alarm_played_for_final_load = flags["final_load"]
        self.alarm_played_for_hold_complete = flags["hold_10_min"]
        self.alarm_played_for_override = flags["override"]  # ⬅️ NEW


    #Hàm “Enter để nối lệnh” có kiểm tra nằm trong HOLD lệnh trước
    def on_add_command_via_enter(self):
        """Thêm lệnh vào queue + rebuild timeline (mặc định hold @429 khi chưa có lệnh trước)."""
        try:
            target_mw = float(self.target_mw_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Target MW (nối lệnh) phải là số.")
            return

        t = self.join_time_edit.time()
        user_dt = datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)

        # start_mw hiện tại: target của lệnh trước, nếu chưa có thì mặc định 429
        start_mw_current = (self.command_queue[-1].target_mw if self.command_queue else self.threshold_429)

        new_cmd = Command(
            start_mw=start_mw_current,
            target_mw=target_mw,
            start_time=user_dt,
            hold_minutes=0,
        )

        # Lịch: nếu đã có lệnh trước → validate; nếu chưa có → chạy đúng giờ nhập
        ok, scheduled_dt, msg = self._validate_and_schedule_next_command(new_cmd)


        if not ok and msg:
            QMessageBox.information(
                self, "Điều chỉnh thời điểm",
                f"{msg}\n\nHệ thống sẽ tự dời sang: {scheduled_dt.strftime('%H:%M')}"
            )

        new_cmd.scheduled_start = scheduled_dt
        self.command_queue.append(new_cmd)
        self.rebuild_joined_plan()

        # mốc hoàn thành lệnh nối = ramp end của lệnh nối (đã set vào hold_start)
        self.override_complete_time = new_cmd.hold_start
        self.alarm_played_for_override = False  # cho phép chuông lần này

    # --- DEBUG PRINT thời gian hoàn thành lệnh nối ---
        def _fmt(dt): return dt.strftime("%H:%M") if dt else "—"
        pivot = self.threshold_429
        direction = "TĂNG" if new_cmd.target_mw > pivot else "GIẢM"

        print(
            f"[JOIN] {direction} {new_cmd.start_mw:.0f}→{new_cmd.target_mw:.0f} MW | "
            f"Start: {_fmt(new_cmd.scheduled_start)} | "
            f"Completed (reach target): {_fmt(new_cmd.hold_start)}"
        )
        if new_cmd.hold_start:
            self.result_panel.set_override_complete(new_cmd.hold_start.strftime("%H:%M"))
        else:
            self.result_panel.set_override_complete(None)
    def _validate_and_schedule_next_command(self, new_cmd: Command) -> tuple[bool, datetime, str]:
        """
        target > 429 -> TĂNG  ⇒ bắt đầu sau HOLD_END(429)
        target < 429 -> GIẢM  ⇒ bắt đầu sau HOLD_END(429) + 45'
        """
        prev_hold_start, prev_hold_end = self._compute_last_command_hold_window()
        if prev_hold_start is None or prev_hold_end is None:
            prev_hold_end = self._compute_last_command_end_time()

        user_dt = new_cmd.start_time

        pivot = self.threshold_429  # 429.0
        is_increasing = new_cmd.target_mw > pivot

        # ✅ Quy tắc đúng:
        required_start = prev_hold_end if is_increasing else (prev_hold_end + timedelta(minutes=45))

        in_hold_window = (prev_hold_start is not None and prev_hold_start <= user_dt <= prev_hold_end)
        if in_hold_window:
            scheduled_start = required_start
            return True, scheduled_start, ""
        else:
            scheduled_start = required_start
            action = "Tăng (sau HOLD_END)" if is_increasing else "Giảm (sau HOLD_END + 45')"
            msg = (
                "Thời điểm anh nhập nằm trong giai đoạn HOLD của lệnh trước.\n"
                "Để đảm bảo hold đủ thời gian, lệnh kế sẽ được tự động dời theo quy định:\n"
                f"- {action} theo mốc 429 MW.\n"
                f"Giờ người nhập: {user_dt.strftime('%H:%M')}\n"
                f"Giờ yêu cầu:    {scheduled_start.strftime('%H:%M')}"
            )
            return False, scheduled_start, msg



    def _build_segments_for_one_command(self, start_mw: float, target_mw: float,
                                    start_dt: datetime, hold_minutes: int):
        """
        Kết quả: (segments, hold_start, hold_end)
        segments: list[{"t": datetime, "mw": float, "tag": str}]
        """
        # Lấy cấu hình hiện tại từ UI/state
        pulverizer_mode = self.pulverizer_combo.currentText() if hasattr(self, "pulverizer_combo") else "3 Puls"
        cfg = CalcConfig(
            threshold_429=self.threshold_429,
            hold_power=self.holding_complete_mw,
            pause_time_429_min=self.pause_time_429_min,
            # dùng hold theo lệnh này để vẽ đoạn hold sau ramp
            pause_time_hold_min=hold_minutes,
            pulverizer_mode=pulverizer_mode,
        )

        # GỌI HÀM TRẢ VỀ OBJECT, KHÔNG UNPACK
        result = compute_power_change_and_pauses(
            start_power=start_mw,
            target_power=target_mw,
            start_time=start_dt,   # datetime ok (hàm của anh đã hỗ trợ)
            cfg=cfg,               # tham số tên 'cfg' đúng như on_enter_clicked
        )

        times = result.times
        mw_values = result.powers

        segs = []
        if times and mw_values:
            segs = [{"t": t, "mw": mw, "tag": "ramp"} for t, mw in zip(times, mw_values)]

        ramp_end  = times[-1] if times else None
        hold_start = ramp_end           # dùng như “thời điểm hoàn tất lệnh nối”
        hold_end   = None               # không có HoldEnd khi hold_minutes == 0

        if ramp_end is not None and hold_minutes > 0:
            hold_end = ramp_end + timedelta(minutes=hold_minutes)
            segs.append({"t": hold_start, "mw": target_mw, "tag": "hold_start"})
            segs.append({"t": hold_end,  "mw": target_mw, "tag": "hold_end"})

        return segs, hold_start, hold_end




    def rebuild_joined_plan(self):
        if not self.command_queue:
            self.current_plan_segments = []
            return

        plan_segments = []
        for idx, cmd in enumerate(self.command_queue):
            if idx == 0:
                scheduled = cmd.scheduled_start or cmd.start_time
            else:
                # đã tính ở _validate_and_schedule_next_command
                scheduled = cmd.scheduled_start

            segs, h_start, h_end = self._build_segments_for_one_command(
                start_mw=cmd.start_mw,
                target_mw=cmd.target_mw,
                start_dt=scheduled,
                hold_minutes=cmd.hold_minutes
            )

            # cập nhật lại vào command để truy vấn sau
            cmd.hold_start = h_start
            cmd.hold_end = h_end

            plan_segments.extend(segs)

        self.current_plan_segments = plan_segments
        self.render_plan()
        self.persist_plan_to_excel()
    
    def render_plan(self):
        """Vẽ timeline của queue nối lệnh từ self.current_plan_segments."""
        if not self.current_plan_segments:
            # Không có gì để vẽ, xóa trục cho sạch
            self.ax.clear()
            self.ax.set_title('TREND: POWER DEPEND ON TIMES (Joined Plan)')
            self.ax.set_xlabel('TIMES')
            self.ax.set_ylabel('POWER (MW)')
            self.canvas.draw_idle()
            return

        xs = [seg["t"] for seg in self.current_plan_segments]
        ys = [seg["mw"] for seg in self.current_plan_segments]

        self.ax.clear()
        self.ax.set_title('TREND: POWER DEPEND ON TIMES (Joined Plan)')
        self.ax.set_xlabel('TIMES')
        self.ax.set_ylabel('POWER (MW)')

        # dùng draw_series như các chỗ khác cho thống nhất
        draw_series(self.ax, [{"x": xs, "y": ys, "label": "Joined Plan"}])
        self.figure.autofmt_xdate()
        self.canvas.draw_idle()


    def persist_plan_to_excel(self):
        """
        Ghi timeline tối giản vào Excel.
        Yêu cầu ExcelUpdater có append_rows(list[dict]) hoặc append_data(dict) (fallback).
        """
        if not self.current_plan_segments:
            return

        rows = []
        for seg in self.current_plan_segments:
            rows.append({
                "Time": seg["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "MW": seg["mw"],
                "Tag": seg.get("tag", ""),
            })

        if hasattr(self.excel_updater, "append_rows"):
            self.excel_updater.append_rows(rows)
        else:
            # fallback nếu class cũ chỉ có append_data
            for r in rows:
                self.excel_updater.append_data(r)

    
    def _compute_last_command_hold_window(self) -> tuple[datetime | None, datetime | None]:
        # Nếu đã có lệnh nối → giữ nguyên như anh đang làm (quét từ command_queue / segments)
        if self.command_queue:
            last = self.command_queue[-1]
            h_start, h_end = last.hold_start, last.hold_end
            if h_start is not None and h_end is not None:
                return h_start, h_end
            if self.current_plan_segments:
                hold_end = None
                hold_start = None
                for seg in reversed(self.current_plan_segments):
                    tag = seg.get("tag")
                    if hold_end is None and tag == "hold_end":
                        hold_end = seg["t"]
                    elif tag == "hold_start":
                        hold_start = seg["t"]
                        if hold_end is not None:
                            break
                if hold_start is not None and hold_end is not None:
                    last.hold_start, last.hold_end = hold_start, hold_end
                    return hold_start, hold_end
            return None, None

        # ⬇️ Fallback khi CHƯA có lệnh nối: dùng cửa sổ HOLD ở 429 (không dùng 462)
        hold_start_429 = self.time_reaching_429
        hold_end_429   = self.post_pause_time  # kết thúc pause ở 429 ⇒ tiếp tục ramp
        return hold_start_429, hold_end_429



    def _compute_last_command_end_time(self) -> datetime:
        if not self.command_queue:
            # end = HOLD_END của 429; nếu thiếu, suy từ 429 + pause_429
            if self.post_pause_time:
                return self.post_pause_time
            if self.time_reaching_429 is not None:
                return self.time_reaching_429 + timedelta(minutes=self.pause_time_429_min or 0)
            return datetime.now()

        last = self.command_queue[-1]
        if last.hold_end is not None:
            return last.hold_end

        if self.current_plan_segments:
            for seg in reversed(self.current_plan_segments):
                if seg.get("tag") == "hold_end":
                    return seg["t"]
            return self.current_plan_segments[-1]["t"]

        return last.scheduled_start or last.start_time

    def _build_join_inputs(self, parent_layout: QVBoxLayout):
        """Cụm ô nhập NỐI LỆNH (không còn Start MW)."""
        join_row = QHBoxLayout()

        title = QLabel("NỐI LỆNH:")
        title.setStyleSheet("font-weight: 600;")
        join_row.addWidget(title)

        # ⬇️ CHỈ GIỮ target_mw + time
        self.target_mw_edit = QLineEdit(self)
        self.target_mw_edit.setPlaceholderText("Target MW (nối lệnh)")
        self.target_mw_edit.setFixedWidth(110)
        join_row.addWidget(QLabel("Kết thúc:"))
        join_row.addWidget(self.target_mw_edit)

        self.join_time_edit = QTimeEdit(self)
        self.join_time_edit.setDisplayFormat("HH:mm")
        self.join_time_edit.setTime(QTime.currentTime())
        self.join_time_edit.setFixedWidth(90)
        join_row.addWidget(QLabel("Thời gian:"))
        join_row.addWidget(self.join_time_edit)

        self.add_cmd_btn = QPushButton("Thêm lệnh (Enter)", self)
        join_row.addWidget(self.add_cmd_btn)

        join_row.addStretch(1)
        parent_layout.addLayout(join_row)

        # Gỡ kết nối cũ nếu có
        try: self.add_cmd_btn.clicked.disconnect()
        except Exception: pass
        try: self.target_mw_edit.returnPressed.disconnect()
        except Exception: pass
        try: self.join_time_edit.editingFinished.disconnect()
        except Exception: pass

        # Kết nối mới
        self.target_mw_edit.returnPressed.connect(self.on_add_command_via_enter)
        # self.join_time_edit.editingFinished.connect(self.on_add_command_via_enter)
        self.add_cmd_btn.clicked.connect(self.on_add_command_via_enter)



