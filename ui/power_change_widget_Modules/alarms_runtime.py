# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime

# dùng lại logic báo động sẵn có
from modules.alarms import check_and_fire
from modules.audio_tts import tts_and_play


def check_and_alarm(widget):
    """
    Bản tách rời của PowerChangeWidget.check_and_alarm(self).
    Kiểm tra các mốc thời gian và phát cảnh báo bằng TTS.
    """
    now = datetime.now()

    timeline = {
        "429":               getattr(widget, "time_reaching_429", None),
        "holding_complete":  getattr(widget, "post_pause_time", None),
        "final_load":        getattr(widget, "final_load_time", None),
        "hold_10_min":       getattr(widget, "hold_complete_time", None),
        "override":          getattr(widget, "override_complete_time", None),
    }

    flags = {
        "429":               getattr(widget, "alarm_played_for_429", False),
        "holding_complete":  getattr(widget, "alarm_played_for_post_pause", False),
        "final_load":        getattr(widget, "alarm_played_for_final_load", False),
        "hold_10_min":       getattr(widget, "alarm_played_for_hold_complete", False),
        "override":          getattr(widget, "alarm_played_for_override", False),
    }

    # gọi engine báo động chung
    flags = check_and_fire(now, timeline, flags, tts_and_play, widget.alarm_texts)

    # cập nhật cờ về widget
    widget.alarm_played_for_429          = flags["429"]
    widget.alarm_played_for_post_pause   = flags["holding_complete"]
    widget.alarm_played_for_final_load   = flags["final_load"]
    widget.alarm_played_for_hold_complete= flags["hold_10_min"]
    widget.alarm_played_for_override     = flags["override"]
