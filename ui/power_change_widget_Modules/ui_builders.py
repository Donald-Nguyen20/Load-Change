# -*- coding: utf-8 -*-
from __future__ import annotations
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTimeEdit, QPushButton,
    QComboBox, QFrame, QWidget
)
from PySide6.QtGui import QDoubleValidator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui.result_panel import ResultPanel

# ---- helpers công khai để widget gọi lại như method ----

def labeled_edit(widget, parent_layout_or_widget, label: str, default: str = "", width: int = 100) -> QLineEdit:
    """Bản tách của _labeled_edit(self, ...)."""
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


def labeled_timeedit(widget, parent_layout_or_widget, label: str, *, width: int = 100,
                     default_now: bool = True) -> QTimeEdit:
    """Bản tách của _labeled_timeedit(self, ...). Gắn cờ live tương ứng."""
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

    def stop_live():
        # map lại đúng cờ live của widget
        if getattr(widget, "start_time_edit", None) is te:
            widget._live_start_time = False
        elif getattr(widget, "holding_time_edit", None) is te:
            widget._live_hold_time = False

    te.editingFinished.connect(stop_live)

    row.addWidget(lab)
    row.addWidget(te)
    return te


def toggle_hidden_layout(widget):
    """Bản tách của toggle_hidden_layout(self)."""
    if hasattr(widget, "hidden_frame") and widget.hidden_frame is not None:
        widget.hidden_frame.setVisible(not widget.hidden_frame.isVisible())


def build_ui(widget: QWidget):
    """
    Bản tách của _build_ui(self): dựng toàn bộ khung UI trái/phải,
    figure/canvas, khối ẩn, và gọi builder 'join_inputs' đã tách.
    """
    # Layout ngang tổng thể
    master_layout = QHBoxLayout(widget)
    master_layout.setContentsMargins(10, 10, 10, 10)
    master_layout.setSpacing(12)

    # --- BÊN TRÁI: root layout (UI chính) ---
    root = QVBoxLayout()
    root.setSpacing(8)
    master_layout.addLayout(root, 4)

    # --- BÊN PHẢI: result_column (kết quả) ---
    widget.result_panel = ResultPanel()
    master_layout.addWidget(widget.result_panel, 1)

    # --- Khung nhập chính ---
    input_row = QHBoxLayout()
    widget.start_power_edit = labeled_edit(widget, input_row, "Start Power (MW):")
    widget.target_power_edit = labeled_edit(widget, input_row, "Target Power (MW):")
    widget.start_time_edit   = labeled_timeedit(widget, input_row, "Start Time (HH:MM):", width=90, default_now=True)

    widget.enter_btn  = QPushButton("Enter")
    widget.reset_btn  = QPushButton("Reset")
    widget.toggle_btn = QPushButton("⚙")

    widget.enter_btn.clicked.connect(widget.on_enter_clicked)
    widget.reset_btn.clicked.connect(widget.on_reset_clicked)
    widget.toggle_btn.clicked.connect(widget.toggle_hidden_layout)

    input_row.addWidget(widget.enter_btn, 0, Qt.AlignLeft)
    input_row.addWidget(widget.reset_btn, 0, Qt.AlignLeft)
    input_row.addWidget(widget.toggle_btn, 0, Qt.AlignLeft)
    input_row.addStretch(1)
    root.addLayout(input_row)

    # --- Cụm NỐI LỆNH + Hold Now (đã tách) ---
    widget._build_join_inputs(root)  # wrapper gọi sang join_inputs module

    # --- Khung nhập bổ sung (Hold thường) ---
    hold_row = QHBoxLayout()
    widget.holding_load_edit = labeled_edit(widget, hold_row, "Holding Load (MW):")
    widget.holding_time_edit = labeled_timeedit(widget, hold_row, "Holding Time (HH:MM):", width=90, default_now=True)
    widget.hold_btn = QPushButton("Hold")
    widget.hold_btn.clicked.connect(widget.on_hold_clicked)
    hold_row.addWidget(widget.hold_btn, 0, Qt.AlignLeft)
    hold_row.addStretch(1)
    root.addLayout(hold_row)

    # --- Figure / Canvas ---
    widget.figure = Figure(figsize=(6, 4), dpi=120)
    widget.ax = widget.figure.add_subplot(111)
    widget.ax.set_title('TREND: POWER DEPEND ON TIMES')
    widget.ax.set_xlabel('TIMES')
    widget.ax.set_ylabel('POWER (MW)')
    widget.canvas = FigureCanvas(widget.figure)
    root.addWidget(widget.canvas, 1)

    # --- Layout ẩn (tuỳ biến cảnh báo + pause + pulverizer) ---
    widget.hidden_frame = QFrame()
    widget.hidden_frame.setFrameShape(QFrame.StyledPanel)
    hidden_layout = QVBoxLayout(widget.hidden_frame)

    title = QLabel("Custom Alarm Messages")
    title.setStyleSheet("font-weight:700;")
    hidden_layout.addWidget(title)

    widget.edit_alarm_429      = labeled_edit(widget, hidden_layout, "429 MW Alert:", default=widget.alarm_texts["429"], width=500)
    widget.edit_alarm_hold_comp= labeled_edit(widget, hidden_layout, "Holding Complete Alert:", default=widget.alarm_texts["holding_complete"], width=500)
    widget.edit_alarm_final    = labeled_edit(widget, hidden_layout, "Final Load Alert:", default=widget.alarm_texts["final_load"], width=500)
    widget.edit_alarm_hold10   = labeled_edit(widget, hidden_layout, "Hold 10 Min Alert:", default=widget.alarm_texts["hold_10_min"], width=500)
    widget.edit_alarm_override = labeled_edit(widget, hidden_layout, "Override Alert:", default=widget.alarm_texts["override"], width=500)

    # pause + pulverizer
    pause_row = QHBoxLayout()
    widget.pause_429_edit = labeled_edit(widget, pause_row, "Pause at 429 MW (min):",
                                        default=str(widget.pause_time_429_min), width=60)
    widget.pause_hold_edit = labeled_edit(widget, pause_row, "Hold duration at holding MW (min):",
                                        default=str(widget.pause_time_hold_min), width=60)


    lab_pulv = QLabel("Pulverizer Mode:")
    widget.pulverizer_combo = QComboBox()
    widget.pulverizer_combo.addItems(["3 Puls", "4 Puls"])
    widget.pulverizer_combo.setCurrentText(widget.pulverizer_mode_default)

    pause_row.addWidget(lab_pulv, 0, Qt.AlignLeft)
    pause_row.addWidget(widget.pulverizer_combo, 0, Qt.AlignLeft)
    pause_row.addStretch(1)
    hidden_layout.addLayout(pause_row)

    # Ẩn ngay từ đầu
    widget.hidden_frame.setVisible(False)
    root.addWidget(widget.hidden_frame)

    # kết thúc build UI
    return widget
