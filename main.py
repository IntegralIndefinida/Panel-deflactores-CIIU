#!/usr/bin/env python3
"""Panel IPP Colombia por CIIU Rev 4 (2006-12 → presente), base `--rebase-year` = 100.

    python main.py [--digits 3] [--rebase-year 2018] [--freq M|Y] [--formats parquet,csv,stata]
                   [--weights value|count] [--weight-years 2007,2011] [--aggregation geometric|arithmetic]
                   [--division-groups 191,263,...]

Requiere data/raw y data/crosswalks (ver scripts/download_sources.py) y, con --weights value (por
defecto), data/processed/pesos_eam_rev3_rev4.csv (ver scripts/build_eam_weights.py).
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

from src.config import FINAL_BASE_YEAR, FILE_BANREP_OI_TOTAL, FILE_PESOS_EAM, WEIGHT_YEARS, FRAGILE_GROUPS, ProjectPaths, setup_logging, COL_DATE, COL_CIIU, COL_IPP
from src.panel import build_panel, consistency_vs_official, to_annual
from src.quality_checks import PanelValidator, PanelExporter

logger = logging.getLogger('main')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--digits', type=int, choices=[2, 3], default=3, help='2=división, 3=grupo (default 3)')
    ap.add_argument('--rebase-year', type=int, default=FINAL_BASE_YEAR)
    ap.add_argument('--freq', choices=['M', 'Y'], default='M')
    ap.add_argument('--formats', default='parquet,csv,stata')
    ap.add_argument('--output-dir', default=None)
    ap.add_argument('--weights', choices=['value', 'count'], default='value',
                    help='ponderación de los orígenes en la retropolación: valor de producción EAM (default) o conteo de vínculos')
    ap.add_argument('--weight-years', default=','.join(map(str, WEIGHT_YEARS)),
                    help='años de referencia de los pesos por valor; varios = interpolación lineal (default 2007,2011)')
    ap.add_argument('--aggregation', choices=['geometric', 'arithmetic'], default='geometric',
                    help='geometric: tasas log encadenadas (default); arithmetic: Laspeyres de pesos fijos (un solo año de pesos)')
    ap.add_argument('--division-groups', default='',
                    help="grupos que se retropolan con su división padre, separados por coma; 'fragiles' = "
                         + ','.join(FRAGILE_GROUPS))
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()
    setup_logging(logging.DEBUG if a.verbose else logging.INFO)

    paths = ProjectPaths(Path(__file__).resolve().parent)
    paths.ensure_dirs()
    out = Path(a.output_dir) if a.output_dir else paths.final
    out.mkdir(parents=True, exist_ok=True)

    years = sorted(int(y) for y in a.weight_years.split(','))
    if a.aggregation == 'arithmetic' and a.weights == 'value' and len(years) > 1:
        ap.error('--aggregation arithmetic usa pesos fijos: pasar un solo año, p. ej. --weight-years 2011')
    force = FRAGILE_GROUPS if a.division_groups == 'fragiles' else tuple(g for g in a.division_groups.split(',') if g)
    links = None
    if a.weights == 'value':
        f = paths.processed / FILE_PESOS_EAM
        if not f.exists():
            ap.error(f'falta {f}: ejecutar scripts/build_eam_weights.py o usar --weights count')
        links = pd.read_csv(f, dtype={'c3': str, 'c4': str})
        missing = set(years) - set(links['anio'])
        if missing:
            ap.error(f'{f.name} no tiene los años {sorted(missing)}: regenerarlo con --years')
        links = links[links['anio'].isin(years)]
    # sufijo de archivo solo para especificaciones distintas de la principal
    tag = '_conteo' if a.weights == 'count' else ('' if tuple(years) == WEIGHT_YEARS else '_pesos' + '-'.join(map(str, years)))
    tag += '_aritmetico' if a.aggregation == 'arithmetic' else ''
    tag += ('_divfragiles' if force == FRAGILE_GROUPS else '_div' + '-'.join(force)) if force else ''
    logger.info('Ponderación: %s', 'conteo de vínculos' if links is None else f'valor EAM, años {years}')

    panel, info = build_panel(paths.raw, paths.crosswalks, a.digits, a.rebase_year, links, a.aggregation, force)
    logger.info('Panel: %d series, %s → %s, %d obs', panel[COL_CIIU].nunique(),
                panel[COL_DATE].min().strftime('%Y-%m'), panel[COL_DATE].max().strftime('%Y-%m'), len(panel))
    logger.info('Grupos retropolados vía división padre: %s', info['fallback_division'] or 'ninguno')
    logger.info('Series que solo existen desde 2014-12: %s', info['solo_desde_2014'] or 'ninguna')

    val = PanelValidator(panel)
    rep = val.summary_report()
    atip = val.check_outliers('growth_rate', 3.0)[[COL_DATE, COL_CIIU, 'ciiu_descripcion', COL_IPP, 'growth', 'g_zscore', 'base_origen']]
    atip = atip.assign(mayor_15pct=atip['growth'].abs() > 0.15).sort_values(['mayor_15pct', COL_DATE], ascending=[False, True])
    atip.to_csv(out / f'atipicos_ciiu{a.digits}d{tag}.csv', index=False)
    for line in rep.split('\n'):
        logger.info('  %s', line)
    if (paths.raw / FILE_BANREP_OI_TOTAL).exists():
        logger.info('Consistencia vs Total oficial (promedio simple, no ponderado):\n%s',
                    consistency_vs_official(panel, paths.raw).round(3).to_string(index=False))
    else:
        logger.warning('Sin %s en data/raw: se omite la comparación con el Total oficial.', FILE_BANREP_OI_TOTAL)

    if a.freq == 'Y':
        panel = to_annual(panel)
        logger.info('Frecuencia anual: %d obs (solo años completos)', len(panel))

    stem = f"ipp_ciiu{a.digits}d_{'anual' if a.freq == 'Y' else 'mensual'}{tag}"
    exp = PanelExporter(panel.rename(columns={'anio': 'year'}), out)
    for fmt in (f.strip().lower() for f in a.formats.split(',')):
        {'parquet': lambda: exp.to_parquet(f'{stem}.parquet'),
         'csv': lambda: exp.to_csv(f'{stem}.csv'),
         'stata': lambda: exp.to_stata(f'{stem}.dta'),
         'excel': lambda: exp.to_excel(f'{stem}.xlsx')}[fmt]()
    logger.info('Exportado en %s', out)


if __name__ == '__main__':
    main()
