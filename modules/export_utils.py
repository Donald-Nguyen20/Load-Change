# -*- coding: utf-8 -*-
"""Export helpers for Load-Change app."""
from __future__ import annotations
import pandas as pd

def export_df_with_minutes(df: pd.DataFrame, path: str) -> None:
    """
    Ghi DataFrame ra Excel kèm cột minute_offset (phút từ mốc đầu).
    Yêu cầu DF có cột 't' (datetime).
    """
    if df is None or df.empty:
        raise ValueError("DataFrame rỗng.")

    if "t" not in df.columns:
        raise ValueError("Thiếu cột 't' trong DataFrame.")

    d = df.copy().sort_values("t").reset_index(drop=True)
    t0 = d["t"].iloc[0]
    d["minute_offset"] = (d["t"] - t0).dt.total_seconds() / 60.0

    # Xuất Excel
    d.to_excel(path, index=False)
