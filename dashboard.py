# dashboard.py

import streamlit as st
from tuya_iot import TuyaOpenAPI
import pandas as pd
import time
from datetime import datetime
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Cloud Fridge Monitor",
    page_icon="🧊",
    layout="wide"
)

# --- Load Secrets from Streamlit's secrets management ---
# Make sure you have these in your Streamlit Cloud app's secrets!
try:
    ACCESS_ID = st.secrets["ACCESS_ID"]
    ACCESS_SECRET = st.secrets["ACCESS_SECRET"]
    API_ENDPOINT = st.secrets["API_ENDPOINT"]
    DEVICE_ID = st.secrets["DEVICE_ID"]
except (FileNotFoundError, KeyError):
    st.error("Could not find Tuya credentials. Please add them to your secrets.")
    st.stop()

# --- Tuya Function Codes (Update these if yours are different!) ---
# Find these in your Tuya IoT Project under: Devices -> Debug Device
POWER_CODE = 'cur_power'
VOLTAGE_CODE = 'cur_voltage'
CURRENT_CODE = 'cur_current'

# --- Connect to Tuya Cloud ---
try:
    openapi = TuyaOpenAPI(API_ENDPOINT, ACCESS_ID, ACCESS_SECRET)
    openapi.connect()
except Exception as e:
    st.error(f"Failed to connect to Tuya Cloud. Please check your credentials. Error: {e}")
    st.stop()

# --- Data Logging & kWh Calculation Functions (No Changes Here) ---
DATA_FILE = "energy_log.csv"

def init_data_log():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=["timestamp", "power_w", "voltage_v", "current_ma"])
        df.to_csv(DATA_FILE, index=False)

def log_data(power, voltage, current):
    new_data = pd.DataFrame([{"timestamp": datetime.now(), "power_w": power, "voltage_v": voltage, "current_ma": current}])
    new_data.to_csv(DATA_FILE, mode='a', header=False, index=False)

def calculate_total_kwh(df):
    if len(df) < 2: return 0.0
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    df['time_diff'] = df['timestamp'].diff().dt.total_seconds()
    df['avg_power'] = df['power_w'].rolling(window=2).mean()
    df['energy_joules'] = df['avg_power'] * df['time_diff']
    total_joules = df['energy_joules'].sum()
    total_kwh = total_joules / 3600000
    return total_kwh
# --- End of helper functions ---


# --- Main Application ---
st.title("🧊 Cloud Fridge Energy Monitor")
st.caption(f"Monitoring Device ID: {DEVICE_ID}")
init_data_log()
placeholder = st.empty()

while True:
    try:
        # Get device status from the cloud
        response = openapi.get(f"/v1.0/devices/{DEVICE_ID}/status")

        if response.get('success', False):
            status_map = {item['code']: item['value'] for item in response['result']}

            # Extract current states
            power = status_map.get(POWER_CODE, 0) / 10.0
            voltage = status_map.get(VOLTAGE_CODE, 0) / 10.0
            current = status_map.get(CURRENT_CODE, 0)

            with placeholder.container():
                st.header("Live Energy Data")
                log_data(power, voltage, current)
                df = pd.read_csv(DATA_FILE)
                total_kwh = calculate_total_kwh(df)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("⚡ Power", f"{power:.2f} W")
                col2.metric("🔌 Voltage", f"{voltage:.1f} V")
                col3.metric("💡 Current", f"{current} mA")
                col4.metric("🔋 Total Usage", f"{total_kwh:.3f} kWh")

                st.subheader("📊 Power Usage Over Time")
                st.line_chart(df.rename(columns={'timestamp':'index'}).set_index('index')['power_w'].tail(100))
        else:
            with placeholder.container():
                st.error(f"Error from Tuya API: {response.get('msg', 'Unknown Error')}")

    except Exception as e:
        with placeholder.container():
            st.error(f"An error occurred: {e}")
            st.warning("Retrying in 30 seconds...")
    
    # Cloud APIs have rate limits, so a longer sleep time is better
    time.sleep(30)
