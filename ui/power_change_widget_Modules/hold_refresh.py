# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime
from modules.Hold_module import get_mw_at
from modules.df_plot import build_plot_df, densify_uniform
from modules.energy import energy_summary_mwh
from modules.plotting import draw_main_and_joined
from modules.Hold_module import trim_xy_until

def refresh_after_hold(widget, profile: dict | None = None):
    """
    Hàm dựng lại màn hình sau khi bấm Hold Now:
    - Cắt dữ liệu main/joined tới hard_hold_dt
    - Vẽ lại plot, kẻ vạch HOLD
    - Rebuild DataFrame và tính lại MWh
    - Cập nhật ResultPanel
    """
    if profile is None:
        profile = widget.build_current_profile()

    # Nếu chưa Hold thì gọi lại flow cũ
    if not (widget.hard_hold_active and widget.hard_hold_dt is not None):
        try:
            return widget.compute_and_refresh()
        except Exception:
            return widget.update_plot()

    hold_dt = widget.hard_hold_dt

    # 1) Trim dữ liệu
    main_xy_in   = profile.get("main_xy")
    joined_xy_in = profile.get("joined_xy")
    main_xy   = trim_xy_until(main_xy_in,   hold_dt) if main_xy_in   else None
    joined_xy = trim_xy_until(joined_xy_in, hold_dt) if joined_xy_in else None

    # 2) Lọc markers ≤ hold_dt và thêm 'hard_hold'
    markers_in = profile.get("markers") or {}
    markers = {k: v for k, v in markers_in.items() if (v is not None and v <= hold_dt)}
    markers["hard_hold"] = hold_dt

    # 3) Vẽ lại
    ax = widget.ax
    ax.clear()
    draw_main_and_joined(
        ax,
        main_xy=main_xy,
        joined_segments=(
            [{"t": t, "mw": y} for t, y in zip(joined_xy["x"], joined_xy["y"])]
            if joined_xy else None
        ),
        hold_windows=None,
        override_point=None,
        trim_time=None, trim_mw=None,
        start_time=None, start_mw=None,
    )
    try:
        ax.axvline(hold_dt, linestyle="--", linewidth=1.5)
        y_top = ax.get_ylim()[1]
        ax.text(hold_dt, y_top, "HOLD", va="top", ha="right", fontsize=9)
    except Exception as _e:
        print("[WARN] draw hard_hold marker failed:", _e)

    widget.figure.autofmt_xdate()
    widget.canvas.draw()

    # 4) Rebuild DataFrame sau cắt
    try:
        joined_segments = (
            [{"t": t, "mw": y} for t, y in zip(joined_xy["x"], joined_xy["y"])]
            if joined_xy else []
        )
        events = {
            "t_429":          getattr(widget, "time_reaching_429", None),
            "post_pause":     getattr(widget, "post_pause_time", None),
            "hold_start_462": getattr(widget, "time_holding_462", None),
            "hold_end_462":   getattr(widget, "hold_complete_time", None),
            "override_done":  getattr(widget, "override_complete_time", None),
        }
        events = {k: v for k, v in events.items() if (v is not None and v <= hold_dt)}

        df = build_plot_df(
            main_xy=main_xy or {"x": [], "y": []},
            joined_xy={"x": [s["t"] for s in joined_segments], "y": [s["mw"] for s in joined_segments]}
                      if joined_segments else None,
            trim_time=None,
            trim_mw=None,
            hold_windows=[],
            events=events,
        )
        df = densify_uniform(
            df,
            step_minutes=1,
            hold_windows_labeled=None,
            plateau_429=widget.threshold_429,
            plateau_462=widget.holding_complete_mw,
        )
        widget._last_plot_df = df

        # 5) Cập nhật MWh
        try:
            summary = energy_summary_mwh(df)
            widget.result_panel.set_origin_capacity(
                f"{summary['origin_mwh']:.2f} MWh" if summary['origin_mwh'] > 0 else ""
            )
            widget.result_panel.set_override_capacity(
                f"{summary['override_mwh']:.2f} MWh" if summary['override_mwh'] > 0 else ""
            )
        except Exception as ex_mwh:
            print("[WARN] energy_summary_mwh failed:", ex_mwh)

    except Exception as ex_df:
        print("[WARN] rebuild plot_df after hold failed:", ex_df)

    # 6) Cập nhật ResultPanel từ markers (nếu có API)
    if hasattr(widget, "result_panel") and widget.result_panel:
        try:
            widget.result_panel.update_from_markers(markers)
        except Exception:
            pass

    # 7) Đặt cờ: update_plot sau hiểu là đã cắt sau Hold
    widget._cut_after_join = True
