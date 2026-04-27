"""Dashboard HAK · Inteligencia Mercado Público + Fondos Concursables.

Versión deployada en Streamlit Community Cloud.
Lee CSVs versionados en data/ que se actualizan vía git push desde el scanner local.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="HAK — Inteligencia Mercado",
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
.estado-proximo { background:#d97706; color:white; padding:2px 8px; border-radius:12px; font-size:0.85em; font-weight:bold; }
.estado-cerrado { background:#dc2626; color:white; padding:2px 8px; border-radius:12px; font-size:0.85em; }
.alta { background:#dc2626; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em; }
.media { background:#d97706; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    op_path = DATA / "oportunidades.csv"
    comp_path = DATA / "competencia.csv"
    fondos_path = DATA / "fondos.csv"
    meta_path = DATA / "meta.json"
    op = pd.read_csv(op_path) if op_path.exists() else pd.DataFrame()
    comp = pd.read_csv(comp_path) if comp_path.exists() else pd.DataFrame()
    fondos = pd.read_csv(fondos_path) if fondos_path.exists() else pd.DataFrame()
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return op, comp, fondos, meta


op, comp, fondos, meta = load_data()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🎓 HAK")
    st.caption("Fundación Helen Adams Keller · Macrozona Sur")
    st.divider()

    if meta.get("ultima_actualizacion"):
        st.caption(f"📅 Actualizado: **{meta['ultima_actualizacion']}**")
    if meta.get("scan_fecha"):
        st.caption(f"🔍 Scan MP: {meta['scan_fecha']}")
    if meta.get("ranking_fecha"):
        st.caption(f"🏆 Competencia: {meta['ranking_fecha']}")

    st.divider()
    st.subheader("Filtros (Mercado Público)")
    if not op.empty:
        regiones = sorted([r for r in op["region"].dropna().unique() if r])
        region_sel = st.multiselect("Región", regiones, default=[])
        prio_sel = st.multiselect("Prioridad", ["ALTA", "MEDIA"], default=["ALTA", "MEDIA"])
        urg_sel = st.multiselect("Urgencia",
                                  ["CRITICA", "URGENTE", "PRONTA", "NORMAL"],
                                  default=["CRITICA", "URGENTE", "PRONTA", "NORMAL"])
        score_min = st.slider("Score mínimo", 0, 100, 5)
        monto_min_M = st.slider("Monto mínimo (M CLP)", 0, 100, 0)
    else:
        region_sel, prio_sel, urg_sel, score_min, monto_min_M = [], [], [], 0, 0

# ─── Header ──────────────────────────────────────────────────────────────────
st.title("🎓 Inteligencia de Mercado · Fundación HAK")
if op.empty and comp.empty and fondos.empty:
    st.warning("No hay datos cargados. Espera al próximo `actualizar_datos_streamlit.py`.")
    st.stop()

# ─── Filtros aplicados a oportunidades MP ────────────────────────────────────
op_f = op.copy()
if not op.empty:
    if region_sel:
        op_f = op_f[op_f["region"].isin(region_sel)]
    if prio_sel:
        op_f = op_f[op_f["priority"].isin(prio_sel)]
    if urg_sel:
        op_f = op_f[op_f["urgencia"].isin(urg_sel)]
    op_f = op_f[op_f["score"].fillna(0) >= score_min]
    if monto_min_M > 0:
        op_f = op_f[op_f["monto"].fillna(0) >= monto_min_M * 1_000_000]

# ─── Métricas ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Oportunidades MP", len(op_f) if not op_f.empty else 0)
c2.metric("Alta prioridad",
          int((op_f["priority"] == "ALTA").sum()) if not op_f.empty else 0)
c3.metric("Críticas/Urgentes",
          int(op_f["urgencia"].isin(["CRITICA", "URGENTE"]).sum()) if not op_f.empty else 0)
monto_total = op_f["monto"].sum() if not op_f.empty else 0
c4.metric("Monto activo MP", f"${monto_total/1e6:,.0f}M CLP")
c5.metric("Competidores año", len(comp) if not comp.empty else 0)
c6.metric("Fondos abiertos",
          int((fondos["estado"] == "abierto").sum()) if not fondos.empty else 0)

st.divider()

tabs = st.tabs([
    "🎯 Oportunidades MP",
    "🏆 TOP del día",
    "🥊 Competencia 365d",
    "🔁 Cross-Reference",
    "📈 Evolución",
    "🔍 HAK vs Mercado",
    "🏛 Organismos",
    "📍 Geografía",
    "💰 Fondos Concursables",
])


# ─── TAB 1: Oportunidades MP ─────────────────────────────────────────────────
with tabs[0]:
    if op_f.empty:
        st.info("Sin oportunidades con los filtros actuales.")
    else:
        st.dataframe(
            op_f[["score", "priority", "urgencia", "horas_restantes",
                   "organismo", "region", "nombre", "monto",
                   "cliente_previo", "organismo_prioritario", "oportunidad_estructural",
                   "matched_high", "codigo", "url"]],
            use_container_width=True, height=600,
            column_config={
                "score": st.column_config.NumberColumn("Score"),
                "priority": "Prio", "urgencia": "Urg",
                "horas_restantes": st.column_config.NumberColumn("Hrs"),
                "organismo": "Organismo", "region": "Región",
                "nombre": "Licitación",
                "monto": st.column_config.NumberColumn("Monto CLP", format="$%d"),
                "cliente_previo": st.column_config.CheckboxColumn("🏆"),
                "organismo_prioritario": st.column_config.CheckboxColumn("🎯"),
                "oportunidad_estructural": "⚡ Estructural",
                "matched_high": "Keywords",
                "codigo": "Código",
                "url": st.column_config.LinkColumn("🔗"),
            }
        )


# ─── TAB 2: TOP del día ──────────────────────────────────────────────────────
with tabs[1]:
    if op_f.empty:
        st.info("Sin oportunidades para el TOP.")
    else:
        for _, r in op_f.head(10).iterrows():
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
                    st.caption(f"🏛 **{r.get('organismo','—')}** · "
                               f"📍 {r.get('region','—')} · "
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


# ─── TAB 3: Competencia 365d ─────────────────────────────────────────────────
with tabs[2]:
    if comp.empty:
        st.info("No hay datos de competencia.")
    else:
        st.markdown(f"**{len(comp)} competidores únicos** detectados en últimos 365 días.")
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("TOP 20 por # contratos")
            top_n = comp.head(20)
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


# ─── TAB 4: Cross-Reference ──────────────────────────────────────────────────
with tabs[3]:
    st.markdown("### Para cada oportunidad activa, ¿quién ganó licitaciones similares en este organismo?")
    if op.empty or comp.empty:
        st.info("Necesita datos de oportunidades + competencia.")
    else:
        # Agrupar competidores por organismos donde han ganado
        # comp tiene "organismos_top" (texto separado por · )
        rows = []
        for _, opp in op.iterrows():
            org_target = (opp.get("organismo") or "").strip()
            if not org_target:
                continue
            # Buscar competidores que han ganado en este organismo
            matches = comp[comp["organismos_top"].fillna("").str.contains(
                org_target, regex=False, na=False)]
            top3 = matches.head(3)
            top_str = " · ".join(f"{r['proveedor'][:30]} ({r['n_contratos']})"
                                 for _, r in top3.iterrows()) if not top3.empty else "—"
            rows.append({
                "score": opp.get("score", 0),
                "urgencia": opp.get("urgencia"),
                "organismo": opp.get("organismo"),
                "licitacion": (opp.get("nombre") or "")[:80],
                "monto": opp.get("monto") or 0,
                "n_competidores_historicos": len(matches),
                "top_3_competidores_historicos": top_str,
                "codigo": opp.get("codigo"),
            })
        cross_df = pd.DataFrame(rows).sort_values(
            ["n_competidores_historicos", "score"], ascending=[False, False])
        c1, c2, c3 = st.columns(3)
        c1.metric("Con historia", (cross_df["n_competidores_historicos"] > 0).sum())
        c2.metric("Vírgenes", (cross_df["n_competidores_historicos"] == 0).sum())
        c3.metric("≥ 3 competidores", (cross_df["n_competidores_historicos"] >= 3).sum())
        st.dataframe(
            cross_df,
            use_container_width=True, height=600,
            column_config={
                "monto": st.column_config.NumberColumn("Monto CLP", format="$%d"),
                "n_competidores_historicos": st.column_config.NumberColumn("# Hist"),
            }
        )


# ─── TAB 5: Evolución ────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown("### Distribución y trends del mercado")
    if op.empty:
        st.info("Sin datos.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Distribución por urgencia")
            urg_count = op["urgencia"].value_counts().reset_index()
            urg_count.columns = ["urgencia", "n"]
            fig = px.pie(urg_count, names="urgencia", values="n",
                         color="urgencia",
                         color_discrete_map={"CRITICA": "#dc2626", "URGENTE": "#d97706",
                                              "PRONTA": "#eab308", "NORMAL": "#16a34a"})
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("Distribución por monto (rangos)")
            def bucket(m):
                if pd.isna(m) or m == 0: return "Sin monto"
                if m < 1e6: return "<1M"
                if m < 5e6: return "1-5M"
                if m < 10e6: return "5-10M"
                if m < 30e6: return "10-30M"
                if m < 100e6: return "30-100M"
                return ">100M"
            op_b = op.copy()
            op_b["bucket"] = op_b["monto"].apply(bucket)
            order = ["Sin monto", "<1M", "1-5M", "5-10M", "10-30M", "30-100M", ">100M"]
            buckets = op_b.groupby("bucket").size().reindex(order, fill_value=0).reset_index()
            buckets.columns = ["rango", "n"]
            fig2 = px.bar(buckets, x="rango", y="n", color="rango")
            fig2.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)


# ─── TAB 6: HAK vs Mercado ───────────────────────────────────────────────────
with tabs[5]:
    st.markdown("### 🎓 Posición de Fundación HAK en el mercado")
    if comp.empty:
        st.info("Sin datos de competencia.")
    else:
        hak = comp[comp["rut"].fillna("").str.contains("65.166.177", na=False)]
        if not hak.empty:
            h = hak.iloc[0]
            pos = comp.reset_index(drop=True).index[
                comp["rut"].fillna("").str.contains("65.166.177", na=False)
            ].tolist()
            posicion = (pos[0] + 1) if pos else None
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Posición ranking", f"#{posicion} de {len(comp)}" if posicion else "n/a")
            c2.metric("Contratos (12m)", int(h["n_contratos"]))
            c3.metric("Monto adjudicado", f"${h['monto_total']/1e6:,.1f}M")
            cuota = (h["n_contratos"] / comp["n_contratos"].sum()) * 100 if comp["n_contratos"].sum() else 0
            c4.metric("Cuota mercado", f"{cuota:.4f}%")
        else:
            st.info("HAK no aparece en adjudicaciones del último año.")

        st.divider()
        st.subheader("Comparativa visual con TOP 10 competidores")
        top10 = comp.head(10).copy()
        if not hak.empty and not (top10["rut"].fillna("").str.contains("65.166.177", na=False)).any():
            top10 = pd.concat([top10, hak], ignore_index=True)
        top10["es_hak"] = top10["rut"].fillna("").str.contains("65.166.177", na=False)
        fig = px.bar(top10.sort_values("n_contratos"), x="n_contratos", y="proveedor",
                     orientation="h", color="es_hak",
                     color_discrete_map={True: "#dc2626", False: "#3b82f6"})
        fig.update_layout(height=500, showlegend=False, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)


# ─── TAB 7: Organismos ───────────────────────────────────────────────────────
with tabs[6]:
    if op.empty:
        st.info("Sin datos.")
    else:
        org_df = (op.groupby("organismo", as_index=False)
                  .agg(licitaciones=("codigo", "count"),
                       monto_total=("monto", "sum"))
                  .sort_values("licitaciones", ascending=False).head(25))
        org_df = org_df[org_df["organismo"].notna() & (org_df["organismo"] != "")]
        st.subheader("TOP 20 organismos compradores activos")
        fig = px.bar(org_df.head(20), x="licitaciones", y="organismo", orientation="h",
                     color="monto_total", color_continuous_scale="Greens")
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600,
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(org_df, use_container_width=True)


# ─── TAB 8: Geografía ────────────────────────────────────────────────────────
with tabs[7]:
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


# ─── TAB 9: Fondos Concursables ──────────────────────────────────────────────
with tabs[8]:
    st.markdown("### 💰 Fondos Concursables relevantes para HAK")
    st.caption("FONDART, ANID, FNDR, FOSIS, MINEDUC, BID, OEI, etc. — filtrado por score_hak > 0")

    if fondos.empty:
        st.info("No hay datos de fondos.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total fondos HAK", len(fondos))
        c2.metric("🟢 Abiertos", int((fondos["estado"] == "abierto").sum()))
        c3.metric("🟡 Próximos", int((fondos["estado"] == "proximo").sum()))
        c4.metric("🌍 Internacionales", int(fondos.get("internacional", 0).fillna(0).sum()))

        st.divider()
        # Filtros locales
        col_a, col_b = st.columns(2)
        with col_a:
            estado_f = st.multiselect("Estado fondo",
                                       ["abierto", "proximo", "cerrado", "desconocido"],
                                       default=["abierto", "proximo"], key="fondo_estado")
        with col_b:
            tipo_f = st.multiselect("Tipo fondo",
                                     ["empresarial", "cultural", "ciencia", "comunitario", "mixto"],
                                     default=[], key="fondo_tipo")

        f_show = fondos.copy()
        if estado_f:
            f_show = f_show[f_show["estado"].isin(estado_f)]
        if tipo_f:
            f_show = f_show[f_show["tipo"].isin(tipo_f)]
        f_show = f_show.sort_values("score_hak", ascending=False)

        st.markdown(f"**{len(f_show)} fondos** con los filtros actuales")
        for _, r in f_show.head(20).iterrows():
            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    intl = "🌍 " if r.get("internacional") else ""
                    estado = r.get("estado", "desconocido")
                    badge = {"abierto": "🟢 ABIERTO", "proximo": "🟡 PRÓXIMO",
                             "cerrado": "🔴 CERRADO"}.get(estado, "⚪ DESC")
                    st.markdown(f"### {intl}{r['nombre']}")
                    st.caption(f"🏛 **{r.get('organismo','—')}** · "
                               f"📁 {r.get('tipo','—')} · "
                               f"{badge}"
                               + (f" · 📍 {r['region']}" if pd.notna(r.get('region')) and r.get('region') else ""))
                    if pd.notna(r.get("descripcion")) and r.get("descripcion"):
                        st.markdown(f"<small>{str(r['descripcion'])[:300]}{'...' if len(str(r.get('descripcion','')))>300 else ''}</small>",
                                    unsafe_allow_html=True)
                    monto_str = ""
                    if pd.notna(r.get("monto_min")) and r.get("monto_min"):
                        monto_str = f"💰 desde ${r['monto_min']/1e6:.1f}M {r.get('moneda','')}"
                        if pd.notna(r.get("monto_max")) and r.get("monto_max"):
                            monto_str += f" hasta ${r['monto_max']/1e6:.1f}M"
                        st.caption(monto_str)
                    if pd.notna(r.get("fecha_cierre")) and r.get("fecha_cierre"):
                        st.caption(f"📅 Cierre: {r['fecha_cierre']}")
                    if pd.notna(r.get("url")) and r.get("url"):
                        st.markdown(f"[🔗 Ver convocatoria]({r['url']})")
                with col_b:
                    st.metric("Score", int(r.get("score_hak", 0)))

        st.divider()
        st.dataframe(f_show, use_container_width=True, height=400)


st.divider()
st.caption(f"⚠️ Datos de la API oficial Mercado Público (ChileCompra) y scrapers de Fondos. "
           f"Última actualización: {meta.get('ultima_actualizacion', '—')}")
