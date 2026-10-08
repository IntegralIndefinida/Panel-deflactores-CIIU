"""Loaders para las fuentes reales descargadas (anexos DANE y CSV del BanRep).

Todos devuelven formato largo: fecha (inicio de mes), ciiu_codigo, ciiu_descripcion, nivel, ipp.
"""
import re
from pathlib import Path

import pandas as pd

from src.config import COL_DATE, COL_CIIU, COL_CIIU_DESC, COL_IPP

COL_LEVEL = 'nivel'

import logging
logger = logging.getLogger(__name__)

_MES = r'(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)'


def parse_spanish_date(date_str: str) -> pd.Timestamp:
    """
    Parse Spanish month names/abbreviations into a pandas Timestamp.
    
    Args:
        date_str (str): Date string (e.g. 'Ene-99', '1999-01', 'Enero 1999').
        
    Returns:
        pd.Timestamp: Parsed timestamp (first day of the month).
    """
    if pd.isna(date_str):
        return pd.NaT

    date_str = str(date_str).strip().lower()
    
    # Map of Spanish months to numbers
    meses = {
        'ene': '01', 'enero': '01',
        'feb': '02', 'febrero': '02',
        'mar': '03', 'marzo': '03',
        'abr': '04', 'abril': '04',
        'may': '05', 'mayo': '05',
        'jun': '06', 'junio': '06',
        'jul': '07', 'julio': '07',
        'ago': '08', 'agosto': '08',
        'sep': '09', 'septiembre': '09', 'set': '09',
        'oct': '10', 'octubre': '10',
        'nov': '11', 'noviembre': '11',
        'dic': '12', 'diciembre': '12'
    }
    
    # Match patterns like 'Ene-99' or 'Ene 1999'
    match_alpha = re.search(r'([a-z]+)[-\s]+(\d{2,4})', date_str)
    if match_alpha:
        mes_str = match_alpha.group(1)
        year_str = match_alpha.group(2)
        mes_num = meses.get(mes_str, '01')
        
        # Handle two-digit years (assuming 1990-2026 range)
        if len(year_str) == 2:
            year_int = int(year_str)
            year_str = f"19{year_str}" if year_int >= 80 else f"20{year_str}"
            
        return pd.Timestamp(f"{year_str}-{mes_num}-01")
        
    # Attempt direct pandas parsing for standard formats like '1999-01'
    try:
        ts = pd.to_datetime(date_str)
        return pd.Timestamp(year=ts.year, month=ts.month, day=1)
    except Exception as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return pd.NaT


def _header_to_date(h):
    """Devuelve (fecha, prioridad) o None. Prioridad menor para cifras preliminares (pr*)."""
    if isinstance(h, (pd.Timestamp,)) or hasattr(h, 'year'):
        return pd.Timestamp(year=h.year, month=h.month, day=1), 2
    s = str(h).strip().lower()
    if not re.match(rf'^{_MES}[-\s]\d{{2}}', s):
        return None
    prio = 1 if '(pr' in s and 'definitiv' not in s else 2
    return parse_spanish_date(s[:6]), prio


def _level(code: str) -> str:
    if code == 'T':
        return 'total'
    if re.fullmatch(r'[A-Z]', code):
        return 'seccion'
    return {2: 'division', 3: 'grupo', 4: 'clase', 5: 'subclase'}.get(len(code), 'otro')


def load_dane_annex(path: Path, sheet: str = '2.1', header_row: int = 5) -> pd.DataFrame:
    """Anexo estadístico DANE (hoja ancha NIVEL/CODIGO/DESCRIPTIVA + una columna por mes)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header = raw.iloc[header_row]
    body = raw.iloc[header_row + 1:].copy()
    body = body[body[1].notna()]
    codes = body[1].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    # elegir una columna por mes: la de mayor prioridad (definitivo sobre preliminar), luego la última
    chosen: dict[pd.Timestamp, tuple[int, int]] = {}
    for j, h in enumerate(header):
        if j < 3:
            continue
        parsed = _header_to_date(h)
        if parsed is None:
            continue
        date, prio = parsed
        if date not in chosen or prio >= chosen[date][0]:
            chosen[date] = (prio, j)

    cols = {d: j for d, (_, j) in sorted(chosen.items())}
    wide = pd.DataFrame({d: pd.to_numeric(body.iloc[:, j], errors='coerce').values for d, j in cols.items()},
                        index=codes.values)
    desc = pd.Series(body[2].astype(str).str.strip().values, index=codes.values)
    wide = wide[~wide.index.duplicated(keep='first')]
    desc = desc[~desc.index.duplicated(keep='first')]
    long = wide.rename_axis(COL_CIIU).reset_index().melt(id_vars=COL_CIIU, var_name=COL_DATE, value_name=COL_IPP)
    long = long.dropna(subset=[COL_IPP])
    long[COL_CIIU_DESC] = long[COL_CIIU].map(desc)
    long[COL_LEVEL] = long[COL_CIIU].map(_level)
    long[COL_DATE] = pd.to_datetime(long[COL_DATE])
    return long[[COL_DATE, COL_CIIU, COL_CIIU_DESC, COL_LEVEL, COL_IPP]].sort_values([COL_CIIU, COL_DATE]).reset_index(drop=True)


# Sectores del CSV BanRep (base 1999) → códigos de sección comunes
BANREP_1999_MAP = {
    'Total': 'T',
    'Agricultura, silvicutura, ganaderia y pesca': 'AGRO',
    'Mineria': 'MIN',
    'Industria manufacturera': 'MAN',
}


def load_banrep_csv_1999(path: Path) -> pd.DataFrame:
    """CSV exportado del BanRep (base 1999=100): fecha, actividad, índice."""
    d = pd.read_csv(path, encoding='utf-8-sig')
    out = pd.DataFrame({
        COL_DATE: pd.to_datetime(d['Fecha (Mes año)']).dt.to_period('M').dt.to_timestamp(),
        COL_CIIU: d['Actividad económica CIIU'].map(BANREP_1999_MAP),
        COL_CIIU_DESC: d['Actividad económica CIIU'],
        COL_IPP: pd.to_numeric(d['Índice'], errors='coerce'),
    })
    out[COL_LEVEL] = out[COL_CIIU].map(lambda c: 'total' if c == 'T' else 'sector')
    return out.dropna(subset=[COL_CIIU, COL_IPP]).drop_duplicates([COL_CIIU, COL_DATE], keep='last').reset_index(drop=True)


def load_banrep_csv_oi_total(path: Path, clasificacion: str = 'Oferta Interna') -> pd.Series:
    """CSV BanRep 'IPP 2014 Total': serie oficial empalmada (Dic 2014=100) desde 1970."""
    d = pd.read_csv(path, encoding='utf-8-sig')
    d = d[d['Clasificación de los bienes'] == clasificacion]
    idx = pd.to_datetime(d['Fecha (Mes año)']).dt.to_period('M').dt.to_timestamp()
    return pd.Series(pd.to_numeric(d['Índice']).values, index=idx).sort_index()
