# 🥇 Bot de Paper Trading — Oro (GC=F)

Sistema completo de paper trading para futuros de oro, construido en Python. Incluye backtesting histórico, optimización automática de parámetros, ejecución diaria automatizada y notificaciones por correo.

---

## 📌 ¿Qué hace?

- **Backtest** con 10 años de datos históricos del oro (GC=F) comparando múltiples versiones de estrategia
- **Optimizador** que prueba 144 combinaciones de parámetros automáticamente y genera un ranking
- **Paper trading** que corre diariamente al cierre del mercado, registra operaciones y capital
- **Dashboard** con gráfica de equity, drawdown y métricas en tema oscuro
- **Notificaciones por correo** automáticas cuando hay señal de compra, venta o stop loss

---

## 📈 Estrategia

**EMA 10/21 + Stop ATR x1.5** — parámetros encontrados con el optimizador sobre 10 años de datos reales.

| Regla | Detalle |
|---|---|
| Entrada | Cruce alcista EMA 10 sobre EMA 21 |
| Salida | Cruce bajista EMA 10 bajo EMA 21 |
| Stop loss | 1.5x ATR(14) por debajo del precio de entrada |
| Riesgo por trade | 1% del capital |
| Comisiones | 0.05% por lado |

### Resultados del backtest (10 años, 2016–2026)

| Estrategia | Rendimiento | CAGR | Drawdown máx |
|---|---|---|---|
| **EMA 10/21 + ATR x1.5** | **+102.8%** | **+7.4%** | -10.0% |
| EMA 9/21 + ATR x2.0 | +55.0% | +4.6% | -9.8% |
| SMA 20/50 + ATR x2.0 | +39.6% | +3.5% | -13.0% |
| Buy & Hold oro | +202.7% | +12.0% | -25.0% |

---

## 🗂 Archivos

| Archivo | Descripción |
|---|---|
| `backtest_oro.py` | Compara versiones V1–V5 de la estrategia con datos históricos |
| `optimizador.py` | Prueba 144 combinaciones EMA + ATR y genera ranking con heatmap |
| `paper_trading.py` | Bot que corre diariamente, registra operaciones y manda correos |
| `dashboard.py` | Gráfica de equity, drawdown y métricas en tema oscuro |

---

## ⚙️ Instalación

```bash
# Clonar el repositorio
git clone https://github.com/rickf63/bot-trading-oro.git
cd bot-trading-oro

# Instalar dependencias
pip install yfinance pandas numpy matplotlib
```

---

## 🚀 Uso

### Correr el backtest
```bash
python backtest_oro.py
```

### Correr el optimizador (prueba 144 combinaciones)
```bash
python optimizador.py
```

### Correr el paper trading una vez
```bash
python paper_trading.py
```

### Ver el dashboard
```bash
python dashboard.py
```

---

## ⏰ Automatización (Windows Task Scheduler)

Para que el bot corra solo cada día al cierre del mercado:

- **Programa:** `python.exe`
- **Argumentos:** `D:\ruta\paper_trading.py`
- **Horario:** 4:05 PM, lunes a viernes

---

## 📬 Notificaciones

El bot manda correo automático **solo cuando hay señal:**

- 🟢 **COMPRA** — cruce alcista detectado (precio de entrada, stop, riesgo)
- 🟡 **VENTA** — cruce bajista (PnL de la operación)
- 🔴 **STOP LOSS** — stop activado (pérdida registrada)

Días sin señal no genera correo.

---

## 🛠 Stack

- Python 3.13+
- yfinance, pandas, numpy, matplotlib
- smtplib (notificaciones Gmail)
- Windows Task Scheduler (automatización)

---

## 📄 Licencia

MIT — libre para usar y modificar.
