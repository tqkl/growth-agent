import os
import time
from typing import Optional
import requests
from fastapi import FastAPI
from pydantic import BaseModel

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
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return "SKIPPED: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing on Render."

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
    ai_analysis = run_ai_growth_reasoning(signal)
    dispatch_status = send_telegram_alert(signal.adset_id, ai_analysis)

    return {
        "status": "processed",
        "adset_id": signal.adset_id,
        "ai_agent_output": ai_analysis,
        "action_execution": dispatch_status,
    }


# ==========================================
# PART 2: OPTION 1 HYBRID PROSPECT SCANNER
# (PageSpeed Insights API + Meta Ad Copy Input)
# ==========================================
class ProspectScanPayload(BaseModel):
    business_name: str
    website_url: Optional[str] = None
    fb_page_url: Optional[str] = None
    active_ads_count: Optional[int] = None
    ad_copy_sample: Optional[str] = None
    contact_info: Optional[str] = None
    language: str = "vi"  # "vi" or "zh"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def fetch_pagespeed_signals(url: str) -> dict:
    target = normalize_url(url)
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": target, "strategy": "mobile", "category": "performance"}

    if os.environ.get("PAGESPEED_API_KEY"):
        params["key"] = os.environ.get("PAGESPEED_API_KEY")

    try:
        r = requests.get(endpoint, params=params, timeout=45)
        data = r.json()

        if "error" in data:
            return {
                "ok": False,
                "error_code": data["error"].get("code"),
                "error_message": data["error"].get("message"),
            }

        lh = data.get("lighthouseResult") or {}
        categories = lh.get("categories") or {}
        perf = categories.get("performance") or {}
        audits = lh.get("audits") or {}

        raw_score = perf.get("score")
        lcp = (audits.get("largest-contentful-paint") or {}).get("displayValue", "N/A")
        fcp = (audits.get("first-contentful-paint") or {}).get("displayValue", "N/A")

        net_items = ((audits.get("network-requests") or {}).get("details") or {}).get("items") or []
        req_urls = " ".join(item.get("url", "") for item in net_items).lower()

        return {
            "ok": True,
            "mode": "website_plus_ads",
            "mobile_score": round(raw_score * 100) if raw_score is not None else "N/A",
            "lcp_load_time": lcp,
            "fcp_load_time": fcp,
            "has_meta_pixel": ("facebook.com/tr" in req_urls) or ("fbevents.js" in req_urls),
            "has_gtm": "googletagmanager.com/gtm.js" in req_urls,
            "has_ga4_or_gads": ("googletagmanager.com/gtag/js" in req_urls) or ("google-analytics.com" in req_urls),
            "has_zalo_widget": "zalo.me" in req_urls,
        }
    except Exception as e:
        return {"ok": False, "error_message": str(e)}


def generate_prospect_audit(payload: ProspectScanPayload, psi: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: GEMINI_API_KEY missing on Render."

    output_lang = "Vietnamese" if payload.language.lower() == "vi" else "Simplified Chinese"
    prompt = f"""
You are a Senior B2B Performance Growth Strategist preparing a fast, high-value pre-call audit for an SME prospect in Vietnam.
Business Name: {payload.business_name}
Website URL: {payload.website_url or "None (Fanpage-only funnel)"}
Facebook Page URL: {payload.fb_page_url or "Not provided"}
Active Meta Ads Count (from Ad Library): {payload.active_ads_count if payload.active_ads_count is not None else "Not specified"}
Live Facebook Ad Copy Sample:
\"\"\"{payload.ad_copy_sample or "Not provided"}\"\"\"

Technical Website & Tracking Signals (Google PageSpeed Insights):
{psi}

Write a sharp, persuasive 1-page audit in {output_lang} ready to paste directly into Zalo or Messenger. Use clean plain text and bullet points ONLY (strictly NO ** bold asterisks or ## headers). Include:
1. 3 LỖ HỔNG ĐANG LÀM TĂNG CHI PHÍ QUẢNG CÁO (3 AD & FUNNEL LEAKS):
   - If website signals exist: cite the exact mobile score, LCP load speed, and missing tags (Meta Pixel, GTM, GA4, Zalo widget) above.
   - If Fanpage-only (no website): explain the conversion/retargeting leak of running Click-to-Inbox ads without a tracked landing page or Pixel.
   - Always critique their live Facebook ad copy sample (or low active ad count) for weak hook, generic offer, or ad fatigue.
2. 3 GỢI Ý HOOK VIDEO NGẮN ĐỂ QUAY DỰNG NGAY (3 PERFORMANCE VIDEO HOOKS):
   - Write 3 specific 30-second video opening hooks tailored to this exact business and offer that an in-house media production team can shoot immediately.
3. BƯỚC TIẾP THEO (15 PHÚT SOI TRỰC TIẾP TRÌNH QUẢNG CÁO):
   - A 2-sentence invitation to open Ads Manager on a 15-minute screen-share to check bidding, audience overlap, and CPL together.
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


def dispatch_prospect_telegram(text: str) -> str:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return "SKIPPED: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing on Render."

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)]
    statuses = []

    for chunk in chunks:
        try:
            r = requests.post(
                url,
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=15,
            )
            if r.status_code == 200:
                statuses.append("SUCCESS")
            else:
                statuses.append(f"FAILED ({r.status_code}): {r.text}")
        except Exception as e:
            statuses.append(f"EXCEPTION: {str(e)}")

    return " | ".join(statuses)


@app.post("/scan-prospect")
def scan_prospect(payload: ProspectScanPayload):
    has_website = bool(payload.website_url and payload.website_url.strip())

    if has_website:
        psi_data = fetch_pagespeed_signals(payload.website_url)
    else:
        psi_data = {
            "ok": True,
            "mode": "fanpage_only_no_website",
            "note": "SME runs Click-to-Messenger/Zalo ads without an external website or Pixel landing page.",
        }

    audit_report = generate_prospect_audit(payload, psi_data)

    tech_summary = (
        f"PageSpeed Mobile: {psi_data.get('mobile_score', 'N/A')}/100 | LCP: {psi_data.get('lcp_load_time', 'N/A')}\n"
        f"Tags: MetaPixel={psi_data.get('has_meta_pixel')} | GTM={psi_data.get('has_gtm')} | Zalo={psi_data.get('has_zalo_widget')}\n"
        if has_website
        else f"Mode: Fanpage-Only Funnel | Active Ads Count: {payload.active_ads_count or 'N/A'}\n"
    )

    header = (
        f"🔍 PROSPECT AUDIT READY (COPY FOR ZALO)\n"
        f"Client: {payload.business_name}\n"
        f"Website: {payload.website_url or 'None'}\n"
        f"Fanpage: {payload.fb_page_url or 'N/A'}\n"
        f"Contact: {payload.contact_info or 'N/A'}\n"
        f"{tech_summary}"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    telegram_status = dispatch_prospect_telegram(header + audit_report)

    return {
        "status": "processed",
        "pagespeed_signals": psi_data,
        "telegram_status": telegram_status,
        "audit_report": audit_report,
    }
