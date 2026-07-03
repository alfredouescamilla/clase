import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Tablero EcoBici", layout="wide")
st.title("Tablero EcoBici - Estaciones en tiempo real")

# URLs de la API pública de EcoBici CDMX (formato GBFS)
URL_INFO = "https://gbfs.mex.lyftbikes.com/gbfs/es/station_information.json"
URL_STATUS = "https://gbfs.mex.lyftbikes.com/gbfs/es/station_status.json"

@st.cache_data(ttl=60)
def cargar_datos():
    info = requests.get(URL_INFO, timeout=30).json()["data"]["stations"]
    status = requests.get(URL_STATUS, timeout=30).json()["data"]["stations"]
    df_info = pd.DataFrame(info)
    df_status = pd.DataFrame(status)
    df = pd.merge(df_info, df_status, on="station_id")
    # Renombrar columnas de coordenadas para st.map
    df = df.rename(columns={"lat": "latitude", "lon": "longitude"})
    return df

try:
    df = cargar_datos()
except Exception as e:
    st.error(f"No se pudieron cargar los datos de EcoBici: {e}")
    st.stop()

st.sidebar.header("Filtros")

# Checkbox en la barra lateral
solo_con_bicis = st.sidebar.checkbox("Mostrar solo estaciones con bicis disponibles")

if solo_con_bicis:
    df_filtrado = df[df["num_bikes_available"] > 0]
else:
    df_filtrado = df

# Metricas rapidas
col1, col2, col3 = st.columns(3)
col1.metric("Estaciones mostradas", len(df_filtrado))
col2.metric("Bicis disponibles", int(df_filtrado["num_bikes_available"].sum()))
col3.metric("Espacios libres", int(df_filtrado["num_docks_available"].sum()))

# Mapa de estaciones
st.subheader("Mapa de estaciones")
st.map(df_filtrado[["latitude", "longitude"]])

# Grafica de bicis disponibles por estacion (top 20)
st.subheader("Estaciones con mas bicis disponibles")
top = df_filtrado.sort_values("num_bikes_available", ascending=False).head(20)
fig = px.bar(top, x="name", y="num_bikes_available",
             labels={"name": "Estacion", "num_bikes_available": "Bicis disponibles"})
fig.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig, use_container_width=True)

# Tabla de datos
st.subheader("Datos de estaciones")
st.dataframe(df_filtrado[["name", "num_bikes_available", "num_docks_available"]])
