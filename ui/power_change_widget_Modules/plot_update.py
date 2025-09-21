# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime
from matplotlib import dates as mdates

from modules.plotting import draw_main_and_joined
from modules.df_plot import build_plot_df, densify_uniform
from modules.energy import energy_summary_mwh
from modules.Hold_module import get_mw_at


# ===================== Helpers nội bộ =====================

def _joined_xy_from_segments(segments):
    """segments -> joined_xy dict {'x': [...], 'y': [...]} hoặc None."""
    if not segments:
        return None
    jx = [seg["t"] for seg in segments]
    jy = [seg["mw"] for seg in segments]
    return {"x": jx, "y": jy}

def _hold_windows(widget):
    """Trích danh sách hold windows [(start, end, label), ...]."""
    hold_windows = []
    if widget.time_reaching_429 and widget.post_pause_time:
        hold_windows.append((widget.time_reaching_429, widget.post_pause_time, "Hold @429"))
    if widget.time_holding_462 and widget.hold_complete_time:
        hold_windows.append((widget.time_holding_462, widget.hold_complete_time, "Hold @462"))
    return hold_windows

def _events(widget):
    """Các mốc sự kiện để build DF."""
    return {
        "t_429":           getattr(widget, "time_reaching_429", None),
        "post_pause":      getattr(widget, "post_pause_time", None),
        "hold_start_462":  getattr(widget, "time_holding_462", None),
        "hold_end_462":    getattr(widget, "hold_complete_time", None),
        "override_done":   getattr(widget, "override_complete_time", None),
    }

def _compute_trim_and_start(widget, joined_segments):
    """
    Tính trim_time/trim_mw và start_time/start_mw phục vụ vẽ nối & cắt main.
    Trả về: trim_time, trim_mw, start_time, start_mw
    """
    trim_time = None
    trim_mw   = None
    start_time = None
    start_mw   = None

    if widget._cut_after_join:
        # mặc định cắt ở post_pause_time, fallback mốc đầu plan nối
        trim_time = widget.post_pause_time
        if trim_time is None and joined_segments:
            trim_time = joined_segments[0]["t"]
        if trim_time is not None:
            trim_mw = widget.threshold_429

    if widget._cut_after_join and joined_segments:
        start_time = joined_segments[0]["t"]
        start_mw   = joined_segments[0]["mw"]

        # cắt main tại đúng mốc start này lấy MW thật từ series main
        trim_time = start_time
        if widget.times1 and widget.powers1:
            main_xy_for_trim = {"x": widget.times1, "y": widget.powers1}
            trim_mw = get_mw_at(main_xy_for_trim, trim_time)
        else:
            trim_mw = start_mw

    return trim_time, trim_mw, start_time, start_mw

def _draw_preview_or_hold(widget):
    """
    Vẽ vạch HOLD thật (nếu đang hold) hoặc PREVIEW (nếu chưa hold).
    Đảm bảo trục X bao trùm thời điểm preview.
    """
    if widget.hard_hold_active and widget.hard_hold_dt is not None:
        try:
            widget.ax.axvline(widget.hard_hold_dt, linestyle="--", linewidth=1.5)
            y_top = widget.ax.get_ylim()[1]
            widget.ax.text(widget.hard_hold_dt, y_top, "HOLD", va="top", ha="right", fontsize=9)
        except Exception as _e:
            print("[WARN] draw hard_hold marker failed:", _e)
        # return

    # PREVIEW

        # PREVIEW: mốc chạy theo thời gian + bám MW live
    try:
        # (A) Thời điểm preview = NOW để vạch chạy theo thời gian
        hold_dt_preview = datetime.now()

        # (B) Đảm bảo trục X bao trùm mốc thời gian hiện tại
        x0, x1 = widget.ax.get_xlim()
        tnum = mdates.date2num(hold_dt_preview)
        if tnum < x0 or tnum > x1:
            widget.ax.set_xlim(min(x0, tnum), max(x1, tnum))

        # (C) Xoá marker preview cũ nếu có (tránh chồng vệt)
        prev = getattr(widget, "_preview_artist", None)
        if prev is not None:
            try:
                prev.remove()
            except Exception:
                pass
            widget._preview_artist = None

        # (D) Vạch dọc thời gian (giữ để dễ quan sát)
        widget.ax.axvline(hold_dt_preview, linestyle=":", linewidth=1.2, alpha=0.5)

        # (E) Lấy MW live và vẽ marker tại (t_now, MW_live)
        y_live = getattr(widget, "current_power_live_value", None)
        if y_live is None:
            # fallback: nội suy trực tiếp nếu tick đầu chưa có biến live
            prof = getattr(widget, "_last_profile", None) or {}
            top_xy = prof.get("joined_xy") or prof.get("main_xy")
            if top_xy:
                y_live = get_mw_at(top_xy, hold_dt_preview)

        if y_live is not None:
            widget._preview_artist = widget.ax.scatter([hold_dt_preview], [y_live], s=28, zorder=7)
            # --- NEW: hiển thị nhãn MW tại mốc preview ---
        # Xoá text cũ nếu có
        old_txt = getattr(widget, "_preview_text", None)
        if old_txt is not None:
            try:
                old_txt.remove()
            except Exception:
                pass
            widget._preview_text = None

        # Nội dung nhãn: "xxx.x MW @ HH:MM:SS"
        try:
            label = f"{float(y_live):.1f} MW @ {hold_dt_preview:%H:%M:%S}"
            # Vẽ lệch nhẹ lên trên để không đè vào chấm
            widget._preview_text = widget.ax.text(
                hold_dt_preview, y_live,
                label,
                fontsize=8, va="bottom", ha="left",
                zorder=8,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7, linewidth=0.0),
            )
        except Exception:
            pass


    except Exception:
        pass



