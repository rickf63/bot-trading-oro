# -*- coding: utf-8 -*-
"""
Paper Trading - EMA 10/21 + Stop ATR x1.5 sobre ORO (GC=F)
============================================================
Parametros optimizados con 10 anios de datos historicos.
Corre una vez al dia al cierre del mercado (4:05pm hora Mexico).
Manda correo solo cuando hay senal importante.

Task Scheduler Windows:
  Programa:   C:/Users/Ricardo/AppData/Local/Programs/Python/Python310/python.exe
  Argumentos: D:/BOTTRADER/paper_trading.py
  Hora:       16:05  Lunes a Viernes

Requisitos:
  pip install yfinance pandas numpy
"""

import json
import csv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
import yfinance as yf
import pandas as pd
import numpy as np

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
TICKER           = "GC=F"
CAPITAL_INICIAL  = 100_000
RIESGO_POR_TRADE = 0.01
EMA_R            = 10
EMA_L            = 21
ATR_PERIODO      = 14
ATR_MULT_STOP    = 1.5
RSI_PERIODO      = 14
COMISION         = 0.0005
SLIPPAGE         = 0.0003
VELAS_HISTORIA   = 60

EMAIL_ORIGEN  = "ricomonsalvedelavega@gmail.com"
EMAIL_DESTINO = "ricomonsalvedelavega@gmail.com"
EMAIL_PASS    = "ckmwjbmrwjkpsoqq"

DIR             = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_ESTADO  = os.path.join(DIR, "paper_estado.json")
ARCHIVO_TRADES  = os.path.join(DIR, "paper_trades.csv")
ARCHIVO_EQUITY  = os.path.join(DIR, "paper_equity.csv")


# ----------------------------------------------------------------------
# CORREO
# ----------------------------------------------------------------------
def mandar_correo(asunto, cuerpo):
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_ORIGEN
        msg["To"]      = EMAIL_DESTINO
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ORIGEN, EMAIL_PASS)
            server.sendmail(EMAIL_ORIGEN, EMAIL_DESTINO, msg.as_string())
        print(f"  Correo enviado: {asunto}")
    except Exception as e:
        print(f"  Error al mandar correo: {e}")


# ----------------------------------------------------------------------
# ESTADO
# ----------------------------------------------------------------------
def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, "r") as f:
            return json.load(f)
    return {
        "capital": CAPITAL_INICIAL, "en_posicion": False,
        "unidades": 0.0, "precio_entrada": 0.0,
        "stop": 0.0, "atr_entrada": 0.0,
        "fecha_entrada": None, "inicio": str(date.today())
    }


def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w") as f:
        json.dump(estado, f, indent=2)


# ----------------------------------------------------------------------
# REGISTROS
# ----------------------------------------------------------------------
def registrar_trade(fecha, tipo, entrada, salida, unidades, pnl, capital):
    nuevo = not os.path.exists(ARCHIVO_TRADES)
    with open(ARCHIVO_TRADES, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "tipo", "entrada", "salida", "unidades", "pnl", "capital"])
        w.writerow([fecha, tipo, f"{entrada:.2f}", f"{salida:.2f}",
                    f"{unidades:.4f}", f"{pnl:.2f}", f"{capital:.2f}"])


def registrar_equity(fecha, capital, en_posicion, precio_actual, unidades, precio_entrada):
    # Evitar duplicados del mismo dia
    if os.path.exists(ARCHIVO_EQUITY):
        df = pd.read_csv(ARCHIVO_EQUITY)
        if fecha in df["fecha"].values:
            return
    valor = capital + (unidades * (precio_actual - precio_entrada) if en_posicion else 0)
    nuevo = not os.path.exists(ARCHIVO_EQUITY)
    with open(ARCHIVO_EQUITY, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "capital_cash", "equity_total", "en_posicion"])
        w.writerow([fecha, f"{capital:.2f}", f"{valor:.2f}", int(en_posicion)])


