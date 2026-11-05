import os
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

def run_ai_growth_reasoning(signal: GrowthSignal) -> str:
    # 1. Fetch API key safely inside execution scope
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: GEMINI_API_KEY environment variable is missing on Render."

    try:
        from google import genai
        # Initialize client inside call scope
        client = genai.Client(api_key=api_key)
        
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
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"AI Generation Error: {str(e)}"

@app.get("/")
def health_check():
    return {"status": "online", "system": "AI Growth Agent Prototype"}

@app.post("/webhooks/mmp-event")
async def handle_mmp_event(signal: GrowthSignal):
    ai_analysis = run_ai_growth_reasoning(signal)
    
    return {
        "status": "processed",
        "adset_id": signal.adset_id,
        "ai_agent_output": ai_analysis
    }import os
from fastapi import FastAPI, BackgroundTasks
from google import genai
from google.genai import types
from pydantic import BaseModel

app = FastAPI(title="AI Growth Agent Engine")

# Initialize Gemini Client (reads GEMINI_API_KEY from environment)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "YOUR_FALLBACK_KEY"))

class GrowthSignal(BaseModel):
    event_name: str
    campaign_name: str
    adset_id: str
    current_cpa: float
    target_cpa: float
    frequency: float

def run_ai_growth_reasoning(signal: GrowthSignal) -> str:
    """Uses Gemini 2.5 Flash to act as an autonomous Growth Engineer."""
    prompt = f"""
    You are an AI Growth Engineer managing performance marketing campaigns.
    Analyze this inbound ad performance signal and decide on an immediate action:
    
    - Event: {signal.event_name}
    - Campaign: {signal.campaign_name}
    - AdSet ID: {signal.adset_id}
    - Current CPA: ${signal.current_cpa} (Target CPA: ${signal.target_cpa})
    - Ad Frequency: {signal.frequency}
    
    Rules:
    1. If CPA > 1.3x Target CPA OR Frequency > 4.5, recommend PAUSE_ADSET.
    2. If CPA < 0.8x Target CPA, recommend SCALE_BUDGET_20_PERCENT.
    3. Otherwise, recommend MAINTAIN.
    
    Return a concise 2-sentence rationale and state the EXACT action command.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

@app.get("/")
def health_check():
    return {"status": "online", "system": "AI Growth Agent Prototype"}

@app.post("/webhooks/mmp-event")
async def handle_mmp_event(signal: GrowthSignal):
    # Run real-time AI reasoning
    ai_analysis = run_ai_growth_reasoning(signal)
    
    return {
        "status": "processed",
        "adset_id": signal.adset_id,
        "ai_agent_output": ai_analysis
    }
