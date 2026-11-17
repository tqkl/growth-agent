import html as html_lib
import os
import re
import time
from typing import Optional
import requests
from fastapi import FastAPI, BackgroundTasks
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
    """
    Step 3: Action Driver
    Dispatches automated push alerts to Telegram when an AI decision is made.
    """
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
# PART 2: ZERO-ACCESS B2B PROSPECT SCANNER
# ==========================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class ProspectScanPayload(BaseModel):
    business_name: str
    website_url: str
    fb_page_url: Optional[str] = None
    contact_info: Optional[str] = None
    language: str = "vi"  # "vi" or "zh"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def clean_html_text(raw: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html_lib.unescape(no_tags)).strip()


def fetch_site_signals(url: str) -> dict:
    target = normalize_url(url)
    try:
        resp = requests.get(target, timeout=12, allow_redirects=True, headers=HEADERS)
        raw_html = resp.text
    except Exception as e:
        return {"reachable": False, "error": str(e), "url": target}

    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", raw_html, re.IGNORECASE | re.DOTALL)
    h2_matches = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.IGNORECASE | re.DOTALL)
    gtm_matches = re.findall(r"GTM-[A-Z0-9]+", raw_html)
    forms_matches = re.findall(r"<form\b", raw_html, re.IGNORECASE)

    return {
        "reachable": True,
        "final_url": resp.url,
        "title": clean_html_text(title_match.group(1)) if title_match else "N/A",
        "h1": [clean_html_text(h) for h in h1_matches if clean_html_text(h)][:3],
        "h2": [clean_html_text(h) for h in h2_matches if clean_html_text(h)][:4],
        "has_meta_pixel": ("fbq(" in raw_html) or ("connect.facebook.net" in raw_html),
        "has_gtm": bool(gtm_matches),
        "gtm_ids": list(set(gtm_matches)),
        "has_ga4_or_gads": ("gtag(" in raw_html) or ("googletagmanager.com/gtag/js" in raw_html),
        "has_tiktok_pixel": "ttq.load" in raw_html,
        "has_zalo_widget": ("zalo.me" in raw_html) or ("sp.zalo.me" in raw_html),
        "forms_count": len(forms_matches),
    }


def fetch_mobile_speed(url: str) -> dict:
    target = normalize_url(url)
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": target, "strategy": "mobile", "category": "performance"}
    if os.environ.get("PAGESPEED_API_KEY"):
        params["key"] = os.environ.get("PAGESPEED_API_KEY")

    try:
        r = requests.get(endpoint, params=params, timeout=30)
        data = r.json()
        lh = data.get("lighthouseResult", {})
        raw_score = lh.get("categories", {}).get("performance", {}).get("score")
        lcp = lh.get("audits", {}).get("largest-contentful-paint", {}).get("displayValue", "N/A")
        fcp = lh.get("audits", {}).get("first-contentful-paint", {}).get("displayValue", "N/A")
        return {
            "mobile_score": round(raw_score * 100) if raw_score is not None else "N/A",
            "lcp_load_time": lcp,
            "fcp_load_time": fcp,
        }
    except Exception as e:
        return {"mobile_score": "N/A", "error": str(e)}


def build_prospect_audit(
    business_name: str,
    website_url: str,
    fb_page_url: Optional[str],
    lang: str = "vi",
) -> tuple[dict, str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    site_signals = fetch_site_signals(website_url)
    speed_signals = fetch_mobile_speed(website_url)

    if not api_key:
        return {"site": site_signals, "speed": speed_signals}, "ERROR: GEMINI_API_KEY missing on Render."

    output_lang = "Vietnamese" if lang.lower() == "vi" else "Simplified Chinese"
    prompt = f"""
You are a Senior B2B Performance Growth Strategist preparing a fast, high-value pre-call audit for an SME prospect.
Business Name: {business_name}
Website: {website_url}
Facebook Page: {fb_page_url or "Not provided"}

Scraped Funnel & Tracking Signals:
{site_signals}

Mobile Speed Metrics:
{speed_signals}

Write a sharp, persuasive 1-page audit in {output_lang} using plain text and bullet points (no Markdown formatting symbols like ** or ##). Include:
1. TOP 3 AD & CONVERSION LEAKS: Cite the exact missing pixels (Meta Pixel, GTM, GA4, Zalo widget), slow mobile load speed (LCP), or weak H1/form friction discovered above. Explain briefly how each leak wastes paid ad budget.
2. 3 PERFORMANCE VIDEO / AD HOOKS: Write 3 specific 30-second short-form video hooks tailored to this business's industry and offer that a media production team can shoot immediately.
3. NEXT STEP (15-MIN DIAGNOSTIC): A 2-sentence invitation to hop on a 15-minute screen-share to inspect their Ads Manager bidding/targeting together.
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
                    return {"site": site_signals, "speed": speed_signals}, response.text
            except Exception as e:
                if attempt == 2:
                    return {"site": site_signals, "speed": speed_signals}, f"AI Generation Error: {str(e)}"
                time.sleep(1)
        return {"site": site_signals, "speed": speed_signals}, "AI Generation Error: No response generated."
    except Exception as e:
        return {"site": site_signals, "speed": speed_signals}, f"Initialization Error: {str(e)}"


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
