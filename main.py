import os
import time
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AI Growth Agent Engine")

class GrowthSignal(BaseModel):
    event_name: str
    campaign_name: str
    adset_id: str
    current_cpa: float
    target_cpa: float
    frequency: float

def send_telegram_alert(adset_id: str, action_summary: str) -> str:
    """
    Step 3: Action Driver
    Dispatches automated push alerts to Telegram when an AI decision is made.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return "SKIPPED: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing on Render."

    # Plain text format prevents Telegram Markdown parsing crashes on AI outputs
    message = f"🚨 AI GROWTH AGENT ACTION EXECUTED\n\nTarget AdSet: {adset_id}\n\n{action_summary}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message})
        if response.status_code == 200:
            return "SUCCESS: TELEGRAM_PUSH_ALERT_DISPATCHED"
        return f"FAILED: Telegram API returned {response.status_code} - {response.text}"
    except Exception as e:
        return f"FAILED: {str(e)}"

def run_ai_growth_reasoning(signal: GrowthSignal) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: GEMINI_API_KEY environment variable is missing on Render."

    prompt = f"""
    You are an autonomous AI Growth Engineer managing performance marketing campaigns.
    Analyze this inbound ad performance signal and make an operational decision:
    
    - Event: {signal.event_name}
    - Campaign: {signal.campaign_name}
    - AdSet ID: {signal.adset_id}
    - Current CPA: ${signal.current_cpa} (Target CPA: ${signal.target_cpa})
    - Ad Frequency: {signal.frequency}
    
    Rules:
    1. If CPA > 1.3x Target CPA OR Frequency > 4.5, output action: PAUSE_ADSET.
    2. If CPA < 0.8x Target CPA, output action: SCALE_BUDGET_20_PERCENT.
    3. Otherwise, output action: MAINTAIN.
    
    Format: State the EXACT action command first, followed by a concise 2-sentence rationale.
    """

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt,
                )
                if response.text:
                    return response.text
            except Exception as e:
                if attempt == 2:
                    return f"AI Generation Error: {str(e)}"
                time.sleep(1)

        return "AI Generation Error: No response generated."
    except Exception as e:
        return f"Initialization Error: {str(e)}"

@app.get("/")
def health_check():
    return {"status": "online", "system": "AI Growth Agent Prototype"}

@app.post("/webhooks/mmp-event")
async def handle_mmp_event(signal: GrowthSignal):
    # Step 2: AI Reasoning
    ai_analysis = run_ai_growth_reasoning(signal)
    
    # Step 3: Action Execution
    dispatch_status = send_telegram_alert(signal.adset_id, ai_analysis)
    
    return {
        "status": "processed",
        "adset_id": signal.adset_id,
        "ai_agent_output": ai_analysis,
        "action_execution": dispatch_status
    }
