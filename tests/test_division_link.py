import numpy as np
import pandas as pd

from src.division_link import backcast_divisions

DATES = pd.date_range('2014-06-01', '2015-01-01', freq='MS')
OV = pd.Timestamp('2014-12-01')


def _old():
    n = np.arange(len(DATES))
    return pd.DataFrame({'A': 100 * 1.01 ** n, 'B': 100 * 1.03 ** n}, index=DATES)


def _new(value=100.0):
    return pd.DataFrame({'X': value * np.ones(len(DATES))}, index=DATES).loc[OV:]


def test_continuity_at_overlap():
    w = pd.DataFrame({'d4': ['X', 'X'], 'd31': ['A', 'B'], 'w': [0.5, 0.5]})
    out = backcast_divisions(_old(), _new(), w, OV)
    assert out.loc[OV, 'X'] == 100.0
    assert out.index.is_monotonic_increasing and not out.index.duplicated().any()


def test_single_parent_replicates_old_growth():
    w = pd.DataFrame({'d4': ['X'], 'd31': ['A'], 'w': [1.0]})
    out = backcast_divisions(_old(), _new(), w, OV)
    old = _old()['A']
    ratio = out.loc[:OV, 'X'] / old.loc[:OV]
    assert np.allclose(ratio, ratio.iloc[0])      # mismo crecimiento => razón constante
    assert np.isclose(out.loc[OV, 'X'], 100.0)


def test_weighted_growth_between_parents():
    w = pd.DataFrame({'d4': ['X', 'X'], 'd31': ['A', 'B'], 'w': [0.5, 0.5]})
    out = backcast_divisions(_old(), _new(), w, OV)
    g = np.log(out['X']).diff().loc[:OV].dropna()
    assert np.allclose(g, 0.5 * np.log(1.01) + 0.5 * np.log(1.03))


def test_missing_old_component_renormalizes_weights():
    old = _old()
    old.loc[old.index[3], 'B'] = np.nan
    w = pd.DataFrame({'d4': ['X', 'X'], 'd31': ['A', 'B'], 'w': [0.5, 0.5]})
    out = backcast_divisions(old, _new(), w, OV)
    assert out['X'].notna().all()
