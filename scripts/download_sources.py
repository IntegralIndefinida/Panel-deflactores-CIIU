#!/usr/bin/env python3
"""Descarga las fuentes DANE verificadas en resume.md hacia data/raw y data/crosswalks."""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import FILE_ANEXO_2006, FILE_ANEXO_2014

BASE = "https://www.dane.gov.co/files"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

RAW = {
    FILE_ANEXO_2006: f"{BASE}/investigaciones/boletines/ipp/{FILE_ANEXO_2006}",
    FILE_ANEXO_2014: f"{BASE}/operaciones/IPP/{FILE_ANEXO_2014}",
    "Ejemplo_Empalmes.xls": f"{BASE}/investigaciones/boletines/ipp/Ejemplo_Empalmes.xls",
    "Instructivo_empalme_seriesIPP.pdf": f"{BASE}/investigaciones/boletines/ipp/Instructivo_empalme_seriesIPP.pdf",
}
CROSSWALKS = {
    "CIIU3ACvsCIIU2DANE.xls": f"{BASE}/sen/nomenclatura/tablasCorrelativas/CIIU3ACvsCIIU2DANE.xls",
    "TC-CIIU-3-1ACvsCIIU-4AC-2020.xlsx": f"{BASE}/sen/nomenclatura/tablasCorrelativas/TC-CIIU-3-1ACvsCIIU-4AC-2020.xlsx",
    "TC-CIIU-3ACvsCIIU-4AC-2020.xlsx": f"{BASE}/sen/nomenclatura/tablasCorrelativas/TC-CIIU-3ACvsCIIU-4AC-2020.xlsx",
    "Correlativa_CPC_CIIU_15.xls": f"{BASE}/investigaciones/boletines/ipp/Correlativa_CPC_CIIU_15.xls",
}


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"= {dest.name} (ya existe)")
        return True
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
        print(f"+ {dest.name} ({dest.stat().st_size/1024:.0f} KB)")
        return True
    except Exception as e:
        print(f"! {dest.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    (ROOT / "data/raw").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/crosswalks").mkdir(parents=True, exist_ok=True)
    ok = [fetch(u, ROOT / "data/raw" / n) for n, u in RAW.items()]
    ok += [fetch(u, ROOT / "data/crosswalks" / n) for n, u in CROSSWALKS.items()]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
