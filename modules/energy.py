# -*- coding: utf-8 -*-
"""Energy calculators (trapezoid method) for Load-Change app."""
from __future__ import annotations
from typing import Dict
import pandas as pd

__all__ = [
    "energy_trapezoid_mwh",
    "energy_by_source_mwh",
    "energy_summary_mwh",
]

def _ensure_cols(df: pd.DataFrame, cols=("t","mw")) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

def energy_trapezoid_mwh(df: pd.DataFrame) -> float:
    """Sum((P_i + P_{i-1})/2 * Δt_i[hour]) over time series."""
    if df is None or df.empty:
        return 0.0
    _ensure_cols(df, ("t","mw"))
    d = df.sort_values("t").copy()
    dt_hours = d["t"].diff().dt.total_seconds().fillna(0.0) / 3600.0
    mw_curr = d["mw"].astype(float)
    mw_prev = mw_curr.shift(1).fillna(mw_curr)
    area = (mw_prev + mw_curr) * 0.5 * dt_hours
    return float(area.sum())

def energy_by_source_mwh(df: pd.DataFrame) -> Dict[str,float]:
    """MWh per 'source' (main/joined) and total."""
    if df is None or df.empty:
        return {"main": 0.0, "joined": 0.0, "total": 0.0}
    _ensure_cols(df, ("t","mw"))
    if "source" not in df.columns:
        total = energy_trapezoid_mwh(df)
        return {"main": total, "joined": 0.0, "total": total}
    out: Dict[str,float] = {}
    for sid, g in df.groupby("source", sort=False):
        out[str(sid)] = energy_trapezoid_mwh(g)
    out.setdefault("main", 0.0)
    out.setdefault("joined", 0.0)
    out["total"] = out.get("main", 0.0) + out.get("joined", 0.0)
    return out

def energy_summary_mwh(df: pd.DataFrame) -> Dict[str,float]:
    """Return origin/override/total + split hold/ramp."""
    if df is None or df.empty:
        return {"origin_mwh": 0.0, "override_mwh": 0.0, "total_mwh": 0.0, "hold_mwh": 0.0, "ramp_mwh": 0.0}
    per = energy_by_source_mwh(df)
    origin = float(per.get("main", 0.0))
    override = float(per.get("joined", 0.0))
    total = origin + override
    hold = 0.0
    if "is_hold" in df.columns and df["is_hold"].any():
        hold = energy_trapezoid_mwh(df[df["is_hold"] == True])  # noqa: E712
    ramp = max(total - hold, 0.0)
    return {
        "origin_mwh": origin,
        "override_mwh": override,
        "total_mwh": total,
        "hold_mwh": hold,
        "ramp_mwh": ramp,
    }
