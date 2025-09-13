# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QMainWindow, QTabWidget
from .power_change_widget import PowerChangeWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Power Change Application (PySide6)")
        self.resize(1000, 800)

        tabs = QTabWidget()
        tabs.addTab(PowerChangeWidget(excel_file="abc.xlsx"), "Power Change")
        self.setCentralWidget(tabs)
