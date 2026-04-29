import requests
import time
import numpy as np
import neurokit2 as nk

SERVER_URL = "http://127.0.0.1:8000/sensor-data"

print("Starting Mock ESP32 Simulator...")

simulated_ppg = nk.ppg_simulate(duration=300, sampling_rate=50, heart_rate=70)
chunk_size = 100 
current_index = 0

try:
    while current_index + chunk_size < len(simulated_ppg):
        chunk = simulated_ppg[current_index : current_index + chunk_size]
        
        for pid in [1, 2, 3]:
            noisy_chunk = chunk + np.random.normal(0, 0.05, chunk_size)
            payload = {"participant_id": pid, "ppg_samples": noisy_chunk.tolist()}
            
            try:
                requests.post(SERVER_URL, json=payload)
            except requests.exceptions.ConnectionError:
                print("Server offline. Start main.py first.")
                break

        print(f"Sent 2-second data chunk (Index {current_index})...")
        current_index += chunk_size
        time.sleep(2) 

except KeyboardInterrupt:
    print("\nSimulator stopped.")