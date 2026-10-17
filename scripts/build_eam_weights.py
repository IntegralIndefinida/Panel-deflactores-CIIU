#!/usr/bin/env python3
"""Pesos por valor para la retropolación, desde los microdatos de la EAM (doble codificación por planta).

    python scripts/build_eam_weights.py [--eam-dir ../EAM/data/datos] [--years 2007 2011] [--link-year 2012]

Escribe data/processed/pesos_eam_rev3_rev4.csv (anio, c3, c4, valor, fuente), que main.py usa con
--weights value. Valor = PRODBR2 (producción bruta) del año de referencia.
"""
import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import FILE_CROSSWALK_3_4, FILE_PESOS_EAM, ProjectPaths, setup_logging
from src.division_link import load_pairs
from src.eam_weights import class_links

logger = logging.getLogger('build_eam_weights')


def read_eam(eam_dir: Path, year: int, code: str) -> pd.DataFrame:
    """nordest, <code> (clase con 4 dígitos), valor. Los nombres de columna cambian de caso entre años."""
    f = next((eam_dir / str(year)).glob('*.*'))
    d = pd.read_csv(f, sep=None, engine='python', encoding='utf-8-sig')
    d.columns = [c.lower() for c in d.columns]
    col = next(c for c in d.columns if re.fullmatch(r'ciiu_?[34]', c))
    return pd.DataFrame({'nordest': d['nordest'],
                         code: d[col].astype(int).astype(str).str.zfill(4),
                         'valor': pd.to_numeric(d['prodbr2'], errors='coerce').fillna(0)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--eam-dir', default=str(ROOT.parent / 'EAM' / 'data' / 'datos'))
    ap.add_argument('--years', type=int, nargs='+', default=[2007, 2011], help='años de referencia (EAM en Rev 3)')
    ap.add_argument('--link-year', type=int, default=2012, help='primer año de la EAM en Rev 4')
    a = ap.parse_args()
    setup_logging()
    paths = ProjectPaths(ROOT)
    paths.ensure_dirs()
    eam = Path(a.eam_dir)

    pairs = load_pairs(paths.crosswalks / FILE_CROSSWALK_3_4).rename(columns={'c31': 'c3'})
    link = read_eam(eam, a.link_year, 'c4')
    out = []
    for y in a.years:
        links, st = class_links(read_eam(eam, y, 'c3'), link, pairs)
        logger.info('%d → %d: valor observado %.1f%%, imputado %.1f%%, descartado (incompatible %.1f%%, '
                    'sin vínculo %.1f%%)', y, a.link_year, *(100 * st[k] for k in
                    ('observado', 'imputado', 'descartado_incompatible', 'descartado_sin_vinculo')))
        out.append(links.assign(anio=y))
    df = pd.concat(out, ignore_index=True)[['anio', 'c3', 'c4', 'valor', 'fuente']]
    dest = paths.processed / FILE_PESOS_EAM
    df.to_csv(dest, index=False)
    logger.info('Escrito %s (%d vínculos)', dest, len(df))


if __name__ == '__main__':
    main()
