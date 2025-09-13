# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
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



class PowerChangeWidget(QWidget):
    def __init__(self, parent=None, *, excel_file: str = "abc.xlsx"):
        super().__init__(parent)

        # --- services/state ---
        self.excel_updater = ExcelUpdater(excel_file)
        self.alarm_played_for_429 = False
        self.alarm_played_for_post_pause = False
        self.alarm_played_for_final_load = False
        self.alarm_played_for_hold_complete = False
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

        # --- UI ---
        self._build_ui()

        # Timer kiểm tra mốc báo động (không hiển thị đồng hồ)
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_and_alarm)
        self.check_timer.start(1000)

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
        self.start_time_edit  = self._labeled_edit(input_row, "Start Time (HH:MM):")

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

        # Khung nhập bổ sung (Hold)
        hold_row = QHBoxLayout()
        self.holding_load_edit = self._labeled_edit(hold_row, "Holding Load (MW):")
        self.holding_time_edit = self._labeled_edit(hold_row, "Holding Time (HH:MM):")
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

    # ----------------------
    # Event handlers
    # ----------------------
    def toggle_hidden_layout(self):
        self.hidden_frame.setVisible(not self.hidden_frame.isVisible())

    def on_enter_clicked(self):
        try:
            start_power = float(self.start_power_edit.text())
            target_power = float(self.target_power_edit.text())
            start_time_str = self.start_time_edit.text().strip()
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Vui lòng nhập đúng định dạng số/giờ.")
            return

        # cập nhật cấu hình từ UI ẩn (nếu người dùng đã mở và chỉnh)
        self.alarm_texts["429"] = self.edit_alarm_429.text()
        self.alarm_texts["holding_complete"] = self.edit_alarm_hold_comp.text()
        self.alarm_texts["final_load"] = self.edit_alarm_final.text()
        self.alarm_texts["hold_10_min"] = self.edit_alarm_hold10.text()

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

        result = compute_power_change_and_pauses(
            start_power=start_power,
            target_power=target_power,
            start_time=start_time_str,  # "HH:MM" hoặc datetime
            cfg=cfg,
        )

        # Gán cho vẽ/logic
        self.times1 = result.times
        self.powers1 = result.powers
        self.final_load_time = result.final_load_time
        self.time_reaching_429 = result.time_reaching_429
        self.post_pause_time = result.post_pause_time
        self.time_holding_462 = result.time_holding_462
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


        # Vẽ đồ thị (KHÔNG tạo FigureCanvas mới)
        self.update_plot()

        # Ghi log Excel
        copy_text = (
            f"Decrease Unit load to {target_power} MW/Giảm tải xuống {target_power} MW"
            if start_power > target_power else
            f"Increase Unit load to {target_power} MW/Tăng tải lên {target_power} MW"
        )
        data = {
            'time_now': datetime.now(),
            'start_power': start_power,
            'target_power': target_power,
            'start_time_str': start_time_str,
            'copy_text': copy_text,
        }
        self.excel_updater.append_data(data)

    def on_hold_clicked(self):
        try:
            holding_load = float(self.holding_load_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Holding Load (MW) phải là số.")
            return

        holding_time = self.holding_time_edit.text().strip()
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
        self.start_power_edit.clear()
        self.target_power_edit.clear()
        self.start_time_edit.clear()
        self.holding_load_edit.clear()
        self.holding_time_edit.clear()

        # 2) Reset cờ báo động
        self.alarm_played_for_429 = False
        self.alarm_played_for_post_pause = False
        self.alarm_played_for_final_load = False
        self.alarm_played_for_hold_complete = False
        self.messagebox_shown = False

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
        }
        flags = {
            "429": self.alarm_played_for_429,
            "holding_complete": self.alarm_played_for_post_pause,
            "final_load": self.alarm_played_for_final_load,
            "hold_10_min": self.alarm_played_for_hold_complete,
        }
        flags = check_and_fire(now, timeline, flags, tts_and_play, self.alarm_texts)
        self.alarm_played_for_429 = flags["429"]
        self.alarm_played_for_post_pause = flags["holding_complete"]
        self.alarm_played_for_final_load = flags["final_load"]
        self.alarm_played_for_hold_complete = flags["hold_10_min"]
