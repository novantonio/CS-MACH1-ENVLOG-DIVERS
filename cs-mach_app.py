import streamlit as st
import pandas as pd
import io
import requests
import matplotlib.pyplot as plt


# =========================================================
# 🧠 LOGGER PROCESSING (cached for speed)
# =========================================================
@st.cache_data(show_spinner=False)
def process_logger(raw_df):

    # metadata extraction (safe)
    serial = raw_df.iloc[9, 1]
    name = raw_df.iloc[10, 1]
    sampling = raw_df.iloc[13, 1]

    lat = pd.to_numeric(raw_df.iloc[15, 1], errors='coerce')
    lon = pd.to_numeric(raw_df.iloc[16, 1], errors='coerce')

    # fallback coordinates
    if pd.isna(lat) or pd.isna(lon):
        lat, lon = 44.377253, 9.073425

    if isinstance(name, str) and "surf" in name.lower():
        lat, lon = 43.573851, 7.126338

    # data extraction
    df = raw_df.iloc[21:, :].copy()
    df.columns = ['time', 'temperature']

    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')

    df = df.dropna(subset=['time', 'temperature'])

    df['month'] = df['time'].dt.month

    # metadata
    df['serial'] = serial
    df['custom_name'] = name
    df['sampling_f'] = sampling
    df['latitude'] = lat
    df['longitude'] = lon

    return df


# =========================================================
# 🌊 CORA DATA (cached by lat/lon)
# =========================================================
@st.cache_data(ttl=86400, show_spinner=False)
def load_cora_data(lat, lon):

    lat = round(lat, 2)
    lon = round(lon, 2)

    url = (
        "https://erddap.emodnet-physics.eu/erddap/griddap/"
        "INSITU_GLO_PHY_TS_OA_MY_013_052_TEMP.csv"
        f"?TEMP[(1990-01-01T00:00:00Z):1:(2023-06-15T00:00:00Z)]"
        f"[(1.0):1:(1)]"
        f"[({lat}):1:({lat})]"
        f"[({lon}):1:({lon})]"
    )

    r = requests.get(url, timeout=30, verify=False)
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text), skiprows=[1])

    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df['TEMP'] = pd.to_numeric(df['TEMP'], errors='coerce')

    df = df.dropna(subset=['time', 'TEMP'])

    df['month'] = df['time'].dt.month

    return df


# =========================================================
# 🎯 STREAMLIT UI
# =========================================================
st.title("🌡 CORA vs Multiple Logger Temperature Comparison")

uploaded_files = st.file_uploader(
    "Upload one or more logger CSV files",
    type=["csv"],
    accept_multiple_files=True
)


if uploaded_files:

    logger_datasets = []

    # =====================================================
    # 📂 PROCESS ALL FILES
    # =====================================================
    for file in uploaded_files:
        raw = pd.read_csv(file)
        df = process_logger(raw)

        if not df.empty:
            logger_datasets.append(df)

    if len(logger_datasets) == 0:
        st.error("No valid logger datasets found.")
        st.stop()

    # =====================================================
    # 🌍 USE FIRST FILE FOR LOCATION
    # =====================================================
    lat = logger_datasets[0]['latitude'].iloc[0]
    lon = logger_datasets[0]['longitude'].iloc[0]

    # =====================================================
    # 🌊 LOAD CORA (FAST CACHE)
    # =====================================================
    try:
        cora_data = load_cora_data(lat, lon)
        st.success("CORA data loaded")
    except Exception as e:
        st.error(f"CORA loading failed: {e}")
        st.stop()

    # =====================================================
    # 📊 CORA MONTHLY STATS
    # =====================================================
    cora_stats = cora_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()

    # =====================================================
    # 📈 PLOT
    # =====================================================
    fig, ax = plt.subplots(figsize=(10, 5))

    # CORA reference
    ax.errorbar(
        cora_stats['month'],
        cora_stats['mean'],
        yerr=cora_stats['std'],
        fmt='-o',
        label='CORA (mean ± std)'
    )

    # =====================================================
    # ⭐ MULTIPLE LOGGERS (STAR MARKERS)
    # =====================================================
    for i, df in enumerate(logger_datasets):

        stats = df.groupby('month')['temperature'].mean().reset_index()

        label = df['custom_name'].iloc[0] if 'custom_name' in df.columns else f"Logger {i+1}"

        ax.plot(
            stats['month'],
            stats['temperature'],
            marker='*',
            linestyle='None',
            markersize=14,
            label=label
        )

    # =====================================================
    # 🎨 FORMATTING
    # =====================================================
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([
        'Jan','Feb','Mar','Apr','May','Jun',
        'Jul','Aug','Sep','Oct','Nov','Dec'
    ])

    ax.set_xlabel("Month")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("CORA vs Multiple Logger Monthly Temperature")
    ax.grid(True)
    ax.legend()

    st.pyplot(fig)
