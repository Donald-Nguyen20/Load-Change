# modules/df_plot.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

# ---- helpers: cắt đến trim_time, ghép mối hàn ----
def _trim_main_until(xs: List[datetime],
                     ys: List[float],
                     trim_time: Optional[datetime],
                     trim_mw: Optional[float]) -> Tuple[List[datetime], List[float]]:
    if not xs or not ys or trim_time is None:
        return xs, ys
    kept_x, kept_y = [], []
    for t, y in zip(xs, ys):
        if t <= trim_time:
            kept_x.append(t)
            kept_y.append(y)
    # “mối hàn” tại trim_time
    if (not kept_x) or (kept_x[-1] < trim_time):
        kept_x.append(trim_time)
        kept_y.append(trim_mw if trim_mw is not None else (kept_y[-1] if kept_y else 0.0))
    return kept_x, kept_y

def _prepare_joined_from(xs: List[datetime],
                         ys: List[float],
                         trim_time: Optional[datetime],
                         trim_mw: Optional[float]) -> Tuple[List[datetime], List[float]]:
    if not xs or not ys or trim_time is None:
        return xs, ys
    jx, jy = [], []
    for t, y in zip(xs, ys):
        if t >= trim_time:
            jx.append(t)
            jy.append(y)
    # chèn điểm đầu = trim_time (nếu thiếu) để khớp mối hàn
    if jx:
        if jx[0] > trim_time:
            jx.insert(0, trim_time)
            jy.insert(0, trim_mw if trim_mw is not None else jy[0])
    else:
        # không có điểm nào >= trim_time, có thể vẫn cần 1 điểm mồi để thể hiện mối hàn
        if trim_time is not None and trim_mw is not None:
            jx = [trim_time]
            jy = [trim_mw]
    return jx, jy

# ---- public API ----
def build_plot_df(
    main_xy: Dict[str, List],
    joined_xy: Optional[Dict[str, List]] = None,
    *,
    trim_time: Optional[datetime] = None,
    trim_mw: Optional[float] = None,
    hold_windows: Optional[List[Tuple[datetime, datetime]]] = None,
    events: Optional[Dict[str, Optional[datetime]]] = None,
) -> pd.DataFrame:
    """
    Tạo DataFrame đúng như polyline(s) sau khi cắt-ghép dùng để vẽ.

    Columns:
      - t: datetime
      - mw: float
      - source: 'main' | 'joined'
      - seg_id: int (0=main, 1=joined)
      - is_hold: bool
      - evt: Optional[str]  (gắn label sự kiện vào điểm gần nhất)

    Params:
      - main_xy: {"x": [datetime], "y": [float]}
      - joined_xy: {"x": [...], "y": [...]}, nếu có đoạn nối/override
      - trim_time/trim_mw: mốc cắt và giá trị MW tại “mối hàn”
      - hold_windows: list[(start_dt, end_dt)] để đánh dấu is_hold
      - events: dict tên_sự_kiện -> datetime (vd: {"t_429": dt, "post_pause": dt, ...})
    """
    mx, my = main_xy.get("x", []), main_xy.get("y", [])
    mx, my = _trim_main_until(mx, my, trim_time, trim_mw)

    rows = []
    for t, mw in zip(mx, my):
        rows.append((t, float(mw), "main", 0))

    if joined_xy:
        jx, jy = joined_xy.get("x", []), joined_xy.get("y", [])
        jx, jy = _prepare_joined_from(jx, jy, trim_time, trim_mw)
        for t, mw in zip(jx, jy):
            rows.append((t, float(mw), "joined", 1))

    if not rows:
        return pd.DataFrame(columns=["t", "mw", "source", "seg_id", "is_hold", "evt"])

    df = pd.DataFrame(rows, columns=["t", "mw", "source", "seg_id"])
    # đảm bảo thứ tự: theo seg rồi theo thời gian
    df = df.sort_values(["seg_id", "t"], kind="stable").reset_index(drop=True)

    # is_hold
    df["is_hold"] = False
    if hold_windows:
        for (hs, he) in hold_windows:
            mask = (df["t"] >= hs) & (df["t"] <= he)
            df.loc[mask, "is_hold"] = True

    # gắn sự kiện vào điểm gần nhất
    df["evt"] = pd.Series([None] * len(df), dtype="object")
    if events:
        # chỉ xét những event có timestamp
        for name, t_evt in events.items():
            if t_evt is None:
                continue
            # tìm chỉ số gần nhất theo |t - t_evt|
            # (chú ý: df['t'] là datetime -> trừ nhau được timedelta)
            idx = (df["t"] - t_evt).abs().idxmin()
            if pd.notna(idx):
                df.at[idx, "evt"] = name

    return df

