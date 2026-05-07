import streamlit as st
import pandas as pd
import numpy as np
import io
import requests
import matplotlib.pyplot as plt

def envlogcsv_to_df(env_data, verbose=0):

    serial = env_data.iloc[9, 1]
    name = env_data.iloc[10, 1]
    sampling = env_data.iloc[13, 1]

    # coordinates
    latitude = pd.to_numeric(env_data.iloc[15, 1], errors='coerce')
    longitude = pd.to_numeric(env_data.iloc[16, 1], errors='coerce')

    if verbose:
        print(f"Latitude: {latitude}, Longitude: {longitude}")

    # fallback coordinates
    if pd.isna(latitude) or pd.isna(longitude):
        if verbose:
            print("Error: invalid coordinates -> using Bogliasco fallback")

        latitude = 44.377253
        longitude = 9.073425

    # special case for surf sensors
    if isinstance(name, str) and 'surf' in name.lower():
        latitude = 43.573851
        longitude = 7.126338

    # extract measurements
    env_data = env_data.iloc[21:, :].copy()

    env_data = env_data.dropna().reset_index(drop=True)

    env_data.columns = ['time', 'temperature']

    env_data['time'] = pd.to_datetime(
        env_data['time'],
        errors='coerce'
    )

    env_data['temperature'] = pd.to_numeric(
        env_data['temperature'],
        errors='coerce'
    )

    # metadata columns
    env_data['serial'] = serial
    env_data['custom_name'] = name
    env_data['sampling_f'] = sampling
    env_data['latitude'] = latitude
    env_data['longitude'] = longitude

    return env_data

st.title("CORA vs Logger Temperature Comparison")

# -------------------------
# 📂 Upload CSV
# -------------------------
uploaded_file = st.file_uploader("Upload your logger CSV file", type=["csv"])

if uploaded_file is not None:

    # read uploaded file
    file_csv = pd.read_csv(uploaded_file)

    st.success("File uploaded successfully!")

    logger_data = envlogcsv_to_df (file_csv, 1)

    # -------------------------
    # basic cleaning (adapt if needed)
    # -------------------------
    if 'time' not in logger_data.columns or 'temperature' not in logger_data.columns:
        st.error("CSV must contain 'time' and 'temperature' columns")
        st.stop()

    logger_data['time'] = pd.to_datetime(logger_data['time'], errors='coerce')
    logger_data['temperature'] = pd.to_numeric(logger_data['temperature'], errors='coerce')
    logger_data = logger_data.dropna(subset=['time', 'temperature'])

    # -------------------------
    # CORA URL (example: replace with your function if needed)
    # -------------------------
    latitude = logger_data['latitude'].iloc[0] if 'latitude' in logger_data.columns else 44.37
    longitude = logger_data['longitude'].iloc[0] if 'longitude' in logger_data.columns else 9.07

    cora_url = (
        "https://erddap.emodnet-physics.eu/erddap/griddap/"
        "INSITU_GLO_PHY_TS_OA_MY_013_052_TEMP.csv"
        f"?TEMP[(1990-01-01T00:00:00Z):1:(2023-06-15T00:00:00Z)]"
        f"[(1.0):1:(1)]"
        f"[({latitude}):1:({latitude})]"
        f"[({longitude}):1:({longitude})]"
    )

    # -------------------------
    # fetch CORA
    # -------------------------
    try:
        response = requests.get(cora_url, timeout=30, verify=False)
        response.raise_for_status()

        cora_temp_data = pd.read_csv(io.StringIO(response.text), skiprows=[1])

        cora_temp_data['time'] = pd.to_datetime(cora_temp_data['time'], errors='coerce')
        cora_temp_data['TEMP'] = pd.to_numeric(cora_temp_data['TEMP'], errors='coerce')
        cora_temp_data = cora_temp_data.dropna(subset=['time', 'TEMP'])

        st.success("CORA data loaded successfully")

    except Exception as e:
        st.error(f"Failed to load CORA data: {e}")
        st.stop()

    # -------------------------
    # monthly stats
    # -------------------------
    cora_temp_data['month'] = cora_temp_data['time'].dt.month

    cora_stats = cora_temp_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()

    logger_data['month'] = logger_data['time'].dt.month
    logger_stats = logger_data.groupby('month')['temperature'].mean().reset_index()

    # -------------------------
    # plot
    # -------------------------
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.errorbar(
        cora_stats['month'],
        cora_stats['mean'],
        yerr=cora_stats['std'],
        fmt='-o',
        label='CORA (mean ± std)'
    )

    ax.plot(
        logger_stats['month'],
        logger_stats['temperature'],
        '*',
        markersize=12,
        label='Logger mean'
    )

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([
        'Jan','Feb','Mar','Apr','May','Jun',
        'Jul','Aug','Sep','Oct','Nov','Dec'
    ])

    ax.set_xlabel("Month")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("CORA vs Logger Monthly Temperature")
    ax.grid(True)
    ax.legend()

    st.pyplot(fig)
