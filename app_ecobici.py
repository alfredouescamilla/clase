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

    # Renombrar coordenadas para st.map y Plotly
    df = df.rename(columns={"lat": "latitude", "lon": "longitude"})

    # Ocupacion: porcentaje de bicis disponibles respecto a la capacidad
    df["capacity"] = df["capacity"].fillna(0)
    df["ocupacion"] = df.apply(
        lambda r: (r["num_bikes_available"] / r["capacity"] * 100) if r["capacity"] > 0 else 0,
        axis=1,
    ).round(1)

    # Categoria de disponibilidad para colorear
    def categoria(pct):
        if pct <= 20:
            return "Baja (0-20%)"
        elif pct <= 60:
            return "Media (21-60%)"
        else:
            return "Alta (61-100%)"

    df["nivel"] = df["ocupacion"].apply(categoria)

    # Ultimo reporte legible
    df["ultimo_reporte"] = pd.to_datetime(df["last_reported"], unit="s")
    return df

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron cargar los datos de EcoBici: {e}")
    st.stop()

# ---------------- BARRA LATERAL: FILTROS ----------------
st.sidebar.header("Filtros")

buscar = st.sidebar.text_input("Buscar estacion por nombre")

min_bicis = st.sidebar.slider(
    "Minimo de bicis disponibles", 0, int(df["num_bikes_available"].max()), 0
)

solo_activas = st.sidebar.checkbox("Mostrar solo estaciones en servicio", value=False)
solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles")

df_filtrado = df.copy()
if buscar:
    df_filtrado = df_filtrado[df_filtrado["name"].str.contains(buscar, case=False, na=False)]
if solo_activas:
    df_filtrado = df_filtrado[df_filtrado["is_renting"] == 1]
if solo_con_bicis:
    df_filtrado = df_filtrado[df_filtrado["num_bikes_available"] > 0]
df_filtrado = df_filtrado[df_filtrado["num_bikes_available"] >= min_bicis]

# ---------------- METRICAS RESUMEN ----------------
st.subheader("Resumen de la red")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Estaciones mostradas", len(df_filtrado))
c2.metric("Bicis disponibles", int(df_filtrado["num_bikes_available"].sum()))
c3.metric("Espacios libres", int(df_filtrado["num_docks_available"].sum()))
ocupacion_prom = round(df_filtrado["ocupacion"].mean(), 1) if len(df_filtrado) else 0
c4.metric("Ocupacion promedio", f"{ocupacion_prom}%")

c5, c6, c7 = st.columns(3)
vacias = int((df_filtrado["num_bikes_available"] == 0).sum())
llenas = int((df_filtrado["num_docks_available"] == 0).sum())
activas = int((df_filtrado["is_renting"] == 1).sum())
c5.metric("Estaciones sin bicis", vacias)
c6.metric("Estaciones sin lugar para devolver", llenas)
c7.metric("Estaciones en servicio", activas)

# ---------------- MAPA CON COLOR POR DISPONIBILIDAD ----------------
st.subheader("Mapa de estaciones (color = nivel de disponibilidad)")
if len(df_filtrado):
    fig_mapa = px.scatter_mapbox(
        df_filtrado,
        lat="latitude",
        lon="longitude",
        color="nivel",
        size="num_bikes_available",
        size_max=15,
        zoom=11,
        height=550,
        hover_name="name",
        hover_data={
            "num_bikes_available": True,
            "num_docks_available": True,
            "capacity": True,
            "ocupacion": True,
            "latitude": False,
            "longitude": False,
        },
        color_discrete_map={
            "Baja (0-20%)": "#d62728",
            "Media (21-60%)": "#ff7f0e",
            "Alta (61-100%)": "#2ca02c",
        },
        category_orders={"nivel": ["Baja (0-20%)", "Media (21-60%)", "Alta (61-100%)"]},
    )
    fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig_mapa, use_container_width=True)
else:
    st.info("No hay estaciones que coincidan con los filtros.")

# ---------------- GRAFICAS ----------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Top 20 estaciones con mas bicis")
    top = df_filtrado.sort_values("num_bikes_available", ascending=False).head(20)
    fig_top = px.bar(
        top, x="num_bikes_available", y="name", orientation="h",
        labels={"name": "Estacion", "num_bikes_available": "Bicis disponibles"},
    )
    fig_top.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
    st.plotly_chart(fig_top, use_container_width=True)

with col_b:
    st.subheader("Distribucion de bicis disponibles")
    fig_hist = px.histogram(
        df_filtrado, x="num_bikes_available", nbins=20,
        labels={"num_bikes_available": "Bicis disponibles"},
    )
    fig_hist.update_layout(height=500)
    st.plotly_chart(fig_hist, use_container_width=True)

# ---------------- ESTACIONES EN ALERTA ----------------
st.subheader("⚠️ Estaciones en alerta")
alerta = df_filtrado[
    (df_filtrado["num_bikes_available"] == 0) | (df_filtrado["num_docks_available"] == 0)
]
st.caption(f"{len(alerta)} estaciones sin bicis o sin lugar para devolver.")
st.dataframe(
    alerta[["name", "num_bikes_available", "num_docks_available", "capacity", "is_renting"]],
    use_container_width=True,
)

# ---------------- TABLA COMPLETA ----------------
st.subheader("Datos de estaciones")
st.dataframe(
    df_filtrado[[
        "name", "num_bikes_available", "num_docks_available", "num_bikes_disabled",
        "capacity", "ocupacion", "nivel", "is_renting", "ultimo_reporte",
    ]],
    use_container_width=True,
)
