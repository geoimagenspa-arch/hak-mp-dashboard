"""Dashboard HAK · Inteligencia Mercado Público + Fondos Concursables.

Versión deployada en Streamlit Community Cloud.
Lee CSVs versionados en data/ que se actualizan vía git push desde el scanner local.
"""
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


REPO_OWNER = "geoimagenspa-arch"
REPO_NAME = "hak-mp-dashboard"
REVISIONES_PATH = "data/revisiones.json"
REVISORES = ["Claudia Vivallo", "Camila Garay", "Paola Rocha"]
ESTADOS = {
    "sirve": ("✅ Sirve", "#16a34a"),
    "no_sirve": ("❌ No sirve", "#dc2626"),
    "en_proceso": ("⏳ En proceso", "#d97706"),
    "postulada": ("📨 Postulada", "#2563eb"),
}


@st.cache_data(ttl=15)
def cargar_revisiones() -> dict:
    """Carga revisiones desde el repo público (raw GitHub)."""
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{REVISIONES_PATH}"
    try:
        r = requests.get(url, timeout=5)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}


def guardar_revision(codigo: str, estado: str, comentario: str, revisor: str) -> bool:
    """Guarda una revisión en data/revisiones.json del repo (vía GitHub Contents API)."""
    token = st.secrets.get("github_token", None)
    if not token:
        st.error("⚠️ Falta `github_token` en Streamlit Secrets. Pide a Nicolás configurarlo.")
        return False

    api = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{REVISIONES_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    # 1) Get current SHA + content
    sha = None
    current = {}
    try:
        r = requests.get(api, headers=headers, timeout=8)
        if r.ok:
            data = r.json()
            sha = data.get("sha")
            decoded = base64.b64decode(data["content"]).decode("utf-8")
            current = json.loads(decoded) if decoded.strip() else {}
    except Exception as e:
        st.warning(f"No se pudo leer revisiones existentes: {e}")

    # 2) Update record
    current[codigo] = {
        "estado": estado,
        "comentario": comentario or "",
        "revisor": revisor,
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # 3) PUT new content
    new_b64 = base64.b64encode(
        json.dumps(current, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    payload = {
        "message": f"rev: {codigo} → {estado} by {revisor}",
        "content": new_b64,
    }
    if sha:
        payload["sha"] = sha
    try:
        r = requests.put(api, headers=headers, json=payload, timeout=15)
        if r.ok:
            # Actualizar session_state INMEDIATAMENTE (no espera CDN GitHub)
            if "revisiones_local" not in st.session_state:
                st.session_state.revisiones_local = {}
            st.session_state.revisiones_local[codigo] = current[codigo]
            cargar_revisiones.clear()  # solo este cache, no todo
            return True
        st.error(f"Error guardando ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        st.error(f"Excepción guardando: {e}")
    return False


def fmt_fecha(s: str) -> str:
    """Formatea ISO datetime a 'DD/MM/YYYY HH:MM'."""
    if not s or pd.isna(s):
        return "—"
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "").split(".")[0])
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(s)[:10]


def render_revision_widget(codigo: str, revisiones: dict, key_prefix: str):
    """Render compacto del widget de revisión bajo cada licitación."""
    rev = revisiones.get(codigo, {})
    if rev:
        nom, color = ESTADOS.get(rev["estado"], ("?", "#6b7280"))
        st.markdown(
            f"<div style='background:{color}20; padding:8px; border-radius:6px; "
            f"border-left:4px solid {color}; margin:4px 0;'>"
            f"<b style='color:{color}'>{nom}</b> · "
            f"por <b>{rev.get('revisor','?')}</b> · "
            f"{fmt_fecha(rev.get('fecha'))}<br>"
            f"<small>💬 {rev.get('comentario') or '(sin comentario)'}</small>"
            "</div>", unsafe_allow_html=True,
        )

    with st.expander("✏️ Marcar / Actualizar revisión", expanded=False):
        revisor = st.selectbox("Revisor", REVISORES,
                                key=f"{key_prefix}_rev_{codigo}",
                                index=0)
        comentario = st.text_area("Comentario (opcional)",
                                   value=rev.get("comentario", ""),
                                   key=f"{key_prefix}_com_{codigo}",
                                   height=68)
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("✅ Sirve", key=f"{key_prefix}_si_{codigo}", use_container_width=True):
            if guardar_revision(codigo, "sirve", comentario, revisor):
                st.success("Guardado"); st.rerun()
        if c2.button("⏳ En proceso", key=f"{key_prefix}_pr_{codigo}", use_container_width=True):
            if guardar_revision(codigo, "en_proceso", comentario, revisor):
                st.success("Guardado"); st.rerun()
        if c3.button("📨 Postulada", key=f"{key_prefix}_po_{codigo}", use_container_width=True):
            if guardar_revision(codigo, "postulada", comentario, revisor):
                st.success("Guardado"); st.rerun()
        if c4.button("❌ No sirve", key=f"{key_prefix}_no_{codigo}", use_container_width=True):
            if guardar_revision(codigo, "no_sirve", comentario, revisor):
                st.success("Guardado · ahora oculta"); st.rerun()

ROOT = Path(__file__).parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="HAK — Inteligencia Mercado",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

def check_password():
    """Gate simple por contraseña usando st.secrets."""
    def password_entered():
        if st.session_state["password"] == st.secrets.get("password", "hak2026"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("# 🎓 HAK · Inteligencia de Mercado")
        st.markdown("### 🔐 Acceso restringido")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.caption("Solicita la contraseña al equipo HAK.")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.markdown("# 🎓 HAK · Inteligencia de Mercado")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.error("❌ Contraseña incorrecta")
        st.stop()


check_password()


st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #f8fafc; padding: 6px 10px; border-radius: 6px;
    border-left: 3px solid #1F4E78;
}
[data-testid="stMetricLabel"] p {
    font-size: 0.78rem !important;
    color: #475569 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    line-height: 1.4 !important;
    font-weight: 600 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
}
h1 {
    font-size: 1.6rem !important;
    margin-bottom: 0.3rem !important;
    padding-top: 0 !important;
}
.block-container {
    padding-top: 1.5rem !important;
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
# Carga remota (cacheada 15s) + overrides locales de esta sesión (instantáneos)
revisiones = cargar_revisiones()
if "revisiones_local" in st.session_state:
    revisiones = {**revisiones, **st.session_state.revisiones_local}

# Convertir fechas a datetime para que DatetimeColumn las renderice
if not op.empty:
    if "fecha_publicacion" in op.columns:
        op["fecha_publicacion"] = pd.to_datetime(op["fecha_publicacion"], errors="coerce")
    if "fecha_cierre" in op.columns:
        op["fecha_cierre"] = pd.to_datetime(op["fecha_cierre"], errors="coerce")


def recalc_urgencia(fc):
    """Recalcula urgencia desde fecha_cierre + ahora."""
    if pd.isna(fc):
        return "NORMAL"
    try:
        cierre = pd.to_datetime(fc, errors="coerce")
        if pd.isna(cierre):
            return "NORMAL"
        delta_h = (cierre - pd.Timestamp.now()).total_seconds() / 3600
        if delta_h < 0: return "CERRADA"
        if delta_h < 24: return "CRITICA"
        if delta_h < 48: return "URGENTE"
        if delta_h < 168: return "PRONTA"
        return "NORMAL"
    except Exception:
        return "NORMAL"


# 1) Descartar OCs/filas sin organismo (no enriquecidas)
if not op.empty and "organismo" in op.columns:
    op = op[op["organismo"].fillna("").str.strip() != ""].reset_index(drop=True)

# 2) Recomputar urgencia con la fecha_cierre real
if not op.empty and "fecha_cierre" in op.columns:
    op["urgencia"] = op["fecha_cierre"].apply(recalc_urgencia)

def _estado_codigo(c):
    return revisiones.get(str(c), {}).get("estado", "")


# 4) Ocultar SIEMPRE: marcadas como no_sirve, y cerradas EXCEPTO Postuladas
if not op.empty:
    estados_op = op["codigo"].apply(_estado_codigo)
    # Quitar no_sirve
    op = op[estados_op != "no_sirve"].reset_index(drop=True)
    # Quitar cerradas SALVO postuladas (para seguimiento)
    estados_op = op["codigo"].apply(_estado_codigo)  # recalc tras filtro
    op = op[(op["urgencia"] != "CERRADA") | (estados_op == "postulada")].reset_index(drop=True)

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

    st.divider()
    st.subheader("Revisiones")
    estados_filtro = st.multiselect(
        "Mostrar revisión",
        ["No revisadas", "✅ Sirve", "⏳ En proceso", "📨 Postulada"],
        default=["No revisadas", "✅ Sirve", "⏳ En proceso", "📨 Postulada"]
    )
    st.caption("ℹ️ Las marcadas como ❌ No sirve se ocultan automáticamente. "
               "Las 📨 Postuladas siguen visibles aunque la licitación cierre.")

    st.divider()
    solo_nuevas_hoy = st.checkbox("⭐ Solo NUEVAS hoy", value=False,
                                   help="Filtra licitaciones publicadas hoy y fondos creados hoy en la DB")

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

    # Filtro por estado de revisión
    def _estado_filt(codigo):
        rev = revisiones.get(str(codigo), {})
        e = rev.get("estado")
        if not e:
            return "No revisadas"
        return {"sirve": "✅ Sirve", "en_proceso": "⏳ En proceso",
                "postulada": "📨 Postulada",
                "no_sirve": "❌ No sirve"}.get(e, "No revisadas")
    if estados_filtro:
        op_f = op_f[op_f["codigo"].apply(_estado_filt).isin(estados_filtro)]

    # Filtro "Solo nuevas hoy" (publicadas hoy)
    if solo_nuevas_hoy and "fecha_publicacion" in op_f.columns:
        hoy = pd.Timestamp.now().normalize()
        _fp = pd.to_datetime(op_f["fecha_publicacion"], errors="coerce")
        op_f = op_f[_fp >= hoy]

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
    "📨 Seguimiento Postulaciones",
    "💰 Fondos Concursables",
    "📋 Acciones Pendientes HAK",
    "🥊 Competencia 365d",
    "🔁 Cross-Reference",
    "📈 Evolución",
    "🔍 HAK vs Mercado",
    "🏛 Organismos",
    "📍 Geografía",
])


# ─── TAB 1: Oportunidades MP ─────────────────────────────────────────────────
with tabs[0]:
    if op_f.empty:
        st.info("Sin oportunidades con los filtros actuales.")
    else:
        # Inyectar columna estado_revision para visualizar
        def _est_emoji(c):
            r = revisiones.get(str(c), {})
            return {"sirve": "✅", "en_proceso": "⏳", "postulada": "📨",
                    "no_sirve": "❌"}.get(r.get("estado"), "")
        op_view = op_f.copy()
        op_view["✓"] = op_view["codigo"].apply(_est_emoji)
        # Etiqueta visible Urgencia (texto descriptivo con emoji + color)
        URG_LABEL = {
            "CRITICA": "🟥 Crítica <24h",
            "URGENTE": "🟧 Urgente <48h",
            "PRONTA":  "🟨 Pronta <7d",
            "NORMAL":  "⬜ Normal",
        }
        op_view["Urg"] = op_view["urgencia"].map(URG_LABEL).fillna("⬜ Normal")

        # Licitación en posición 3 · Urg visible (texto + color en fila)
        cols = ["✓", "score", "nombre", "priority", "Urg",
                "fecha_publicacion", "fecha_cierre",
                "organismo", "region", "monto",
                "cliente_previo", "organismo_prioritario",
                "matched_high", "codigo", "url"]
        cols = [c for c in cols if c in op_view.columns]

        # Contador con desglose por estado
        n_total = len(op_view)
        n_postuladas = (op_view["codigo"].apply(_estado_codigo) == "postulada").sum()
        n_proceso = (op_view["codigo"].apply(_estado_codigo) == "en_proceso").sum()
        n_sirve = (op_view["codigo"].apply(_estado_codigo) == "sirve").sum()
        n_norevisadas = n_total - n_postuladas - n_proceso - n_sirve

        ca, cb, cc, cd, ce = st.columns(5)
        ca.metric("📋 Total visible", n_total)
        cb.metric("🆕 Sin revisar", int(n_norevisadas))
        cc.metric("⏳ En proceso", int(n_proceso))
        cd.metric("✅ Sirven", int(n_sirve))
        ce.metric("📨 Postuladas", int(n_postuladas))

        with st.expander("ℹ️ Cómo leer esta tabla — colores y significado", expanded=False):
            st.markdown("""
**Colores de fila** (urgencia según fecha de cierre — pasa el mouse sobre la columna **Urg** para detalle):

- 🟥 **Rojo claro** = Crítica (cierra en menos de **24 horas**) — postula AHORA
- 🟧 **Naranja claro** = Urgente (cierra en menos de **48 horas**) — postula HOY
- 🟨 **Amarillo claro** = Pronta (cierra en menos de **7 días**) — preparar postulación
- ⬜ **Sin color** = Normal (más de 7 días para cerrar)

**Otras columnas con tooltip** (pasa el mouse sobre el header):
- **Score**: puntaje de relevancia HAK (a más alto, mejor encaje con tu giro)
- **Prio**: ALTA si matchea ≥1 keyword importante
- **🏆**: cliente previo HAK (Temuco, Cerrillos, Cunco, Villarrica)
- **🎯**: organismo prioritario (SLEPs, MINEDUC, JUNJI, GORE, municipios HAK)

**Acciones**: Click `🔗 MP` para abrir la ficha directa en Mercado Público.
Las licitaciones cerradas se ocultan automáticamente, salvo las marcadas como **📨 Postulada** (para seguimiento).
            """)

        # Color de fila según urgencia
        URG_COLORS = {"CRITICA": "#fee2e2", "URGENTE": "#ffedd5", "PRONTA": "#fef9c3"}
        def _row_style(row):
            color = URG_COLORS.get(str(row.get("urgencia", "")), "")
            return [f"background-color: {color}" if color else ""] * len(row)

        df_styled = op_view[cols + ["urgencia"]].copy()
        styled = df_styled.style.apply(_row_style, axis=1)
        try:
            styled = styled.hide(["urgencia"], axis="columns")
        except Exception:
            pass

        st.dataframe(
            styled,
            use_container_width=True, height=720,  # ~20 filas visibles
            column_config={
                "✓": st.column_config.TextColumn(
                    "✓", width="small",
                    help="✅ Sirve · ⏳ En proceso · 📨 Postulada · ❌ No sirve · vacío = no revisada"),
                "score": st.column_config.NumberColumn("Score", width="small",
                    help="Puntaje de relevancia HAK (suma de keywords + bonuses)"),
                "nombre": "Licitación",
                "priority": st.column_config.TextColumn("Prio", width="small",
                    help="ALTA si matchea ≥1 keyword de alta prioridad"),
                "Urg": st.column_config.TextColumn("Urg", width="small",
                    help="🟥 Crítica = cierra <24h · 🟧 Urgente <48h · 🟨 Pronta <7d · ⬜ Normal >7d. El color de la fila refleja la urgencia."),
                "fecha_publicacion": st.column_config.DatetimeColumn(
                    "Publicada", format="DD/MM/YYYY",
                    help="Fecha en que el organismo publicó la licitación"),
                "fecha_cierre": st.column_config.DatetimeColumn(
                    "Cierra", format="DD/MM/YYYY HH:mm",
                    help="Fecha y hora límite para postular"),
                "organismo": "Organismo", "region": "Región",
                "monto": st.column_config.NumberColumn("Monto CLP", format="$%d"),
                "cliente_previo": st.column_config.CheckboxColumn("🏆", width="small",
                    help="HAK ya ganó licitación con este organismo (Temuco, Cerrillos, Cunco, Villarrica)"),
                "organismo_prioritario": st.column_config.CheckboxColumn("🎯", width="small",
                    help="Organismo dentro de los 177 priorizados (SLEPs, MINEDUC, JUNJI, GORE, municipios HAK)"),
                "matched_high": "Keywords",
                "codigo": st.column_config.TextColumn("Código", width="small"),
                "url": st.column_config.LinkColumn("🔗 MP", width="small",
                                                    display_text="Abrir MP"),
            }
        )

        st.divider()
        st.markdown("### ✏️ Revisar una oportunidad")
        st.caption("Selecciona usando el **N° de fila** que ves en la tabla de arriba "
                   "(la primera columna numerada). Click 🔗 MP de cada fila para abrir su ficha.")

        # Construir mapping: row_idx → codigo, ordenado igual que la tabla mostrada
        op_f_indexed = op_f.reset_index(drop=True)
        opciones = list(op_f_indexed["codigo"])

        def _format_opt(c):
            row = op_f_indexed[op_f_indexed["codigo"] == c].iloc[0]
            idx = op_f_indexed.index[op_f_indexed["codigo"] == c].tolist()[0]
            estado_emoji = {"sirve":"✅","en_proceso":"⏳","postulada":"📨","no_sirve":"❌"}.get(
                revisiones.get(str(c), {}).get("estado", ""), "")
            score = int(row.get("score", 0))
            nombre = (row.get("nombre") or "")[:70]
            return f"#{idx} · [{score}pts] {estado_emoji} {c} — {nombre}"

        codigo_sel = st.selectbox(
            "Buscar por N° fila o código",
            options=opciones,
            format_func=_format_opt,
        )
        if codigo_sel:
            row = op_f[op_f["codigo"] == codigo_sel].iloc[0]
            st.markdown(f"**🏛 {row['organismo']}** · 📍 {row.get('region','—')} · "
                        f"💰 ${(row.get('monto') or 0)/1e6:,.1f}M CLP")
            st.code(codigo_sel, language=None)  # con botón copy nativo
            render_revision_widget(str(codigo_sel), revisiones, key_prefix="t1")


# ─── TAB 2: Seguimiento Postulaciones ────────────────────────────────────────
with tabs[1]:
    st.markdown("### 📨 Postulaciones en seguimiento")
    st.caption("Solo licitaciones marcadas como ✅ Sirve · ⏳ En proceso · 📨 Postulada. "
               "Las Postuladas aparecen aquí aunque la licitación haya cerrado, para hacer seguimiento del fallo.")

    # Construir desde revisiones + datos del CSV original (no op_f filtrado)
    seguimiento_codigos = {c: rev for c, rev in revisiones.items()
                           if rev.get("estado") in ("sirve", "en_proceso", "postulada")}
    if not seguimiento_codigos:
        st.info("Aún no hay licitaciones marcadas. Marca alguna como ✅ Sirve / ⏳ En proceso / 📨 Postulada en la pestaña anterior.")
    else:
        # Recuperar info de cada código del CSV (puede estar cerrada)
        # Nota: op original ya tiene filtro fecha_cierre, hay que cargar SIN ese filtro
        op_all_path = DATA / "oportunidades.csv"
        try:
            op_all = pd.read_csv(op_all_path)
        except Exception:
            op_all = pd.DataFrame()

        rows_seg = []
        for codigo, rev in seguimiento_codigos.items():
            if not op_all.empty:
                match = op_all[op_all["codigo"].astype(str) == str(codigo)]
                if not match.empty:
                    r = match.iloc[0].to_dict()
                else:
                    r = {"codigo": codigo}
            else:
                r = {"codigo": codigo}
            r["_estado"] = rev.get("estado")
            r["_revisor"] = rev.get("revisor", "")
            r["_comentario"] = rev.get("comentario", "")
            r["_fecha_rev"] = rev.get("fecha", "")
            rows_seg.append(r)

        # Métricas top
        n_sir = sum(1 for r in rows_seg if r["_estado"] == "sirve")
        n_pro = sum(1 for r in rows_seg if r["_estado"] == "en_proceso")
        n_pos = sum(1 for r in rows_seg if r["_estado"] == "postulada")
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Sirven", n_sir)
        c2.metric("⏳ En proceso", n_pro)
        c3.metric("📨 Postuladas", n_pos)
        st.divider()

        # Orden: postuladas primero, después en proceso, después sirve
        prio = {"postulada": 0, "en_proceso": 1, "sirve": 2}
        rows_seg.sort(key=lambda r: (prio.get(r["_estado"], 9), str(r.get("fecha_cierre") or "9999")))

        for r in rows_seg:
            codigo = str(r.get("codigo", ""))
            estado = r["_estado"]
            est_label, est_color = ESTADOS.get(estado, ("?", "#6b7280"))

            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f"<span style='background:{est_color}; color:white; padding:3px 10px; "
                        f"border-radius:12px; font-size:0.85em; font-weight:bold;'>{est_label}</span> "
                        f"<b>{r.get('nombre','(sin nombre)')[:120]}</b>",
                        unsafe_allow_html=True
                    )
                    st.caption(f"📅 Publicada: **{fmt_fecha(r.get('fecha_publicacion'))}** · "
                               f"Cierra: **{fmt_fecha(r.get('fecha_cierre'))}**")
                    st.caption(f"🏛 **{r.get('organismo','—')}** · "
                               f"📍 {r.get('region','—')} · "
                               f"💰 ${(r.get('monto') or 0)/1e6:.1f}M CLP")
                    if r.get("_comentario"):
                        st.markdown(f"💬 _{r['_comentario']}_")
                    st.caption(f"👤 Revisor: **{r.get('_revisor','—')}** · "
                               f"🕐 {fmt_fecha(r.get('_fecha_rev'))}")
                    if r.get("url"):
                        st.markdown(f"[🔗 Abrir en Mercado Público]({r['url']})")
                with col_b:
                    if r.get("score") is not None and not pd.isna(r.get("score")):
                        st.metric("Score", int(r["score"]))
                # Permitir actualizar la revisión desde aquí
                render_revision_widget(codigo, revisiones, key_prefix="t2")


# ─── TAB 3: Competencia 365d ─────────────────────────────────────────────────
with tabs[4]:
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
with tabs[5]:
    st.markdown("### Para cada oportunidad activa, ¿quién ganó licitaciones similares en este organismo?")
    if op.empty or comp.empty:
        st.info("Necesita datos de oportunidades + competencia.")
    else:
        # Agrupar competidores por organismos donde han ganado
        # comp tiene "organismos_top" (texto separado por · )
        rows = []
        for _, opp in op.iterrows():
            org_raw = opp.get("organismo")
            org_target = str(org_raw).strip() if pd.notna(org_raw) else ""
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
with tabs[6]:
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
with tabs[7]:
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
with tabs[8]:
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
with tabs[9]:
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
with tabs[2]:
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
        # Filtro "Solo nuevas hoy" (created_at en el día actual)
        if solo_nuevas_hoy and "created_at" in f_show.columns:
            hoy = pd.Timestamp.now().normalize()
            _ca = pd.to_datetime(f_show["created_at"], errors="coerce")
            f_show = f_show[_ca >= hoy]
        f_show = f_show.sort_values("score_hak", ascending=False)

        st.markdown(f"**{len(f_show)} fondos** con los filtros actuales")
        st.caption("ℹ️ Muchos fondos provienen del catálogo manual y enlazan a la home del organismo "
                   "(no a la convocatoria específica). Apertura/cierre frecuentemente no disponibles. "
                   "Sprint dedicado a mejorar scrapers en curso.")

        # Construir tabla con todos los campos visibles
        def _f_url(u):
            return u if pd.notna(u) and u else ""
        def _f_text(v, fallback="ℹ️ Info no disponible"):
            if pd.isna(v) or v == "" or v is None:
                return fallback
            return str(v)
        def _f_monto(mn, mx, mon):
            mon = mon if pd.notna(mon) and mon else "CLP"
            if pd.isna(mn) and pd.isna(mx):
                return "ℹ️ No disponible"
            if pd.notna(mn) and pd.notna(mx):
                return f"${mn/1e6:.1f}M – ${mx/1e6:.1f}M {mon}"
            if pd.notna(mx):
                return f"hasta ${mx/1e6:.1f}M {mon}"
            return f"desde ${mn/1e6:.1f}M {mon}"
        def _f_estado(e):
            return {"abierto": "🟢 Abierto", "proximo": "🟡 Próximo",
                    "cerrado": "🔴 Cerrado"}.get(e, "⚪ Desconocido")

        tabla_view = pd.DataFrame([{
            "Score": int(r.get("score_hak", 0)),
            "🌍": "🌍" if r.get("internacional") else "",
            "Estado": _f_estado(r.get("estado")),
            "Fondo": _f_text(r.get("nombre")),
            "Organismo": _f_text(r.get("organismo")),
            "Tipo": _f_text(r.get("tipo")),
            "Región": _f_text(r.get("region")),
            "Monto": _f_monto(r.get("monto_min"), r.get("monto_max"), r.get("moneda")),
            "Apertura": _f_text(r.get("fecha_apertura")),
            "Cierre": _f_text(r.get("fecha_cierre")),
            "URL": _f_url(r.get("url")),
        } for _, r in f_show.iterrows()])

        st.dataframe(
            tabla_view, use_container_width=True, height=600,
            column_config={
                "Score": st.column_config.NumberColumn("Score", width="small"),
                "🌍": st.column_config.TextColumn("🌍", width="small",
                    help="Fondo internacional"),
                "Estado": st.column_config.TextColumn("Estado", width="small"),
                "Fondo": st.column_config.TextColumn("Fondo", width="medium"),
                "Organismo": st.column_config.TextColumn("Organismo", width="medium"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Región": st.column_config.TextColumn("Región"),
                "Monto": st.column_config.TextColumn("Monto"),
                "Apertura": st.column_config.TextColumn("Apertura", width="small"),
                "Cierre": st.column_config.TextColumn("Cierre", width="small"),
                "URL": st.column_config.LinkColumn("🔗 Ver", width="small",
                    display_text="Abrir"),
            }
        )


# ─── TAB 10: Acciones Pendientes HAK (independientes del sistema) ────────────
with tabs[3]:
    st.markdown("# 📋 Acciones Pendientes — HAK")
    st.markdown("Estas son acciones que el equipo HAK debe ejecutar **fuera del sistema** "
                "para desbloquear nuevas fuentes de financiamiento, mejorar competitividad "
                "en licitaciones y profesionalizar la captación.")

    ACCIONES = [
        # ───────── CRÍTICAS (próximos 30 días) ─────────
        {
            "prio": "🔴 CRÍTICA",
            "titulo": "Inscribirse en registro Ley 21.440",
            "porque": (
                "**Sin esto, todas las donaciones privadas con beneficio tributario quedan bloqueadas.** "
                "La Ley 21.440 (Donaciones Sociales) creó un registro único; las empresas que quieran donar "
                "a HAK con franquicia tributaria SOLO pueden hacerlo si HAK está inscrita. "
                "Esto desbloquea: donaciones de empresas (RSE Codelco/CMPC/BHP/etc.), Fundaciones nacionales "
                "que exigen el registro como prerequisito (Mustakis, Colunga, etc.), Ley Valdés (donaciones culturales)."
            ),
            "url": "https://donacionesley21440.gob.cl/registro-publico",
            "tiempo": "1 día (gestión + documentos)",
            "responsable": "Camila Garay / Claudia Vivallo",
        },
        {
            "prio": "🔴 CRÍTICA",
            "titulo": "Postular FFOIP 2026 (SEGEGOB)",
            "porque": (
                "Hasta **$10M CLP** anuales para fundaciones con 2+ años de trayectoria. HAK califica. "
                "Postulación abre marzo-abril; ya hay bases publicadas. Es de las más accesibles para fundaciones "
                "consolidadas y permite financiar fortalecimiento institucional, formación, proyectos sociales. "
                "Histórico: aproximadamente 60% tasa de adjudicación para postulantes con experiencia documentada."
            ),
            "url": "https://fondodefortalecimiento.gob.cl/bases-del-concurso/",
            "tiempo": "2-3 días (preparar postulación)",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🔴 CRÍTICA",
            "titulo": "LOI a Tinker Foundation",
            "porque": (
                "Foco perfecto: **educación primaria temprana 5-10 años, alfabetización y numeración**. "
                "Chile incluido explícitamente como país elegible. Grants entre **$30M-$100M CLP**. "
                "Proceso 3 etapas (LOI → propuesta corta → propuesta completa); ventaja: hay tiempo para iterar. "
                "HAK encaja con escuelas red El Trencito (Temuco) + Rengalil + Sta Cruz Loncoche."
            ),
            "url": "https://tinker.org/institutional-grants-apply-page/",
            "tiempo": "1 semana (preparar LOI en inglés)",
            "responsable": "Claudia Vivallo + apoyo traducción",
        },
        {
            "prio": "🔴 CRÍTICA",
            "titulo": "Crear cuenta institucional en GlobalGiving",
            "porque": (
                "Plataforma global con acceso a donantes corporativos US (Google, Microsoft, etc. donan "
                "vía employee match) + crowdfunding internacional. Después de inscripción, HAK puede recibir "
                "donaciones recurrentes en USD. Requiere documentos en inglés (estatutos, evidencia de impacto, "
                "estados financieros). **Una vez inscrita, queda como infraestructura permanente.**"
            ),
            "url": "https://www.globalgiving.org/dy/v2/pe/application/start.html",
            "tiempo": "2 semanas (proceso de validación)",
            "responsable": "Equipo HAK + traducción",
        },
        {
            "prio": "🔴 CRÍTICA",
            "titulo": "Inscribirse en plataformas chilenas de donaciones",
            "porque": (
                "**DonarOnline, Donando.cl, YoDono** — permiten captar donaciones recurrentes desde el sitio web HAK. "
                "Cobran fee bajo (3-5%) pero entregan toda la infraestructura: pasarela pago, recibo automático, "
                "reportes a donantes, integración con bancos chilenos. Modelo probado por Fundación Las Rosas, Hogar de Cristo. "
                "Sumar a la web fundacionhelenadamskeller.com un botón 'DONAR' aumenta captación 5-10% mensualmente."
            ),
            "url": "https://donaronline.org/",
            "tiempo": "1 día por plataforma",
            "responsable": "Camila Garay + diseño web",
        },

        # ───────── ALTA (próximos 90 días) ─────────
        {
            "prio": "🟠 ALTA",
            "titulo": "Postular IAF Inter-American Foundation",
            "porque": (
                "Aplicación **rolling todo el año** (no espera convocatoria). Grants de **$25M-$380M CLP** para 1-4 años. "
                "Foco: ONG locales LATAM con foco educación, inclusión social. HAK perfil 100% encaja. "
                "Ya HAK tiene track record (4 contratos públicos, 16 establecimientos atendidos) — narrativa fuerte."
            ),
            "url": "https://iaf.gov/apply-for-grant/",
            "tiempo": "2-3 semanas (propuesta inglés + métricas impacto)",
            "responsable": "Claudia Vivallo + traducción",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Contactar Embajada Canadá - CFLI",
            "porque": (
                "Canada Fund for Local Initiatives Chile prioriza **pueblos indígenas y educación**. "
                "Proyecto educación intercultural mapuche encaja perfecto. Monto AUD 30K-100K (~$25M-$80M CLP). "
                "Ciclo abr-mar; es un PROCESO RELACIONAL — empezar contacto con la Embajada con anticipación."
            ),
            "url": "https://www.international.gc.ca/world-monde/funding-financement/cfli-fcil/index.aspx?lang=eng",
            "tiempo": "Email inicial inmediato + reunión",
            "responsable": "Claudia Vivallo",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Postular Caja La Araucana - STEM",
            "porque": (
                "$5M Caja La Araucana + $3M aliado tecnológico = **$8M para colegios alto IVE rurales**. "
                "HAK tiene ya 3 colegios en Araucanía rural (Rengalil, Trencito, Sta Cruz Loncoche/Victoria) "
                "que califican alto IVE. Postulación anual."
            ),
            "url": "https://educacion.beneficioslaaraucana.cl/",
            "tiempo": "1 semana (alianza con tecnológico + propuesta)",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Postular Fondo Social CMPC (agosto-septiembre)",
            "porque": (
                "Fondo regional CMPC cubre Araucanía explícitamente. Hasta **$1.2M CLP por proyecto**. "
                "Cierre típico septiembre-octubre. Para proyectos territoriales en comunas con presencia forestal. "
                "HAK con su red de colegios rurales puede armar 3-4 propuestas paralelas."
            ),
            "url": "https://www.fundacioncmpc.cl/",
            "tiempo": "Calendarizar para septiembre",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Buscar ONGD española para AECID + La Caixa",
            "porque": (
                "AECID y La Caixa requieren que el solicitante sea una ONG española; HAK puede ser SOCIO LOCAL. "
                "Hay ONGD españolas con foco educación intercultural Chile-LATAM (Entreculturas, Educo, Save the Children España). "
                "Una alianza con ONGD española desbloquea EUR 50K (La Caixa) + hasta EUR 300K (AECID convenios)."
            ),
            "url": "https://www.aecid.es/w/la-aecid-publica-el-calendario-de-convocatorias-de-subvenciones-para-2026",
            "tiempo": "1 mes (búsqueda + LOI conjunto)",
            "responsable": "Claudia Vivallo (relacionamiento)",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Solicitar alianza Fundación SM Chile",
            "porque": (
                "Fundación SM España tiene **oficina en Chile**. Programa formación docente + investigación educativa. "
                "Acuerdos directos con ONG (no concurso público). Reunión inicial puede llevar a co-financiar formación HAK."
            ),
            "url": "https://cl.fundacion-sm.org/",
            "tiempo": "Reunión inicial 1 semana",
            "responsable": "Claudia Vivallo",
        },
        {
            "prio": "🟠 ALTA",
            "titulo": "Inscribirse como aliado implementador ProFuturo",
            "porque": (
                "ProFuturo (Fundación Telefónica + La Caixa) busca aliados locales para implementar Aula Digital "
                "en escuelas vulnerables. HAK con su red de 16 establecimientos es candidato ideal. "
                "No es concurso, es relacionamiento + propuesta."
            ),
            "url": "https://profuturo.education/paises/chile/",
            "tiempo": "Email inicial + reunión",
            "responsable": "Claudia Vivallo",
        },

        # ───────── MEDIA (estructural en el año) ─────────
        {
            "prio": "🟡 MEDIA",
            "titulo": "Acreditación OTEC SENCE (NCh 2728:2015)",
            "porque": (
                "Habilita acceso al **mercado SENCE** (becas laborales, franquicia tributaria empresarial). "
                "Empresas con planilla pueden capacitar a sus trabajadores con HAK y descontar el costo de impuestos. "
                "Mercado adicional ~$300M CLP/año potencial. Inversión: 6 meses + ~$2M CLP."
            ),
            "url": "https://www.sence.gob.cl/organismos/otec",
            "tiempo": "6 meses (segundo semestre 2026 según equipo HAK)",
            "responsable": "Camila Garay (lead)",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Verificar/renovar Registro ATE MINEDUC",
            "porque": (
                "ATE = Asistencia Técnica Educativa. Es prerequisito para que escuelas usen recursos SEP/PME en HAK. "
                "Verificar vigencia en registroycertificacionate.mineduc.cl al inicio de cada postulación."
            ),
            "url": "https://registroycertificacionate.mineduc.cl/",
            "tiempo": "1 día (verificación)",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Avanzar primer curso certificado CPEIP (Decreto 401)",
            "porque": (
                "CPEIP certifica cursos de perfeccionamiento docente. Cursos certificados CPEIP entran al "
                "Registro Público y son financiables con SEP/PME automáticamente. HAK tiene cursos en preparación; "
                "sacar el primero abre canal continuo de demanda."
            ),
            "url": "https://www.cpeip.cl/registro-publico-y-acreditacion-de-cursos-y-postitulos-cpeip/",
            "tiempo": "3-6 meses",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Estados financieros auditados anuales",
            "porque": (
                "Requisito de muchos donantes internacionales (Tinker, IAF, Fundación La Caixa) y "
                "buena práctica de transparencia. Costo aprox $1.5M-$3M CLP/año por auditor externo. "
                "Una vez se tiene 1 año auditado, se puede postular a fondos que antes estaban bloqueados."
            ),
            "url": "https://www.colegiocontadores.cl/buscar-contador",
            "tiempo": "Contratar auditor en mayo-junio para auditoría 2025",
            "responsable": "Dirección Ejecutiva",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Política de Protección a la Infancia (Child Safeguarding Policy)",
            "porque": (
                "Requisito de TODOS los donantes internacionales con foco infancia (Tinker, IAF, UNICEF, "
                "Save the Children, Plan International, World Vision). Documento formal aprobado por directorio "
                "que define protocolos ante denuncias, medidas preventivas, capacitación staff. "
                "Sin esto, varios fondos están bloqueados aunque HAK califique en lo demás."
            ),
            "url": "https://www.unicef.org/protection/child-safeguarding",
            "tiempo": "1 mes (redacción + aprobación directorio)",
            "responsable": "Dirección Ejecutiva + asesor legal",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Memoria anual pública (transparencia)",
            "porque": (
                "Documento institucional de 20-30 páginas con: misión/visión, equipo, proyectos del año, métricas "
                "de impacto, estados financieros resumidos. Publicada en sitio web + entregable a donantes. "
                "Estándar de fundaciones LATAM consolidadas (Educacional Arauco, Mustakis, etc.). Mejora la "
                "credibilidad ante todos los donantes."
            ),
            "url": "https://fundacionarauco.cl/memorias/",
            "tiempo": "2 meses (recopilación + diseño)",
            "responsable": "Coord. Extensión + diseño externo",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Newsletter / lista de email seguidores",
            "porque": (
                "Captura de leads para futuras campañas de captación + transparencia de impacto. "
                "Mailchimp tier gratuito hasta 500 contactos. Envíos mensuales con: postulaciones ganadas, "
                "actividades en escuelas, oportunidades de voluntariado. Construye base de futuros donantes."
            ),
            "url": "https://mailchimp.com/",
            "tiempo": "1 semana setup + flujo continuo",
            "responsable": "Coord. Extensión",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Política de transparencia + sitio web actualizado",
            "porque": (
                "Sitio web actual: https://fundacionhelenadamskeller.com/ — propuestas de mejora identificadas "
                "en sesión previa (ver Propuesta_Mejoras_Web_HAK.docx). Agregar: transparencia financiera, "
                "memoria anual, equipo con CVs, proyectos con resultados, botón DONAR (DonarOnline integrado), "
                "FAQ donantes."
            ),
            "url": "https://fundacionhelenadamskeller.com/",
            "tiempo": "1-2 meses",
            "responsable": "Coord. Extensión + diseño web",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Postular FPA Establecimientos Educacionales (cierre 7 octubre)",
            "porque": (
                "Fondo Protección Ambiental MMA — línea Establecimientos Educacionales. **$6M CLP por proyecto**. "
                "HAK con red de colegios puede armar 2-3 propuestas. Para educación ambiental escolar (huerto, "
                "compostaje, energía solar, etc.). Cierra octubre — calendarizar postulación en septiembre."
            ),
            "url": "https://fondos.mma.gob.cl/fpa-2026-proyectos-sustentables-en-establecimientos-educacionales/",
            "tiempo": "Calendarizar agosto-septiembre",
            "responsable": "Camila Garay",
        },
        {
            "prio": "🟡 MEDIA",
            "titulo": "Contactar Microproyectos Embajada Alemania",
            "porque": (
                "EUR 25K (~$25M CLP) por microproyecto. Resultados verificables, ejecución en mismo año. "
                "Embajada Alemania prioriza ODS 4 (educación), ODS 5 (género), ODS 16 (paz/justicia). "
                "Contacto inicial a sección Cooperación de la Embajada."
            ),
            "url": "https://santiago.diplo.de/cl-es",
            "tiempo": "Email inicial + propuesta 2 semanas",
            "responsable": "Claudia Vivallo",
        },
    ]

    # Render por prioridad
    for prio_grupo in ["🔴 CRÍTICA", "🟠 ALTA", "🟡 MEDIA"]:
        st.markdown(f"## {prio_grupo}")
        items = [a for a in ACCIONES if a["prio"] == prio_grupo]
        for a in items:
            with st.expander(f"**{a['titulo']}** — ⏱ {a['tiempo']}", expanded=(prio_grupo == "🔴 CRÍTICA")):
                st.markdown(a["porque"])
                col1, col2 = st.columns([3, 2])
                col1.markdown(f"🔗 **[Ir al sitio]({a['url']})**")
                col2.markdown(f"👤 **Responsable**: {a['responsable']}")
        st.divider()

    # Recordatorio de configuración pendiente
    st.markdown("## ⚙️ Configuración pendiente del sistema (técnico)")
    with st.expander("📧 Activar envío automático de email diario"):
        st.markdown("""
        El sistema **YA detecta y envía Telegram** al grupo "A y Hak" 3 veces al día,
        pero el envío de **email a `gestion@fundacionhak.com`** está pendiente.

        **Lo que falta**:
        1. Generar **App Password de Gmail** (16 caracteres) desde la cuenta que enviará:
           - Activar 2FA en https://myaccount.google.com/security
           - Crear App Password en https://myaccount.google.com/apppasswords
        2. Configurar 2 secrets en GitHub Actions del repo `hak-scanner`:
           - `EMAIL_USER` = email del remitente (ej: `geoimagen.spa@gmail.com`)
           - `EMAIL_PASSWORD` = los 16 caracteres del App Password
        3. Confirmar con Nicolás para subir los secrets vía API.

        Una vez configurado, el equipo HAK recibirá **3 emails diarios** (08:00, 13:00, 18:00 Chile)
        con el reporte completo de oportunidades nuevas + TOP 5.
        """)

    with st.expander("🔐 Token GitHub para guardar revisiones"):
        st.markdown("""
        Las revisiones (✅ Sirve / ⏳ En proceso / 📨 Postulada / ❌ No sirve) que hacen
        en la pestaña Oportunidades MP **se guardan en GitHub** para que todos los del equipo las vean.

        Para activar el guardado, falta agregar un secret `github_token` en
        Streamlit Cloud → Settings → Secrets:
        ```toml
        github_token = "ghp_xxxxxxxxxxxxxxxxxxxx"
        ```
        Sin esto, las marcaciones del equipo se pierden al refrescar la página.
        """)


st.divider()
st.caption(f"⚠️ Datos de la API oficial Mercado Público (ChileCompra) y scrapers de Fondos. "
           f"Última actualización: {meta.get('ultima_actualizacion', '—')}")
