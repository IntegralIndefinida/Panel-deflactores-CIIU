# Panel de deflactores IPP Colombia por CIIU

Panel mensual del Índice de Precios del Productor (IPP, Oferta Interna) de Colombia por división (2 dígitos) y grupo (3 dígitos) CIIU Rev. 4 A.C., diciembre 2006 – septiembre 2026, pensado para deflactar producción, consumo intermedio y capital en la estimación de funciones de producción (Translog) con microdatos de firmas (p. ej. EAM).

**Atención:** el tramo anterior a 2014-12 no es dato observado en Rev. 4; se retropola desde la base Dic-2006 (Rev. 3.1), ponderando los orígenes por valor de producción de la EAM (ver [Método](#método)). La columna `base_origen` lo distingue.

## Uso rápido

```bash
pip install -r requirements.txt
python scripts/download_sources.py        # anexos y correlativas del DANE -> data/raw, data/crosswalks
python scripts/build_eam_weights.py       # pesos por valor desde la EAM -> data/processed/pesos_eam_rev3_rev4.csv
python main.py --digits 3                 # grupos; --digits 2 = divisiones; --freq Y = anual
python -m pytest                          # pruebas
```

Opciones de `main.py`: `--digits {2,3}`, `--rebase-year` (2018), `--freq {M,Y}`, `--formats parquet,csv,stata,excel`, `--output-dir`, `--weights {value,count}` (value), `--weight-years` (2007,2011), `--aggregation {geometric,arithmetic}` (geometric; arithmetic exige un solo año de pesos), `--division-groups` (lista de grupos o `fragiles`). Las especificaciones distintas de la principal se exportan con sufijo: `_conteo`, `_pesos2011`, `_aritmetico`, `_divfragiles`, combinables.

`python scripts/build_variants.py` (después de `build_eam_weights.py`) arma el archivo anual de variantes de robustez.

`scripts/build_eam_weights.py` lee los microdatos de la EAM del proyecto hermano `../EAM/data/datos` (cambiar con `--eam-dir`). Sin ese archivo, `main.py` solo corre con `--weights count`.

Para la comparación con el Total oficial y para `scripts/build_sections.py` se necesitan además dos CSV exportados manualmente del portal de estadísticas del Banco de la República (no hay URL estable de descarga): `1_IPP_base_1999_segun_actividad_economica_iqy.csv` y `1_IPP_2014_Total_iqy.csv`, en `data/raw/`. Sin ellos `main.py` omite esa comparación.

## Resultados (`data/final/`)

| Archivo | Contenido |
|---|---|
| `ipp_ciiu3d_mensual.{csv,dta,parquet}` | 78 grupos × 238 meses (2006-12…2026-09) |
| `ipp_ciiu3d_anual.{csv,dta,parquet}` | Promedio anual, solo años completos (2007–2025) |
| `ipp_ciiu2d_mensual.{csv,dta,parquet}` | 30 divisiones |
| `ipp_ciiu3d_anual_variantes.{csv,dta}` | Grupos, promedio anual 2007–2025, una columna por especificación de la retropolación (`ipp` principal, `ipp_conteo`, `ipp_pesos2007`, `ipp_pesos2011`, `ipp_aritmetico2011`, `ipp_div_fragiles`), `ipp_min`/`ipp_max` entre ellas, `fragil` y `retropolado` (`scripts/build_variants.py`). Desde 2015 todas coinciden |
| `ipp_sectores_amplios.csv` | Total, Agro, Minería, Manufactura; 1970-01…2026-09 (`scripts/build_sections.py`) |
| `validacion_total_vs_oficial.csv` | Total empalmado vs serie oficial empalmada del BanRep |
| `atipicos_ciiu{2,3}d.csv` | Observaciones marcadas como atípicas (ver abajo) |

Columnas del panel: `fecha` (primer día del mes), `ciiu_codigo` (texto con ceros: leerlo como `str`), `ciiu_descripcion`, `ipp` (promedio de `--rebase-year` = 100), `base_origen` (`base_2006_retropolada` hasta 2014-11; `base_2014` desde 2014-12), `ciiu_revision` (`rev4ac`).

## Fuentes

| Fuente | Qué se usa | Archivo |
|---|---|---|
| DANE – IPP, anexo estadístico base Dic-2006=100 (CIIU Rev. 3.1 A.C.) | Índices 2006-12…2014-12 | `anex_ipp_dic14.xls` |
| DANE – IPP, anexo estadístico base Dic-2014=100 (CIIU Rev. 4 A.C.) | Índices 2014-12…presente (definitivos sobre preliminares) | `anex-IPP-<mes><año>.xlsx` |
| DANE – Tablas correlativas CIIU 3.1 A.C. ↔ 4 A.C. (2020) | Vínculos entre clases | `TC-CIIU-3-1ACvsCIIU-4AC-2020.xlsx` |
| DANE – Tablas correlativas CIIU 3 A.C. ↔ 4 A.C. (2020) | Validación de los vínculos por planta | `TC-CIIU-3ACvsCIIU-4AC-2020.xlsx` |
| DANE – EAM, microdatos anonimizados (ANDA) 2007, 2011, 2012 | Pesos por valor (`PRODBR2`) y código Rev. 3/Rev. 4 por planta | proyecto `EAM/` |
| Banco de la República – IPP por actividad económica (exportación manual) | Sectores amplios 1970–2014 y Total oficial empalmado | CSV `*_iqy.csv` |

Los datos son de los respectivos titulares (DANE, Banco de la República); este repositorio solo los transforma. Consultar sus condiciones de uso antes de redistribuir los archivos originales.

### URLs

`scripts/download_sources.py` usa las URLs del DANE bajo `https://www.dane.gov.co/files/` (`investigaciones/boletines/ipp/`, `operaciones/IPP/` y `sen/nomenclatura/tablasCorrelativas/`). El anexo vigente (base 2014) cambia de nombre con cada publicación (p. ej. `anex-IPP-sep2026.xlsx`), así que la URL se rompe cuando el DANE lo reemplaza. Para actualizar: cambiar el nombre en `FILE_ANEXO_2014` (`src/config.py`; lo usan el script y el panel) y, si cambió la carpeta, la ruta en `RAW` de `scripts/download_sources.py`. Si una descarga falla, el script lo informa y sigue con las demás.

## Método

1. **Sin cambio de clasificación (2014-12 → presente):** se usan directamente los índices de la base Dic-2014 (Rev. 4).
2. **Retropolación (2006-12 → 2014-12):** la serie Rev. 4 se reconstruye hacia atrás con la tasa de crecimiento log mensual ponderada de los grupos de la base 2006 vinculados, anclada en 2014-12. El peso de cada origen en un destino Rev. 4 es:
   - **Por valor (principal, `--weights value`).** Participación en la producción bruta (`PRODBR2`) de la EAM de las plantas que pasan de ese origen al destino. La EAM publica Rev. 3 hasta 2011 y Rev. 4 desde 2012, y `nordest` identifica al establecimiento entre años (9.289 plantas en ambos 2011 y 2012, 99,2 % del valor de 2011): el código Rev. 4 que el DANE asignó a cada planta en 2012 se cruza con su código Rev. 3 del año de referencia (doble codificación, enfoque preferido por Eurostat y la ONU; ver `retropolacion-deflactores-ciiu.md`). Solo se usan vínculos permitidos por la correlativa oficial Rev. 3 → Rev. 4; los demás son cambios de actividad o códigos enmascarados por anonimización (p. ej. una refinería codificada 3699) y se descartan: 14,1 % del valor en 2007 y 12,5 % en 2011. Las plantas que no llegan a 2012 reparten su valor según las participaciones de su clase en el mismo año (7,8 % del valor en 2007, 0,8 % en 2011). Los pesos se calculan para 2007 y 2011 y se interpolan linealmente entre ambos (constantes antes de mediados de 2007 y después de mediados de 2011). Solo para destinos manufactureros (divisiones 10–33) con plantas en la EAM; el resto usa conteo. Los códigos de grupo de la EAM (Rev. 3) coinciden con los del anexo base 2006 (99,6 % del valor de 2011 cae en grupos con índice).
   - **Por conteo (contraste, `--weights count`).** Fracción de vínculos clase-clase de la correlativa Rev. 3.1 → Rev. 4, sin ponderaciones.

   Los grupos Rev. 4 con menos de 50 % del peso en orígenes con dato en algún año de referencia usan su división padre: 020, 030, 051, 191 y 301 por valor; 020, 030, 051, 243 y 301 por conteo.

   **Agregación.** La principal es geométrica: se encadenan tasas log mensuales ponderadas, lo que admite pesos que cambian en el tiempo. Como contraste, `--aggregation arithmetic` es un Laspeyres de pesos fijos (la variante de Destatis descrita por Eurostat): los índices de origen se rebasan al promedio del año de los pesos y se promedian con ellos.

   **Grupos frágiles** (`FRAGILE_GROUPS` en `src/config.py`): 120, 261, 263, 264, 273, 301, 302 y 303 no tienen plantas con vínculo válido en la EAM pública (en 2012 no aparece ninguna planta en 261, 263, 264, 301, 303 ni 304; probablemente se agregaron por confidencialidad) y además combinan varios orígenes o tienen un origen sin índice; siguen con pesos por conteo. 191 y 323 cambian más de 5 puntos según el año de los pesos. Para todos ellos `ipp_div_fragiles` usa la división padre.
3. **Re-basado:** promedio del año `--rebase-year` = 100 por serie.
4. **Sectores amplios:** empalme por razón en el mes de traslape (base 1999 → base 2006 en 2006-12; base 2006 → base 2014 en 2014-12).

## Validación

- Total empalmado 1970–2026 vs serie oficial empalmada del BanRep: diferencia media −0.002 %, máxima 0.34 %.
- Panel de grupos: 78/78 series completas, sin huecos ni duplicados; rebasado a 100 en el año base.
- Plausibilidad frente al Total oficial (promedio simple, sin ponderadores; no es prueba de igualdad): correlación de variaciones mensuales 0.86 (2007–2014, retropolado; 0.83 con pesos por conteo) y 0.80 (2015–2026); inflación media anual del panel menor que la oficial (1.4 % vs 2.4 % y 4.1 % vs 5.4 %), esperable al no ponderar.
- Pesos por valor frente a conteo, 67 grupos manufactureros: diferencia media de nivel de 2,0 puntos log en 2007, 0,9 en 2010 y 0,4 en 2014; 10 grupos difieren en más de 5 puntos en 2007 (los mayores: 191 coque −26, 243 fundición +12, 324 juguetes −11, 210 farmacéuticos −9, 311 muebles −9, 242 metales preciosos y no ferrosos −8). Pesos solo de 2007 frente a solo de 2011: diferencia media de 0,6 puntos en 2007; solo 191 (+26) y 323 (+6) superan 2 puntos.
- Agregación aritmética frente a geométrica, ambas con pesos 2011: diferencia media de 0,13 puntos en 2007 y 0,01 en 2010; las mayores en electrónica (264: 3,7; 263: 2,2; 261: 1,6). La fórmula no cambia los resultados.
- Rango entre todas las variantes (`ipp_max`/`ipp_min`) en 2007: 4,0 puntos en promedio; 18 de 67 grupos superan 5 puntos. Los mayores vienen de usar la división padre en electrónica (263: 33; 264: 32) y aeronaves (303: 22), y del año de pesos en coque (191: 26). En 2010 el rango medio baja a 1,6 puntos.
- Pruebas automáticas en `tests/` (parsing de fuentes, retropolación sobre datos sintéticos y propiedades de los archivos finales).

### Casos atípicos

Criterio: variación mensual con |z| > 3 respecto a la propia serie (`PanelValidator.check_outliers`, método `growth_rate`). Lista completa en `data/final/atipicos_ciiu3d.csv` (`mayor_15pct` distingue los dos grupos; leer `ciiu_codigo` como texto para no perder ceros).

**A. Con variación mensual superior a 15 % (21 casos).** Casi todos son extractivas (petróleo, gas, carbón, minerales) en fechas de shocks conocidos (caída de 2008-09, pandemia de 2020). Los de manufactura y agro (272, 107, 191, 011) no están verificados contra el boletín del DANE.

| Fecha | Grupo | Descripción | Var. mensual | Tramo |
|---|---|---|---|---|
| 2008-08 | 272 | Fabricación de pilas, baterías y acumuladores eléctricos | +15.1 % | retropolado |
| 2008-10 | 051 | Extracción de hulla (carbón de piedra) | -22.3 % | retropolado |
| 2008-10 | 089 | Extracción de otros minerales no metálicos n.c.p. | +17.2 % | retropolado |
| 2009-01 | 061 | Extracción de petróleo crudo | -28.9 % | retropolado |
| 2009-01 | 062 | Extracción de gas natural | -28.9 % | retropolado |
| 2009-03 | 051 | Extracción de hulla (carbón de piedra) | -17.7 % | retropolado |
| 2009-06 | 062 | Extracción de gas natural | +25.2 % | retropolado |
| 2016-08 | 011 | Cultivos agrícolas transitorios | -21.4 % | observado |
| 2020-03 | 061 | Extracción de petróleo crudo | -42.9 % | observado |
| 2020-04 | 061 | Extracción de petróleo crudo | -33.6 % | observado |
| 2020-06 | 061 | Extracción de petróleo crudo | +60.8 % | observado |
| 2021-04 | 107 | Elaboración de azúcar y panela | +15.1 % | observado |
| 2021-11 | 051 | Extracción de hulla (carbón de piedra) | +18.7 % | observado |
| 2022-01 | 191 | Fabricación de productos de hornos de coque | +15.2 % | observado |
| 2022-04 | 051 | Extracción de hulla (carbón de piedra) | +18.6 % | observado |
| 2022-05 | 107 | Elaboración de azúcar y panela | +15.7 % | observado |
| 2023-07 | 062 | Extracción de gas natural | -18.3 % | observado |
| 2024-05 | 051 | Extracción de hulla (carbón de piedra) | -19.6 % | observado |
| 2025-02 | 081 | Extracción de piedra, arena, arcillas, cal, yeso, caolín, be | -21.3 % | observado |
| 2025-08 | 062 | Extracción de gas natural | +36.1 % | observado |
| 2026-03 | 061 | Extracción de petróleo crudo | +57.7 % | observado |

**B. Con variación mensual de 15 % o menos (333 casos).** 333 casos con |variación mensual| ≤ 15 % (máx. 14.8 %; 54 entre 10 % y 15 %; mediana 4.9 %). Son marcados porque la serie es poco volátil, no por magnitud; no se consideran errores. Ninguno se ha revisado individualmente.

## Justificación del nivel de 3 dígitos (grupo CIIU)

Se propone el grupo (3 dígitos) como nivel objetivo por dos razones:

1. **Sesgo por precios no observados.** Con datos de planta se observa valor, no cantidades. Si el deflactor es muy agregado, la razón entre el precio de la firma y el del deflactor queda en el residuo y se correlaciona con los insumos, lo que sesga a la baja los retornos a escala (Klette & Griliches, 1996; De Loecker, 2011). A 2 dígitos se asume el mismo precio para ramas muy distintas (p. ej. azúcar y panadería); a 3 dígitos se separan aceites, carnes, lácteos, café.
2. **Compromiso con la continuidad.** A 4 dígitos las reclasificaciones CIIU Rev 2→3→4 rompen muchas series; a 3 dígitos la correlativa del DANE permite un empalme razonable. La literatura sobre la EAM colombiana (Eslava et al.; panel armonizado del CEDE) usa deflactores de 3–4 dígitos.

| Criterio | 2 dígitos | 3 dígitos | 4 dígitos |
|---|---|---|---|
| Separación de precios | Muy baja | Alta | Muy alta |
| Estabilidad del empalme CIIU | Alta | Buena | Deficiente |

## Limitaciones y trabajo pendiente

1. **Grupos frágiles sin solución con los datos públicos.** Para los 10 grupos de `FRAGILE_GROUPS` el deflactor 2007–2014 depende de una elección sin respaldo en datos (conteo o división padre). En electrónica (263, 264) la diferencia entre ambas llega a 30 puntos en 2007. 191 (coque) termina en la división padre, dominada por la refinación. En la Translog conviene probar la robustez excluyendo estos grupos o usando `ipp_div_fragiles`. Resolverlo exige microdatos con códigos sin enmascarar o ponderaciones del IPP base 2006. La EAM excluye plantas pequeñas, así que los pesos representan la industria de 10 o más ocupados.
2. **Chequeo ponderado contra el Total oficial** (requiere ponderadores) y revisión individual de atípicos/quiebres de `PanelValidator` (354 atípicos y 102 "quiebres" con umbrales por defecto; sin errores de empalme evidentes).
3. **Nivel de clase (4 dígitos):** no implementado; la literatura lo considera inviable para series largas.
4. **Unión con la EAM:** falta el diccionario CIIU de las firmas → grupo del panel (la EAM usa Rev. 3 o Rev. 4 según el año).
5. **Ampliar a 1992–2005:** requiere series por rama del BanRep (base 1990 y 1999; hoy solo hay 4 sectores amplios), correlativas Rev. 2→3→4 y los empalmes 1990→1999 y 1999→2006 a nivel rama.
6. **Agro (sectores amplios):** la base 2006 separa Pesca (sección B) y las bases 1999 y 2014 la incluyen en Agro; el empalme usa solo la sección A en 2006.

## Licencia

El código se distribuye bajo la licencia MIT (ver `LICENSE`). Los datos de origen pertenecen al DANE y al Banco de la República y conservan sus propias condiciones de uso (ver [Fuentes](#fuentes)).

## Cómo citar

Ver `CITATION.cff`.
