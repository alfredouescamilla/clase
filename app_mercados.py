import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Tablero de Mercados", layout="wide")
st.title("📈 Tablero de Mercados - Datos de Yahoo Finance")

ACTIVOS = {
    "USD/MXN": "MXN=X",
    "EUR/MXN": "EURMXN=X",
    "IPC BMV": "^MXX",
    "S&P 500": "^GSPC",
    "Petroleo WTI": "CL=F",
    "Oro": "GC=F",
    "Bono 10Y EE.UU. (rendimiento)": "^TNX",
}

st.sidebar.header("Filtros")

if st.sidebar.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

periodo_opciones = {
    "1 mes": "1mo",
    "3 meses": "3mo",
    "6 meses": "6mo",
    "1 ano": "1y",
    "2 anos": "2y",
    "5 anos": "5y",
}
periodo_label = st.sidebar.selectbox("Periodo", list(periodo_opciones.keys()), index=2)
periodo = periodo_opciones[periodo_label]

seleccion = st.sidebar.multiselect(
    "Activos a mostrar", list(ACTIVOS.keys()), default=list(ACTIVOS.keys())
)

if not seleccion:
    st.warning("Selecciona al menos un activo en la barra lateral.")
    st.stop()

@st.cache_data(ttl=300)
def cargar_datos(tickers, periodo):
    data = yf.download(tickers, period=periodo, interval="1d", progress=False, auto_adjust=True)
    if isinstance(data.columns, pd.MultiIndex):
        cierre = data["Close"]
    else:
        cierre = data[["Close"]]
        cierre.columns = tickers
    cierre = cierre.dropna(how="all")
    return cierre

tickers_sel = [ACTIVOS[nombre] for nombre in seleccion]
try:
    df_cierre = cargar_datos(tickers_sel, periodo)
except Exception as e:
    st.error(f"No se pudieron cargar los datos de Yahoo Finance: {e}")
    st.stop()

if df_cierre.empty:
    st.error("No se recibieron datos para los activos seleccionados.")
    st.stop()

nombre_por_ticker = {v: k for k, v in ACTIVOS.items()}
df_cierre = df_cierre.rename(columns=nombre_por_ticker)

st.subheader("Resumen")
cols = st.columns(len(seleccion))
for col, nombre in zip(cols, seleccion):
    serie = df_cierre[nombre].dropna()
    if len(serie) >= 2:
        ultimo = serie.iloc[-1]
        anterior = serie.iloc[-2]
        variacion = (ultimo / anterior - 1) * 100
        col.metric(nombre, f"{ultimo:,.2f}", f"{variacion:+.2f}%")
    elif len(serie) == 1:
        col.metric(nombre, f"{serie.iloc[-1]:,.2f}")
    else:
        col.metric(nombre, "N/D")

st.caption(f"Ultimo dato: {df_cierre.index.max():%d/%m/%Y}")

tab_series, tab_rendimientos, tab_corr, tab_datos = st.tabs(
    ["📈 Series de tiempo", "📊 Rendimientos", "🔗 Correlacion", "📄 Datos"]
)

with tab_series:
    st.caption("Evolucion normalizada (base 100 al inicio del periodo) para comparar activos con escalas distintas.")
    df_norm = df_cierre.dropna(how="all")
    df_norm = df_norm / df_norm.bfill().iloc[0] * 100
    fig = px.line(
        df_norm, x=df_norm.index, y=df_norm.columns,
        labels={"value": "Indice (base 100)", "index": "Fecha", "variable": "Activo"},
    )
    fig.update_layout(height=550, legend_title_text="Activo")
    st.plotly_chart(fig, use_container_width=True)

with tab_rendimientos:
    st.caption(f"Rendimiento porcentual acumulado durante el periodo seleccionado ({periodo_label}).")
    rendimientos = ((df_cierre.bfill().iloc[-1] / df_cierre.bfill().iloc[0]) - 1) * 100
    rendimientos = rendimientos.sort_values()
    fig_bar = px.bar(
        x=rendimientos.values, y=rendimientos.index, orientation="h",
        labels={"x": "Rendimiento (%)", "y": "Activo"},
        color=rendimientos.values, color_continuous_scale=["#d62728", "#2ca02c"],
    )
    fig_bar.update_layout(height=450, coloraxis_showscale=False)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.caption("Volatilidad diaria anualizada (desviacion estandar de rendimientos diarios).")
    rend_diarios = df_cierre.pct_change().dropna(how="all")
    vol = (rend_diarios.std() * np.sqrt(252) * 100).sort_values()
    fig_vol = px.bar(
        x=vol.values, y=vol.index, orientation="h",
        labels={"x": "Volatilidad anualizada (%)", "y": "Activo"},
    )
    fig_vol.update_layout(height=450)
    st.plotly_chart(fig_vol, use_container_width=True)

with tab_corr:
    st.caption("Correlacion de rendimientos diarios entre activos durante el periodo seleccionado.")
    rend_diarios = df_cierre.pct_change().dropna(how="all")
    if len(seleccion) >= 2:
        corr = rend_diarios.corr()
        fig_heat = px.imshow(
            corr, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto",
        )
        fig_heat.update_layout(height=500)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Selecciona al menos dos activos para ver la matriz de correlacion.")

with tab_datos:
    st.caption("Precios de cierre historicos.")
    st.dataframe(df_cierre.sort_index(ascending=False), use_container_width=True)
    csv = df_cierre.to_csv().encode("utf-8")
    st.download_button("Descargar CSV", csv, "mercados.csv", "text/csv")

st.caption("Fuente: Yahoo Finance (via yfinance). Datos con posible retraso; solo para fines informativos, no constituye recomendacion de inversion.")
