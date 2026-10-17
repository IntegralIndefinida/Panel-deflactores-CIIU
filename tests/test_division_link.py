import numpy as np
import pandas as pd

from src.division_link import backcast_divisions, value_weights

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


def test_interpolated_weights_move_from_first_to_second_parent():
    dates = pd.date_range('2010-01-01', '2014-12-01', freq='MS')
    n = np.arange(len(dates))
    old = pd.DataFrame({'A': 100 * 1.01 ** n, 'B': 100 * 1.03 ** n}, index=dates)
    new = pd.DataFrame({'X': [100.0]}, index=[OV])
    w = pd.DataFrame({'anio': [2011, 2011, 2013, 2013], 'd4': 'X', 'd31': ['A', 'B', 'A', 'B'], 'w': [1.0, 0.0, 0.0, 1.0]})
    g = np.log(backcast_divisions(old, new, w, OV)['X']).diff()
    assert np.allclose(g.loc['2010-02':'2011-06'], np.log(1.01))   # antes de mitad de 2011: solo A
    assert np.allclose(g.loc['2013-07':'2014-12'], np.log(1.03))   # después de mitad de 2013: solo B
    assert g.loc['2011-07':'2013-06'].is_monotonic_increasing


def test_value_weights_are_value_shares_by_destination():
    links = pd.DataFrame({'anio': 2011, 'c3': ['1511', '1512', '1520'], 'c4': ['1011', '1012', '1040'],
                          'valor': [30.0, 10.0, 5.0]})
    w = value_weights(links, 2).set_index(['d4', 'd31'])['w']
    assert np.isclose(w[('10', '15')], 1.0)
    w3 = value_weights(links, 3).set_index(['d4', 'd31'])['w']
    assert np.isclose(w3[('101', '151')], 1.0) and np.isclose(w3[('104', '152')], 1.0)
    links.loc[2, 'c4'] = '1012'
    w3 = value_weights(links, 3).set_index(['d4', 'd31'])['w']
    assert np.isclose(w3[('101', '151')], 40 / 45) and np.isclose(w3[('101', '152')], 5 / 45)
