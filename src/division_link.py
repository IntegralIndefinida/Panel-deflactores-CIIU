"""Empalme entre CIIU Rev 3.1 A.C. (base Dic-2006) y Rev 4 A.C. (base Dic-2014).

w[d4, d31] es la participación del origen d31 en el destino d4. Dos variantes:
- conteo (`load_weights`): fracción de vínculos clase-clase de la correlativa oficial.
- valor (`value_weights`): participación en el valor de producción de la EAM de las plantas
  que pasan de d31 (Rev 3, año de referencia) a d4 (Rev 4, año de enlace); ver src/eam_weights.py.
La serie retropolada de cada d4 usa la tasa de crecimiento log mensual ponderada de los d31
vinculados. Con varios años de referencia (columna `anio`) los pesos se interpolan linealmente.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd


def load_pairs(path: Path, skiprows: int = 10) -> pd.DataFrame:
    """Pares (clase vieja, clase Rev 4) de una correlativa DANE (TC-CIIU-*vsCIIU-4AC-2020.xlsx)."""
    d = pd.read_excel(path, header=None, skiprows=skiprows)
    cur, pairs = None, set()
    for _, r in d.iterrows():
        if pd.notna(r[1]) and pd.isna(r[2]):
            cur = None                      # fila de grupo: reinicia
        if pd.notna(r[2]):
            m = re.sub(r'\D', '', str(r[2]).split('.')[0])
            cur = m.zfill(4) if m else None
        if pd.notna(r[6]) and cur:
            c4 = re.sub(r'\D', '', str(r[6]))
            if len(c4) == 4:
                pairs.add((cur, c4))
    return pd.DataFrame(sorted(pairs), columns=['c31', 'c4'])


def load_weights(path: Path, digits: int = 2) -> pd.DataFrame:
    p = load_pairs(path)
    p['d31'], p['d4'] = p['c31'].str[:digits], p['c4'].str[:digits]
    w = p.groupby(['d4', 'd31']).size().rename('n').reset_index()
    w['w'] = w['n'] / w.groupby('d4')['n'].transform('sum')
    return w[['d4', 'd31', 'w']]


def value_weights(links: pd.DataFrame, digits: int) -> pd.DataFrame:
    """links: anio, c3, c4, valor (clase Rev 3 → clase Rev 4). Devuelve anio, d4, d31, w."""
    l = links.assign(d31=links['c3'].str[:digits], d4=links['c4'].str[:digits])
    w = l.groupby(['anio', 'd4', 'd31'], as_index=False)['valor'].sum()
    w = w[w['valor'] > 0]
    w['w'] = w['valor'] / w.groupby(['anio', 'd4'])['valor'].transform('sum')
    return w[['anio', 'd4', 'd31', 'w']]


def weight_path(g: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Pesos por mes (fecha x d31), normalizados. Sin `anio` (o con uno solo) son fijos; con varios,
    se interpolan linealmente entre años de referencia (centrados a mitad de año) y se mantienen
    constantes fuera de ese rango."""
    if 'anio' not in g:
        g = g.assign(anio=0)
    W = g.pivot_table(index='anio', columns='d31', values='w', aggfunc='sum', fill_value=0.0)
    W = W.div(W.sum(axis=1), axis=0)
    if len(W) == 1:
        return pd.DataFrame(np.tile(W.values, (len(dates), 1)), index=dates, columns=W.columns)
    t = dates.year + (dates.month - 0.5) / 12
    x = W.index.to_numpy(dtype=float) + 0.5
    return pd.DataFrame({c: np.interp(t, x, W[c].to_numpy()) for c in W.columns}, index=dates)


def backcast_divisions(old: pd.DataFrame, new: pd.DataFrame, w: pd.DataFrame, overlap: pd.Timestamp) -> pd.DataFrame:
    """old: fecha x origen Rev3.1 (base 2006); new: fecha x destino Rev4; w: d4, d31, w [, anio].
    Devuelve panel Rev4 continuo."""
    dlog = np.log(old).diff()
    out = {}
    for d4, g in w.groupby('d4'):
        if d4 not in new.columns:
            continue
        g = g[g['d31'].isin(old.columns)]
        if g.empty:
            continue
        wt = weight_path(g, dlog.index)
        g_ = dlog[wt.columns]
        # renormaliza los pesos en cada mes sobre los componentes con dato
        growth = (g_ * wt).sum(axis=1, min_count=1) / (g_.notna() * wt).sum(axis=1)
        growth = growth.loc[growth.index <= overlap].fillna(0)
        # índice hacia atrás desde el traslape (valor new en overlap)
        lvl = new.loc[overlap, d4] * np.exp(-growth.iloc[::-1].cumsum().iloc[::-1].shift(-1, fill_value=0))
        # lvl[t] = new[ov] * exp(-sum_{s>t}^{ov} growth[s])
        lvl = lvl[lvl.index < overlap]
        out[d4] = pd.concat([lvl, new[d4].dropna()])
    return pd.DataFrame(out).sort_index()
