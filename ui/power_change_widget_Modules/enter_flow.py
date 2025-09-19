# -*- coding: utf-8 -*-
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
from modules.power_logic import CalcConfig, compute_power_change_and_pauses

def on_enter_clicked(widget):
    """Xử lý khi bấm Enter đầu tiên (lệnh chính)."""
    try:
        start_power = float(widget.start_power_edit.text())
        target_power = float(widget.target_power_edit.text())
        t = widget.start_time_edit.time()
        start_dt = datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
    except ValueError:
        QMessageBox.critical(widget, "Input Error", "Vui lòng nhập đúng định dạng số/giờ.")
        return

    # cập nhật cấu hình từ UI ẩn
    widget.alarm_texts["429"] = widget.edit_alarm_429.text()
    widget.alarm_texts["holding_complete"] = widget.edit_alarm_hold_comp.text()
    widget.alarm_texts["final_load"] = widget.edit_alarm_final.text()
    widget.alarm_texts["hold_10_min"] = widget.edit_alarm_hold10.text()
    widget.alarm_texts["override"] = widget.edit_alarm_override.text()

    try:
        widget.pause_time_429_min = int(widget.pause_429_edit.text() or "0")
        widget.pause_time_hold_min = int(widget.pause_hold_edit.text() or "30")
    except ValueError:
        QMessageBox.critical(widget, "Input Error", "Thời gian pause/hold phải là số phút.")
        return

    pulverizer_mode = widget.pulverizer_combo.currentText()

    # Tính toán bằng modules.power_logic
    try:
        cfg = CalcConfig(
            threshold_429=widget.threshold_429,
            hold_power=widget.holding_complete_mw,
            pause_time_429_min=widget.pause_time_429_min,
            pause_time_hold_min=widget.pause_time_hold_min,
            pulverizer_mode=pulverizer_mode,
        )
    except Exception as e:
        QMessageBox.critical(widget, "Config Error", f"Lỗi cấu hình: {e}")
        return

    result = compute_power_change_and_pauses(
        start_power=start_power,
        target_power=target_power,
        start_time=start_dt,
        cfg=cfg,
    )

    # Gán kết quả vào widget
    widget.times1 = result.times
    widget.powers1 = result.powers
    widget.final_load_time    = result.final_load_time
    widget.time_reaching_429  = result.time_reaching_429
    widget.post_pause_time    = result.post_pause_time
    widget.time_holding_462   = result.time_holding_462
    widget.hold_complete_time = result.hold_complete_time

    # Cập nhật nhãn
    widget.result_panel.set_total_load_time(
        widget.final_load_time.strftime("%H:%M") if widget.final_load_time else None
    )
    if widget.time_reaching_429:
        widget.result_panel.set_429_time(widget.time_reaching_429.strftime("%H:%M"))
        widget.result_panel.set_post_pause_time(
            widget.post_pause_time.strftime("%H:%M") if widget.post_pause_time else None
        )
    else:
        widget.result_panel.set_429_time(None)
        widget.result_panel.set_post_pause_time(None)

    widget.result_panel.set_hold_complete(
        widget.hold_complete_time.strftime("%H:%M") if widget.hold_complete_time else None,
        minutes=widget.pause_time_hold_min
    )

    # Vẽ đồ thị
    widget.update_plot()