def _overlay_df_plot(widget, df):
    """Vẽ overlay từ DataFrame để đối chiếu (main/joined/events)."""
    try:
        if df is None or df.empty:
            return
        dfo = df.sort_values(["seg_id", "t"], kind="stable")

        main_df = dfo[dfo["source"] == "main"]
        if not main_df.empty:
            widget.ax.plot(
                main_df["t"], main_df["mw"],
                linestyle="--", linewidth=1.2, alpha=0.9,
                label="DF main (check)", zorder=5
            )

        joined_df = dfo[dfo["source"] == "joined"]
        if not joined_df.empty:
            widget.ax.plot(
                joined_df["t"], joined_df["mw"],
                linestyle="--", linewidth=1.2, alpha=0.9,
                label="DF joined (check)", zorder=5
            )

        evt_df = dfo[dfo["evt"].notna()]
        if not evt_df.empty:
            widget.ax.scatter(
                evt_df["t"], evt_df["mw"],
                s=18, alpha=0.9, label="DF events", zorder=6
            )

        widget.ax.legend()
    except Exception as e:
        print("[WARN] DF overlay plot failed:", e)


# ===================== API chính =====================

def update_plot(widget):
    """
    Bản tách rời từ PowerChangeWidget.update_plot(self).
    Giữ nguyên hành vi hiện tại: vẽ main + joined + hold windows, build DF, MWh, overlay, vạch HOLD/PREVIEW.
    """
    # main_xy từ times1/powers1
    main_xy = {"x": widget.times1, "y": widget.powers1, "label": "Main Load Change"} \
              if (widget.times1 and widget.powers1) else None

    joined_segments = widget.current_plan_segments or None
    hold_windows = _hold_windows(widget)

    override_point = None
    if getattr(widget, "override_complete_time", None) and widget.command_queue:
        last_cmd = widget.command_queue[-1]
        override_point = (widget.override_complete_time, last_cmd.target_mw, "Override")

    # tính trim/start
    trim_time, trim_mw, start_time, start_mw = _compute_trim_and_start(widget, joined_segments)

    # joined_xy cho DF
    joined_xy = _joined_xy_from_segments(joined_segments)

    # hold windows -> dạng (start,end) cho DF
    _hold_windows_df = []
    for hw in (hold_windows or []):
        if len(hw) >= 2:
            _hold_windows_df.append((hw[0], hw[1]))

    # events cho DF
    events = _events(widget)

    # ---------- Build DF + tính MWh ----------
    try:
        df = build_plot_df(
            main_xy=main_xy or {"x": [], "y": []},
            joined_xy=joined_xy,
            trim_time=trim_time,
            trim_mw=trim_mw,
            hold_windows=_hold_windows_df,
            events=events,
        )
        df = densify_uniform(
            df,
            step_minutes=1,
            hold_windows_labeled=hold_windows,
            plateau_429=widget.threshold_429,
            plateau_462=widget.holding_complete_mw,
        )
        widget._last_plot_df = df

        summary = energy_summary_mwh(df)
        widget.result_panel.set_origin_capacity(
            f"{summary['origin_mwh']:.2f} MWh" if summary['origin_mwh'] > 0 else ""
        )
        widget.result_panel.set_override_capacity(
            f"{summary['override_mwh']:.2f} MWh" if summary['override_mwh'] > 0 else ""
        )

        # Debug (tuỳ chọn)
        # print("\n=== PLOT_DF (first 40 rows) ===")
        # print(df.head(40).to_string(index=False))

    except Exception as e:
        print("[WARN] build_plot_df/densify/energy failed:", e)
        df = None

    # ---------- Vẽ đường chính ----------
    draw_main_and_joined(
        widget.ax,
        main_xy=main_xy,
        joined_segments=joined_segments,
        hold_windows=hold_windows,
        override_point=override_point,
        trim_time=trim_time, trim_mw=trim_mw,
        start_time=start_time, start_mw=start_mw,
    )

    # HOLD/PREVIEW line
    _draw_preview_or_hold(widget)

    # Overlay từ DF
    _overlay_df_plot(widget, getattr(widget, "_last_plot_df", None))

    # Render
    widget.figure.autofmt_xdate()
    widget.canvas.draw()
    try:
        widget.fig.canvas.draw_idle()
    except Exception:
        pass
