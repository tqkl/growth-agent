import os
import time
from typing import Optional
import requests
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from prospect_scanner import build_prospect_audit

app = FastAPI(title="AI Growth Agent Engine")


# ==========================================
# PART 1: EXISTING 24/7 CPA & BUDGET GUARD
# ==========================================
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
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
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
                    model="gemini-3.5-flash-lite",
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
        "action_execution": dispatch_status,
    }


# ==========================================
# PART 2: ZERO-ACCESS B2B PROSPECT SCANNER
# ==========================================
class ProspectScanPayload(BaseModel):
    business_name: str
    website_url: str
    fb_page_url: Optional[str] = None
    contact_info: Optional[str] = None
    language: str = "vi"  # "vi" or "zh"


def send_telegram_chunks(text: str) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)]

    for chunk in chunks:
        try:
            requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
        except Exception:
            pass


def run_scan_and_notify(payload: ProspectScanPayload) -> None:
    signals, audit_report = build_prospect_audit(
        business_name=payload.business_name,
        website_url=payload.website_url,
        fb_page_url=payload.fb_page_url,
        lang=payload.language,
    )
    site = signals["site"]
    speed = signals["speed"]

    header = (
        f"🔍 PROSPECT FUNNEL SCAN READY\n"
        f"Client: {payload.business_name}\n"
        f"URL: {payload.website_url}\n"
        f"Contact: {payload.contact_info or 'N/A'}\n"
        f"Signals: MetaPixel={site.get('has_meta_pixel')} | "
        f"GTM={site.get('has_gtm')} | Zalo={site.get('has_zalo_widget')} | "
        f"Mobile={speed.get('mobile_score')}/100 (LCP {speed.get('lcp_load_time')})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    send_telegram_chunks(header + audit_report)


@app.post("/scan-prospect")
async def scan_prospect(payload: ProspectScanPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan_and_notify, payload)
    return {
        "status": "queued",
        "message": f"Scanning {payload.business_name}. Audit will arrive on Telegram in ~15 seconds.",
    }
