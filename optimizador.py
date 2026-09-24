# -*- coding: utf-8 -*-
"""
Optimizador de parametros - Estrategia EMA + Stop ATR sobre ORO
================================================================
Prueba 144 combinaciones de EMA rapida, EMA lenta y multiplicador ATR.
Genera ranking con las mejores combinaciones y graficas comparativas.

Requisitos:
  pip install yfinance pandas numpy matplotlib
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import itertools
import warnings
warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
TICKER           = "GC=F"
ANIOS            = 10
CAPITAL_INICIAL  = 100_000
RIESGO_POR_TRADE = 0.01
ATR_PERIODO      = 14
COMISION         = 0.0005
SLIPPAGE         = 0.0003
MIN_OPERACIONES  = 8

EMA_RAPIDAS = [7, 8, 9, 10, 12, 15]
EMA_LENTAS  = [18, 21, 25, 30, 35, 50]
ATR_MULTS   = [1.5, 2.0, 2.5, 3.0]


def descargar_datos(ticker, anios):
    print(f"Descargando {anios} anios de datos de {ticker}...")
    df = yf.download(ticker, period=f"{anios}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError("No se descargaron datos.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    print(f"  {len(df)} velas, de {df.index[0].date()} a {df.index[-1].date()}")
    return df


def calcular_base(df):
    df = df.copy()
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(ATR_PERIODO).mean()
    return df.dropna()


def backtest(df, ema_r, ema_l, atr_mult):
    ema_rapida = df["Close"].ewm(span=ema_r, adjust=False).mean()
    ema_lenta  = df["Close"].ewm(span=ema_l, adjust=False).mean()
    compra = (ema_rapida > ema_lenta) & (ema_rapida.shift() <= ema_lenta.shift())
    venta  = (ema_rapida < ema_lenta) & (ema_rapida.shift() >= ema_lenta.shift())

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
            elif venta.iloc[i]:
                salida = maniana["Open"] * (1 - SLIPPAGE)
            if salida:
                pnl = uni * (salida - ent) - uni * salida * COMISION
                capital += pnl
                trades.append(pnl)
                en_pos = False

        if not en_pos and compra.iloc[i]:
            ent  = maniana["Open"] * (1 + SLIPPAGE)
            dist = atr_mult * hoy["ATR"]
            if dist <= 0:
                continue
            stop = ent - dist
            uni  = min((capital * RIESGO_POR_TRADE) / dist, capital / ent)
            capital -= uni * ent * COMISION
            en_pos = True

        valor = capital + (uni * (hoy["Close"] - ent) if en_pos else 0)
        equity.append(valor)

    if not equity or len(trades) < MIN_OPERACIONES:
        return None

    eq   = pd.Series(equity)
    rend = eq.iloc[-1] / CAPITAL_INICIAL - 1
    n    = len(df) / 252
    cagr = (eq.iloc[-1] / CAPITAL_INICIAL) ** (1 / n) - 1 if n > 0 else 0
    dd   = (eq / eq.cummax() - 1).min()
    gan  = [p for p in trades if p > 0]
    per  = [p for p in trades if p <= 0]
    wr   = len(gan) / len(trades)
    pf   = sum(gan) / abs(sum(per)) if per and gan else 0
    score = cagr / abs(dd) if dd != 0 else 0

    return {"ema_r": ema_r, "ema_l": ema_l, "atr_mult": atr_mult,
            "rendimiento": rend, "cagr": cagr, "drawdown": dd,
            "operaciones": len(trades), "win_rate": wr,
            "profit_factor": pf, "score": score}


def optimizar(df):
    combos = [(r, l, a)
              for r, l, a in itertools.product(EMA_RAPIDAS, EMA_LENTAS, ATR_MULTS)
              if r < l]
    total = len(combos)
    print(f"\nProbando {total} combinaciones de parametros...")
    print("  (esto tarda unos segundos)\n")
    resultados = []
    for i, (r, l, a) in enumerate(combos):
        res = backtest(df, r, l, a)
        if res:
            resultados.append(res)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total} combinaciones probadas...")
    print(f"  {total}/{total} combinaciones probadas.")
    return pd.DataFrame(resultados)


def reporte(df_res):
    if df_res.empty:
        print("No hubo resultados validos.")
        return
    df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)
    print("\n" + "=" * 65)
    print("  TOP 10 COMBINACIONES (ordenadas por Score = CAGR / |Drawdown|)")
    print("=" * 65)
    print(f"{'#':<3} {'EMA':^8} {'ATR':^5} {'Rend':>7} {'CAGR':>7} "
          f"{'DD':>7} {'Ops':>5} {'WR':>6} {'PF':>6} {'Score':>7}")
    print("-" * 65)
    for i, r in df_res.head(10).iterrows():
        print(f"{i+1:<3} {int(r.ema_r)}/{int(r.ema_l):<5} {r.atr_mult:<5.1f} "
              f"{r.rendimiento:>7.1%} {r.cagr:>7.1%} {r.drawdown:>7.1%} "
              f"{int(r.operaciones):>5} {r.win_rate:>6.0%} "
              f"{r.profit_factor:>6.2f} {r.score:>7.2f}")

    v5 = df_res[(df_res.ema_r == 9) & (df_res.ema_l == 21) & (df_res.atr_mult == 2.0)]
    if not v5.empty:
        pos = v5.index[0] + 1
        print(f"\n  Nuestra V5 (EMA 9/21 ATR x2.0) queda en el lugar #{pos} de {len(df_res)}")
        print(f"  Score V5: {v5.iloc[0].score:.2f}  |  Score #1: {df_res.iloc[0].score:.2f}")

    mejor_atr = df_res.groupby(["ema_r", "ema_l"])["score"].max().reset_index()
    pivot = mejor_atr.pivot(index="ema_l", columns="ema_r", values="score")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    im = axes[0].imshow(pivot.values, aspect="auto", cmap="RdYlGn")
    axes[0].set_xticks(range(len(pivot.columns)))
    axes[0].set_xticklabels(pivot.columns)
    axes[0].set_yticks(range(len(pivot.index)))
    axes[0].set_yticklabels(pivot.index)
    axes[0].set_xlabel("EMA Rapida")
    axes[0].set_ylabel("EMA Lenta")
    axes[0].set_title("Score por combinacion EMA\n(verde=mejor, rojo=peor)")
    plt.colorbar(im, ax=axes[0])

    sc = axes[1].scatter(df_res["drawdown"] * 100, df_res["rendimiento"] * 100,
                         c=df_res["score"], cmap="RdYlGn", alpha=0.7, s=60)
    if not v5.empty:
        axes[1].scatter(v5.iloc[0].drawdown * 100, v5.iloc[0].rendimiento * 100,
                        color="blue", s=150, zorder=5, label="V5 actual (9/21)")
        axes[1].legend()
    plt.colorbar(sc, ax=axes[1], label="Score")
    axes[1].set_xlabel("Drawdown maximo (%)")
    axes[1].set_ylabel("Rendimiento total (%)")
    axes[1].set_title("Rendimiento vs Drawdown\n(esquina sup-derecha = ideal)")
    axes[1].axhline(0, color="gray", linewidth=0.8, alpha=0.5)

    fig.suptitle(f"Optimizador EMA + ATR | {TICKER} {ANIOS} anios", fontsize=13)
    fig.tight_layout()
    fig.savefig("optimizador_resultado.png", dpi=120)
    print(f"\n  Grafica guardada en optimizador_resultado.png")
    plt.show()
    return df_res


if __name__ == "__main__":
    datos = descargar_datos(TICKER, ANIOS)
    datos = calcular_base(datos)
    resultados = optimizar(datos)
    reporte(resultados)
    resultados.sort_values("score", ascending=False).to_csv(
        "optimizador_ranking.csv", index=False)
    print("  Ranking completo guardado en optimizador_ranking.csv")
