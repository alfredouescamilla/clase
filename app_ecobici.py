import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Tablero EcoBici", layout="wide")
st.title("🚲 Tablero EcoBici - Estaciones en tiempo real")

# URLs de la API pública de EcoBici CDMX (formato GBFS)
URL_INFO = "https://gbfs.mex.lyftbikes.com/gbfs/es/station_information.json"
URL_STATUS = "https://gbfs.mex.lyftbikes.com/gbfs/es/station_status.json"

@st.cache_data(ttl=60)
def cargar_datos():
    info = requests.get(URL_INFO, timeout=30).json()["data"]["stations"]
    status = requests.get(URL_STATUS, timeout=30).json()["data"]["stations"]
    df_info = pd.DataFrame(info)
    df_status = pd.DataFrame(status)
    df = pd.merge(df_info, df_status, on="station_id", suffixes=("", "_status"))
    df = df.rename(columns={"lat": "latitude", "lon": "longitude"})

    df["capacity"] = df["capacity"].fillna(0)
    df["ocupacion"] = df.apply(
        lambda r: (r["num_bikes_available"] / r["capacity"] * 100) if r["capacity"] > 0 else 0,
        axis=1,
    ).round(1)

    def categoria(pct):
        if pct <= 20:
            return "Baja (0-20%)"
        elif pct <= 60:
            return "Media (21-60%)"
        else:
            return "Alta (61-100%)"

    df["nivel"] = df["ocupacion"].apply(categoria)
    df["ultimo_reporte"] = pd.to_datetime(df["last_reported"], unit="s")
    return df

# ---------------- BARRA LATERAL: FILTROS ----------------
st.sidebar.header("Filtros")

if st.sidebar.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron cargar los datos de EcoBici: {e}")
    st.stop()

ultimo = df["ultimo_reporte"].max()
st.sidebar.caption(f"Ultimo reporte: {ultimo:%d/%m/%Y %H:%M}")

buscar = st.sidebar.text_input("Buscar estacion por nombre")

niveles = ["Baja (0-20%)", "Media (21-60%)", "Alta (61-100%)"]
nivel_sel = st.sidebar.multiselect("Nivel de disponibilidad", niveles, default=niveles)

rango_ocup = st.sidebar.slider("Rango de ocupacion (%)", 0, 100, (0, 100))

min_bicis = st.sidebar.slider(
    "Minimo de bicis disponibles", 0, int(df["num_bikes_available"].max()), 0
)

solo_activas = st.sidebar.checkbox("Mostrar solo estaciones en servicio", value=False)
solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles")

# ---------------- APLICAR FILTROS ----------------
df_filtrado = df.copy()
if buscar:
    df_filtrado = df_filtrado[df_filtrado["name"].str.contains(buscar, case=False, na=False)]
if nivel_sel:
    df_filtrado = df_filtrado[df_filtrado["nivel"].isin(nivel_sel)]
df_filtrado = df_filtrado[
    (df_filtrado["ocupacion"] >= rango_ocup[0]) & (df_filtrado["ocupacion"] <= rango_ocup[1])
]
if solo_activas:
    df_filtrado = df_filtrado[df_filtrado["is_renting"] == 1]
if solo_con_bicis:
    df_filtrado = df_filtrado[df_filtrado["num_bikes_available"] > 0]
df_filtrado = df_filtrado[df_filtrado["num_bikes_available"] >= min_bicis]

# ---------------- METRICAS RESUMEN ----------------
st.subheader("Resumen de la red")
c1, c2, c3, c4 = st.columns(4)
ocup_red = round(df["ocupacion"].mean(), 1)
ocup_filtro = round(df_filtrado["ocupacion"].mean(), 1) if len(df_filtrado) else 0
c1.metric("Estaciones mostradas", len(df_filtrado))
c2.metric("Bicis disponibles", int(df_filtrado["num_bikes_available"].sum()))
c3.metric("Espacios libres", int(df_filtrado["num_docks_available"].sum()))
c4.metric("Ocupacion promedio", f"{ocup_filtro}%", delta=f"{round(ocup_filtro - ocup_red, 1)}% vs red")

c5, c6, c7 = st.columns(3)
c5.metric("Estaciones sin bicis", int((df_filtrado["num_bikes_available"] == 0).sum()))
c6.metric("Sin lugar para devolver", int((df_filtrado["num_docks_available"] == 0).sum()))
c7.metric("Estaciones en servicio", int((df_filtrado["is_renting"] == 1).sum()))

# ---------------- PESTANAS ----------------
tab_mapa, tab_graf, tab_alertas, tab_datos = st.tabs(
    ["🗺️ Mapa", "📊 Graficas", "⚠️ Alertas", "📄 Datos"]
)

