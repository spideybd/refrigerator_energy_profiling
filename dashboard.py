# dashboard.py

import streamlit as st
import tinytuya
import pandas as pd
import time
from datetime import datetime
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Fridge Energy Monitor",
    page_icon="⚡",
    layout="wide"
)

# Load secrets from Streamlit's secrets management
DEVICE_ID = st.secrets["DEVICE_ID"]
DEVICE_IP = st.secrets["DEVICE_IP"]
LOCAL_KEY = st.secrets["LOCAL_KEY"]
# ------------------------------------

# --- Data Logging Setup ---
DATA_FILE = "energy_log.csv"

def init_data_log():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=["timestamp", "power_w", "voltage_v", "current_ma"])
        df.to_csv(DATA_FILE, index=False)

def log_data(power, voltage, current):
    new_data = pd.DataFrame([{
        "timestamp": datetime.now(),
        "power_w": power,
        "voltage_v": voltage,
        "current_ma": current
    }])
    new_data.to_csv(DATA_FILE, mode='a', header=False, index=False)

# --- NEW: kWh Calculation Function ---
def calculate_total_kwh(df):
    """Calculates the total energy consumption in kWh from the log data."""
    if len(df) < 2:
        return 0.0  # Not enough data to calculate

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # Calculate time difference between readings in seconds
    df['time_diff'] = df['timestamp'].diff().dt.total_seconds()

    # Calculate average power between consecutive readings (trapezoidal rule)
    df['avg_power'] = df['power_w'].rolling(window=2).mean()

    # Energy in Joules for each interval = avg_power (W) * time_diff (s)
    df['energy_joules'] = df['avg_power'] * df['time_diff']

    # Total energy in Joules is the sum of all intervals
    total_joules = df['energy_joules'].sum()

    # Convert Joules to kWh (1 kWh = 3,600,000 Joules)
    total_kwh = total_joules / 3600000
    
    return total_kwh

# --- Main Application ---
st.title("Refrigerator Real-Time Energy Monitor")
st.caption(f"Device ID: {DEVICE_ID}")

init_data_log()
placeholder = st.empty()

try:
    d = tinytuya.OutletDevice(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
    d.set_version(3.5)
except Exception as e:
    st.error(f"Failed to initialize connection to the Tuya device. Please check your configuration. Error: {e}")
    st.stop()

while True:
    try:
        data = d.status()
        if 'dps' in data:
            power = data['dps'].get('19', 0) / 10.0
            voltage = data['dps'].get('20', 0) / 10.0
            current = data['dps'].get('18', 0)

            log_data(power, voltage, current)

            with placeholder.container():
                df = pd.read_csv(DATA_FILE)
                total_kwh = calculate_total_kwh(df)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("⚡ Power", f"{power:.2f} W")
                col2.metric("🔌 Voltage", f"{voltage:.1f} V")
                col3.metric("💡 Current", f"{current} mA")
                col4.metric("🔋 Total Usage", f"{total_kwh:.3f} kWh")

                # --- Historical Data Chart ---
                st.subheader("Power Usage Over Time (Last 100 readings)")
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                recent_df = df.tail(100)
                st.line_chart(recent_df.rename(columns={'timestamp':'index'}).set_index('index')['power_w'])
                
                with st.expander("Show Raw Data Log"):
                    st.dataframe(df.tail(20))
        else:
            with placeholder.container():
                st.warning("Waiting for data... The device did not return DPS values.")

    except Exception as e:
        with placeholder.container():
            st.error(f"An error occurred while fetching data: {e}")
            st.warning("Will attempt to reconnect in 15 seconds...")
    
    time.sleep(15)