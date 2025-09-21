# -*- coding: utf-8 -*-
from __future__ import annotations
from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QTimeEdit, QPushButton, QVBoxLayout,
    QFrame
)
from PySide6.QtGui import QDoubleValidator

from ui.power_change_widget_modules.hold_actions import hold_now_clicked

def build_join_inputs(widget, parent_layout: QVBoxLayout):
    """
    Tạo cụm HOLD NOW + cụm NỐI LỆNH nằm cùng một dòng nhưng có nền riêng.
    """

    join_row = QHBoxLayout()
    join_row.setSpacing(20)  # cách nhau 1 chút

    # ========== CỤM HOLD NOW ==========
    hold_frame = QFrame(widget)
    hold_frame.setObjectName("holdFrame")
    hold_frame.setStyleSheet("""
        QFrame#holdFrame {
            background: rgba(255, 208, 0, 0.08);  /* vàng nhạt */
            border: 1px solid rgba(255, 208, 0, 0.4);
            border-radius: 6px;
        }
        QFrame#holdFrame QLabel {
            font-weight: 600;
        }
    """)
    hold_layout = QHBoxLayout(hold_frame)
    hold_layout.setContentsMargins(8, 6, 8, 6)
    hold_layout.setSpacing(6)

    hold_layout.addWidget(QLabel("Hold MW:"))
    widget.hold_now_mw_edit = QLineEdit(widget)
    widget.hold_now_mw_edit.setFixedWidth(80)
    widget.hold_now_mw_edit.setPlaceholderText("auto")
    widget.hold_now_mw_edit.setValidator(QDoubleValidator(0.0, 2000.0, 2, widget))
    hold_layout.addWidget(widget.hold_now_mw_edit)
    widget.hold_now_mw_edit.editingFinished.connect(lambda: setattr(widget, "_live_holdnow_mw", False))

    hold_layout.addWidget(QLabel("Edit Time:"))
    widget.hold_now_time_edit = QTimeEdit(widget)
    widget.hold_now_time_edit.setDisplayFormat("HH:mm")
    widget.hold_now_time_edit.setTime(QTime.currentTime())
    widget.hold_now_time_edit.setFixedWidth(80)
    hold_layout.addWidget(widget.hold_now_time_edit)
    widget.hold_now_time_edit.editingFinished.connect(lambda: setattr(widget, "_live_holdnow_time", False))

    widget.btn_hold_now = QPushButton("Hold Now", widget)
    widget.btn_hold_now.setToolTip("Dừng tại thời điểm bấm; MW lấy từ ô 'Hold MW' hoặc tự động nếu để trống")
    widget.btn_hold_now.clicked.connect(lambda: hold_now_clicked(widget))
    hold_layout.addWidget(widget.btn_hold_now)

    # ========== CỤM NỐI LỆNH ==========
    join_frame = QFrame(widget)
    join_frame.setObjectName("joinFrame")
    join_frame.setStyleSheet("""
        QFrame#joinFrame {
            background: rgba(0, 150, 255, 0.08);  /* xanh nhạt */
            border: 1px solid rgba(0, 150, 255, 0.4);
            border-radius: 6px;
        }
        QFrame#joinFrame QLabel {
            font-weight: 600;
        }
    """)
    join_inner = QHBoxLayout(join_frame)
    join_inner.setContentsMargins(8, 6, 8, 6)
    join_inner.setSpacing(6)

    join_inner.addWidget(QLabel("Override Target:"))
    widget.target_mw_edit = QLineEdit(widget)
    widget.target_mw_edit.setPlaceholderText("Target MW (nối lệnh)")
    widget.target_mw_edit.setFixedWidth(110)
    join_inner.addWidget(widget.target_mw_edit)

    join_inner.addWidget(QLabel("Timeline:"))
    widget.join_time_edit = QTimeEdit(widget)
    widget.join_time_edit.setDisplayFormat("HH:mm")
    widget.join_time_edit.setTime(QTime.currentTime())
    widget.join_time_edit.setFixedWidth(90)
    join_inner.addWidget(widget.join_time_edit)
    widget.join_time_edit.editingFinished.connect(lambda: setattr(widget, "_live_join_time", False))

    widget.add_cmd_btn = QPushButton("Enter", widget)
    join_inner.addWidget(widget.add_cmd_btn)

    # ========== GHÉP 2 KHUNG VÀO DÒNG ==========
    join_row.addWidget(hold_frame)
    join_row.addWidget(join_frame)
    join_row.addStretch(1)
    parent_layout.addLayout(join_row)

    # ========== GẮN SỰ KIỆN ==========
    try:
        widget.target_mw_edit.returnPressed.disconnect()
    except Exception:
        pass
    try:
        widget.add_cmd_btn.clicked.disconnect()
    except Exception:
        pass

    widget.target_mw_edit.returnPressed.connect(widget.on_add_command_via_enter)
    widget.add_cmd_btn.clicked.connect(widget.on_add_command_via_enter)
