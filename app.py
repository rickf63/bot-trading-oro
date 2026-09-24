# -*- coding: utf-8 -*-
"""
Dashboard Web - Bot de Paper Trading Oro
=========================================
Servidor Flask que muestra el estado del bot
en tiempo real desde cualquier dispositivo.

Uso:
  python app.py

Luego abre en el navegador o celular:
  http://localhost:5000
  o desde el celular (misma red WiFi):
  http://<IP-de-tu-PC>:5000

Requisitos:
  pip install flask pandas
"""

import json
import os
from datetime import date
import pandas as pd
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

DIR            = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_EQUITY = os.path.join(DIR, "paper_equity.csv")
ARCHIVO_TRADES = os.path.join(DIR, "paper_trades.csv")
ARCHIVO_ESTADO = os.path.join(DIR, "paper_estado.json")
CAPITAL_INICIAL = 100_000

# ----------------------------------------------------------------------
# HTML TEMPLATE
# ----------------------------------------------------------------------
HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bot Oro — Dashboard</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0f;
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      padding: 16px;
    }
    h1 {
      font-size: 1.3rem;
      color: #00d4aa;
      margin-bottom: 4px;
    }
    .subtitulo {
      font-size: 0.8rem;
      color: #888;
      margin-bottom: 16px;
    }
    .grid-metricas {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metrica {
      background: #1a1a1a;
      border-radius: 10px;
      padding: 12px;
      border: 1px solid #2a2a2a;
    }
    .metrica .label {
      font-size: 0.7rem;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .metrica .valor {
      font-size: 1.3rem;
      font-weight: 700;
      margin-top: 4px;
    }
    .positivo { color: #00d4aa; }
    .negativo { color: #ff4444; }
    .neutro   { color: #ffffff; }
    .card {
      background: #1a1a1a;
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
      border: 1px solid #2a2a2a;
    }
    .card h2 {
      font-size: 0.85rem;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;
    }
    canvas { max-height: 250px; }
    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .badge-verde  { background: #00d4aa22; color: #00d4aa; border: 1px solid #00d4aa44; }
    .badge-rojo   { background: #ff444422; color: #ff4444; border: 1px solid #ff444444; }
    .badge-gris   { background: #88888822; color: #888888; border: 1px solid #88888844; }
    table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    th { color: #888; font-weight: 500; padding: 6px 8px; text-align: left;
         border-bottom: 1px solid #2a2a2a; }
    td { padding: 6px 8px; border-bottom: 1px solid #1f1f1f; }
    .refresh { color: #555; font-size: 0.7rem; text-align: right; margin-top: 8px; }
    @media (max-width: 480px) {
      .metrica .valor { font-size: 1.1rem; }
    }
  </style>
</head>
<body>
  <h1>🥇 Bot de Paper Trading — Oro</h1>
  <p class="subtitulo">GC=F | EMA 10/21 | Stop ATR x1.5 | Actualizado: <span id="ts"></span></p>

  <div class="grid-metricas" id="metricas"></div>

  <div class="card">
    <h2>Equity</h2>
    <canvas id="chartEquity"></canvas>
  </div>

  <div class="card">
    <h2>Drawdown</h2>
    <canvas id="chartDD"></canvas>
  </div>

  <div class="card">
    <h2>Historial de operaciones</h2>
    <div id="tablaOps"></div>
  </div>

  <p class="refresh">Actualiza cada 60 segundos</p>

<script>
let chartEquity = null;
let chartDD     = null;

function fmt(n, dec=1) {
  return n >= 0
    ? '<span class="positivo">+' + n.toFixed(dec) + '%</span>'
    : '<span class="negativo">'  + n.toFixed(dec) + '%</span>';
}

function fmtMXN(n) {
  return '$' + n.toLocaleString('es-MX', {minimumFractionDigits:2, maximumFractionDigits:2});
}

async function cargar() {
  const r = await fetch('/api/datos');
  const d = await r.json();

  document.getElementById('ts').textContent = d.fecha_hoy;

  // --- Metricas ---
  const posColor = d.en_posicion ? 'badge-verde' : 'badge-gris';
  const posLabel = d.en_posicion ? 'EN POSICION' : 'ESPERANDO';
  const rendClass = d.rendimiento >= 0 ? 'positivo' : 'negativo';
  const rendSign  = d.rendimiento >= 0 ? '+' : '';

  document.getElementById('metricas').innerHTML = `
    <div class="metrica">
      <div class="label">Equity</div>
      <div class="valor neutro">${fmtMXN(d.equity)}</div>
    </div>
    <div class="metrica">
      <div class="label">Rendimiento</div>
      <div class="valor ${rendClass}">${rendSign}${d.rendimiento.toFixed(1)}%</div>
    </div>
    <div class="metrica">
      <div class="label">Drawdown max</div>
      <div class="valor negativo">${d.dd_max.toFixed(1)}%</div>
    </div>
    <div class="metrica">
      <div class="label">Operaciones</div>
      <div class="valor neutro">${d.n_ops}</div>
    </div>
    <div class="metrica">
      <div class="label">Win rate</div>
      <div class="valor neutro">${d.win_rate.toFixed(0)}%</div>
    </div>
    <div class="metrica">
      <div class="label">Dias operando</div>
      <div class="valor neutro">${d.dias}</div>
    </div>
    <div class="metrica">
      <div class="label">Estado</div>
      <div class="valor" style="margin-top:6px"><span class="badge ${posColor}">${posLabel}</span></div>
    </div>
  `;

  // --- Grafica equity ---
  const ctx1 = document.getElementById('chartEquity').getContext('2d');
  const lineaBase = new Array(d.fechas.length).fill(100000);
  if (chartEquity) chartEquity.destroy();
  chartEquity = new Chart(ctx1, {
    type: 'line',
    data: {
      labels: d.fechas,
      datasets: [
        {
          label: 'Equity',
          data: d.equity_serie,
          borderColor: '#00d4aa',
          backgroundColor: 'rgba(0,212,170,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          tension: 0.3
        },
        {
          label: 'Capital inicial',
          data: lineaBase,
          borderColor: '#444',
          borderWidth: 1,
          borderDash: [4,4],
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#888', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#666', maxTicksLimit: 6 }, grid: { color: '#1f1f1f' } },
        y: { ticks: { color: '#666', callback: v => '$'+v.toLocaleString() }, grid: { color: '#1f1f1f' } }
      }
    }
  });

  // --- Grafica drawdown ---
  const ctx2 = document.getElementById('chartDD').getContext('2d');
  if (chartDD) chartDD.destroy();
  chartDD = new Chart(ctx2, {
    type: 'line',
    data: {
      labels: d.fechas,
      datasets: [{
        label: 'Drawdown %',
        data: d.dd_serie,
        borderColor: '#ff4444',
        backgroundColor: 'rgba(255,68,68,0.15)',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#888', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#666', maxTicksLimit: 6 }, grid: { color: '#1f1f1f' } },
        y: { ticks: { color: '#666', callback: v => v.toFixed(1)+'%' }, grid: { color: '#1f1f1f' } }
      }
    }
  });

  // --- Tabla operaciones ---
  if (d.trades.length === 0) {
    document.getElementById('tablaOps').innerHTML = '<p style="color:#555;font-size:0.8rem">Sin operaciones cerradas aun.</p>';
  } else {
    let html = '<table><thead><tr><th>Fecha</th><th>Tipo</th><th>Entrada</th><th>Salida</th><th>PnL</th></tr></thead><tbody>';
    d.trades.slice().reverse().forEach(t => {
      const pnl    = parseFloat(t.pnl);
      const color  = pnl >= 0 ? '#00d4aa' : '#ff4444';
      const signo  = pnl >= 0 ? '+' : '';
      const badge  = t.tipo === 'STOP'
        ? '<span class="badge badge-rojo">STOP</span>'
        : '<span class="badge badge-verde">VENTA</span>';
      html += `<tr>
        <td>${t.fecha}</td>
        <td>${badge}</td>
        <td>$${parseFloat(t.entrada).toLocaleString('es-MX',{minimumFractionDigits:2})}</td>
        <td>$${parseFloat(t.salida).toLocaleString('es-MX',{minimumFractionDigits:2})}</td>
        <td style="color:${color};font-weight:600">${signo}$${Math.abs(pnl).toLocaleString('es-MX',{minimumFractionDigits:2})}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('tablaOps').innerHTML = html;
  }
}

cargar();
setInterval(cargar, 60000);
</script>
</body>
</html>
"""

# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/datos")
def datos():
    # Equity
    fechas = equity_serie = dd_serie = []
    dias = 0
    dd_max = rendimiento = 0.0
    equity = CAPITAL_INICIAL

    if os.path.exists(ARCHIVO_EQUITY):
        eq = pd.read_csv(ARCHIVO_EQUITY, parse_dates=["fecha"])
        eq = eq.drop_duplicates("fecha").sort_values("fecha")
        if not eq.empty:
            fechas       = eq["fecha"].dt.strftime("%d/%m").tolist()
            equity_serie = eq["equity_total"].round(2).tolist()
            dd_s         = (eq["equity_total"] / eq["equity_total"].cummax() - 1) * 100
            dd_serie     = dd_s.round(2).tolist()
            dd_max       = dd_s.min()
            equity       = float(eq["equity_total"].iloc[-1])
            dias         = len(eq)
            rendimiento  = (equity / CAPITAL_INICIAL - 1) * 100

    # Trades
    trades = []
    n_ops = win_rate = 0
    if os.path.exists(ARCHIVO_TRADES):
        tr = pd.read_csv(ARCHIVO_TRADES, parse_dates=["fecha"])
        cerradas = tr[tr["tipo"].isin(["STOP", "CRUCE_BAJA"])]
        n_ops    = len(cerradas)
        if n_ops > 0:
            gan      = cerradas[cerradas["pnl"].astype(float) > 0]
            win_rate = len(gan) / n_ops * 100
        trades = cerradas.to_dict("records")
        for t in trades:
            t["fecha"] = pd.Timestamp(t["fecha"]).strftime("%d/%m/%Y")

    # Estado
    en_posicion = False
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO) as f:
            estado = json.load(f)
        en_posicion = estado.get("en_posicion", False)

    return jsonify({
        "fecha_hoy":    str(date.today()),
        "equity":       round(equity, 2),
        "rendimiento":  round(rendimiento, 2),
        "dd_max":       round(dd_max, 2),
        "dias":         dias,
        "n_ops":        n_ops,
        "win_rate":     round(win_rate, 1),
        "en_posicion":  en_posicion,
        "fechas":       fechas,
        "equity_serie": equity_serie,
        "dd_serie":     dd_serie,
        "trades":       trades,
    })


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "127.0.0.1"

    print("=" * 55)
    print("  DASHBOARD WEB — Bot Oro")
    print("=" * 55)
    print(f"\n  Abre en tu PC:     http://localhost:5000")
    print(f"  Abre en tu CEL:    http://{ip}:5000")
    print(f"  (ambos deben estar en la misma red WiFi)")
    print("\n  Ctrl+C para detener el servidor")
    print("=" * 55)

    app.run(host="0.0.0.0", port=5000, debug=False)
