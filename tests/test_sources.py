import pandas as pd
import pytest

from src.sources import _header_to_date, _level, parse_spanish_date


def test_parse_spanish_date_two_digit_year():
    assert parse_spanish_date('ene-07') == pd.Timestamp('2007-01-01')
    assert parse_spanish_date('Dic-99') == pd.Timestamp('1999-12-01')


@pytest.mark.parametrize('header, expected', [
    ('dic-06', (pd.Timestamp('2006-12-01'), 2)),
    ('Ago-26 (definitivos) Disponibles desde el 6 de Octubre de 2026', (pd.Timestamp('2026-08-01'), 2)),
    ('Sep-26 (pr*)', (pd.Timestamp('2026-09-01'), 1)),
    (pd.Timestamp('2014-12-01'), (pd.Timestamp('2014-12-01'), 2)),
])
def test_header_to_date(header, expected):
    assert _header_to_date(header) == expected


def test_header_to_date_ignores_non_dates():
    assert _header_to_date('DESCRIPTIVA') is None


@pytest.mark.parametrize('code, level', [
    ('T', 'total'), ('A', 'seccion'), ('10', 'division'), ('101', 'grupo'),
    ('1010', 'clase'), ('01111', 'subclase'),
])
def test_level(code, level):
    assert _level(code) == level
