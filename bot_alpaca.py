# -*- coding: utf-8 -*-
"""
Bot Oro en Alpaca - EMA 10/21 + Stop ATR x1.5 sobre GLD
=========================================================
Misma estrategia que paper_trading.py, pero con ordenes reales en una cuenta
PAPER de Alpaca. Alpaca no opera futuros (GC=F), asi que se usa el ETF GLD,
que sigue al oro (backtest 10 anios: casi identico a GC=F).

Reglas (iguales al backtest de multi_activos.py):
  - Cruce alcista EMA 10 > EMA 21 al cierre  -> compra a la apertura siguiente
  - Stop loss fijo = cierre - 1.5 x ATR(14), orden stop GTC en Alpaca
    (vive en el servidor, se ejecuta aunque la PC este apagada)
  - Cruce bajista EMA 10 < EMA 21 al cierre  -> vende a la apertura siguiente
  - Tamano: arriesgar 1% del equity (distancia al stop), sin apalancamiento

Uso:
  python bot_alpaca.py            Corre el ciclo del dia (despues del cierre)
  python bot_alpaca.py simulacro  Calcula la senal sin enviar ordenes
  python bot_alpaca.py estado     Muestra cuenta, posicion y ordenes abiertas
  python bot_alpaca.py prueba     Orden limite inalcanzable + cancelacion (verifica conexion)

Programador de tareas: lunes a viernes 16:00 hora CDMX (despues del cierre de NY
todo el anio). Credenciales en D:\\BOTTRADER\\.env (usa set-alpaca-keys.ps1).
"""
import csv
import json
import math
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import requests
import truststore
from dotenv import load_dotenv

truststore.inject_into_ssl()  # usa los certificados de Windows

# ----------------------------------------------------------------------
# CONFIGURACION
# ----------------------------------------------------------------------
SIMBOLO          = "GLD"
RIESGO_POR_TRADE = 0.01
EMA_R            = 10
EMA_L            = 21
ATR_PERIODO      = 14
ATR_MULT_STOP    = 1.5
DIAS_HISTORIA    = 400   # calendario; ~270 velas para que las EMAs converjan
SOLO_PAPER       = True

BASE      = Path(__file__).resolve().parent
ESTADO    = BASE / "alpaca_estado.json"
TRADES    = BASE / "alpaca_trades.csv"
EQUITY    = BASE / "alpaca_equity.csv"
BITACORA  = BASE / "alpaca_bitacora.md"

load_dotenv(BASE / ".env")  # no pisa variables ya definidas en el entorno
TRADING_API = os.getenv("ALPACA_BASE_URL", "").rstrip("/")
DATA_API    = "https://data.alpaca.markets/v2"
HDR = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
}


# ----------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------
def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bitacora(texto):
    linea = f"- `{ahora()}` {texto}"
    print(linea)
    with BITACORA.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"stop": None, "fecha_entrada": None, "orden_stop": None}


def guardar_estado(estado):
    ESTADO.write_text(json.dumps(estado, indent=2), encoding="utf-8")


def anexar_csv(ruta, fila):
    nuevo = not ruta.exists()
    with ruta.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fila))
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def enviar_email(asunto, cuerpo):
    user, pwd = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD")
    if not user or not pwd:
        return
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = user, os.getenv("EMAIL_TO") or user, asunto
        msg.set_content(cuerpo)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.send_message(msg)
    except Exception as e:
        print(f"  Error al mandar correo: {e}")


# ----------------------------------------------------------------------
# ALPACA
# ----------------------------------------------------------------------
def alpaca(method, path, **kw):
    r = requests.request(method, TRADING_API + path, headers=HDR, timeout=30, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"Alpaca {method} {path} -> {r.status_code} {r.text}")
    return r.json() if r.text else None


def verificar_config():
    if not HDR["APCA-API-KEY-ID"] or not TRADING_API:
        sys.exit("Faltan credenciales: corre set-alpaca-keys.ps1 para crear D:\\BOTTRADER\\.env")
    if SOLO_PAPER and "paper-api" not in TRADING_API:
        sys.exit("ALTO: SOLO_PAPER=True pero .env apunta a una cuenta real.")


def velas():
    """Velas diarias ajustadas de los ultimos DIAS_HISTORIA dias (feed SIP)."""
    fin = datetime.now(timezone.utc) - timedelta(minutes=16)  # plan gratis: SIP con 15 min de retraso
    params = {"timeframe": "1Day", "adjustment": "all", "feed": "sip", "limit": 10000,
              "start": (fin - timedelta(days=DIAS_HISTORIA)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "end": fin.strftime("%Y-%m-%dT%H:%M:%SZ")}
    r = requests.get(f"{DATA_API}/stocks/{SIMBOLO}/bars", headers=HDR, params=params, timeout=30)
    r.raise_for_status()
    bars = r.json().get("bars") or []
    if not bars:
        raise RuntimeError(f"Alpaca no devolvio velas de {SIMBOLO}")
    df = pd.DataFrame(bars)
    df.index = pd.to_datetime(df["t"]).dt.tz_convert("America/New_York").dt.date
    return df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close"})[
        ["Open", "High", "Low", "Close"]]


