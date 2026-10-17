import numpy as np
import pandas as pd

from src.eam_weights import class_links

PAIRS = pd.DataFrame({'c3': ['1511', '1511', '2320'], 'c4': ['1011', '1012', '1921']})


def _links(base, link):
    return class_links(pd.DataFrame(base, columns=['nordest', 'c3', 'valor']),
                       pd.DataFrame(link, columns=['nordest', 'c4']), PAIRS)


def test_observed_links_follow_plant_codes():
    out, st = _links([(1, '1511', 60.0), (2, '1511', 40.0)], [(1, '1011'), (2, '1012')])
    v = out.set_index(['c3', 'c4'])['valor']
    assert v[('1511', '1011')] == 60 and v[('1511', '1012')] == 40
    assert np.isclose(st['observado'], 1.0)


def test_incompatible_links_are_dropped_not_reallocated():
    # planta 2 pasa de 1511 a refinación: no está en la correlativa (código enmascarado o cambio de actividad)
    out, st = _links([(1, '1511', 60.0), (2, '1511', 900.0)], [(1, '1011'), (2, '1921')])
    assert out['valor'].sum() == 60 and not (out['c4'] == '1921').any()
    assert np.isclose(st['descartado_incompatible'], 900 / 960)


def test_unmatched_plants_use_class_shares_of_same_year():
    out, st = _links([(1, '1511', 75.0), (2, '1511', 25.0), (3, '1511', 100.0)], [(1, '1011'), (2, '1012')])
    imp = out[out['fuente'] == 'imputado'].set_index('c4')['valor']
    assert np.isclose(imp['1011'], 75) and np.isclose(imp['1012'], 25)
    assert np.isclose(st['imputado'], 0.5)


def test_eam_specific_class_validated_at_group_level():
    # 2323 no existe en la correlativa Rev 3 A.C.; su grupo (232) sí se vincula con 1921
    out, _ = _links([(1, '2323', 10.0)], [(1, '1921')])
    assert out.set_index(['c3', 'c4'])['valor'][('2323', '1921')] == 10
