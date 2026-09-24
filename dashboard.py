# -*- coding: utf-8 -*-
"""
Dashboard - Paper Trading Bot Oro
==================================
Lee paper_equity.csv y paper_trades.csv y genera
una grafica en tema oscuro con el desempeno del bot.

Uso:
  python dashboard.py
"""

import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
from datetime import date

CAPITAL_INICIAL = 100_000
DIR             = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_EQUITY  = os.path.join(DIR, "paper_equity.csv")
ARCHIVO_TRADES  = os.path.join(DIR, "paper_trades.csv")
ARCHIVO_ESTADO  = os.path.join(DIR, "paper_estado.json")


def cargar_equity():
    if not os.path.exists(ARCHIVO_EQUITY):
        print("No existe paper_equity.csv. Corre paper_trading.py primero.")
        return None
    df = pd.read_csv(ARCHIVO_EQUITY, parse_dates=["fecha"])
    return df.drop_duplicates("fecha").sort_values("fecha").reset_index(drop=True)


def cargar_trades():
    if not os.path.exists(ARCHIVO_TRADES):
        return pd.DataFrame()
    df = pd.read_csv(ARCHIVO_TRADES, parse_dates=["fecha"])
    return df[df["tipo"] != "COMPRA"]


def cargar_compras():
    if not os.path.exists(ARCHIVO_TRADES):
        return pd.DataFrame()
    df = pd.read_csv(ARCHIVO_TRADES, parse_dates=["fecha"])
    return df[df["tipo"] == "COMPRA"]


def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return {}
    with open(ARCHIVO_ESTADO) as f:
        return json.load(f)


def calcular_metricas(eq, trades):
    if eq is None or len(eq) == 0:
        return {}
    equity = eq["equity_total"]
    rend   = equity.iloc[-1] / CAPITAL_INICIAL - 1
    dd_max = (equity / equity.cummax() - 1).min()
    dias   = (eq["fecha"].iloc[-1] - eq["fecha"].iloc[0]).days
    cagr   = (equity.iloc[-1] / CAPITAL_INICIAL) ** (365 / max(dias, 1)) - 1 if dias > 0 else 0
    ops    = trades[trades["tipo"].isin(["STOP", "CRUCE_BAJA"])] if not trades.empty else pd.DataFrame()
    n_ops  = len(ops)
    wr = pf = 0
    if n_ops > 0:
        pnls = ops["pnl"].astype(float)
        gan  = pnls[pnls > 0]
        per  = pnls[pnls <= 0]
        wr   = len(gan) / n_ops
        pf   = gan.sum() / abs(per.sum()) if len(per) > 0 and per.sum() != 0 else 0
    return {"rendimiento": rend, "cagr": cagr, "dd_max": dd_max,
            "dias": dias, "n_ops": n_ops, "win_rate": wr,
            "profit_factor": pf, "equity_actual": equity.iloc[-1]}


