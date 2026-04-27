"""Dashboard HAK · Mercado Público — versión pública (Streamlit Cloud).

Lee CSVs versionados (data/oportunidades.csv, data/competencia.csv) que se
actualizan vía git push desde el scanner local.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="HAK — Inteligencia Mercado Público",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #f8fafc; padding: 12px; border-radius: 8px;
    border-left: 4px solid #1F4E78;
}
.estado-abierto { background:#16a34a; color:white; padding:2px 8px; border-radius:12px; font-size:0.85em; font-weight:bold; }
.alta { background:#dc2626; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em; }
.media { background:#d97706; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    op_path = DATA / "oportunidades.csv"
    comp_path = DATA / "competencia.csv"
    meta_path = DATA / "meta.json"
    op = pd.read_csv(op_path) if op_path.exists() else pd.DataFrame()
    comp = pd.read_csv(comp_path) if comp_path.exists() else pd.DataFrame()
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return op, comp, meta


op, comp, meta = load_data()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://fundacionhelenadamskeller.com/favicon.ico", width=80)
    st.title("🎓 HAK")
    st.caption("Fundación Helen Adams Keller · Educación Macrozona Sur")
    st.divider()

    if meta.get("ultima_actualizacion"):
        st.caption(f"📅 Última actualización: **{meta['ultima_actualizacion']}**")
    if meta.get("scan_fecha"):
        st.caption(f"🔍 Scan: {meta['scan_fecha']}")
    st.caption(f"🌐 [Repositorio]({meta.get('repo', 'https://github.com')})")

    st.divider()
    st.subheader("Filtros")

    if not op.empty:
        regiones = sorted(op["region"].dropna().unique())
        region_sel = st.multiselect("Región", regiones, default=[])
        prio_sel = st.multiselect("Prioridad", ["ALTA", "MEDIA"], default=["ALTA", "MEDIA"])
        urg_sel = st.multiselect("Urgencia", ["CRITICA", "URGENTE", "PRONTA", "NORMAL"],
                                  default=["CRITICA", "URGENTE", "PRONTA", "NORMAL"])
        score_min = st.slider("Score mínimo", 0, 100, 5)
        monto_min_M = st.slider("Monto mínimo (M CLP)", 0, 100, 0)
    else:
        region_sel, prio_sel, urg_sel, score_min, monto_min_M = [], [], [], 0, 0

# ─── Header ──────────────────────────────────────────────────────────────────
st.title("🎓 Inteligencia de Mercado Público — Fundación HAK")
if op.empty and comp.empty:
    st.warning("No hay datos cargados. Espera al próximo `actualizar_datos.py`.")
    st.stop()

# ─── Filtros aplicados ───────────────────────────────────────────────────────
op_f = op.copy()
if not op.empty:
    if region_sel:
        op_f = op_f[op_f["region"].isin(region_sel)]
    if prio_sel:
        op_f = op_f[op_f["priority"].isin(prio_sel)]
    if urg_sel:
        op_f = op_f[op_f["urgencia"].isin(urg_sel)]
    op_f = op_f[op_f["score"] >= score_min]
    if monto_min_M > 0:
        op_f = op_f[(op_f["monto"].fillna(0) >= monto_min_M * 1_000_000)]

# ─── Métricas ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Oportunidades activas", len(op_f) if not op_f.empty else 0)
c2.metric("Alta prioridad", int((op_f["priority"] == "ALTA").sum()) if not op_f.empty else 0)
c3.metric("Críticas/Urgentes", int(op_f["urgencia"].isin(["CRITICA", "URGENTE"]).sum()) if not op_f.empty else 0)
c4.metric("Cliente previo", int(op_f["cliente_previo"].sum()) if not op_f.empty and "cliente_previo" in op_f.columns else 0)
monto_total = op_f["monto"].sum() if not op_f.empty else 0
c5.metric("Monto total", f"${monto_total/1e6:,.0f}M CLP")

st.divider()

tab_op, tab_top, tab_comp, tab_org, tab_geo = st.tabs([
    "🎯 Oportunidades activas", "🏆 TOP del día", "🥊 Competencia 365d",
    "🏛 Organismos compradores", "📍 Geografía"
])


# ─── TAB 1: Oportunidades activas ────────────────────────────────────────────
with tab_op:
    if op_f.empty:
        st.info("Sin oportunidades con filtros actuales.")
    else:
        st.dataframe(
            op_f[["score", "priority", "urgencia", "horas_restantes",
                   "organismo", "region", "nombre", "monto",
                   "cliente_previo", "organismo_prioritario", "oportunidad_estructural",
                   "matched_high", "codigo", "url"]],
            use_container_width=True, height=600,
            column_config={
                "score": st.column_config.NumberColumn("Score"),
                "priority": "Prio",
                "urgencia": "Urgencia",
                "horas_restantes": st.column_config.NumberColumn("Hrs"),
                "organismo": "Organismo",
                "region": "Región",
                "nombre": "Licitación",
                "monto": st.column_config.NumberColumn("Monto CLP", format="$%d"),
                "cliente_previo": st.column_config.CheckboxColumn("🏆 Cli"),
                "organismo_prioritario": st.column_config.CheckboxColumn("🎯 Prio"),
                "oportunidad_estructural": "⚡ Estructural",
                "matched_high": "Keywords",
                "codigo": "Código",
                "url": st.column_config.LinkColumn("🔗"),
            }
        )


# ─── TAB 2: TOP del día ──────────────────────────────────────────────────────
with tab_top:
    if op_f.empty:
        st.info("Sin oportunidades para el TOP.")
    else:
        for i, r in op_f.head(10).iterrows():
            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    badges = []
                    if r.get("cliente_previo"):
                        badges.append("🏆 CLIENTE PREVIO")
                    if r.get("organismo_prioritario"):
                        badges.append("🎯 ORG PRIORITARIO")
                    if pd.notna(r.get("oportunidad_estructural")) and r.get("oportunidad_estructural"):
                        badges.append(f"⚡ {r['oportunidad_estructural'][:30]}")
                    badge_str = " · ".join(badges)
                    st.markdown(f"### {r['nombre']}")
                    st.caption(f"🏛 **{r.get('organismo','—')}** · 📍 {r.get('region','—')} · "
                               f"💰 ${(r.get('monto') or 0)/1e6:.1f}M CLP")
                    if badge_str:
                        st.markdown(f"`{badge_str}`")
                    if pd.notna(r.get("matched_high")) and r.get("matched_high"):
                        st.caption(f"🔑 {r['matched_high']}")
                    if pd.notna(r.get("url")) and r.get("url"):
                        st.markdown(f"[🔗 Ver en Mercado Público]({r['url']})")
                with col_b:
                    st.metric("Score", int(r.get("score", 0)))
                    st.caption(f"{r.get('urgencia','')}")


# ─── TAB 3: Competencia 365d ──────────────────────────────────────────────────
with tab_comp:
    if comp.empty:
        st.info("No hay datos de competencia. Ejecuta `python competencia.py --dias 365`.")
    else:
        st.markdown(f"**{len(comp)} competidores únicos** detectados en últimos 365 días.")
        col_a, col_b = st.columns(2)
        top_n = comp.head(20).copy()
        with col_a:
            st.subheader("TOP 20 por # contratos")
            fig = px.bar(top_n, x="n_contratos", y="proveedor", orientation="h",
                         color="monto_total", color_continuous_scale="Blues",
                         hover_data={"rut": True})
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600,
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("TOP 20 por monto")
            top_m = comp.sort_values("monto_total", ascending=False).head(20)
            fig2 = px.bar(top_m, x="monto_total", y="proveedor", orientation="h",
                          color="n_contratos", color_continuous_scale="Oranges",
                          hover_data={"rut": True})
            fig2.update_layout(yaxis={"categoryorder": "total ascending"}, height=600,
                               margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig2, use_container_width=True)
        st.divider()
        st.dataframe(comp, use_container_width=True, height=500)


# ─── TAB 4: Organismos compradores ───────────────────────────────────────────
with tab_org:
    if op.empty:
        st.info("Sin datos.")
    else:
        org_df = (op.groupby("organismo", as_index=False)
                  .agg(licitaciones=("codigo", "count"), monto_total=("monto", "sum"))
                  .sort_values("licitaciones", ascending=False).head(25))
        org_df = org_df[org_df["organismo"].notna() & (org_df["organismo"] != "")]
        fig = px.bar(org_df.head(20), x="licitaciones", y="organismo", orientation="h",
                     color="monto_total", color_continuous_scale="Greens")
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600,
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(org_df, use_container_width=True)


# ─── TAB 5: Geografía ────────────────────────────────────────────────────────
with tab_geo:
    if op.empty:
        st.info("Sin datos.")
    else:
        reg_df = (op.groupby("region", as_index=False)
                  .agg(licitaciones=("codigo", "count"), monto_total=("monto", "sum"))
                  .sort_values("licitaciones", ascending=False))
        reg_df = reg_df[reg_df["region"].notna() & (reg_df["region"] != "")]
        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(reg_df, x="licitaciones", y="region", orientation="h",
                         color="monto_total", color_continuous_scale="Blues")
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            if reg_df["monto_total"].sum() > 0:
                fig2 = px.treemap(reg_df, path=["region"], values="monto_total",
                                   color="licitaciones", color_continuous_scale="Viridis")
                fig2.update_layout(height=500, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(reg_df, use_container_width=True)


st.divider()
st.caption("⚠️ Datos extraídos de la API oficial Mercado Público (ChileCompra). "
           f"Última actualización: {meta.get('ultima_actualizacion', '—')}")
