"""
Configuraciones centrales para el pipeline ETL del Panel Unificado del IPP Colombia.
"""

import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Rutas del proyecto."""
    root: Path
    raw: Path
    crosswalks: Path
    processed: Path
    final: Path

    def __init__(self, root: Path):
        object.__setattr__(self, 'root', root)
        object.__setattr__(self, 'raw', root / 'data' / 'raw')
        object.__setattr__(self, 'crosswalks', root / 'data' / 'crosswalks')
        object.__setattr__(self, 'processed', root / 'data' / 'processed')
        object.__setattr__(self, 'final', root / 'data' / 'final')

    def ensure_dirs(self) -> None:
        """Crea todos los directorios necesarios si no existen."""
        self.raw.mkdir(parents=True, exist_ok=True)
        self.crosswalks.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)
        self.final.mkdir(parents=True, exist_ok=True)


# Archivos de data/raw. El anexo vigente del DANE cambia cada mes: actualizar aquí y en
# scripts/download_sources.py (ver README, sección "URLs").
FILE_ANEXO_2006 = 'anex_ipp_dic14.xls'          # base Dic-2006=100, CIIU Rev 3.1 A.C.
FILE_ANEXO_2014 = 'anex-IPP-sep2026.xlsx'       # base Dic-2014=100, CIIU Rev 4 A.C.
FILE_CROSSWALK_31_4 = 'TC-CIIU-3-1ACvsCIIU-4AC-2020.xlsx'
FILE_BANREP_1999 = '1_IPP_base_1999_segun_actividad_economica_iqy.csv'   # exportación manual BanRep
FILE_BANREP_OI_TOTAL = '1_IPP_2014_Total_iqy.csv'                        # exportación manual BanRep

FINAL_BASE_YEAR: int = 2018

def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logger raíz."""
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(name)s — %(levelname)s — %(message)s'
    )

COL_DATE = 'fecha'
COL_CIIU = 'ciiu_codigo'
COL_CIIU_DESC = 'ciiu_descripcion'
COL_IPP = 'ipp'
COL_BASE = 'base_origen'
COL_CIIU_REV = 'ciiu_revision'
