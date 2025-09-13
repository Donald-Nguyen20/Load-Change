from PySide6.QtWidgets import QApplication

def apply_electric_theme(app: QApplication):
    app.setStyleSheet("""
        /* ===== Base ===== */
        QWidget {
            background: #0b0f14;
            color: #f5f9fc;                        /* chữ rất sáng */
            font-size: 14px;
            font-weight: 600;                     /* đậm nhẹ toàn bộ */
        }
        QLabel  { color: #f5f9fc; }

        /* ===== Tabs ===== */
        QTabWidget::pane {
            border: 1px solid #2b3b44;
            background: #0b0f14;
        }
        QTabBar::tab {
            background: #16212c;
            color: #e8f2f5;
            padding: 6px 12px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
            font-weight: 600;
        }
        QTabBar::tab:selected {
            background: #1e2e3a;
            color: #5affc9;                        /* xanh điện sáng chói */
            font-weight: 700;
        }

        /* ===== Inputs ===== */
        QLineEdit, QComboBox {
            background: #101821;
            color: #f5f9fc;
            border: 1px solid #2b3b44;
            border-radius: 6px;
            padding: 6px 8px;
        }
  QLineEdit:focus, QComboBox:focus {
    border: 2px solid #5affc9;
    background: #1e2e3a;
}


        /* ===== Buttons ===== */
        QPushButton {
            background: #1a2a35;                    /* tối hơn xung quanh để nổi chữ */
            color: #f5f9fc;
            border: 1px solid #2b3b44;
            border-radius: 8px;
            padding: 6px 12px;
            font-weight: 700;                       /* đậm hơn */
        }
        QPushButton:hover {
            border-color: #5affc9;
            color: #5affc9;
        }
        QPushButton:pressed {
            background: #223442;
        }
    """)
