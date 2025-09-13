# -*- coding: utf-8 -*-
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.theme import apply_electric_theme   # <-- import theme

def main():
    app = QApplication(sys.argv)
    apply_electric_theme(app)               # <-- GỌI theme Ở ĐÂY
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
