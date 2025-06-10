import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import time
import os

st.set_page_config(page_title="Solana Epoch Tracker", layout="wide")
st.title("🟢 Solana Epoch Tracker")

RPC_URL = "https://api.mainnet-beta.solana.com"
SLOTS_PER_EPOCH = 432000
FIXED_SLOT_DURATION = 0.4
TRACKING_FILE = "realtime_epoch_data.csv"

@st.cache_data(ttl=300)
def estimate_slot_duration(samples=5, interval_sec=10):
    def get_current_slot():
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getSlot"}
        try:
            response = requests.post(RPC_URL, json=payload, timeout=5)
            return response.json()["result"]
        except Exception:
            return None

    slots = []
    for _ in range(samples):
        slot = get_current_slot()
        if slot is not None:
            slots.append((time.time(), slot))
        time.sleep(interval_sec)

    if len(slots) >= 2:
        t0, s0 = slots[0]
        t1, s1 = slots[-1]
        if s1 != s0:
            return (t1 - t0) / (s1 - s0)
    return FIXED_SLOT_DURATION

def get_epoch_info():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getEpochInfo"}
    try:
        response = requests.post(RPC_URL, json=payload, timeout=5)
        return response.json()["result"]
    except Exception as e:
        st.error(f"Failed to fetch epoch info: {e}")
        return None

def get_block(slot):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBlock", "params": [slot]}
    try:
        response = requests.post(RPC_URL, json=payload, timeout=5)
        return response.json().get("result")
    except Exception:
        return None

def estimate_total_transactions(start_slot, end_slot, sample_rate=1000):
    tx_count = 0
    slots_sampled = 0
    for slot in range(start_slot, end_slot, sample_rate):
        block = get_block(slot)
        if block and "transactions" in block:
            tx_count += len(block["transactions"])
            slots_sampled += 1
    avg_tx_per_block = tx_count / slots_sampled if slots_sampled else 0
    estimated_total = avg_tx_per_block * (end_slot - start_slot)
    return int(estimated_total)

def record_epoch_stats(epoch, tx_estimate, file_path=TRACKING_FILE):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = {"Epoch": epoch, "Estimated Total Transactions": tx_estimate, "Timestamp": timestamp}
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if epoch not in df["Epoch"].values:
            df = df.append(row, ignore_index=True)
            df.to_csv(file_path, index=False)
    else:
        df = pd.DataFrame([row])
        df.to_csv(file_path, index=False)

def load_epoch_stats(file_path=TRACKING_FILE):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=["Epoch", "Estimated Total Transactions", "Timestamp"])

def render_current_epoch(data, slot_duration):
    epoch = data['epoch']
    slot_index = data['slotIndex']
    slots_in_epoch = data['slotsInEpoch']
    remaining_slots = slots_in_epoch - slot_index
    pct_done = (slot_index / slots_in_epoch) * 100
    time_remaining_sec = remaining_slots * slot_duration
    estimated_end = datetime.utcnow() + timedelta(seconds=time_remaining_sec)

    start_slot = data['absoluteSlot'] - data['slotIndex']
    end_slot = start_slot + slots_in_epoch - 1

    st.subheader("📈 Current Epoch Summary")
    st.metric("Epoch", epoch)
    st.metric("Slot Index", f"{slot_index:,} / {slots_in_epoch:,}")
    st.progress(pct_done / 100)
    st.metric("Progress", f"{pct_done:.2f}%")
    st.metric("Time Remaining", str(timedelta(seconds=time_remaining_sec)).split('.')[0])
    st.metric("Estimated Epoch End (UTC)", estimated_end.strftime("%b %d, %Y, %H:%M UTC"))
    st.caption(f"🧠 Estimated Slot Duration: {slot_duration:.3f} seconds (adaptive)")

    # If we're at the beginning of a new epoch, estimate tx count
    if slot_index < 10:
        tx_estimate = estimate_total_transactions(start_slot, end_slot)
        record_epoch_stats(epoch - 1, tx_estimate)

def generate_full_epoch_history(current_epoch, current_starting_slot):
    rows = []
    for i in range(current_epoch + 1):
        epoch = current_epoch - i
        start_slot = current_starting_slot - (SLOTS_PER_EPOCH * i)
        end_slot = start_slot + SLOTS_PER_EPOCH - 1
        est_start = datetime.utcnow() - timedelta(seconds=(SLOTS_PER_EPOCH * i * FIXED_SLOT_DURATION))
        est_end = est_start + timedelta(seconds=(SLOTS_PER_EPOCH * FIXED_SLOT_DURATION))
        rows.append({
            "Epoch": epoch,
            "Start Slot": start_slot,
            "End Slot": end_slot,
            "Start Block": "Approximate",
            "End Block": "Approximate",
            "Est. Start Time (UTC)": est_start.strftime("%Y-%m-%d %H:%M:%S"),
            "Est. End Time (UTC)": est_end.strftime("%Y-%m-%d %H:%M:%S")
        })
    return pd.DataFrame(rows)

def render_historical(df):
    st.subheader("📜 Full Historical Epochs (Estimated)")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download History CSV", data=csv, file_name="solana_epoch_history.csv")

def render_epoch_stats():
    df = load_epoch_stats()
    if not df.empty:
        st.subheader("🧾 Recorded Epoch Stats (Forward-Tracked Only)")
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Stats CSV", data=csv, file_name="realtime_epoch_stats.csv")

data = get_epoch_info()
if data:
    live_slot_duration = estimate_slot_duration()
    render_current_epoch(data, live_slot_duration)
    hist_df = generate_full_epoch_history(data['epoch'], data['absoluteSlot'] - data['slotIndex'])
    render_historical(hist_df)
    render_epoch_stats()
