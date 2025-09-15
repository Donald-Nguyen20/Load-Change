# modules/plotting.py
# -*- coding: utf-8 -*-
from matplotlib.figure import Figure

def make_figure():
    fig = Figure(figsize=(6, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.set_title('TREND: POWER DEPEND ON TIMES')
    ax.set_xlabel('TIMES')
    ax.set_ylabel('POWER (MW)')
    return fig, ax


def _trim_main_until(main_xy, trim_time, trim_mw):
    if not main_xy or not trim_time:
        return main_xy
    xs, ys = main_xy["x"], main_xy["y"]
    if not xs or not ys:
        return main_xy

    kept_x, kept_y = [], []
    for t, y in zip(xs, ys):
        if t <= trim_time:
            kept_x.append(t)
            kept_y.append(y)

    # đảm bảo có “mối hàn” tại trim_time với MW chuẩn
    if not kept_x or kept_x[-1] < trim_time:
        kept_x.append(trim_time)
        kept_y.append(trim_mw)
    else:
        if kept_x[-1] == trim_time and kept_y[-1] != trim_mw:
            kept_y[-1] = trim_mw

    return {"x": kept_x, "y": kept_y, "label": main_xy.get("label", "Plan")}


def _prepare_joined_from(joined_segments, start_time, start_mw):
    if not joined_segments or not start_time:
        return None
    xs = [seg["t"] for seg in joined_segments]
    ys = [seg["mw"] for seg in joined_segments]
    if not xs:
        return None

    kept_x, kept_y = [], []
    for t, y in zip(xs, ys):
        if t >= start_time:
            kept_x.append(t)
            kept_y.append(y)

    if not kept_x or kept_x[0] > start_time:
        kept_x.insert(0, start_time)
        kept_y.insert(0, start_mw)
    else:
        if kept_x[0] == start_time and kept_y[0] != start_mw:
            kept_y[0] = start_mw

    return {"x": kept_x, "y": kept_y, "label": "Plan"}


def draw_main_and_joined(
    ax, *,
    main_xy=None,
    joined_segments=None,
    hold_windows=None,
    override_point=None,
    trim_time=None, trim_mw=None,
    start_time=None, start_mw=None,
    main_color="tab:green",
    joined_color="tab:orange",   # tách riêng với bridge
    bridge_color="tab:orange",
    hold_color="#5dade2"
):
    ax.clear()

    if hold_windows:
        for t0, t1, _label in hold_windows:
            if t0 and t1 and t1 > t0:
                ax.axvspan(t0, t1, alpha=0.15, color=hold_color)

    if main_xy and trim_time and trim_mw is not None:
        main_xy = _trim_main_until(main_xy, trim_time, trim_mw)

    joined_xy = None
    if joined_segments and start_time and start_mw is not None:
        joined_xy = _prepare_joined_from(joined_segments, start_time, start_mw)

    if (trim_time is not None and start_time is not None and start_time > trim_time
            and trim_mw is not None and start_mw is not None):
        y = start_mw
        ax.plot([trim_time, start_time], [y, y],
                linestyle="-", color=bridge_color, label="_nolegend_", zorder=1)

    plotted = False
    if main_xy and main_xy["x"]:
        ax.plot(main_xy["x"], main_xy["y"],
                marker="o", linestyle="-", color=main_color, label=main_xy.get("label", "Plan (Main)"), zorder=3)
        plotted = True
    if joined_xy and joined_xy["x"]:
        ax.plot(joined_xy["x"], joined_xy["y"],
                marker="o", linestyle="-", color=joined_color, label="Plan (Joined)", zorder=2)
        plotted = True


    # 5) marker override
    if override_point:
        t_ov, mw_ov, text = override_point
        ax.annotate(text, (t_ov, mw_ov), xytext=(5, 5), textcoords="offset points")

    if plotted:
        ax.legend()

    ax.set_title('TREND: POWER DEPEND ON TIMES')
    ax.set_xlabel('TIMES')
    ax.set_ylabel('POWER (MW)')