with tab_mapa:
    st.caption("Color = nivel de disponibilidad. Tamano = bicis disponibles.")
    if len(df_filtrado):
        fig_mapa = px.scatter_mapbox(
            df_filtrado, lat="latitude", lon="longitude", color="nivel",
            size="num_bikes_available", size_max=15, zoom=11, height=550,
            hover_name="name",
            hover_data={
                "num_bikes_available": True, "num_docks_available": True,
                "capacity": True, "ocupacion": True,
                "latitude": False, "longitude": False,
            },
            color_discrete_map={
                "Baja (0-20%)": "#d62728", "Media (21-60%)": "#ff7f0e", "Alta (61-100%)": "#2ca02c",
            },
            category_orders={"nivel": niveles},
        )
        fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig_mapa, use_container_width=True)

        st.markdown("**Mapa de densidad (zonas con mas bicis)**")
        fig_dens = px.density_mapbox(
            df_filtrado, lat="latitude", lon="longitude", z="num_bikes_available",
            radius=20, zoom=10, height=400, center={"lat": 19.42, "lon": -99.16},
        )
        fig_dens.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig_dens, use_container_width=True)
    else:
        st.info("No hay estaciones que coincidan con los filtros.")

with tab_graf:
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Top 20 estaciones con mas bicis**")
        top = df_filtrado.sort_values("num_bikes_available", ascending=False).head(20)
        fig_top = px.bar(
            top, x="num_bikes_available", y="name", orientation="h",
            labels={"name": "Estacion", "num_bikes_available": "Bicis disponibles"},
        )
        fig_top.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig_top, use_container_width=True)
    with col_b:
        st.markdown("**Estaciones por nivel de disponibilidad**")
        conteo = df_filtrado["nivel"].value_counts().reindex(niveles).fillna(0).reset_index()
        conteo.columns = ["nivel", "cantidad"]
        fig_dona = px.pie(
            conteo, names="nivel", values="cantidad", hole=0.45,
            color="nivel",
            color_discrete_map={
                "Baja (0-20%)": "#d62728", "Media (21-60%)": "#ff7f0e", "Alta (61-100%)": "#2ca02c",
            },
        )
        fig_dona.update_layout(height=500)
        st.plotly_chart(fig_dona, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("**Distribucion de bicis disponibles**")
        fig_hist = px.histogram(df_filtrado, x="num_bikes_available", nbins=20)
        st.plotly_chart(fig_hist, use_container_width=True)
    with col_d:
        st.markdown("**Capacidad vs bicis disponibles**")
        fig_disp = px.scatter(
            df_filtrado, x="capacity", y="num_bikes_available", color="nivel",
            hover_name="name",
            color_discrete_map={
                "Baja (0-20%)": "#d62728", "Media (21-60%)": "#ff7f0e", "Alta (61-100%)": "#2ca02c",
            },
        )
        st.plotly_chart(fig_disp, use_container_width=True)

with tab_alertas:
    alerta = df_filtrado[
        (df_filtrado["num_bikes_available"] == 0) | (df_filtrado["num_docks_available"] == 0)
    ]
    st.caption(f"{len(alerta)} estaciones sin bicis o sin lugar para devolver.")
    st.dataframe(
        alerta[["name", "num_bikes_available", "num_docks_available", "capacity", "is_renting"]],
        use_container_width=True,
    )

with tab_datos:
    st.markdown("**Detalle por estacion**")
    if len(df_filtrado):
        est = st.selectbox("Selecciona una estacion", df_filtrado["name"].sort_values().unique())
        fila = df_filtrado[df_filtrado["name"] == est].iloc[0]
        d1, d2, d3 = st.columns(3)
        d1.metric("Bicis disponibles", int(fila["num_bikes_available"]))
        d2.metric("Espacios libres", int(fila["num_docks_available"]))
        d3.metric("Ocupacion", f"{fila['ocupacion']}%")
        d4, d5, d6 = st.columns(3)
        d4.metric("Capacidad", int(fila["capacity"]))
        d5.metric("Bicis descompuestas", int(fila["num_bikes_disabled"]))
        d6.metric("En servicio", "Si" if fila["is_renting"] == 1 else "No")

    st.markdown("**Tabla completa (filtrada)**")
    tabla = df_filtrado[[
        "name", "num_bikes_available", "num_docks_available", "num_bikes_disabled",
        "capacity", "ocupacion", "nivel", "is_renting", "ultimo_reporte",
    ]]
    st.dataframe(
        tabla.style.background_gradient(subset=["ocupacion"], cmap="RdYlGn"),
        use_container_width=True,
    )
    st.download_button(
        "⬇️ Descargar datos filtrados (CSV)",
        tabla.to_csv(index=False).encode("utf-8"),
        "ecobici_filtrado.csv",
        "text/csv",
    )
