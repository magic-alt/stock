"""
Analysis Tools Module

Provides analysis utilities for backtest optimization results.
Includes Pareto front calculation and heatmap visualization.
"""
from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd


def pareto_front(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter out dominated configurations based on Sharpe, return, and drawdown.
    
    A configuration dominates another if it's better or equal in all metrics
    and strictly better in at least one.
    
    Args:
        df: DataFrame with columns 'sharpe', 'cum_return', 'mdd'
        
    Returns:
        DataFrame containing only non-dominated configurations
    """
    needed = ["sharpe", "cum_return", "mdd"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"pareto_front missing required column: {col}")
    
    vals = df[needed].astype(float).values
    dominated = np.zeros(len(df), dtype=bool)
    
    for i, (si, ri, di) in enumerate(vals):
        for j, (sj, rj, dj) in enumerate(vals):
            if i == j:
                continue
            # j dominates i if: sj>=si, rj>=ri, dj<=di, and at least one is strictly better
            if (sj >= si) and (rj >= ri) and (dj <= di) and ((sj > si) or (rj > ri) or (dj < di)):
                dominated[i] = True
                break
    
    return df.loc[~dominated]


def save_heatmap(module, df: pd.DataFrame, out_dir: str) -> None:
    """
    Persist quick-look visualizations for optimization surfaces.
    
    Args:
        module: StrategyModule with name and parameter info
        df: DataFrame with optimization results
        out_dir: Output directory for heatmap images
    """
    import matplotlib.pyplot as plt
    import os
    
    def _safe_imshow(piv_val: pd.DataFrame, piv_tr: pd.DataFrame, title: str,
                     xlab: str, ylab: str, out_path: str) -> None:
        """Helper to create heatmap with masking for zero-trade cells."""
        vals = piv_val.copy()
        mask = None
        if piv_tr is not None and piv_tr.shape == vals.shape:
            mask = (piv_tr.values.astype(float) <= 0)
        arr = vals.values.astype(float)
        if mask is not None:
            arr = np.ma.masked_where(mask, arr)
        
        # Handle single row/column with extent+aspect
        fig, ax = plt.subplots()
        nrow, ncol = arr.shape
        extent = [0, max(ncol, 1), 0, max(nrow, 1)]
        im = ax.imshow(arr, aspect="auto", origin="lower", extent=extent)
        ax.set_title(title)
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        
        # Friendly tick labels
        ax.set_xticks(np.arange(ncol) + 0.5)
        ax.set_yticks(np.arange(nrow) + 0.5)
        ax.set_xticklabels(list(vals.columns))
        ax.set_yticklabels(list(vals.index))
        fig.colorbar(im)
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)

    # Use expectancy if available, otherwise cum_return
    val_key = "expectancy" if "expectancy" in df.columns else "cum_return"
    
    if module.name == "ema" and "period" in df.columns:
        df_sorted = df.sort_values("period")
        plt.figure()
        plt.plot(df_sorted["period"], df_sorted[val_key])
        if "trades" in df_sorted.columns:
            z = df_sorted["trades"].fillna(0) <= 0
            if z.any():
                plt.scatter(df_sorted.loc[z, "period"], df_sorted.loc[z, val_key], marker="x")
        plt.title(f"EMA period vs {val_key}")
        plt.xlabel("period")
        plt.ylabel(val_key)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "heat_ema.png"))
        plt.close()
        
    elif module.name == "macd" and {"fast", "slow"}.issubset(df.columns):
        piv = df.pivot_table(index="fast", columns="slow", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="fast", columns="slow", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"MACD {val_key}", "slow", "fast", os.path.join(out_dir, "heat_macd.png"))
        
    elif module.name == "bollinger" and {"period", "devfactor"}.issubset(df.columns):
        piv = df.pivot_table(index="period", columns="devfactor", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="period", columns="devfactor", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"Bollinger {val_key}", "devfactor", "period", os.path.join(out_dir, "heat_bollinger.png"))
        
    elif module.name == "rsi" and {"period", "upper"}.issubset(df.columns):
        piv = df.pivot_table(index="period", columns="upper", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="period", columns="upper", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"RSI {val_key}", "upper", "period", os.path.join(out_dir, "heat_rsi.png"))
        
    elif module.name == "zscore" and {"z_entry", "z_exit"}.issubset(df.columns):
        # ZScore has 3 parameters (period, z_entry, z_exit)
        # Create a 2D heatmap: z_entry vs z_exit, averaged over period
        piv = df.pivot_table(index="z_entry", columns="z_exit", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="z_entry", columns="z_exit", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"ZScore {val_key} (avg over period)", "z_exit", "z_entry", os.path.join(out_dir, "heat_zscore.png"))
        
    elif module.name == "donchian" and {"upper","lower"}.issubset(df.columns):
        piv = df.pivot_table(index="lower", columns="upper", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="lower", columns="upper", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"Donchian {val_key}", "upper", "lower", os.path.join(out_dir, "heat_donchian.png"))
        
    elif module.name == "triple_ma" and {"fast","mid","slow"}.issubset(df.columns):
        # Use fast vs mid (average over slow)
        piv = df.pivot_table(index="fast", columns="mid", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="fast", columns="mid", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"TripleMA {val_key}", "mid", "fast", os.path.join(out_dir, "heat_triple_ma.png"))
        
    elif module.name == "adx_trend" and {"adx_period","adx_th"}.issubset(df.columns):
        piv = df.pivot_table(index="adx_period", columns="adx_th", values=val_key, aggfunc="mean")
        piv_tr = df.pivot_table(index="adx_period", columns="adx_th", values="trades", aggfunc="sum") if "trades" in df.columns else None
        _safe_imshow(piv, piv_tr, f"ADX {val_key}", "adx_th", "adx_period", os.path.join(out_dir, "heat_adx.png"))
        
    elif module.name == "risk_parity" and "vol_window" in df.columns:
        if "max_weight" in df.columns:
            piv = df.pivot_table(index="vol_window", columns="max_weight", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="vol_window", columns="max_weight", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"RiskParity {val_key}", "max_weight", "vol_window", os.path.join(out_dir, "heat_risk_parity.png"))
        else:
            df_sorted = df.sort_values("vol_window")
            plt.figure()
            plt.plot(df_sorted["vol_window"], df_sorted[val_key])
            plt.title(f"RiskParity vol_window vs {val_key}")
            plt.xlabel("vol_window")
            plt.ylabel(val_key)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "heat_risk_parity.png"))
            plt.close()
    
    # Print zero-trade ratio
    if "trades" in df.columns and len(df) > 0:
        zero_ratio = float((df["trades"].fillna(0) <= 0).mean())
        print(f"[{module.name}] zero-trade cells: {zero_ratio:.1%}")
