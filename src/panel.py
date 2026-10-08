"""Construcción del panel IPP por división (2 dígitos) o grupo (3 dígitos) CIIU Rev 4, 2006-12 → presente."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (COL_DATE, COL_CIIU, COL_CIIU_DESC, COL_IPP, COL_BASE, COL_CIIU_REV,
                        FILE_ANEXO_2006, FILE_ANEXO_2014, FILE_CROSSWALK_31_4, FILE_BANREP_OI_TOTAL)
from src.sources import load_dane_annex, load_banrep_csv_oi_total
from src.division_link import load_weights, backcast_divisions

logger = logging.getLogger(__name__)

LEVEL = {2: 'division', 3: 'grupo'}
OVERLAP = pd.Timestamp('2014-12-01')
CW_FILE = FILE_CROSSWALK_31_4
MIN_COVERAGE = 0.5  # si <50% del peso del crosswalk cae en grupos con dato, se usa la división


def _wide(df: pd.DataFrame, level: str) -> pd.DataFrame:
    d = df[df['nivel'] == level]
    return d.pivot(index='fecha', columns='ciiu_codigo', values='ipp').sort_index()


def build_panel(raw: Path, crosswalks: Path, digits: int = 3, rebase_year: int = 2018):
    """Devuelve (panel_largo, descripciones, info). Base `rebase_year` = 100 (promedio anual)."""
    if digits not in LEVEL:
        raise ValueError('digits debe ser 2 o 3')
    a06 = load_dane_annex(raw / FILE_ANEXO_2006)
    a14 = load_dane_annex(raw / FILE_ANEXO_2014)
    old, new = _wide(a06, LEVEL[digits]), _wide(a14, LEVEL[digits])
    w = load_weights(crosswalks / CW_FILE, digits)
    info = {'n_old': old.shape[1], 'n_new': new.shape[1]}

    fallback = []
    if digits == 3:
        # respaldo: grupos Rev4 sin contraparte con dato se retropolan con la división padre
        old = pd.concat([old, _wide(a06, 'division')], axis=1)
        wdiv = load_weights(crosswalks / CW_FILE, 2)
        w = w[w['d31'].isin(old.columns)].copy()
        w['cov'] = w.groupby('d4')['w'].transform('sum')   # peso total que cae en grupos con dato
        w = w.assign(w=lambda x: x['w'] / x['cov'])
        for g in new.columns:
            cov = w.loc[w['d4'] == g, 'cov'].max() if (w['d4'] == g).any() else 0.0
            if cov < MIN_COVERAGE:
                rows = wdiv[wdiv['d4'] == g[:2]]
                rows = rows[rows['d31'].isin(old.columns)]
                if len(rows):
                    w = pd.concat([w[w['d4'] != g], rows.assign(d4=g)[['d4', 'd31', 'n', 'w']]], ignore_index=True)
                    fallback.append(g)
    info['fallback_division'] = fallback

    s = backcast_divisions(old, new, w[['d4', 'd31', 'w']], OVERLAP)
    s = s[[c for c in s.columns if c in new.columns]]
    info['solo_desde_2014'] = sorted(c for c in s.columns if s[c].first_valid_index() > pd.Timestamp('2006-12-01'))
    s = s / s.loc[str(rebase_year)].mean() * 100

    desc = a14[a14['nivel'] == LEVEL[digits]].drop_duplicates(COL_CIIU).set_index(COL_CIIU)[COL_CIIU_DESC]
    long = s.rename_axis(COL_DATE).reset_index().melt(id_vars=COL_DATE, var_name=COL_CIIU, value_name=COL_IPP).dropna()
    long[COL_CIIU_DESC] = long[COL_CIIU].map(desc)
    long[COL_BASE] = np.where(long[COL_DATE] < OVERLAP, 'base_2006_retropolada', 'base_2014')
    long[COL_CIIU_REV] = 'rev4ac'
    long = long[[COL_DATE, COL_CIIU, COL_CIIU_DESC, COL_IPP, COL_BASE, COL_CIIU_REV]].sort_values([COL_CIIU, COL_DATE])
    return long.reset_index(drop=True), info


def official_total(raw: Path) -> pd.Series:
    return load_banrep_csv_oi_total(raw / FILE_BANREP_OI_TOTAL)


def consistency_vs_official(panel: pd.DataFrame, raw: Path) -> pd.DataFrame:
    """Compara el promedio geométrico simple del panel con el Total oficial (variación log mensual).
    Sin ponderadores no se espera igualdad; sirve como chequeo de plausibilidad por subperíodo."""
    wide = panel.pivot(index=COL_DATE, columns=COL_CIIU, values=COL_IPP)
    gm = np.log(wide).diff().mean(axis=1)
    off = np.log(official_total(raw)).diff()
    c = pd.concat({'panel': gm, 'oficial': off}, axis=1).dropna()
    rows = []
    for name, m in [('2007-2014 (retropolado)', c.index < OVERLAP), ('2015-2026 (observado)', c.index >= OVERLAP)]:
        x = c[m]
        rows.append({'subperiodo': name, 'corr_mensual': x['panel'].corr(x['oficial']),
                     'inflacion_anual_panel_%': x['panel'].mean() * 1200,
                     'inflacion_anual_oficial_%': x['oficial'].mean() * 1200})
    return pd.DataFrame(rows)


def to_annual(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d['anio'] = d[COL_DATE].dt.year
    n = d.groupby([COL_CIIU, 'anio'])[COL_DATE].transform('count')
    d = d[n == 12]  # solo años completos
    out = d.groupby([COL_CIIU, COL_CIIU_DESC, 'anio'], as_index=False)[COL_IPP].mean()
    return out
