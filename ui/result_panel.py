# -*- coding: utf-8 -*-
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class ResultPanel(QFrame):
    """Bảng kết quả bên phải: độc lập layout + style + API set/reset."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ResultPanel")
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(6)

        self.total_load_time_label = QLabel("Load reached: ")
        self.hold_complete_label = QLabel("Holding 462MW compl:")
        self.time_reaching_429_label = QLabel("429 MW: ")
        self.post_pause_time_label = QLabel("Holding 429MW compl: ")
        # ⬇️ NEW: thời gian hoàn thành lệnh nối
        self.override_complete_label = QLabel("Override load: ")
        self.origin_capacity_label = QLabel("Origin Capacity:")
        self.override_capacity_label = QLabel("Override Capacity:")
        for w in [
            self.total_load_time_label,
            self.hold_complete_label,
            self.time_reaching_429_label,
            self.post_pause_time_label,
            self.override_complete_label,   # ⬅️ add vào layout
            self.origin_capacity_label,
            self.override_capacity_label,
        ]:
            w.setProperty("role", "result")
            self.layout.addWidget(w, 0, Qt.AlignLeft)

        self.layout.addStretch(1)

    def _apply_style(self):
        self.setStyleSheet("""
            QFrame#ResultPanel {
                background: #0d1117;
                border-left: 4px solid #00e676;
                border-top: 1px solid #20262e;
                border-bottom: 1px solid #20262e;
                border-right: 1px solid #20262e;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel[role="result"] {
                font-size: 16px;
                letter-spacing: 0.3px;
            }
        """)

    # ---------- Public API ----------
    def reset(self):
        self.total_load_time_label.setText("Load reaching: ")
        self.hold_complete_label.setText("Holding 462MW comp:")
        self.time_reaching_429_label.setText("429 MW: ")
        self.post_pause_time_label.setText("Holding 429MW comp: ")
        # ⬇️ NEW: reset dòng “Override load”
        self.override_complete_label.setText("Override load: ")
        self.origin_capacity_label.setText("Origin Capacity:")
        self.override_capacity_label.setText("Override Capacity:")

    def set_total_load_time(self, t: Optional[str]):
        self.total_load_time_label.setText(
            f'<span style="color:#b0bec5;">Load reaching:</span> '
            f'<span style="color:#00e676;font-weight:700;">{t or ""}</span>'
        )

    def set_429_time(self, t: Optional[str]):
        if t:
            self.time_reaching_429_label.setText(
                f'<span style="color:#b0bec5;">429 MW:</span> '
                f'<span style="color:#00e676;font-weight:700;">{t}</span>'
            )
        else:
            self.time_reaching_429_label.setText(
                '<span style="color:#ffab91;font-weight:700;">'
                'Do not reach 429 MW in the load changing process.</span>'
            )

    def set_post_pause_time(self, t: Optional[str]):
        self.post_pause_time_label.setText(
            f'<span style="color:#b0bec5;">Holding 429MW:</span> '
            f'<span style="color:#00e676;font-weight:700;">{t or ""}</span>'
        )

    def set_hold_complete(self, t: Optional[str], minutes: int = 10):
        if t:
            self.hold_complete_label.setText(
                f'<span style="color:#b0bec5;">Holding 462MW compl:</span> '
                f'<span style="color:#00e676;font-weight:700;">{t}</span>'
            )
        else:
            self.hold_complete_label.setText(
                '<span style="color:#b0bec5;">Holding 462MW:</span>'
            )

    # ⬇️ NEW: API hiển thị thời điểm hoàn thành lệnh nối (reach target của lệnh nối)
    def set_override_complete(self, t: Optional[str]):
        self.override_complete_label.setText(
            f'<span style="color:#b0bec5;">Override load:</span> '
            f'<span style="color:#00e676;font-weight:700;">{t or ""}</span>'
        )
    def set_origin_capacity(self, mwh_text: Optional[str]):
        self.origin_capacity_label.setText(
            f'<span style="color:#b0bec5;">Origin Capacity:</span> '
            f'<span style="color:#00e676;font-weight:700;">{mwh_text or ""}</span>'
        )

    def set_override_capacity(self, mwh_text: Optional[str]):
        self.override_capacity_label.setText(
            f'<span style="color:#b0bec5;">Override Capacity:</span> '
            f'<span style="color:#00e676;font-weight:700;">{mwh_text or ""}</span>'
        )