def graficar(eq, trades, compras, estado, m):
    fig = plt.figure(figsize=(14, 8))
    fig.patch.set_facecolor("#0f0f0f")
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[3, 1],
                           hspace=0.35, wspace=0.3)
    ax_equity  = fig.add_subplot(gs[0, :])
    ax_dd      = fig.add_subplot(gs[1, 0])
    ax_metrics = fig.add_subplot(gs[1, 1])

    for ax in [ax_equity, ax_dd]:
        ax.set_facecolor("#1a1a1a")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#333333")

    ax_equity.plot(eq["fecha"], eq["equity_total"],
                   color="#00d4aa", linewidth=2, label="Equity")
    ax_equity.axhline(CAPITAL_INICIAL, color="#555555",
                      linewidth=1, linestyle="--")
    ax_equity.fill_between(eq["fecha"], CAPITAL_INICIAL, eq["equity_total"],
                           where=eq["equity_total"] >= CAPITAL_INICIAL,
                           alpha=0.15, color="#00d4aa")
    ax_equity.fill_between(eq["fecha"], CAPITAL_INICIAL, eq["equity_total"],
                           where=eq["equity_total"] < CAPITAL_INICIAL,
                           alpha=0.15, color="#ff4444")

    if not compras.empty:
        for _, row in compras.iterrows():
            ax_equity.axvline(row["fecha"], color="#00ff88",
                              linewidth=1, alpha=0.6, linestyle=":")
    if not trades.empty:
        for _, row in trades[trades["tipo"] == "STOP"].iterrows():
            ax_equity.axvline(row["fecha"], color="#ff4444",
                              linewidth=1, alpha=0.6, linestyle=":")
        for _, row in trades[trades["tipo"] == "CRUCE_BAJA"].iterrows():
            ax_equity.axvline(row["fecha"], color="#ffaa00",
                              linewidth=1, alpha=0.6, linestyle=":")

    leyenda = [
        Line2D([0], [0], color="#00d4aa", linewidth=2, label="Equity"),
        Line2D([0], [0], color="#555555", linewidth=1,
               linestyle="--", label=f"Capital inicial ${CAPITAL_INICIAL:,.0f}"),
        Line2D([0], [0], color="#00ff88", linewidth=1,
               linestyle=":", label="Compra"),
        Line2D([0], [0], color="#ffaa00", linewidth=1,
               linestyle=":", label="Venta"),
        Line2D([0], [0], color="#ff4444", linewidth=1,
               linestyle=":", label="Stop Loss"),
    ]
    ax_equity.legend(handles=leyenda, facecolor="#1a1a1a",
                     labelcolor="white", fontsize=8)
    ax_equity.set_title("Equity Paper Trading — Bot Oro (GC=F)", fontsize=13)
    ax_equity.set_ylabel("Capital (MXN)")
    ax_equity.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax_equity.grid(alpha=0.15, color="#333333")

    dd = (eq["equity_total"] / eq["equity_total"].cummax() - 1) * 100
    ax_dd.fill_between(eq["fecha"], dd, 0, alpha=0.6, color="#ff4444")
    ax_dd.plot(eq["fecha"], dd, color="#ff6666", linewidth=1)
    ax_dd.set_title("Drawdown (%)", fontsize=10)
    ax_dd.set_ylabel("%")
    ax_dd.grid(alpha=0.15, color="#333333")

    ax_metrics.set_facecolor("#1a1a1a")
    ax_metrics.axis("off")
    ax_metrics.set_title("Metricas", fontsize=10, color="white")

    rend_color = "#00d4aa" if m.get("rendimiento", 0) >= 0 else "#ff4444"
    lineas = [
        ("Equity actual",  f"${m.get('equity_actual', CAPITAL_INICIAL):,.2f}"),
        ("Rendimiento",    f"{m.get('rendimiento', 0):+.1%}"),
        ("CAGR",           f"{m.get('cagr', 0):+.1%}"),
        ("Drawdown max",   f"{m.get('dd_max', 0):.1%}"),
        ("Dias operando",  f"{m.get('dias', 0)}"),
        ("Operaciones",    f"{m.get('n_ops', 0)}"),
        ("Win rate",       f"{m.get('win_rate', 0):.0%}"),
        ("Profit factor",  f"{m.get('profit_factor', 0):.2f}"),
        ("En posicion",    "SI" if estado.get("en_posicion") else "NO"),
    ]
    for i, (label, valor) in enumerate(lineas):
        y = 0.92 - i * 0.10
        ax_metrics.text(0.05, y, label + ":", transform=ax_metrics.transAxes,
                        color="#aaaaaa", fontsize=9, va="top")
        color = rend_color if label == "Rendimiento" else "white"
        ax_metrics.text(0.65, y, valor, transform=ax_metrics.transAxes,
                        color=color, fontsize=9, va="top", fontweight="bold")

    fig.suptitle(f"Dashboard Bot Oro  |  Actualizado: {date.today()}",
                 color="white", fontsize=11, y=0.98)
    output = os.path.join(DIR, "dashboard.png")
    fig.savefig(output, dpi=130, bbox_inches="tight", facecolor="#0f0f0f")
    print(f"Dashboard guardado en: {output}")
    plt.show()


if __name__ == "__main__":
    eq      = cargar_equity()
    trades  = cargar_trades()
    compras = cargar_compras()
    estado  = cargar_estado()
    if eq is None or eq.empty:
        print("Sin datos suficientes. Corre paper_trading.py al menos un dia.")
    else:
        m = calcular_metricas(eq, trades if not trades.empty else pd.DataFrame())
        graficar(eq, trades, compras, estado, m)
