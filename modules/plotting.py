# -*- coding: utf-8 -*-
from matplotlib.figure import Figure

def make_figure():
    fig = Figure(figsize=(6, 4), dpi=120)
    ax = fig.add_subplot(111)
    ax.set_title('TREND: POWER DEPEND ON TIMES')
    ax.set_xlabel('TIMES')
    ax.set_ylabel('POWER (MW)')
    return fig, ax

def draw_series(ax, series_list):
    # series_list: List[{"x": list_dt, "y": list_float, "label": "name"}]
    ax.clear()
    has_any = False
    for s in series_list:
        if s["x"] and s["y"]:
            ax.plot(s["x"], s["y"], marker='o', linestyle='-', label=s.get("label", "Series"))
            has_any = True
    if has_any:
        ax.legend()
    ax.set_title('TREND: POWER DEPEND ON TIMES')
    ax.set_xlabel('TIMES')
    ax.set_ylabel('POWER (MW)')
