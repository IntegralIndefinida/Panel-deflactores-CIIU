#!/usr/bin/env python3
"""Panel mensual 1970–2026 de IPP (Oferta Interna) por sector amplio: AGRO, MIN, MAN, Total.

Empalma por razón en el mes de traslape:
  base 1999 (BanRep) -> base Dic-2006 (DANE) en 2006-12 -> base Dic-2014 (DANE) en 2014-12
y re-basa a promedio de FINAL_BASE_YEAR = 100. Valida el Total contra la serie oficial empalmada.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (FINAL_BASE_YEAR, FILE_ANEXO_2006, FILE_ANEXO_2014,
                        FILE_BANREP_1999, FILE_BANREP_OI_TOTAL)
from src.sources import load_dane_annex, load_banrep_csv_1999, load_banrep_csv_oi_total

RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'data' / 'final'

# código de sección en cada fuente -> sector común
MAP_99 = {'T': 'T', 'AGRO': 'AGRO', 'MIN': 'MIN', 'MAN': 'MAN'}
MAP_06 = {'T': 'T', 'A': 'AGRO', 'C': 'MIN', 'D': 'MAN'}   # Rev 3.1: B=Pesca (se omite)
MAP_14 = {'T': 'T', 'A': 'AGRO', 'B': 'MIN', 'C': 'MAN'}   # Rev 4: A incluye pesca


def wide(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    d = df[df['ciiu_codigo'].isin(mapping)].copy()
    d['sector'] = d['ciiu_codigo'].map(mapping)
    return d.pivot(index='fecha', columns='sector', values='ipp').sort_index()


def link(old: pd.DataFrame, new: pd.DataFrame, month: str) -> pd.DataFrame:
    """Lleva `old` al nivel de `new` usando el mes de traslape; devuelve old(<month) + new(>=month)."""
    t = pd.Timestamp(month)
    factor = new.loc[t] / old.loc[t]
    return pd.concat([old.loc[old.index < t] * factor, new.loc[new.index >= t]])


def main():
    b99 = wide(load_banrep_csv_1999(RAW / FILE_BANREP_1999), MAP_99)
    b06 = wide(load_dane_annex(RAW / FILE_ANEXO_2006), MAP_06)
    b14 = wide(load_dane_annex(RAW / FILE_ANEXO_2014), MAP_14)

    s = link(b99, b06, '2006-12-01')
    s = link(s, b14, '2014-12-01')

    # re-basado: promedio del año base = 100
    base = s.loc[str(FINAL_BASE_YEAR)].mean()
    panel = (s / base * 100).rename_axis('fecha')

    # validación del Total contra la serie oficial empalmada (Dic 2014 = 100)
    official = load_banrep_csv_oi_total(RAW / FILE_BANREP_OI_TOTAL)
    mine = s['T'] / s.loc['2014-12-01', 'T'] * 100
    cmp = pd.concat({'propio': mine, 'oficial': official}, axis=1).dropna()
    cmp['dif_pct'] = (cmp['propio'] / cmp['oficial'] - 1) * 100
    print('Validación Total vs oficial (dif %):')
    print(cmp['dif_pct'].describe().round(3).to_string())
    for y in (1980, 1990, 1999, 2006):
        print(f'  {y}-12: propio={cmp.loc[f"{y}-12-01","propio"]:.3f} oficial={cmp.loc[f"{y}-12-01","oficial"]:.3f}')

    OUT.mkdir(parents=True, exist_ok=True)
    long = panel.reset_index().melt(id_vars='fecha', var_name='sector', value_name='ipp').dropna()
    long.to_csv(OUT / 'ipp_sectores_amplios.csv', index=False)
    cmp.to_csv(OUT / 'validacion_total_vs_oficial.csv')
    print(f'\nPanel: {panel.index.min():%Y-%m} → {panel.index.max():%Y-%m}, {panel.shape[1]} sectores, base {FINAL_BASE_YEAR}=100')
    print(panel.iloc[[0, -1]].round(2).to_string())


if __name__ == '__main__':
    main()