def indicadores(df):
    """Mismos calculos que multi_activos.py."""
    df = df.copy()
    df["EMA_R"] = df["Close"].ewm(span=EMA_R, adjust=False).mean()
    df["EMA_L"] = df["Close"].ewm(span=EMA_L, adjust=False).mean()
    df["compra"] = (df["EMA_R"] > df["EMA_L"]) & (df["EMA_R"].shift() <= df["EMA_L"].shift())
    df["venta"]  = (df["EMA_R"] < df["EMA_L"]) & (df["EMA_R"].shift() >= df["EMA_L"].shift())
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(ATR_PERIODO).mean()
    return df.dropna()


def posicion():
    for p in alpaca("GET", "/v2/positions"):
        if p["symbol"] == SIMBOLO:
            return p
    return None


def ordenes_abiertas():
    return alpaca("GET", "/v2/orders", params={"status": "open", "symbols": SIMBOLO})


def cancelar_ordenes():
    for o in ordenes_abiertas():
        alpaca("DELETE", f"/v2/orders/{o['id']}")
    time.sleep(2)


# ----------------------------------------------------------------------
# REVISAR STOPS EJECUTADOS
# ----------------------------------------------------------------------
def revisar_stop(estado, pos):
    """Si el stop se ejecuto (en el servidor) desde la ultima corrida, lo registra."""
    if pos or not estado.get("orden_stop"):
        return
    o = alpaca("GET", f"/v2/orders/{estado['orden_stop']}")
    if o["status"] == "filled":
        precio = float(o["filled_avg_price"])
        bitacora(f"**STOP EJECUTADO**: vendidas {o['filled_qty']} {SIMBOLO} a ${precio:,.2f}")
        anexar_csv(TRADES, {"fecha": o["filled_at"][:10], "tipo": "STOP", "cantidad": o["filled_qty"],
                            "precio": f"{precio:.2f}", "orden": o["id"]})
        enviar_email(f"STOP LOSS Bot Oro Alpaca | {o['filled_at'][:10]}",
                     f"Stop ejecutado: {o['filled_qty']} {SIMBOLO} a ${precio:,.2f}")
    estado.update({"stop": None, "fecha_entrada": None, "orden_stop": None})


