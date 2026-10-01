# -*- coding: utf-8 -*-
"""
Limpieza de carpeta BOTTRADER
==============================
Muestra que va a borrar antes de hacerlo.
Corre desde D:\BOTTRADER con:
  python limpiar_bottrader.py
"""

import os
import shutil

DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------
# Archivos que SI conservamos
# ----------------------------------------------------------------------
CONSERVAR = {
    "backtest_oro.py",
    "dashboard.py",
    "optimizador.py",
    "paper_trading.py",
    "paper_equity.csv",
    "paper_estado.json",
    "optimizador_ranking.csv",
    "limpiar_bottrader.py",   # este mismo script
}

# ----------------------------------------------------------------------
# Escanear carpeta
# ----------------------------------------------------------------------
print("=" * 55)
print("  LIMPIEZA BOTTRADER")
print("=" * 55)

borrar_archivos = []
borrar_carpetas = []

for item in os.listdir(DIR):
    ruta = os.path.join(DIR, item)

    if item in CONSERVAR:
        continue  # lo saltamos

    if os.path.isfile(ruta):
        borrar_archivos.append(item)
    elif os.path.isdir(ruta):
        borrar_carpetas.append(item)

# ----------------------------------------------------------------------
# Mostrar que se va a borrar
# ----------------------------------------------------------------------
if not borrar_archivos and not borrar_carpetas:
    print("\n  Todo esta limpio, no hay nada que borrar.")
else:
    print("\n  Archivos a BORRAR:")
    for f in sorted(borrar_archivos):
        print(f"    - {f}")

    if borrar_carpetas:
        print("\n  Carpetas a BORRAR (con todo su contenido):")
        for c in sorted(borrar_carpetas):
            print(f"    - {c}/")

    print("\n  Archivos a CONSERVAR:")
    for f in sorted(CONSERVAR):
        ruta = os.path.join(DIR, f)
        if os.path.exists(ruta):
            print(f"    + {f}")

    # ----------------------------------------------------------------------
    # Pedir confirmacion
    # ----------------------------------------------------------------------
    print()
    respuesta = input("  Confirmas el borrado? (s/n): ").strip().lower()

    if respuesta == "s":
        for f in borrar_archivos:
            os.remove(os.path.join(DIR, f))
            print(f"  Borrado: {f}")
        for c in borrar_carpetas:
            shutil.rmtree(os.path.join(DIR, c))
            print(f"  Borrada carpeta: {c}/")
        print("\n  Limpieza completada!")
    else:
        print("\n  Cancelado, no se borro nada.")

print("=" * 55)