# ----------------------------------------------------------------------
# DATOS
# ----------------------------------------------------------------------
def obtener_datos():
    df = yf.download(TICKER, period=f"{VELAS_HISTORIA}d", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError("No se pudieron descargar datos.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df["EMA_R"] = df["Close"].ewm(span=EMA_R, adjust=False).mean()
    df["EMA_L"] = df["Close"].ewm(span=EMA_L, adjust=False).mean()
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
# LOGICA PRINCIPAL
# ----------------------------------------------------------------------
def ejecutar():
    hoy_str = str(date.today())
    print("=" * 55)
    print(f"  PAPER TRADING - ORO (GC=F)  |  {hoy_str}")
    print(f"  EMA {EMA_R}/{EMA_L}  |  Stop ATR x{ATR_MULT_STOP}")
    print("=" * 55)

    estado      = cargar_estado()
    capital     = estado["capital"]
    en_posicion = estado["en_posicion"]
    unidades    = estado["unidades"]
    ent         = estado["precio_entrada"]
    stop        = estado["stop"]
    atr_ent     = estado["atr_entrada"]

    try:
        df = obtener_datos()
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    if len(df) < 3:
        print("  Sin suficientes velas.")
        return

    ayer          = df.iloc[-2]
    hoy           = df.iloc[-1]
    precio_actual = float(hoy["Close"])
    fecha_vela    = str(df.index[-1].date())

    print(f"\n  Precio cierre:  ${precio_actual:,.2f}")
    print(f"  EMA {EMA_R}:         ${float(hoy['EMA_R']):,.2f}")
    print(f"  EMA {EMA_L}:         ${float(hoy['EMA_L']):,.2f}")
    print(f"  ATR:            ${float(hoy['ATR']):,.2f}")
    print(f"  RSI:            {float(hoy['RSI']):.1f}")
    print(f"  Capital cash:   ${capital:,.2f}")

    accion = "ESPERAR"

    if en_posicion:
        valor_pos = unidades * (precio_actual - ent)
        print(f"\n  POSICION ABIERTA")
        print(f"  Entrada:        ${ent:,.2f}")
        print(f"  Stop actual:    ${stop:,.2f}")
        print(f"  Unidades:       {unidades:.4f}")
        print(f"  PnL no realiz.: ${valor_pos:+,.2f}")

        if float(ayer["Low"]) <= stop:
            precio_salida = stop * (1 - SLIPPAGE)
            pnl = unidades * (precio_salida - ent) - unidades * precio_salida * COMISION
            capital += pnl
            registrar_trade(fecha_vela, "STOP", ent, precio_salida, unidades, pnl, capital)
            print(f"\n  *** STOP LOSS ACTIVADO ***")
            print(f"  Salida: ${precio_salida:,.2f}  |  PnL: ${pnl:+,.2f}")
            mandar_correo(
                f"STOP LOSS Bot Oro | {fecha_vela}",
                f"Stop loss activado.\n\nEntrada: ${ent:,.2f}\nSalida: ${precio_salida:,.2f}\n"
                f"PnL: ${pnl:+,.2f}\nCapital: ${capital:,.2f}\n"
                f"Rendimiento: {(capital/CAPITAL_INICIAL - 1):+.1%}"
            )
            en_posicion = False
            unidades = ent = stop = atr_ent = 0.0
            accion = "STOP"

        elif (float(ayer["EMA_R"]) < float(ayer["EMA_L"]) and
              float(df.iloc[-3]["EMA_R"]) >= float(df.iloc[-3]["EMA_L"])):
            precio_salida = precio_actual * (1 - SLIPPAGE)
            pnl = unidades * (precio_salida - ent) - unidades * precio_salida * COMISION
            capital += pnl
            registrar_trade(fecha_vela, "CRUCE_BAJA", ent, precio_salida, unidades, pnl, capital)
            print(f"\n  *** SENAL DE VENTA ***")
            print(f"  Salida: ${precio_salida:,.2f}  |  PnL: ${pnl:+,.2f}")
            mandar_correo(
                f"VENTA Bot Oro | {fecha_vela}",
                f"Senal de venta por cruce bajista EMA {EMA_R}/{EMA_L}.\n\n"
                f"Entrada: ${ent:,.2f}\nSalida: ${precio_salida:,.2f}\n"
                f"PnL: ${pnl:+,.2f}\nCapital: ${capital:,.2f}\n"
                f"Rendimiento: {(capital/CAPITAL_INICIAL - 1):+.1%}"
            )
            en_posicion = False
            unidades = ent = stop = atr_ent = 0.0
            accion = "VENTA"
        else:
            print(f"\n  Sin senal de salida. Posicion activa.")
            accion = "MANTENER"

    if not en_posicion:
        cruce_alcista = (float(ayer["EMA_R"]) > float(ayer["EMA_L"]) and
                         float(df.iloc[-3]["EMA_R"]) <= float(df.iloc[-3]["EMA_L"]))
        if cruce_alcista:
            ent      = precio_actual * (1 + SLIPPAGE)
            atr_ent  = float(hoy["ATR"])
            stop     = ent - ATR_MULT_STOP * atr_ent
            dist     = ATR_MULT_STOP * atr_ent
            unidades = min((capital * RIESGO_POR_TRADE) / dist, capital / ent)
            capital -= unidades * ent * COMISION
            en_posicion = True
            registrar_trade(fecha_vela, "COMPRA", ent, 0, unidades, 0, capital)
            print(f"\n  *** SENAL DE COMPRA ***")
            print(f"  Entrada: ${ent:,.2f}  |  Stop: ${stop:,.2f}  |  Unidades: {unidades:.4f}")
            mandar_correo(
                f"COMPRA Bot Oro | {fecha_vela}",
                f"Senal de compra por cruce alcista EMA {EMA_R}/{EMA_L}.\n\n"
                f"Entrada: ${ent:,.2f}\nStop: ${stop:,.2f}\n"
                f"Riesgo: ${capital * RIESGO_POR_TRADE:,.2f} (1%)\n"
                f"Unidades: {unidades:.4f}\nCapital: ${capital:,.2f}"
            )
            accion = "COMPRA"
        else:
            print(f"\n  Sin senal de entrada.")

    registrar_equity(fecha_vela, capital, en_posicion, precio_actual, unidades, ent)
    estado.update({"capital": capital, "en_posicion": en_posicion,
                   "unidades": unidades, "precio_entrada": ent,
                   "stop": stop, "atr_entrada": atr_ent})
    guardar_estado(estado)

    equity_total = capital + (unidades * (precio_actual - ent) if en_posicion else 0)
    rendimiento  = equity_total / CAPITAL_INICIAL - 1
    print(f"\n  RESUMEN DEL DIA")
    print(f"  Accion:       {accion}")
    print(f"  Equity total: ${equity_total:,.2f}")
    print(f"  Rendimiento:  {rendimiento:+.1%}")
    print(f"  Estado:       {ARCHIVO_ESTADO}")
    print("=" * 55)


if __name__ == "__main__":
    ejecutar()
