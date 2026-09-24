# -*- coding: utf-8 -*-
"""
Multi Activos - Estrategia EMA 10/21 + ATR x1.5
=================================================
Corre el backtest optimizado sobre tres activos en paralelo:
  - Oro      (GC=F)
  - Plata    (SI=F)
  - Petroleo (CL=F)

Requisitos:
  pip install yfinance pandas numpy matplotlib
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
ACTIVOS = {
    "Oro":      {"ticker": "GC=F", "color": "#FFD700"},
    "Plata":    {"ticker": "SI=F", "color": "#C0C0C0"},
    "Petroleo": {"ticker": "CL=F", "color": "#CD853F"},
}

ANIOS            = 10
CAPITAL_INICIAL  = 100_000
RIESGO_POR_TRADE = 0.01
EMA_R            = 10
EMA_L            = 21
ATR_PERIODO      = 14
ATR_MULT_STOP    = 1.5
COMISION         = 0.0005
SLIPPAGE         = 0.0003
RSI_PERIODO      = 14


def descargar(ticker, anios):
    df = yf.download(ticker, period=f"{anios}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close"]].dropna()


def indicadores(df):
    df = df.copy()
    df["EMA_R"] = df["Close"].ewm(span=EMA_R, adjust=False).mean()
    df["EMA_L"] = df["Close"].ewm(span=EMA_L, adjust=False).mean()
    df["compra"] = (df["EMA_R"] > df["EMA_L"]) & (df["EMA_R"].shift() <= df["EMA_L"].shift())
    df["venta"]  = (df["EMA_R"] < df["EMA_L"]) & (df["EMA_R"].shift() >= df["EMA_L"].shift())
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(ATR_PERIODO).mean()
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).rolling(RSI_PERIODO).mean()
    loss  = (-delta.clip(upper=0)).rolling(RSI_PERIODO).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df.dropna()


def backtest(df):
    capital = CAPITAL_INICIAL
    en_pos  = False
    uni = ent = stop = 0.0
    equity, trades = [], []

    for i in range(len(df) - 1):
        hoy     = df.iloc[i]
        maniana = df.iloc[i + 1]

        if en_pos:
            salida = None
            if hoy["Low"] <= stop:
                salida = stop * (1 - SLIPPAGE)
            elif hoy["venta"]:
                salida = maniana["Open"] * (1 - SLIPPAGE)
            if salida:
                pnl = uni * (salida - ent) - uni * salida * COMISION
                capital += pnl
                trades.append(pnl)
                en_pos = False

        if not en_pos and hoy["compra"]:
            ent  = maniana["Open"] * (1 + SLIPPAGE)
            dist = ATR_MULT_STOP * hoy["ATR"]
            if dist <= 0:
                continue
            stop = ent - dist
            uni  = min((capital * RIESGO_POR_TRADE) / dist, capital / ent)
            capital -= uni * ent * COMISION
            en_pos = True

        valor = capital + (uni * (hoy["Close"] - ent) if en_pos else 0)
        equity.append(valor)

    eq   = pd.Series(equity, index=df.index[:len(equity)])
    rend = eq.iloc[-1] / CAPITAL_INICIAL - 1
    n    = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / CAPITAL_INICIAL) ** (1 / n) - 1 if n > 0 else 0
    dd   = (eq / eq.cummax() - 1).min()
    ops  = len(trades)
    gan  = [p for p in trades if p > 0]
    per  = [p for p in trades if p <= 0]
    wr   = len(gan) / ops if ops > 0 else 0
    pf   = sum(gan) / abs(sum(per)) if gan and per else 0

    return eq, {"rendimiento": rend, "cagr": cagr, "drawdown": dd,
                "operaciones": ops, "win_rate": wr, "profit_factor": pf}


def graficar(resultados):
    fig = plt.figure(figsize=(15, 10))
    fig.patch.set_facecolor("#0f0f0f")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    ax_equity = fig.add_subplot(gs[0, :])
    ax_rend   = fig.add_subplot(gs[1, 0])
    ax_dd     = fig.add_subplot(gs[1, 1])
    ax_ops    = fig.add_subplot(gs[1, 2])

    for ax in [ax_equity, ax_rend, ax_dd, ax_ops]:
        ax.set_facecolor("#1a1a1a")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333333")
        ax.grid(alpha=0.15, color="#333333")

    nombres = []
    rends   = []
    dds     = []
    ops_l   = []
    wrs     = []

    for nombre, datos in resultados.items():
        eq    = datos["equity"]
        m     = datos["metricas"]
        color = datos["color"]
        bh    = datos["bh"]

        eq_norm = eq / CAPITAL_INICIAL * 100
        bh_norm = bh / CAPITAL_INICIAL * 100

        ax_equity.plot(eq_norm.index, eq_norm.values,
                       label=f"{nombre} estrategia",
                       linewidth=2, color=color)
        ax_equity.plot(bh_norm.index, bh_norm.values,
                       linewidth=1, alpha=0.3, color=color,
                       linestyle="--", label=f"{nombre} buy&hold")

        nombres.append(nombre)
        rends.append(m["rendimiento"] * 100)
        dds.append(m["drawdown"] * 100)
        ops_l.append(m["operaciones"])
        wrs.append(m["win_rate"] * 100)

    ax_equity.axhline(100, color="#555555", linewidth=1, linestyle=":")
    ax_equity.set_title(f"Equity comparativo (base 100) — EMA {EMA_R}/{EMA_L} + ATR x{ATR_MULT_STOP}",
                        fontsize=12)
    ax_equity.set_ylabel("Base 100")
    ax_equity.legend(facecolor="#1a1a1a", labelcolor="white", fontsize=8, ncol=2)

    colores = [resultados[n]["color"] for n in nombres]

    bars = ax_rend.bar(nombres, rends, color=colores, alpha=0.85)
    ax_rend.set_title("Rendimiento total (%)")
    for bar, val in zip(bars, rends):
        ax_rend.text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + 1 if val >= 0 else bar.get_height() - 3,
                     f"{val:.1f}%", ha="center", va="bottom",
                     color="white", fontsize=9, fontweight="bold")

    bars2 = ax_dd.bar(nombres, dds, color=colores, alpha=0.85)
    ax_dd.set_title("Drawdown maximo (%)")
    for bar, val in zip(bars2, dds):
        ax_dd.text(bar.get_x() + bar.get_width()/2, val - 0.5,
                   f"{val:.1f}%", ha="center", va="top",
                   color="white", fontsize=9, fontweight="bold")

    bars3 = ax_ops.bar(nombres, ops_l, color=colores, alpha=0.85)
    ax_ops.set_title("Operaciones totales")
    for bar, val, wr in zip(bars3, ops_l, wrs):
        ax_ops.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f"{val}\n({wr:.0f}% WR)", ha="center", va="bottom",
                    color="white", fontsize=8, fontweight="bold")

    fig.suptitle(f"Comparativa Multi-Activos | EMA {EMA_R}/{EMA_L} + ATR x{ATR_MULT_STOP} | {ANIOS} anos",
                 color="white", fontsize=13, y=0.98)
    fig.tight_layout()
    fig.savefig("multi_activos.png", dpi=130, bbox_inches="tight", facecolor="#0f0f0f")
    print("Grafica guardada en multi_activos.png")
    plt.show()


if __name__ == "__main__":
    print("=" * 55)
    print(f"  MULTI ACTIVOS | EMA {EMA_R}/{EMA_L} + ATR x{ATR_MULT_STOP} | {ANIOS} anos")
    print("=" * 55)

    resultados = {}

    for nombre, cfg in ACTIVOS.items():
        ticker = cfg["ticker"]
        print(f"\nDescargando {nombre} ({ticker})...")
        df = descargar(ticker, ANIOS)
        if df is None:
            print(f"  ERROR: no se pudieron descargar datos de {ticker}")
            continue
        print(f"  {len(df)} velas, de {df.index[0].date()} a {df.index[-1].date()}")
        df = indicadores(df)
        eq, m = backtest(df)
        bh = CAPITAL_INICIAL * df["Close"] / df["Close"].iloc[0]

        resultados[nombre] = {
            "equity": eq, "metricas": m,
            "color": cfg["color"], "bh": bh
        }

        print(f"  Rendimiento:   {m['rendimiento']:+.1%}")
        print(f"  CAGR:          {m['cagr']:+.1%}")
        print(f"  Drawdown max:  {m['drawdown']:.1%}")
        print(f"  Operaciones:   {m['operaciones']}")
        print(f"  Win rate:      {m['win_rate']:.0%}")
        print(f"  Profit factor: {m['profit_factor']:.2f}")

    if resultados:
        print("\n" + "=" * 55)
        print("  RANKING POR RENDIMIENTO")
        print("=" * 55)
        ranking = sorted(resultados.items(),
                         key=lambda x: x[1]["metricas"]["rendimiento"],
                         reverse=True)
        for i, (nombre, datos) in enumerate(ranking):
            m = datos["metricas"]
            print(f"  #{i+1} {nombre}: {m['rendimiento']:+.1%} | "
                  f"CAGR {m['cagr']:+.1%} | DD {m['drawdown']:.1%} | "
                  f"WR {m['win_rate']:.0%}")
        graficar(resultados)
