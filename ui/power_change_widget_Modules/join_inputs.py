# -*- coding: utf-8 -*-
from __future__ import annotations
from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QTimeEdit, QPushButton, QVBoxLayout,
)
from PySide6.QtGui import QDoubleValidator

# Nếu đã tách on_hold_now_clicked:
from ui.power_change_widget_Modules.hold_actions import hold_now_clicked  # dùng để gắn vào nút Hold Now

def build_join_inputs(widget, parent_layout: QVBoxLayout):
    """
    Tạo cụm ô nhập NỐI LỆNH + Hold Now.
    Gán các control vào thuộc tính của widget (giữ API cũ):
      - widget.target_mw_edit, widget.join_time_edit, widget.add_cmd_btn
      - widget.hold_now_mw_edit, widget.hold_now_time_edit, widget.btn_hold_now
    """
    join_row = QHBoxLayout()

    # Target MW
    widget.target_mw_edit = QLineEdit(widget)
    widget.target_mw_edit.setPlaceholderText("Target MW (nối lệnh)")
    widget.target_mw_edit.setFixedWidth(110)
    join_row.addWidget(QLabel("Override Target:"))
    join_row.addWidget(widget.target_mw_edit)

    # Timeline (Join time)
    widget.join_time_edit = QTimeEdit(widget)
    widget.join_time_edit.setDisplayFormat("HH:mm")
    widget.join_time_edit.setTime(QTime.currentTime())
    widget.join_time_edit.setFixedWidth(90)

    def _stop_live_join():
        widget._live_join_time = False
    widget.join_time_edit.editingFinished.connect(_stop_live_join)
    join_row.addWidget(QLabel("Timeline:"))
    join_row.addWidget(widget.join_time_edit)

    # Nút Enter (thêm lệnh)
    widget.add_cmd_btn = QPushButton("Enter", widget)
    join_row.addWidget(widget.add_cmd_btn)

    # --- Hold Now cluster ---
    join_row.addWidget(QLabel("Hold MW:"))
    widget.hold_now_mw_edit = QLineEdit(widget)
    widget.hold_now_mw_edit.setFixedWidth(80)
    widget.hold_now_mw_edit.setPlaceholderText("auto")
    widget.hold_now_mw_edit.setValidator(QDoubleValidator(0.0, 2000.0, 2, widget))
    join_row.addWidget(widget.hold_now_mw_edit)

    def _stop_live_holdmw():
        widget._live_holdnow_mw = False
    widget.hold_now_mw_edit.editingFinished.connect(_stop_live_holdmw)

    join_row.addWidget(QLabel("Edit Time:"))
    widget.hold_now_time_edit = QTimeEdit(widget)
    widget.hold_now_time_edit.setDisplayFormat("HH:mm")
    widget.hold_now_time_edit.setTime(QTime.currentTime())
    widget.hold_now_time_edit.setFixedWidth(80)

    def _stop_live_holdnow_time():
        widget._live_holdnow_time = False
    widget.hold_now_time_edit.editingFinished.connect(_stop_live_holdnow_time)
    join_row.addWidget(widget.hold_now_time_edit)

    widget.btn_hold_now = QPushButton("Hold Now", widget)
    widget.btn_hold_now.setToolTip(
        "Dừng tại thời điểm bấm; MW dùng ô 'Hold MW' (nếu nhập), hoặc tự lấy theo dữ liệu hiện tại khi để trống/auto"
    )
    # Nếu anh vẫn giữ on_hold_now_clicked trong class, có thể gắn: widget.btn_hold_now.clicked.connect(widget.on_hold_now_clicked)
    # Ở đây ưu tiên gọi module đã tách:
    widget.btn_hold_now.clicked.connect(lambda: hold_now_clicked(widget))
    join_row.addWidget(widget.btn_hold_now)

    join_row.addStretch(1)
    parent_layout.addLayout(join_row)

    # --- Disconnect kết nối cũ (nếu có) rồi gắn mới ---
    try:
        widget.add_cmd_btn.clicked.disconnect()
    except Exception:
        pass
    try:
        widget.target_mw_edit.returnPressed.disconnect()
    except Exception:
        pass
    try:
        widget.join_time_edit.editingFinished.disconnect()
    except Exception:
        pass

    # Kết nối mới (giữ logic cũ)
    widget.target_mw_edit.returnPressed.connect(widget.on_add_command_via_enter)
    widget.add_cmd_btn.clicked.connect(widget.on_add_command_via_enter)
