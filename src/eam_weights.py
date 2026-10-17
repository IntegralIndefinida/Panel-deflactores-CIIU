"""Vínculos clase CIIU Rev 3 → Rev 4 observados planta por planta en la EAM (doble codificación).

La EAM publica Rev 3 hasta 2011 y Rev 4 desde 2012, y `nordest` identifica al mismo establecimiento
entre años. El código Rev 4 que el DANE asignó a cada planta en el año de enlace (2012) se cruza con
su código Rev 3 del año de referencia. Reglas:
- Solo cuentan los vínculos compatibles con la correlativa oficial Rev 3 → Rev 4; los demás son
  cambios de actividad o códigos que no reflejan la actividad (posiblemente por la anonimización del
  archivo público) y se descartan.
- Las plantas del año de referencia que no aparecen en el año de enlace reparten su valor según las
  participaciones observadas de su clase en ese mismo año.
"""
import pandas as pd


def _is_valid(c3: pd.Series, c4: pd.Series, pairs: pd.DataFrame) -> pd.Series:
    """Par permitido por la correlativa. Clases propias de la EAM (fuera de la correlativa) se
    validan a nivel de grupo."""
    exact = set(zip(pairs['c3'], pairs['c4']))
    by_group = set(zip(pairs['c3'].str[:3], pairs['c4']))
    known = set(pairs['c3'])
    return pd.Series([(a, b) in exact or (a not in known and (a[:3], b) in by_group)
                      for a, b in zip(c3, c4)], index=c3.index)


def class_links(base: pd.DataFrame, link: pd.DataFrame, pairs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """base: nordest, c3, valor (año de referencia); link: nordest, c4 (año de enlace);
    pairs: c3, c4 de la correlativa oficial.
    Devuelve (c3, c4, valor, fuente ∈ {observado, imputado}) y la composición del valor."""
    m = base.merge(link[['nordest', 'c4']], on='nordest', how='left')
    matched = m['c4'].notna()
    ok = matched & _is_valid(m['c3'], m['c4'].fillna(''), pairs)
    obs = m[ok].groupby(['c3', 'c4'], as_index=False)['valor'].sum()
    share = obs.assign(s=obs['valor'] / obs.groupby('c3')['valor'].transform('sum'))[['c3', 'c4', 's']]
    unm = m[~matched].groupby('c3', as_index=False)['valor'].sum()
    imp = unm.merge(share, on='c3')                 # clases sin vínculo observado quedan fuera
    imp = imp.assign(valor=imp['valor'] * imp['s'])[['c3', 'c4', 'valor']]
    out = pd.concat([obs.assign(fuente='observado'), imp.assign(fuente='imputado')], ignore_index=True)
    tot = m['valor'].sum()
    stats = {'observado': obs['valor'].sum() / tot,
             'imputado': imp['valor'].sum() / tot,
             'descartado_incompatible': m.loc[matched & ~ok, 'valor'].sum() / tot,
             'descartado_sin_vinculo': (unm['valor'].sum() - imp['valor'].sum()) / tot}
    return out, stats
