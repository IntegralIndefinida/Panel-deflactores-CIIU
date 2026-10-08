"""Pruebas sobre los archivos finales publicados en data/final."""
from pathlib import Path

import pandas as pd
import pytest

FINAL = Path(__file__).resolve().parent.parent / 'data' / 'final'
SPLICE = pd.Timestamp('2014-12-01')


def _load(name):
    path = FINAL / name
    if not path.exists():
        pytest.skip(f'{name} no existe; ejecutar main.py')
    return pd.read_csv(path, parse_dates=['fecha'], dtype={'ciiu_codigo': str})


@pytest.fixture(scope='module', params=['ipp_ciiu3d_mensual.csv', 'ipp_ciiu2d_mensual.csv'])
def panel(request):
    return _load(request.param)


def test_schema_and_no_duplicates(panel):
    assert {'fecha', 'ciiu_codigo', 'ciiu_descripcion', 'ipp', 'base_origen', 'ciiu_revision'} <= set(panel.columns)
    assert not panel.duplicated(['ciiu_codigo', 'fecha']).any()
    assert panel['ipp'].notna().all() and (panel['ipp'] > 0).all()


def test_codes_are_zero_padded_strings(panel):
    n = panel['ciiu_codigo'].str.len().unique()
    assert len(n) == 1 and n[0] in (2, 3)


def test_balanced_without_gaps(panel):
    wide = panel.pivot(index='fecha', columns='ciiu_codigo', values='ipp')
    assert not wide.isna().any().any()
    assert (wide.index == pd.date_range(wide.index.min(), wide.index.max(), freq='MS')).all()
    assert wide.index.min() == pd.Timestamp('2006-12-01')


def test_rebased_to_2018_mean_100(panel):
    m = panel[panel['fecha'].dt.year == 2018].groupby('ciiu_codigo')['ipp'].mean()
    assert ((m - 100).abs() < 1e-6).all()


def test_base_origen_matches_splice_date(panel):
    assert (panel.loc[panel['fecha'] < SPLICE, 'base_origen'] == 'base_2006_retropolada').all()
    assert (panel.loc[panel['fecha'] >= SPLICE, 'base_origen'] == 'base_2014').all()


def test_no_artificial_jump_at_splice(panel):
    """El crecimiento en el mes del empalme no debe diferir sistemáticamente del resto."""
    g = panel.pivot(index='fecha', columns='ciiu_codigo', values='ipp').pipe(lambda w: w.pct_change())
    around = g.loc['2014-11-01':'2015-01-01'].abs()
    assert around.median(axis=None) < 0.05
    assert g.loc['2015-01-01'].abs().median() < 0.05


def test_sectors_total_matches_official_if_available():
    s = FINAL / 'validacion_total_vs_oficial.csv'
    if not s.exists():
        pytest.skip('sin validación')
    v = pd.read_csv(s)
    assert v['dif_pct'].abs().max() < 0.5
