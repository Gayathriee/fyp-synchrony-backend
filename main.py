import os
import math
import asyncio
import logging
from collections import deque
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

# Setup basic logging to catch errors instead of swallowing them silently
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Initialize the LLM Agent
# Pull the API key from environment variables for security. 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY environment variable is missing!")

genai.configure(api_key=GEMINI_API_KEY)
llm_model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI(title="Hybrid AI Synchrony Backend")

# Allow the React frontend to talk to the FastAPI backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Pushes real-time JSON data to the React dashboard"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to a websocket client: {e}")

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keeps the pipe open
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ... [Keep your WINDOW_SIZE, buffers, and classify_stress_clinically function exactly as they were] ...


def generate_dynamic_message(team_state: str, style: str) -> str:
    """Calls Gemini to generate a unique, context-aware intervention."""
    prompt = (
        f"You are an AI assistant helping a team of 3 people collaborate on a complex puzzle. "
        f"Right now, the team is {team_state}. "
        f"Write a single, short sentence to display on their screen to help them. "
        f"The tone must be {style}. Be natural and human-like. Do not be robotic."
    )
    
    try:
        response = llm_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "Let's take a quick pause to sync up, team!" # Fallback message


def safe_correlation(p_a, p_b):
    """Helper to calculate correlation and handle NaNs cleanly."""
    corr = np.corrcoef(p_a, p_b)[0, 1]
    return 0 if math.isnan(corr) else corr


def calculate_synchrony_and_intervene():
    global last_intervention_time
    
    # Ensure we have enough data to calculate
    if any(len(rmssd_history[i]) < 3 for i in (1, 2, 3)):
        return

    p1, p2, p3 = rmssd_history[1][-3:], rmssd_history[2][-3:], rmssd_history[3][-3:]

    try:
        # Calculate group synchrony
        sync_12 = safe_correlation(p1, p2)
        sync_13 = safe_correlation(p1, p3)
        sync_23 = safe_correlation(p2, p3)
        group_sync = np.mean([sync_12, sync_13, sync_23])
        
        current_time = asyncio.get_event_loop().time()
        
        # Cooldown check (120 seconds)
        if current_time - last_intervention_time < 120:
            return

        # Determine if an intervention is needed
        trigger_type = None
        team_state = ""
        style = ""

        if "High Stress" in current_stress_states.values():
            trigger_type = "Individual High Stress"
            team_state = "experiencing high cognitive load and stress"
            style = "calming, empathetic, and brief"
            
        elif group_sync < 0.30:
            trigger_type = "Low Team Synchrony"
            team_state = "working independently and not communicating well"
            style = "encouraging, collaborative, and directive"

        # Execute the intervention if a trigger condition was met
        if trigger_type:
            logger.info(f"\n>> HYBRID AI: {trigger_type} Detected!")
            logger.info(">> Asking LLM to generate an intervention...")
            
            message = generate_dynamic_message(team_state, style)
            logger.info(f">> AI SAYS: '{message}'\n")
            
            last_intervention_time = current_time
            
            # Send the AI message to the React Dashboard instantly safely
            payload = {
                "type": "intervention",
                "trigger": trigger_type,
                "message": message
            }
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(payload),
                asyncio.get_event_loop()
            )
            
    except Exception as e:
        logger.error(f"Error calculating synchrony: {e}")

# ... [Keep your process_hrv and receive_data functions exactly as they were] ...