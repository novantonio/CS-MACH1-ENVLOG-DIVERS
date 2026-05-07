import streamlit as st
import pandas as pd
import io
import requests
import matplotlib.pyplot as plt


# =========================================================
# 🧠 LOGGER PROCESSING (cached)
# =========================================================
@st.cache_data(show_spinner=False)
def process_logger(raw_df):

    serial = raw_df.iloc[9, 1]
    name = raw_df.iloc[10, 1]
    sampling = raw_df.iloc[13, 1]

    lat = pd.to_numeric(raw_df.iloc[15, 1], errors='coerce')
    lon = pd.to_numeric(raw_df.iloc[16, 1], errors='coerce')

    if pd.isna(lat) or pd.isna(lon):
        lat, lon = 44.377253, 9.073425

    if isinstance(name, str) and "surf" in name.lower():
        lat, lon = 43.573851, 7.126338

    df = raw_df.iloc[21:, :].copy()
    df.columns = ['time', 'temperature']

    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')

    df = df.dropna(subset=['time', 'temperature'])

    df['month'] = df['time'].dt.month

    df['serial'] = serial
    df['custom_name'] = name
    df['sampling_f'] = sampling
    df['latitude'] = lat
    df['longitude'] = lon

    return df


# =========================================================
# 🌊 CORA DATA (cached)
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
st.title("🌡 CORA vs Multiple Logger Comparison")

uploaded_files = st.file_uploader(
    "Upload one or more logger CSV files",
    type=["csv"],
    accept_multiple_files=True
)

# store raw files in session state
if uploaded_files:
    st.session_state["files"] = uploaded_files

# =========================================================
# ▶️ START BUTTON
# =========================================================
if "files" in st.session_state and st.session_state["files"]:

    if st.button("▶️ Start Processing"):

        files = st.session_state["files"]

        logger_datasets = []

        progress = st.progress(0)
        status = st.empty()

        # =====================================================
        # 📂 PROCESS FILES WITH PROGRESS BAR
        # =====================================================
        for i, file in enumerate(files):

            status.write(f"Processing {file.name}...")

            raw = pd.read_csv(file)
            df = process_logger(raw)

            if not df.empty:
                logger_datasets.append(df)

            progress.progress((i + 1) / len(files))

        if len(logger_datasets) == 0:
            st.error("No valid datasets found.")
            st.stop()

        # =====================================================
        # 🌍 LOCATION FROM FIRST FILE
        # =====================================================
        lat = logger_datasets[0]['latitude'].iloc[0]
        lon = logger_datasets[0]['longitude'].iloc[0]

        # =====================================================
        # 🌊 LOAD CORA
        # =====================================================
        try:
            cora_data = load_cora_data(lat, lon)
            st.success("CORA data loaded")
        except Exception as e:
            st.error(f"CORA loading failed: {e}")
            st.stop()

        # =====================================================
        # 📊 STATS
        # =====================================================
        cora_stats = cora_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()
        
        cora_data['month'] = cora_data['time'].dt.month
        cora_monthly_stats = cora_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()


        # =====================================================
        # 📈 PLOT
        # =====================================================
        fig, ax = plt.subplots(figsize=(10, 5))

        # CORA
        ax.scatter(cora_monthly_stats['month'], cora_monthly_stats['mean'], label='Monthly Mean Temperature')
        ax.errorbar(cora_monthly_stats['month'], cora_monthly_stats['mean'], yerr=cora_monthly_stats['std'], fmt='o', capsize=3, label='Monthly Standard Deviation')

        #ax.errorbar(cora_stats['month'], cora_stats['mean'], yerr=cora_stats['std'], fmt='-o', label='CORA (mean ± std)')

        # ⭐ LOGGERS
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
