# -*- coding: utf-8 -*-
"""
Reporte Semanal - Bot de Paper Trading Oro
==========================================
Corre los viernes automaticamente y manda un resumen
por correo del desempeno de la semana.

Task Scheduler Windows:
  Programa:   C:/Users/Ricardo/AppData/Local/Programs/Python/Python314/python.exe
  Argumentos: D:/BOTTRADER/reporte_semanal.py
  Hora:       16:10  Solo Viernes

Requisitos:
  pip install yfinance pandas numpy
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
TICKER           = "GC=F"
CAPITAL_INICIAL  = 100_000
EMA_R            = 10
EMA_L            = 21
ATR_PERIODO      = 14
RSI_PERIODO      = 14
VELAS_HISTORIA   = 60

EMAIL_ORIGEN  = "ricomonsalvedelavega@gmail.com"
EMAIL_DESTINO = "ricomonsalvedelavega@gmail.com"
EMAIL_PASS    = "ckmwjbmrwjkpsoqq"

DIR            = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_ESTADO = os.path.join(DIR, "paper_estado.json")
ARCHIVO_TRADES = os.path.join(DIR, "paper_trades.csv")
ARCHIVO_EQUITY = os.path.join(DIR, "paper_equity.csv")


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
        print(f"  Reporte enviado a {EMAIL_DESTINO}")
    except Exception as e:
        print(f"  Error al mandar correo: {e}")


# ----------------------------------------------------------------------
# DATOS DE MERCADO
# ----------------------------------------------------------------------
def obtener_mercado():
    df = yf.download(TICKER, period=f"{VELAS_HISTORIA}d", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        return None
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
# REPORTE
# ----------------------------------------------------------------------
def generar_reporte():
    hoy = date.today()
    semana_inicio = hoy - timedelta(days=hoy.weekday())  # lunes de esta semana

    print("=" * 55)
    print(f"  REPORTE SEMANAL - {hoy}")
    print("=" * 55)

    # --- Estado actual ---
    estado = {}
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f:
            estado = json.load(f)

    capital     = estado.get("capital", CAPITAL_INICIAL)
    en_posicion = estado.get("en_posicion", False)
    ent         = estado.get("precio_entrada", 0.0)
    stop        = estado.get("stop", 0.0)
    fecha_inicio = estado.get("inicio", str(hoy))

    # --- Equity historica ---
    dias_operando = 0
    equity_ini_semana = CAPITAL_INICIAL
    if os.path.exists(ARCHIVO_EQUITY):
        eq = pd.read_csv(ARCHIVO_EQUITY, parse_dates=["fecha"])
        eq = eq.drop_duplicates("fecha").sort_values("fecha")
        dias_operando = len(eq)
        # Equity al inicio de esta semana
        eq_semana = eq[eq["fecha"] >= pd.Timestamp(semana_inicio)]
        if not eq_semana.empty:
            equity_ini_semana = float(eq_semana.iloc[0]["equity_total"])

    # --- Operaciones de la semana ---
    trades_semana = []
    trades_total  = []
    if os.path.exists(ARCHIVO_TRADES):
        tr = pd.read_csv(ARCHIVO_TRADES, parse_dates=["fecha"])
        tr = tr[tr["tipo"] != "COMPRA"]
        trades_total  = tr.to_dict("records")
        tr_semana = tr[tr["fecha"] >= pd.Timestamp(semana_inicio)]
        trades_semana = tr_semana.to_dict("records")

    # --- Mercado actual ---
    df = obtener_mercado()
    precio_actual = 0.0
    ema_r = ema_l = rsi = atr = 0.0
    tendencia = "Sin datos"
    if df is not None and not df.empty:
        ult = df.iloc[-1]
        precio_actual = float(ult["Close"])
        ema_r  = float(ult["EMA_R"])
        ema_l  = float(ult["EMA_L"])
        rsi    = float(ult["RSI"])
        atr    = float(ult["ATR"])
        tendencia = "ALCISTA 📈" if ema_r > ema_l else "BAJISTA 📉"

    # --- Calcular metricas ---
    equity_actual = capital
    if en_posicion and precio_actual > 0:
        unidades = estado.get("unidades", 0.0)
        equity_actual = capital + unidades * (precio_actual - ent)

    rend_total   = equity_actual / CAPITAL_INICIAL - 1
    rend_semana  = equity_actual / equity_ini_semana - 1 if equity_ini_semana > 0 else 0

    pnl_semana = sum(float(t["pnl"]) for t in trades_semana)
    n_ops_total = len(trades_total)
    n_ops_semana = len(trades_semana)

    gan_total = [float(t["pnl"]) for t in trades_total if float(t["pnl"]) > 0]
    per_total = [float(t["pnl"]) for t in trades_total if float(t["pnl"]) <= 0]
    wr = len(gan_total) / n_ops_total if n_ops_total > 0 else 0
    pf = sum(gan_total) / abs(sum(per_total)) if per_total and gan_total else 0

    # --- Armar correo ---
    linea = "=" * 45
    cuerpo = f"""
{linea}
  REPORTE SEMANAL — BOT ORO (GC=F)
  Semana del {semana_inicio.strftime('%d/%m/%Y')} al {hoy.strftime('%d/%m/%Y')}
{linea}