def dfplot_to_draw_inputs(df: pd.DataFrame) -> Tuple[Dict[str, List], Optional[Dict[str, List]]]:
    """
    Từ DataFrame đã build, tái tạo lại 2 series để vẽ:
      return main_xy, joined_xy (joined_xy có thể None nếu không có)
    """
    if df.empty:
        return {"x": [], "y": []}, None

    # giữ nguyên thứ tự theo seg_id và thời gian
    d = df.sort_values(["seg_id", "t"], kind="stable")
    main = d[d["source"] == "main"]
    joined = d[d["source"] == "joined"]

    main_xy = {"x": main["t"].tolist(), "y": main["mw"].tolist()}
    joined_xy = {"x": joined["t"].tolist(), "y": joined["mw"].tolist()} if not joined.empty else None
    return main_xy, joined_xy
# modules/df_plot.py
import pandas as pd
from datetime import timedelta

# def densify_hold_windows(
#     df: pd.DataFrame,
#     hold_windows_labeled,          # [(start, end, label), ...] như ở update_plot
#     *,
#     plateau_429: float | None = None,
#     plateau_462: float | None = None,
#     step_minutes: int = 1
# ) -> pd.DataFrame:
#     """
#     Chèn các điểm phẳng (constant MW) theo bước phút bên trong mỗi hold window.
#     - label chứa '429'  => dùng plateau_429 (vd: 429.0)
#     - label chứa '462'  => dùng plateau_462 (vd: 462.0)
#     - nếu None: fallback lấy MW gần đầu window (hs).
#     """
#     if df is None or df.empty or not hold_windows_labeled:
#         return df

#     d = df.copy()
#     existing_times = set(d["t"].tolist())
#     add_rows = []

#     for hw in hold_windows_labeled:
#         if not hw or len(hw) < 2:
#             continue
#         hs, he = hw[0], hw[1]
#         label = hw[2] if len(hw) >= 3 else ""
#         if hs is None or he is None or he <= hs:
#             continue

#         mw_plat = None
#         if "429" in str(label):
#             mw_plat = plateau_429
#         elif "462" in str(label):
#             mw_plat = plateau_462

#         if mw_plat is None:
#             try:
#                 idx = (d["t"] - hs).abs().idxmin()
#                 mw_plat = float(d.at[idx, "mw"])
#             except Exception:
#                 continue

#         step = timedelta(minutes=step_minutes)
#         cur = hs + step
#         while cur < he:
#             if cur not in existing_times:
#                 add_rows.append((cur, mw_plat, "main", 0, True, None))
#                 existing_times.add(cur)
#             cur += step

#     if add_rows:
#         extra = pd.DataFrame(add_rows, columns=["t", "mw", "source", "seg_id", "is_hold", "evt"])
#         d = pd.concat([d, extra], ignore_index=True)
#         d = d.sort_values(["seg_id", "t"], kind="stable").reset_index(drop=True)

    # return d
def densify_uniform(
    df: pd.DataFrame,
    *,
    step_minutes: int = 1,
    hold_windows_labeled=None,      # [(start, end, label), ...]
    plateau_429: float | None = None,
    plateau_462: float | None = None,
) -> pd.DataFrame:
    """
    Nội suy đều theo phút cho TẤT CẢ các nguồn ('main' và 'joined'):
      - Resample theo bậc thời gian: mỗi step_minutes một điểm.
      - 'mw' nội suy tuyến tính theo thời gian (interpolate time).
      - 'evt' chỉ giữ tại mốc gốc (không lan truyền).
      - Áp cờ 'is_hold' và ép phẳng 429/462 trong các window có label.
    """
    if df is None or df.empty:
        return df

    outs = []
    for sid, g in df.groupby("source", sort=False):
        g = g.sort_values("t").drop_duplicates("t")
        if g.empty:
            continue

        full_t = pd.date_range(g["t"].min(), g["t"].max(), freq=f"{step_minutes}min")
        gi = g.set_index("t").reindex(full_t)

        # nội suy MW theo thời gian
        gi["mw"] = gi["mw"].interpolate(method="time")

        gi["source"] = sid
        gi["seg_id"] = int(g["seg_id"].iloc[0])  # 0=main, 1=joined

        # evt: chỉ giữ ở thời điểm gốc
        if "evt" in gi.columns:
            gi["evt"] = gi["evt"].where(gi.index.isin(g.set_index("t").index))
        else:
            gi["evt"] = None

        # is_hold set sau theo windows
        gi["is_hold"] = False

        gi = gi.reset_index(names="t")
        outs.append(gi)

    d = pd.concat(outs, ignore_index=True) if outs else df.copy()

    # Áp hold windows + plateau
    if hold_windows_labeled:
        for hw in hold_windows_labeled:
            if not hw or len(hw) < 2:
                continue
            hs, he = hw[0], hw[1]
            label = hw[2] if len(hw) >= 3 else ""
            if hs is None or he is None or he <= hs:
                continue
            mask = (d["t"] >= hs) & (d["t"] <= he)
            d.loc[mask, "is_hold"] = True
            if "429" in str(label) and plateau_429 is not None:
                d.loc[mask, "mw"] = float(plateau_429)
            elif "462" in str(label) and plateau_462 is not None:
                d.loc[mask, "mw"] = float(plateau_462)

    return d.sort_values(["seg_id", "t"], kind="stable").reset_index(drop=True)

