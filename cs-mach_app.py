import streamlit as st
import pandas as pd
import io
import requests
import matplotlib.pyplot as plt


# -------------------------
# 🧠 DATA PROCESSING
# -------------------------
def envlogcsv_to_df(env_data, verbose=False):

    serial = env_data.iloc[9, 1]
    name = env_data.iloc[10, 1]
    sampling = env_data.iloc[13, 1]

    # coordinates
    latitude = pd.to_numeric(env_data.iloc[15, 1], errors='coerce')
    longitude = pd.to_numeric(env_data.iloc[16, 1], errors='coerce')

    if verbose:
        st.write(f"Latitude: {latitude}, Longitude: {longitude}")

    # fallback coordinates
    if pd.isna(latitude) or pd.isna(longitude):
        latitude, longitude = 44.377253, 9.073425

    # special case
    if isinstance(name, str) and "surf" in name.lower():
        latitude, longitude = 43.573851, 7.126338

    # extract measurements
    df = env_data.iloc[21:, :].copy()
    df.columns = ['time', 'temperature']

    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')

    df = df.dropna(subset=['time', 'temperature'])

    # metadata
    df['serial'] = serial
    df['custom_name'] = name
    df['sampling_f'] = sampling
    df['latitude'] = latitude
    df['longitude'] = longitude

    return df


# -------------------------
# 🌊 CORA DATA FETCH
# -------------------------
@st.cache_data(ttl=3600)
def load_cora_data(url):
    response = requests.get(url, timeout=60, verify=False)
    response.raise_for_status()

    cora = pd.read_csv(io.StringIO(response.text), skiprows=[1])

    cora['time'] = pd.to_datetime(cora['time'], errors='coerce')
    cora['TEMP'] = pd.to_numeric(cora['TEMP'], errors='coerce')

    return cora.dropna(subset=['time', 'TEMP'])


# -------------------------
# 🎯 STREAMLIT UI
# -------------------------
st.title("🌡 CORA vs Logger Temperature Comparison")

uploaded_file = st.file_uploader("Upload logger CSV file", type=["csv"])

if uploaded_file:

    # -------------------------
    # LOAD + PROCESS LOGGER
    # -------------------------
    raw_df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully!")

    logger_data = envlogcsv_to_df(raw_df)

    # safety check
    if logger_data.empty:
        st.error("No valid data found in CSV")
        st.stop()

    # -------------------------
    # CORA URL
    # -------------------------
    lat = logger_data['latitude'].iloc[0]
    lon = logger_data['longitude'].iloc[0]

    cora_url = (
        "https://erddap.emodnet-physics.eu/erddap/griddap/"
        "INSITU_GLO_PHY_TS_OA_MY_013_052_TEMP.csv"
        f"?TEMP[(1990-01-01T00:00:00Z):1:(2023-06-15T00:00:00Z)]"
        f"[(1.0):1:(1)]"
        f"[({lat}):1:({lat})]"
        f"[({lon}):1:({lon})]"
    )

    # -------------------------
    # LOAD CORA
    # -------------------------
    try:
        cora_data = load_cora_data(cora_url)
        st.success("CORA data loaded successfully")
    except Exception as e:
        st.error(f"Failed to load CORA data: {e}")
        st.stop()

    # -------------------------
    # MONTHLY STATS
    # -------------------------
  
    cora_stats = cora_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()


    cora_temp_data['month'] = cora_data['time'].dt.month
    cora_monthly_stats = cora_temp_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()

    
    # -------------------------
    # PLOT
    # -------------------------
    fig, ax = plt.subplots(figsize=(10, 5))

    
    plt.figure(figsize=(12, 6))
    ax.scatter(cora_monthly_stats['month'], cora_monthly_stats['mean'], label='Monthly Mean Temperature')
    ax.errorbar(cora_monthly_stats['month'], cora_monthly_stats['mean'], yerr=cora_monthly_stats['std'], fmt='o', capsize=3, label='Monthly Standard Deviation')  
    
    d = logger_data['time'].iloc[0].month
    tavg = logger_data['temperature'].mean()
    ax.plot(d, tavg, '*', markersize=20, label=fn)
    
    ax.set_xlabel('Month')
    ax.set_ylabel("Temperature [°C]")
    ax.set_title('Monthly Mean and Standard Deviation of Temperature from Cora Data')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([
        'Jan','Feb','Mar','Apr','May','Jun',
        'Jul','Aug','Sep','Oct','Nov','Dec'
    ])
    ax.grid(True)
   

    st.pyplot(fig)
