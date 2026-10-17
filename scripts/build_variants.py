#!/usr/bin/env python3
"""Variantes de robustez del panel anual de grupos (3 dígitos) en un solo archivo.

    python scripts/build_variants.py

Escribe data/final/ipp_ciiu3d_anual_variantes.{csv,dta}: una columna por especificación de la
retropolación, el rango entre ellas y la marca de grupos frágiles (FRAGILE_GROUPS en src/config.py).
Desde 2015 todas coinciden (dato observado); difieren en 2007–2014.
"""
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (COL_CIIU, COL_CIIU_DESC, COL_IPP, FILE_PESOS_EAM, FINAL_BASE_YEAR, FRAGILE_GROUPS,
                        WEIGHT_YEARS, ProjectPaths, setup_logging)
from src.panel import build_panel, to_annual
from src.quality_checks import PanelExporter

logger = logging.getLogger('build_variants')

# nombre de columna -> (años de pesos por valor o None = conteo, agregación, grupos con división padre)
VARIANTS = {
    'ipp': (WEIGHT_YEARS, 'geometric', ()),                      # especificación principal
    'ipp_conteo': (None, 'geometric', ()),
    'ipp_pesos2007': ((2007,), 'geometric', ()),
    'ipp_pesos2011': ((2011,), 'geometric', ()),
    'ipp_aritmetico2011': ((2011,), 'arithmetic', ()),
    'ipp_div_fragiles': (WEIGHT_YEARS, 'geometric', FRAGILE_GROUPS),
}


def main():
    setup_logging()
    paths = ProjectPaths(ROOT)
    links = pd.read_csv(paths.processed / FILE_PESOS_EAM, dtype={'c3': str, 'c4': str})
    cols = {}
    for name, (years, agg, force) in VARIANTS.items():
        l = None if years is None else links[links['anio'].isin(years)]
        panel, _ = build_panel(paths.raw, paths.crosswalks, 3, FINAL_BASE_YEAR, l, agg, force)
        cols[name] = to_annual(panel).set_index([COL_CIIU, COL_CIIU_DESC, 'anio'])[COL_IPP]
        logger.info('%s listo', name)
    df = pd.DataFrame(cols).reset_index()
    v = df[list(VARIANTS)]
    df['ipp_min'], df['ipp_max'] = v.min(axis=1), v.max(axis=1)
    df.insert(3, 'fragil', df[COL_CIIU].isin(FRAGILE_GROUPS))
    df.insert(4, 'retropolado', df['anio'] <= 2014)
    df = df.sort_values([COL_CIIU, 'anio']).rename(columns={'anio': 'year'})

    exp = PanelExporter(df, paths.final)
    exp.to_csv('ipp_ciiu3d_anual_variantes.csv')
    exp.to_stata('ipp_ciiu3d_anual_variantes.dta')

    # resumen: diferencia de nivel frente a la principal (puntos log), grupos manufactureros, 2007–2010
    man = df[df[COL_CIIU].str[:2].astype(int).between(10, 33) & df['year'].between(2007, 2010)]
    d = {k: (100 * np.log(man[k] / man['ipp'])).abs().groupby(man['year']).mean() for k in VARIANTS if k != 'ipp'}
    logger.info('|Diferencia| media frente a la principal, grupos manufactureros (puntos log):\n%s',
                pd.DataFrame(d).round(2).to_string())
    fr = df[df['fragil'] & (df['year'] == 2007)].set_index(COL_CIIU)[list(VARIANTS) + ['ipp_min', 'ipp_max']]
    logger.info('Grupos frágiles, 2007 (2018=100):\n%s', fr.round(1).to_string())


if __name__ == '__main__':
    main()
