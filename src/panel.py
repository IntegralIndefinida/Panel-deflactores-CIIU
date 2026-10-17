"""Construcción del panel IPP por división (2 dígitos) o grupo (3 dígitos) CIIU Rev 4, 2006-12 → presente."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (COL_DATE, COL_CIIU, COL_CIIU_DESC, COL_IPP, COL_BASE, COL_CIIU_REV,
                        FILE_ANEXO_2006, FILE_ANEXO_2014, FILE_CROSSWALK_31_4, FILE_BANREP_OI_TOTAL)
from src.sources import load_dane_annex, load_banrep_csv_oi_total
from src.division_link import load_weights, value_weights, backcast_divisions

logger = logging.getLogger(__name__)

LEVEL = {2: 'division', 3: 'grupo'}
OVERLAP = pd.Timestamp('2014-12-01')
CW_FILE = FILE_CROSSWALK_31_4
MIN_COVERAGE = 0.5  # si <50% del peso del crosswalk cae en grupos con dato, se usa la división


def _wide(df: pd.DataFrame, level: str) -> pd.DataFrame:
    d = df[df['nivel'] == level]
    return d.pivot(index='fecha', columns='ciiu_codigo', values='ipp').sort_index()


def _fallback_groups(w: pd.DataFrame, old_cols, new_cols) -> set:
    """Grupos Rev4 cuyo peso con dato en la base 2006 es menor que MIN_COVERAGE."""
    cov = w[w['d31'].isin(old_cols)].groupby('d4')['w'].sum()
    return {g for g in new_cols if cov.get(g, 0.0) < MIN_COVERAGE}


def _resolve(w: pd.DataFrame, wdiv: pd.DataFrame, old_cols, fallback: set) -> pd.DataFrame:
    """Restringe a orígenes con dato (renormalizando) y sustituye los grupos de `fallback` por su división."""
    w = w[w['d31'].isin(old_cols)]
    w = w.assign(w=w['w'] / w.groupby('d4')['w'].transform('sum'))
    w = w[~w['d4'].isin(fallback)]
    rows = [wdiv[(wdiv['d4'] == g[:2]) & wdiv['d31'].isin(old_cols)].assign(d4=g) for g in sorted(fallback)]
    return pd.concat([w, *rows], ignore_index=True)


def _with_value(val: pd.DataFrame, cnt: pd.DataFrame) -> pd.DataFrame:
    """Pesos por valor para los destinos manufactureros (divisiones 10–33) con plantas en la EAM; conteo para el resto."""
    val = val[val['d4'].str[:2].astype(int).between(10, 33)]
    return pd.concat([val, cnt[~cnt['d4'].isin(val['d4'])]], ignore_index=True)


def build_panel(raw: Path, crosswalks: Path, digits: int = 3, rebase_year: int = 2018,
                eam_links: pd.DataFrame | None = None, aggregation: str = 'geometric'):
    """Devuelve (panel_largo, info). Base `rebase_year` = 100 (promedio anual).

    eam_links (anio, c3, c4, valor; ver src/eam_weights.py): si se da, los orígenes se ponderan por valor
    de producción, con pesos interpolados entre los años de referencia; si no, por conteo de vínculos.
    aggregation: 'geometric' (tasas log encadenadas) o 'arithmetic' (Laspeyres de pesos fijos, rebasado al
    año de los pesos; requiere un solo año)."""
    if digits not in LEVEL:
        raise ValueError('digits debe ser 2 o 3')
    a06 = load_dane_annex(raw / FILE_ANEXO_2006)
    a14 = load_dane_annex(raw / FILE_ANEXO_2014)
    old, new = _wide(a06, LEVEL[digits]), _wide(a14, LEVEL[digits])
    info = {'n_old': old.shape[1], 'n_new': new.shape[1]}

    cnt = load_weights(crosswalks / CW_FILE, digits)
    cnt_div = load_weights(crosswalks / CW_FILE, 2)
    if eam_links is None:
        ws, wdivs = {None: cnt}, {None: cnt_div}
    else:
        ws = {y: _with_value(g.drop(columns='anio'), cnt) for y, g in value_weights(eam_links, digits).groupby('anio')}
        wdivs = {y: _with_value(g.drop(columns='anio'), cnt_div) for y, g in value_weights(eam_links, 2).groupby('anio')}

    fallback = set()
    if digits == 3:
        # respaldo: grupos Rev4 sin contraparte con dato se retropolan con la división padre
        old = pd.concat([old, _wide(a06, 'division')], axis=1)
        fallback = set().union(*(_fallback_groups(w, old.columns, new.columns) for w in ws.values()))
        fallback = {g for g in fallback if any(((wd['d4'] == g[:2]) & wd['d31'].isin(old.columns)).any()
                                               for wd in wdivs.values())}
    w = pd.concat([_resolve(ws[y], wdivs[y], old.columns, fallback).assign(anio=y) for y in ws], ignore_index=True)
    if eam_links is None:
        w = w.drop(columns='anio')
    info['fallback_division'] = sorted(fallback)

    ref_year = next(iter(ws)) if aggregation == 'arithmetic' and len(ws) == 1 else None
    s = backcast_divisions(old, new, w, OVERLAP, aggregation, ref_year)
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
