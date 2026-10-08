"""Empalme a nivel división entre CIIU Rev 3.1 A.C. (base Dic-2006) y Rev 4 A.C. (base Dic-2014).

La correlativa oficial es a nivel clase y sin ponderaciones. Se agrega a divisiones contando
los vínculos clase-clase: w[d4, d31] = vínculos(d31->d4) / vínculos totales hacia d4.
La serie retropolada de cada división Rev 4 usa la tasa de crecimiento log mensual
ponderada de las divisiones Rev 3.1 vinculadas (aproximación documentada).
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd


def load_weights(path: Path, digits: int = 2) -> pd.DataFrame:
    d = pd.read_excel(path, header=None, skiprows=10)
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
    p = pd.DataFrame(sorted(pairs), columns=['c31', 'c4'])
    p['d31'], p['d4'] = p['c31'].str[:digits], p['c4'].str[:digits]
    w = p.groupby(['d4', 'd31']).size().rename('n').reset_index()
    w['w'] = w['n'] / w.groupby('d4')['n'].transform('sum')
    return w


def backcast_divisions(old: pd.DataFrame, new: pd.DataFrame, w: pd.DataFrame, overlap: pd.Timestamp) -> pd.DataFrame:
    """old: fecha x división Rev3.1 (base 2006); new: fecha x división Rev4. Devuelve panel Rev4 continuo."""
    dlog = np.log(old).diff()
    out = {}
    for d4, g in w.groupby('d4'):
        if d4 not in new.columns:
            continue
        g = g[g['d31'].isin(old.columns)]
        if g.empty:
            continue
        wt = g.set_index('d31')['w']
        wt = wt / wt.sum()
        g_ = dlog[wt.index]
        # renormaliza los pesos en cada mes sobre los componentes con dato
        growth = g_.mul(wt, axis=1).sum(axis=1, min_count=1) / g_.notna().mul(wt, axis=1).sum(axis=1)
        growth = growth.loc[growth.index <= overlap].fillna(0)
        # índice hacia atrás desde el traslape (valor new en overlap)
        lvl = new.loc[overlap, d4] * np.exp(-growth.iloc[::-1].cumsum().iloc[::-1].shift(-1, fill_value=0))
        # lvl[t] = new[ov] * exp(-sum_{s>t}^{ov} growth[s])
        lvl = lvl[lvl.index < overlap]
        out[d4] = pd.concat([lvl, new[d4].dropna()])
    return pd.DataFrame(out).sort_index()

