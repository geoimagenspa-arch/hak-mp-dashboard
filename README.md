# HAK · Inteligencia Mercado Público — Dashboard público

Versión deployada en Streamlit Community Cloud para el equipo de
**Fundación Helen Adams Keller**.

## URL en producción

Pendiente de deploy → se completa al conectar a Streamlit Cloud.

## Cómo se actualiza

El scanner local (no incluido en este repo) corre 3 veces al día sobre la API
oficial de Mercado Público. Después de cada scan, ejecuta:

```bash
python ../src/actualizar_datos_streamlit.py
```

Esto:
1. Exporta los JSON locales del último scan a CSVs en `data/`
2. Hace `git add` + `commit` + `push` a este repo
3. Streamlit Cloud detecta el push y redeploya automáticamente (~2 min)

## Datos contenidos

- `data/oportunidades.csv` — licitaciones activas detectadas
- `data/competencia.csv` — ranking de competidores año móvil
- `data/meta.json` — fecha de actualización + metadatos

## Stack

- Streamlit 1.32+
- Pandas 2.x
- Plotly 5.18+

## Stack scanner (no incluido aquí)

Ver carpeta `Mercadopublico/src/` del proyecto principal.
