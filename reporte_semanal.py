# -*- coding: utf-8 -*-
"""
Reporte Semanal - Bot Oro en Alpaca (GLD)
=========================================
Corre los viernes despues del cierre y manda por correo el
desempeno de la semana, leyendo la cuenta paper de Alpaca.

Task Scheduler Windows:
  Programa:   C:/Users/Ricardo/AppData/Local/Programs/Python/Python314/pythonw.exe
  Argumentos: D:/BOTTRADER/reporte_semanal.py
  Hora:       16:10  Solo Viernes

Correo: configura con set-gmail-password.ps1 (se guarda en .env).
"""

import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import bot_alpaca as bot

CAPITAL_INICIAL = 100_000
RSI_PERIODO     = 14


def mercado():
    df = bot.indicadores(bot.velas())
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).rolling(RSI_PERIODO).mean()
    loss  = (-delta.clip(upper=0)).rolling(RSI_PERIODO).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    return df.iloc[-1]


def generar_reporte():
    bot.verificar_config()
    hoy = date.today()
    semana_inicio = hoy - timedelta(days=hoy.weekday())  # lunes de esta semana

    cuenta = bot.alpaca("GET", "/v2/account")
    estado = bot.estado_actual()
    eq     = bot.historial_equity()
    trades = bot.historial_trades()
    ult    = mercado()

    equity_actual = float(cuenta["equity"])
    antes = eq[eq["fecha"] < pd.Timestamp(semana_inicio)]
    equity_ini_semana = float(antes["equity_total"].iloc[-1]) if not antes.empty else CAPITAL_INICIAL
    rend_total  = equity_actual / CAPITAL_INICIAL - 1
    rend_semana = equity_actual / equity_ini_semana - 1
    dd_max = (eq["equity_total"] / eq["equity_total"].cummax() - 1).min() if not eq.empty else 0.0

    cerradas = trades[trades["tipo"] != "COMPRA"]
    semana   = cerradas[cerradas["fecha"] >= pd.Timestamp(semana_inicio)]
    gan = cerradas[cerradas["pnl"] > 0]["pnl"]
    per = cerradas[cerradas["pnl"] <= 0]["pnl"]
    wr  = len(gan) / len(cerradas) if len(cerradas) else 0
    pf  = gan.sum() / abs(per.sum()) if len(gan) and per.sum() != 0 else 0

    tendencia = "ALCISTA 📈" if ult["EMA_R"] > ult["EMA_L"] else "BAJISTA 📉"
    linea = "=" * 45
    cuerpo = f"""
{linea}
  REPORTE SEMANAL — BOT ORO ALPACA ({bot.SIMBOLO})
  Semana del {semana_inicio.strftime('%d/%m/%Y')} al {hoy.strftime('%d/%m/%Y')}
{linea}

📊 RESUMEN DE LA SEMANA
  Rendimiento semanal:  {rend_semana:+.2%}
  PnL esta semana:      ${semana['pnl'].sum():+,.2f}
  Operaciones cerradas: {len(semana)}
"""
    if len(semana):
        cuerpo += "\n  Detalle operaciones:\n"
        for _, t in semana.iterrows():
            emoji = "✅" if t["pnl"] > 0 else "❌"
            cuerpo += (f"    {emoji} {t['tipo']} | {t['unidades']:.0f} acc | Entrada: ${t['entrada']:,.2f} | "
                       f"Salida: ${t['salida']:,.2f} | PnL: ${t['pnl']:+,.2f}\n")
    else:
        cuerpo += "  Sin operaciones cerradas esta semana.\n"

    cuerpo += f"""
{linea}
💰 ESTADO DEL CAPITAL
  Capital inicial:      ${CAPITAL_INICIAL:,.2f}
  Equity actual:        ${equity_actual:,.2f}
  Rendimiento total:    {rend_total:+.2%}
  Drawdown maximo:      {dd_max:.2%}
  Dias con registro:    {len(eq)}

📈 ESTADISTICAS ACUMULADAS
  Operaciones cerradas: {len(cerradas)}
  Win rate:             {wr:.0%}
  Profit factor:        {pf:.2f}

{linea}
🥇 MERCADO — {bot.SIMBOLO}
  Precio cierre:        ${ult['Close']:,.2f}
  EMA {bot.EMA_R}:               ${ult['EMA_R']:,.2f}
  EMA {bot.EMA_L}:               ${ult['EMA_L']:,.2f}
  ATR:                  ${ult['ATR']:,.2f}
  RSI:                  {ult['RSI']:.1f}
  Tendencia:            {tendencia}
  En posicion:          {'SI' if estado['en_posicion'] else 'NO'}
"""
    if estado["en_posicion"]:
        cuerpo += f"""
  Acciones:             {estado['unidades']:.0f}
  Precio entrada:       ${estado['precio_entrada']:,.2f}
  Stop loss:            ${estado['stop']:,.2f}
  PnL no realizado:     ${estado['pnl_no_realizado']:+,.2f}
"""
    cuerpo += f"""
{linea}
Reporte generado automaticamente el {datetime.now().strftime('%d/%m/%Y %H:%M')}
Bot de Paper Trading — github.com/rickf63/bot-trading-oro
{linea}
"""
    print(cuerpo)
    bot.enviar_email(f"📊 Reporte Semanal Bot Oro | {hoy.strftime('%d/%m/%Y')} | {rend_semana:+.1%}", cuerpo)


if __name__ == "__main__":
    if sys.stdout is None:  # lanzado con pythonw (sin ventana)
        sys.stdout = sys.stderr = open(bot.BASE / "alpaca_bot.log", "a", encoding="utf-8", buffering=1)
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # la consola de Windows no muestra emojis
    generar_reporte()
