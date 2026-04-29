import os
import asyncio
import math
from datetime import datetime
from collections import deque

import numpy as np
import neurokit2 as nk
import uvicorn
from dotenv import load_dotenv
from google import genai
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 1. SETUP & SECURITY
load_dotenv()
llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="Hybrid AI Synchrony Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. STATE & CONFIGURATION
WINDOW_SIZE = 3000 
participant_buffers = {1: deque(maxlen=WINDOW_SIZE), 2: deque(maxlen=WINDOW_SIZE), 3: deque(maxlen=WINDOW_SIZE)}
last_inference_time = {1: 0, 2: 0, 3: 0}
rmssd_history = {1: [], 2: [], 3: []}
current_stress_states = {1: "Waiting...", 2: "Waiting...", 3: "Waiting..."}
last_intervention_time = 0

# Store the main event loop globally to access it from background threads
main_loop = None

class SensorData(BaseModel):
    participant_id: int
    ppg_samples: list[float]

# 3. WEBSOCKET FOR DASHBOARD
active_websockets = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

async def broadcast_to_dashboard(message_dict):
    """Pushes real-time JSON data to all connected dashboard tabs"""
    for connection in active_websockets:
        try:
            await connection.send_json(message_dict)
        except Exception:
            pass

def safe_broadcast(data):
    """Safely bridges the thread gap to send data to the WebSocket"""
    if main_loop:
        main_loop.call_soon_threadsafe(
            lambda: asyncio.create_task(broadcast_to_dashboard(data))
        )

# 4. CLINICAL HRV ANALYSIS
def classify_stress_clinically(rmssd, sdnn, hr, pnn50):
    scores = {"Calm": 0, "Mild Stress": 0, "High Stress": 0}
    if rmssd > 50: scores["Calm"] += 1
    elif 20 <= rmssd <= 50: scores["Mild Stress"] += 1
    else: scores["High Stress"] += 1

    if sdnn > 50: scores["Calm"] += 1
    elif 30 <= sdnn <= 50: scores["Mild Stress"] += 1
    else: scores["High Stress"] += 1

    if 60 <= hr <= 75: scores["Calm"] += 1
    elif 76 <= hr <= 90: scores["Mild Stress"] += 1
    else: scores["High Stress"] += 1

    if pnn50 > 20: scores["Calm"] += 1
    elif 5 <= pnn50 <= 20: scores["Mild Stress"] += 1
    else: scores["High Stress"] += 1
    return max(scores, key=scores.get)

# 5. HYBRID AI AGENT (LLM)
def generate_dynamic_message(team_state: str, style: str):
    prompt = f"You are an AI assistant helping a team of 3 solve a puzzle. The team is {team_state}. Write one short, natural sentence to help them. Tone: {style}."
    try:
        response = llm_client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Let's take a quick moment to regroup, team."

def calculate_synchrony_and_intervene():
    global last_intervention_time
    if len(rmssd_history[1]) < 3 or len(rmssd_history[2]) < 3 or len(rmssd_history[3]) < 3:
        return

    try:
        p1, p2, p3 = rmssd_history[1][-3:], rmssd_history[2][-3:], rmssd_history[3][-3:]
        sync_12 = np.nan_to_num(np.corrcoef(p1, p2)[0, 1])
        sync_13 = np.nan_to_num(np.corrcoef(p1, p3)[0, 1])
        sync_23 = np.nan_to_num(np.corrcoef(p2, p3)[0, 1])
        group_sync = np.mean([sync_12, sync_13, sync_23])
        
        # WE USE 1.1 TO FORCE A TRIGGER FOR TONIGHT'S TEST
        if (datetime.now().timestamp() - last_intervention_time) > 60: # 1 min cooldown
            msg, trig = None, None
            if "High Stress" in current_stress_states.values():
                msg = generate_dynamic_message("stressed", "calming")
                trig = "High Stress"
            elif group_sync < 1.1: 
                msg = generate_dynamic_message("needing sync", "supportive")
                trig = "Sync Check"
                
            if msg:
                print(f"\n>> AI INTERVENTION: {msg}")
                last_intervention_time = datetime.now().timestamp()
                safe_broadcast({"type": "intervention", "trigger": trig, "message": msg})
    except Exception as e:
        print(f"Sync Error: {e}")

# 6. DATA PROCESSING
def process_hrv(participant_id: int, raw_window: np.ndarray):
    try:
        signals, info = nk.ppg_process(raw_window, sampling_rate=50)
        if len(info['PPG_Peaks']) > 3:
            hrv_time = nk.hrv_time(info['PPG_Peaks'], sampling_rate=50)
            rmssd = float(hrv_time['HRV_RMSSD'].values[0])
            sdnn = float(hrv_time['HRV_SDNN'].values[0])
            pnn50 = float(hrv_time['HRV_pNN50'].values[0])
            hr = float(np.mean(signals['PPG_Rate']))
            
            stress_state = classify_stress_clinically(rmssd, sdnn, hr, pnn50)
            rmssd_history[participant_id].append(rmssd)
            current_stress_states[participant_id] = stress_state
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] P{participant_id} | {stress_state} | RMSSD: {rmssd:.1f}ms")
            
            # SEND LIVE STATS TO DASHBOARD
            safe_broadcast({
                "type": "live_stats",
                "participant_id": participant_id,
                "stress": stress_state,
                "rmssd": round(rmssd, 2)
            })

            if participant_id == 3:
                calculate_synchrony_and_intervene()
    except Exception as e:
        print(f"Analysis Error P{participant_id}: {e}")

# 7. ROUTES
@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

@app.post("/sensor-data")
async def receive_data(data: SensorData, background_tasks: BackgroundTasks):
    pid = data.participant_id
    if pid not in [1, 2, 3]: return {"error": "Invalid PID"}
    participant_buffers[pid].extend(data.ppg_samples)
    
    if len(participant_buffers[pid]) == WINDOW_SIZE:
        curr_t = datetime.now().timestamp()
        if curr_t - last_inference_time[pid] >= 10.0:
            last_inference_time[pid] = curr_t
            background_tasks.add_task(process_hrv, pid, np.array(participant_buffers[pid]))
    return {"status": "buffered"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)