# ----------------------------------------------------------------------
# CICLO PRINCIPAL
# ----------------------------------------------------------------------
def ejecutar(simulacro=False):
    verificar_config()
    reloj = alpaca("GET", "/v2/clock")
    if reloj["is_open"] and not simulacro:
        sys.exit("El mercado esta abierto: la vela de hoy no ha cerrado. Corre despues del cierre.")

    estado = cargar_estado()
    cuenta = alpaca("GET", "/v2/account")
    pos = posicion()
    if not simulacro:
        revisar_stop(estado, pos)

    df = indicadores(velas())
    hoy = df.iloc[-1]
    fecha = str(df.index[-1])
    equity = float(cuenta["equity"])

    print("=" * 55)
    print(f"  BOT ORO ALPACA - {SIMBOLO}  |  vela {fecha}")
    print(f"  EMA {EMA_R}/{EMA_L}  |  Stop ATR x{ATR_MULT_STOP}")
    print("=" * 55)
    print(f"  Cierre:  ${hoy['Close']:,.2f}   EMA{EMA_R}: ${hoy['EMA_R']:,.2f}   "
          f"EMA{EMA_L}: ${hoy['EMA_L']:,.2f}   ATR: ${hoy['ATR']:,.2f}")
    print(f"  Equity:  ${equity:,.2f}   Efectivo: ${float(cuenta['cash']):,.2f}")

    pendientes = [o for o in ordenes_abiertas() if o["type"] != "stop"]
    if pendientes:
        bitacora(f"Hay {len(pendientes)} orden(es) de {SIMBOLO} pendientes; no se hace nada hoy.")
        return

    accion = "ESPERAR"
    if pos:
        qty = int(float(pos["qty"]))
        print(f"  Posicion: {qty} {SIMBOLO} a ${float(pos['avg_entry_price']):,.2f}  "
              f"P&L ${float(pos['unrealized_pl']):+,.2f}  stop ${estado.get('stop') or 0:,.2f}")
        if hoy["venta"]:
            accion = "VENTA"
            if not simulacro:
                cancelar_ordenes()
                o = alpaca("DELETE", f"/v2/positions/{SIMBOLO}")
                bitacora(f"**VENTA** cruce bajista: {qty} {SIMBOLO} a mercado en la apertura (orden {o['id']})")
                anexar_csv(TRADES, {"fecha": fecha, "tipo": "VENTA", "cantidad": qty,
                                    "precio": f"{hoy['Close']:.2f} (cierre)", "orden": o["id"]})
                enviar_email(f"VENTA Bot Oro Alpaca | {fecha}",
                             f"Cruce bajista EMA {EMA_R}/{EMA_L}. Se venden {qty} {SIMBOLO} en la apertura.")
                estado.update({"stop": None, "fecha_entrada": None, "orden_stop": None})
        else:
            accion = "MANTENER"
            if not simulacro and not any(o["type"] == "stop" for o in ordenes_abiertas()) and estado.get("stop"):
                o = alpaca("POST", "/v2/orders", json={
                    "symbol": SIMBOLO, "qty": str(qty), "side": "sell", "type": "stop",
                    "stop_price": f"{estado['stop']:.2f}", "time_in_force": "gtc"})
                estado["orden_stop"] = o["id"]
                bitacora(f"Stop repuesto a ${estado['stop']:,.2f} (no habia orden stop abierta)")

    elif hoy["compra"]:
        dist = ATR_MULT_STOP * float(hoy["ATR"])
        stop = round(float(hoy["Close"]) - dist, 2)
        qty = math.floor(min(equity * RIESGO_POR_TRADE / dist,
                             float(cuenta["cash"]) / (float(hoy["Close"]) * 1.02)))
        accion = "COMPRA"
        print(f"  Compra: {qty} {SIMBOLO} (~${qty * hoy['Close']:,.0f}), stop ${stop:,.2f}, "
              f"riesgo ${qty * dist:,.0f}")
        if qty < 1:
            bitacora("Senal de compra pero el tamano calculado es 0 acciones.")
        elif not simulacro:
            # Compra a mercado en la apertura; al llenarse se activa el stop GTC (orden OTO)
            o = alpaca("POST", "/v2/orders", json={
                "symbol": SIMBOLO, "qty": str(qty), "side": "buy", "type": "market",
                "time_in_force": "gtc", "order_class": "oto",
                "stop_loss": {"stop_price": f"{stop:.2f}"}})
            stop_id = next((l["id"] for l in o.get("legs") or []), None)
            estado.update({"stop": stop, "fecha_entrada": fecha, "orden_stop": stop_id})
            bitacora(f"**COMPRA** cruce alcista: {qty} {SIMBOLO} en la apertura, stop ${stop:,.2f} "
                     f"(riesgo ${qty * dist:,.0f} = {qty * dist / equity:.1%})")
            anexar_csv(TRADES, {"fecha": fecha, "tipo": "COMPRA", "cantidad": qty,
                                "precio": f"{hoy['Close']:.2f} (cierre)", "orden": o["id"]})
            enviar_email(f"COMPRA Bot Oro Alpaca | {fecha}",
                         f"Cruce alcista EMA {EMA_R}/{EMA_L}. Se compran {qty} {SIMBOLO} en la apertura.\n"
                         f"Stop: ${stop:,.2f}\nRiesgo: ${qty * dist:,.0f}")

    print(f"\n  Accion: {accion}{'  (simulacro, sin ordenes)' if simulacro else ''}")
    if not simulacro:
        guardar_estado(estado)
        if accion in ("ESPERAR", "MANTENER"):
            bitacora(f"Vela {fecha}: {accion} (cierre ${hoy['Close']:,.2f}, equity ${equity:,.2f})")
        if not EQUITY.exists() or fecha not in EQUITY.read_text(encoding="utf-8"):
            anexar_csv(EQUITY, {"fecha": fecha, "equity": f"{equity:.2f}",
                                "efectivo": cuenta["cash"], "acciones": pos["qty"] if pos else 0})


def ver_estado():
    verificar_config()
    c = alpaca("GET", "/v2/account")
    print(f"Cuenta {c['account_number']} ({TRADING_API})")
    print(f"  Equity ${float(c['equity']):,.2f}  Efectivo ${float(c['cash']):,.2f}")
    pos = posicion()
    print(f"  Posicion {SIMBOLO}: {pos['qty'] + ' a $' + pos['avg_entry_price'] if pos else 'ninguna'}")
    for o in ordenes_abiertas():
        print(f"  Orden abierta: {o['side']} {o['qty']} {o['type']} stop={o.get('stop_price')} {o['status']}")
    print(f"  Estado local: {cargar_estado()}")


def prueba():
    """Verifica conexion y permisos sin arriesgar nada: orden limite a $1 y se cancela."""
    verificar_config()
    o = alpaca("POST", "/v2/orders", json={"symbol": SIMBOLO, "qty": "1", "side": "buy",
                                           "type": "limit", "limit_price": "1.00", "time_in_force": "day"})
    bitacora(f"PRUEBA: orden limite 1 {SIMBOLO} a $1 -> {o['status']}")
    alpaca("DELETE", f"/v2/orders/{o['id']}")
    time.sleep(2)
    bitacora(f"PRUEBA: orden cancelada -> {alpaca('GET', '/v2/orders/' + o['id'])['status']}")


if __name__ == "__main__":
    if sys.stdout is None:  # lanzado con pythonw (sin ventana)
        sys.stdout = sys.stderr = open(BASE / "alpaca_bot.log", "a", encoding="utf-8", buffering=1)
    modo = sys.argv[1] if len(sys.argv) > 1 else "correr"
    {"correr": ejecutar, "simulacro": lambda: ejecutar(simulacro=True),
     "estado": ver_estado, "prueba": prueba}[modo]()