📊 RESUMEN DE LA SEMANA
  Rendimiento semanal:  {rend_semana:+.2%}
  PnL esta semana:      ${pnl_semana:+,.2f}
  Operaciones cerradas: {n_ops_semana}
"""

    if trades_semana:
        cuerpo += "\n  Detalle operaciones:\n"
        for t in trades_semana:
            emoji = "✅" if float(t["pnl"]) > 0 else "❌"
            cuerpo += f"    {emoji} {t['tipo']} | Entrada: ${float(t['entrada']):,.2f} | Salida: ${float(t['salida']):,.2f} | PnL: ${float(t['pnl']):+,.2f}\n"
    else:
        cuerpo += "  Sin operaciones cerradas esta semana.\n"

    cuerpo += f"""
{linea}
💰 ESTADO DEL CAPITAL
  Capital inicial:      ${CAPITAL_INICIAL:,.2f}
  Equity actual:        ${equity_actual:,.2f}
  Rendimiento total:    {rend_total:+.2%}
  Dias operando:        {dias_operando}

📈 ESTADISTICAS ACUMULADAS
  Operaciones totales:  {n_ops_total}
  Win rate:             {wr:.0%}
  Profit factor:        {pf:.2f}

{linea}
🥇 MERCADO — ORO (GC=F)
  Precio actual:        ${precio_actual:,.2f}
  EMA {EMA_R}:               ${ema_r:,.2f}
  EMA {EMA_L}:               ${ema_l:,.2f}
  ATR:                  ${atr:,.2f}
  RSI:                  {rsi:.1f}
  Tendencia:            {tendencia}
  En posicion:          {'SI' if en_posicion else 'NO'}
"""

    if en_posicion:
        unidades = estado.get("unidades", 0.0)
        pnl_no_real = unidades * (precio_actual - ent) if precio_actual > 0 else 0
        cuerpo += f"""
  Precio entrada:       ${ent:,.2f}
  Stop loss:            ${stop:,.2f}
  PnL no realizado:     ${pnl_no_real:+,.2f}
"""

    cuerpo += f"""
{linea}
Reporte generado automaticamente el {hoy.strftime('%d/%m/%Y %H:%M')}
Bot de Paper Trading — github.com/rickf63/bot-trading-oro
{linea}
"""

    print(cuerpo)
    mandar_correo(
        f"📊 Reporte Semanal Bot Oro | {hoy.strftime('%d/%m/%Y')} | {rend_semana:+.1%}",
        cuerpo
    )


if __name__ == "__main__":
    generar_reporte()
