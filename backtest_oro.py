# -*- coding: utf-8 -*-
"""
Backtest - Estrategia SMA 20/50 sobre ORO - Evolucion de versiones
===================================================================
V1: SMA 20/50 + Stop fijo ATR            (referencia)
V4: SMA 20/50 + ATR trailing + RSI>80   (mejor salida)
V5: EMA  9/21 + Stop fijo ATR            (entrada mas rapida)
V5b: EMA 9/21 + trailing ATR + RSI>80   (combo completo)

Requisitos:
  pip install yfinance pandas numpy matplotlib
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
TICKER           = "GC=F"
ANIOS            = 10
SMA_R            = 20
SMA_L            = 50
EMA_R            = 9
EMA_L            = 21
CAPITAL_INICIAL  = 100_000
RIESGO_POR_TRADE = 0.01
ATR_PERIODO      = 14
ATR_MULT_STOP    = 2.0
ATR_MULT_TRAIL   = 2.5
GANANCIA_ACTIVA  = 0.5
RSI_PERIODO      = 14
RSI_SALIDA       = 80
COMISION         = 0.0005
SLIPPAGE         = 0.0003


# ----------------------------------------------------------------------
# 1. DESCARGA
# ----------------------------------------------------------------------
def descargar_datos(ticker, anios):
    print(f"Descargando {anios} anios de {ticker}...")
    df = yf.download(ticker, period=f"{anios}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError("No se descargaron datos.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    print(f"  {len(df)} velas, de {df.index[0].date()} a {df.index[-1].date()}")
    return df


# ----------------------------------------------------------------------
# 2. INDICADORES
# ----------------------------------------------------------------------
def agregar_indicadores(df):
    df = df.copy()
    df["SMA_R"] = df["Close"].rolling(SMA_R).mean()
    df["SMA_L"] = df["Close"].rolling(SMA_L).mean()
    df["sma_compra"] = (df["SMA_R"] > df["SMA_L"]) & (df["SMA_R"].shift() <= df["SMA_L"].shift())
    df["sma_venta"]  = (df["SMA_R"] < df["SMA_L"]) & (df["SMA_R"].shift() >= df["SMA_L"].shift())
    df["EMA_R"] = df["Close"].ewm(span=EMA_R, adjust=False).mean()
    df["EMA_L"] = df["Close"].ewm(span=EMA_L, adjust=False).mean()
    df["ema_compra"] = (df["EMA_R"] > df["EMA_L"]) & (df["EMA_R"].shift() <= df["EMA_L"].shift())
    df["ema_venta"]  = (df["EMA_R"] < df["EMA_L"]) & (df["EMA_R"].shift() >= df["EMA_L"].shift())
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


# ----------------------------------------------------------------------
# 3. METRICAS
# ----------------------------------------------------------------------
def metricas(df_eq, trades, nombre):
    eq   = df_eq["equity"]
    rend = eq.iloc[-1] / CAPITAL_INICIAL - 1
    anios = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr  = (eq.iloc[-1] / CAPITAL_INICIAL) ** (1 / anios) - 1 if anios > 0 else 0
    dd    = (eq / eq.cummax() - 1).min()
    print(f"\n===== {nombre} =====")
    print(f"  Capital final:     ${eq.iloc[-1]:,.0f}")
    print(f"  Rendimiento total: {rend:+.1%}")
    print(f"  CAGR (anualizado): {cagr:+.1%}")
    print(f"  Drawdown maximo:   {dd:.1%}")
    if trades:
        pnls = [t["pnl"] for t in trades]
        gan  = [p for p in pnls if p > 0]
        per  = [p for p in pnls if p <= 0]
        print(f"  Operaciones:       {len(pnls)}")
        print(f"  Win rate:          {len(gan)/len(pnls):.0%}")
        if gan and per:
            print(f"  Profit factor:     {sum(gan)/abs(sum(per)):.2f}")


# ----------------------------------------------------------------------
# 4. MOTOR GENERICO
# ----------------------------------------------------------------------
def motor(df, col_compra, col_venta, usar_trailing=False, usar_rsi_parcial=False):
    capital        = CAPITAL_INICIAL
    en_pos         = False
    uni            = ent = stop_fijo = atr_ent = maximo = 0.0
    trail_activo   = False
    parcial_tomada = False
    equity, trades = [], []
    fechas         = df.index

    for i in range(len(df) - 1):
        hoy     = df.iloc[i]
        maniana = df.iloc[i + 1]

        if en_pos:
            if hoy["High"] > maximo:
                maximo = hoy["High"]
            if usar_trailing:
                if not trail_activo and maximo >= ent + GANANCIA_ACTIVA * atr_ent:
                    trail_activo = True
                stop_actual = (maximo - ATR_MULT_TRAIL * atr_ent) if trail_activo else stop_fijo
            else:
                stop_actual = stop_fijo

            if usar_rsi_parcial and not parcial_tomada and hoy["RSI"] > RSI_SALIDA and uni > 0:
                mitad  = uni * 0.5
                precio = hoy["Close"] * (1 - SLIPPAGE)
                pnl    = mitad * (precio - ent) - mitad * precio * COMISION
                capital       += pnl
                uni           -= mitad
                parcial_tomada = True
                trades.append({"fecha": fechas[i], "tipo": "RSI_PARCIAL",
                               "entrada": ent, "salida": precio, "pnl": pnl})

            salida = tipo = None
            if hoy["Low"] <= stop_actual:
                salida, tipo = stop_actual * (1 - SLIPPAGE), "STOP"
            elif hoy[col_venta]:
                salida, tipo = maniana["Open"] * (1 - SLIPPAGE), "CRUCE"
            if salida and uni > 0:
                pnl = uni * (salida - ent) - uni * salida * COMISION
                capital += pnl
                trades.append({"fecha": fechas[i], "tipo": tipo,
                               "entrada": ent, "salida": salida, "pnl": pnl})
                en_pos         = False
                trail_activo   = False
                parcial_tomada = False

        if not en_pos and hoy[col_compra]:
            ent        = maniana["Open"] * (1 + SLIPPAGE)
            atr_ent    = hoy["ATR"]
            stop_fijo  = ent - ATR_MULT_STOP * atr_ent
            maximo     = ent
            trail_activo   = False
            parcial_tomada = False
            dist = ATR_MULT_STOP * atr_ent
            uni  = min((capital * RIESGO_POR_TRADE) / dist, capital / ent)
            capital -= uni * ent * COMISION
            en_pos = True

        valor = capital + (uni * (hoy["Close"] - ent) if en_pos else 0)
        equity.append(valor)

    return pd.DataFrame({"equity": equity}, index=fechas[:len(equity)]), trades


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    datos = descargar_datos(TICKER, ANIOS)
    datos = agregar_indicadores(datos)

    eq_v1,  t_v1  = motor(datos, "sma_compra", "sma_venta", False, False)
    eq_v4,  t_v4  = motor(datos, "sma_compra", "sma_venta", True,  True)
    eq_v5,  t_v5  = motor(datos, "ema_compra", "ema_venta", False, False)
    eq_v5b, t_v5b = motor(datos, "ema_compra", "ema_venta", True,  True)

    bh    = CAPITAL_INICIAL * datos["Close"] / datos["Close"].iloc[0]
    eq_bh = pd.DataFrame({"equity": bh.values}, index=datos.index)

    metricas(eq_v1,  t_v1,  f"V1  - SMA {SMA_R}/{SMA_L} + Stop ATR fijo")
    metricas(eq_v4,  t_v4,  f"V4  - SMA {SMA_R}/{SMA_L} + Trailing + RSI parcial")
    metricas(eq_v5,  t_v5,  f"V5  - EMA {EMA_R}/{EMA_L} + Stop ATR fijo")
    metricas(eq_v5b, t_v5b, f"V5b - EMA {EMA_R}/{EMA_L} + Trailing + RSI parcial")
    metricas(eq_bh,  [],    "BUY & HOLD ORO")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(eq_v1.index,  eq_v1["equity"],  label=f"V1  SMA {SMA_R}/{SMA_L} stop ATR",
            linewidth=1.5, linestyle="--", color="steelblue")
    ax.plot(eq_v4.index,  eq_v4["equity"],  label=f"V4  SMA {SMA_R}/{SMA_L} trailing+RSI",
            linewidth=1.5, linestyle=":",  color="tomato")
    ax.plot(eq_v5.index,  eq_v5["equity"],  label=f"V5  EMA {EMA_R}/{EMA_L} stop ATR",
            linewidth=2.5, color="limegreen")
    ax.plot(eq_v5b.index, eq_v5b["equity"], label=f"V5b EMA {EMA_R}/{EMA_L} trailing+RSI",
            linewidth=2.0, color="mediumpurple")
    ax.plot(eq_bh.index,  eq_bh["equity"],  label="Buy & hold oro",
            linewidth=1.5, alpha=0.6, color="orange")
    ax.axhline(CAPITAL_INICIAL, color="gray", linewidth=0.8, alpha=0.4)
    ax.set_title(f"Backtest | {TICKER} - {ANIOS} anios | SMA vs EMA | Stop ATR vs Trailing")
    ax.set_ylabel("Capital (MXN)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("backtest_oro.png", dpi=120)
    print("\nGrafica guardada en backtest_oro.png")
    plt.show()
