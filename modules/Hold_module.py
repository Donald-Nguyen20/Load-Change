from datetime import datetime

def get_mw_at(xy: dict | None, t: datetime) -> float | None:
    """
    Lấy MW tại thời điểm t theo xy {"x":[dt...], "y":[float...]}.
    Giả định đoạn thẳng (linear) giữa các điểm; nếu trước/giữa/đúng mốc đều xử lý ổn.
    """
    if not xy or "x" not in xy or "y" not in xy: return None
    xs, ys = xy["x"], xy["y"]
    if not xs or not ys: return None

    # nếu t trước điểm đầu hoặc đúng bằng: trả y đầu
    if t <= xs[0]: return ys[0]
    # nếu t sau điểm cuối hoặc đúng bằng: trả y cuối
    if t >= xs[-1]: return ys[-1]

    # tìm vị trí k sao cho xs[k] <= t <= xs[k+1]
    # (tuyến tính: y = y0 + (y1 - y0) * (t - x0)/(x1 - x0))
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x0 <= t <= x1:
            y0, y1 = ys[i], ys[i + 1]
            if x1 == x0:  # tránh chia 0 (điểm trùng)
                return y0
            frac = (t - x0).total_seconds() / (x1 - x0).total_seconds()
            return y0 + (y1 - y0) * frac
    return ys[-1]


def trim_xy_until(xy: dict | None, trim_dt: datetime) -> dict | None:
    """
    Cắt XY đến đúng trim_dt, giữ 'mối hàn' tại trim_dt để vẽ liên tục.
    """
    if not xy or "x" not in xy or "y" not in xy: return xy
    xs, ys = xy["x"], xy["y"]
    if not xs or not ys: return xy

    kept_x, kept_y = [], []
    last_y = None
    for t, y in zip(xs, ys):
        if t <= trim_dt:
            kept_x.append(t)
            kept_y.append(y)
            last_y = y
        else:
            break

    # thêm 'mối hàn' tại trim_dt
    if kept_x:
        if kept_x[-1] < trim_dt:
            kept_x.append(trim_dt)
            kept_y.append(last_y if last_y is not None else ys[0])
    else:
        kept_x = [trim_dt]
        kept_y = [ys[0]]

    return {"x": kept_x, "y": kept_y}
