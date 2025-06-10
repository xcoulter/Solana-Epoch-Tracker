import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Solana Epoch Tracker", layout="centered")

st.title("🟢 Solana Epoch Tracker")

RPC_URL = "https://api.mainnet-beta.solana.com"
SLOT_DURATION_SEC = 0.4  # Approximate slot time
SLOTS_PER_EPOCH = 432000
NUM_PAST_EPOCHS = 5

def get_epoch_info():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getEpochInfo"
    }
    try:
        response = requests.post(RPC_URL, json=payload, timeout=5)
        data = response.json()["result"]
        return data
    except Exception as e:
        st.error(f"Failed to fetch epoch info: {e}")
        return None

def get_block_height_for_slot(slot):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBlock",
        "params": [slot]
    }
    try:
        res = requests.post(RPC_URL, json=payload, timeout=5)
        block_data = res.json()["result"]
        return block_data.get("blockHeight")
    except Exception:
        return None

def render_current_epoch(data):
    epoch = data['epoch']
    slot_index = data['slotIndex']
    slots_in_epoch = data['slotsInEpoch']
    remaining_slots = slots_in_epoch - slot_index
    pct_done = (slot_index / slots_in_epoch) * 100
    time_remaining_sec = remaining_slots * SLOT_DURATION_SEC
    time_remaining = timedelta(seconds=time_remaining_sec)
    estimated_end = datetime.utcnow() + time_remaining

    starting_slot = data['absoluteSlot'] - data['slotIndex']
    ending_slot = starting_slot + data['slotsInEpoch'] - 1

    start_block = get_block_height_for_slot(starting_slot)
    end_block = get_block_height_for_slot(ending_slot)

    st.subheader("📈 Current Epoch Summary")
    st.metric("Epoch", epoch)
    st.metric("Slot Index", f"{slot_index:,} / {slots_in_epoch:,}")
    st.progress(pct_done / 100)
    st.metric("Progress", f"{pct_done:.2f}%")
    st.metric("Time Remaining", str(time_remaining).split('.')[0])
    st.metric("Estimated Epoch End (UTC)", estimated_end.strftime("%b %d, %Y, %H:%M UTC"))
    st.metric("Epoch Start Block", f"{start_block:,}" if start_block else "Unavailable")
    st.metric("Epoch End Block", f"{end_block:,}" if end_block else "Unavailable")

def generate_historical_epochs(current_epoch, current_starting_slot, slots_per_epoch=SLOTS_PER_EPOCH, num_epochs=NUM_PAST_EPOCHS):
    rows = []
    for i in range(num_epochs):
        epoch = current_epoch - i
        start_slot = current_starting_slot - (slots_per_epoch * i)
        end_slot = start_slot + slots_per_epoch - 1
        estimated_start_time = datetime.utcnow() - timedelta(seconds=(slots_per_epoch * i * SLOT_DURATION_SEC))
        estimated_end_time = estimated_start_time + timedelta(seconds=(slots_per_epoch * SLOT_DURATION_SEC))

        start_block = get_block_height_for_slot(start_slot)
        end_block = get_block_height_for_slot(end_slot)

        rows.append({
            "Epoch": epoch,
            "Start Slot": start_slot,
            "End Slot": end_slot,
            "Start Block": start_block if start_block else "Unavailable",
            "End Block": end_block if end_block else "Unavailable",
            "Est. Start Time (UTC)": estimated_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Est. End Time (UTC)": estimated_end_time.strftime("%Y-%m-%d %H:%M:%S")
        })
    return pd.DataFrame(rows)

def render_historical_table(df):
    st.subheader("📜 Historical Epochs")
    st.dataframe(df)

# Run dashboard
data = get_epoch_info()
if data:
    render_current_epoch(data)
    historical_df = generate_historical_epochs(
        current_epoch=data['epoch'],
        current_starting_slot=data['absoluteSlot'] - data['slotIndex']
    )
    render_historical_table(historical_df)
