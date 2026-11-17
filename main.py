import os
import re
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
# PART 2: 3-SCENARIO PROSPECT SCANNER + ZALO
# ==========================================
class ProspectScanPayload(BaseModel):
    business_name: str
    website_url: Optional[str] = None
    fb_page_url: Optional[str] = None
    active_ads_count: Optional[int] = None
    ad_copy_sample: Optional[str] = None
    contact_info: Optional[str] = None
    pain_point: Optional[str] = None
    monthly_budget: Optional[str] = None
    language: str = "vi"  # "vi" or "zh"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def is_social_link(url: str) -> bool:
    social_domains = ["facebook.com", "fb.com", "zalo.me", "tiktok.com", "instagram.com"]
    return any(d in url.lower() for d in social_domains)


def build_zalo_link(contact: Optional[str]) -> str:
    if not contact:
        return "N/A"
    digits = re.sub(r"\D", "", contact)
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return f"https://zalo.me/{digits}" if len(digits) >= 9 else contact


def fetch_pagespeed_signals(url: str) -> dict:
    target = normalize_url(url)
    signals = {
        "ok": True,
        "has_meta_pixel": False,
        "has_gtm": False,
        "has_ga4_or_gads": False,
        "has_zalo_widget": False,
        "mobile_score": "N/A",
        "lcp_load_time": "N/A",
        "fcp_load_time": "N/A",
    }

    # 1. Direct HTML tag scan (fast, never rate-limited)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
        html_resp = requests.get(target, timeout=10, allow_redirects=True, headers=headers)
        raw_html = html_resp.text.lower()
        signals["has_meta_pixel"] = (
            ("fbq(" in raw_html)
            or ("connect.facebook.net" in raw_html)
            or ("fbevents.js" in raw_html)
        )
        signals["has_gtm"] = ("googletagmanager.com/gtm.js" in raw_html) or ("gtm-" in raw_html)
        signals["has_ga4_or_gads"] = (
            ("gtag(" in raw_html) or ("googletagmanager.com/gtag/js" in raw_html)
        )
        signals["has_zalo_widget"] = "zalo.me" in raw_html
    except Exception:
        pass

    # 2. Google PageSpeed Insights Mobile Speed + Dynamic GTM Network Requests
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": target, "strategy": "mobile", "category": "performance"}
    if os.environ.get("PAGESPEED_API_KEY"):
        params["key"] = os.environ.get("PAGESPEED_API_KEY")

    try:
        r = requests.get(endpoint, params=params, timeout=45)
        data = r.json()
        if "error" not in data:
            lh = data.get("lighthouseResult") or {}
            raw_score = (lh.get("categories") or {}).get("performance", {}).get("score")
            audits = lh.get("audits") or {}

            signals["mobile_score"] = round(raw_score * 100) if raw_score is not None else "N/A"
            signals["lcp_load_time"] = (audits.get("largest-contentful-paint") or {}).get("displayValue", "N/A")
            signals["fcp_load_time"] = (audits.get("first-contentful-paint") or {}).get("displayValue", "N/A")

            net_items = ((audits.get("network-requests") or {}).get("details") or {}).get("items") or []
            req_urls = " ".join(item.get("url", "") for item in net_items).lower()
            if ("facebook.com/tr" in req_urls) or ("fbevents.js" in req_urls):
                signals["has_meta_pixel"] = True
            if "googletagmanager.com/gtm.js" in req_urls:
                signals["has_gtm"] = True
            if ("googletagmanager.com/gtag/js" in req_urls) or ("google-analytics.com" in req_urls):
                signals["has_ga4_or_gads"] = True
            if "zalo.me" in req_urls:
                signals["has_zalo_widget"] = True
    except Exception:
        pass

    return signals


def generate_prospect_audit(payload: ProspectScanPayload, psi: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: GEMINI_API_KEY missing on Render."

    output_lang = "Vietnamese" if payload.language.lower() == "vi" else "Simplified Chinese"
    scenario = psi.get("funnel_scenario", "website_only")

    prompt = f"""
You are a Marketing Growth Strategist (chuyên gia chiến lược tăng trưởng marketing) preparing a sharp, high-value pre-call audit for a business in Vietnam.
Business Name: {payload.business_name}
Funnel Scenario: {scenario}
Website URL: {payload.website_url or "None (Fanpage-only funnel)"}
Facebook Page URL: {payload.fb_page_url or "Not provided"}
Client Reported Pain Point: {payload.pain_point or "Not specified"}
Active Meta Ads Count (if checked): {payload.active_ads_count if payload.active_ads_count is not None else "Not specified"}
Live Facebook Ad Copy Sample (if provided):
\"\"\"{payload.ad_copy_sample or "Not provided"}\"\"\"

Confirmed Technical Signals:
{psi}

STRICT RULES:
- When writing in Vietnamese, introduce yourself in the opening sentence using the exact phrase: "tôi là chuyên gia chiến lược tăng trưởng marketing" (do NOT say "B2B").
- NEVER mention API limits, technical errors, or missing input fields in your response. Only analyze the confirmed data and funnel structure above.
- Use clean plain text and bullet points ONLY (strictly NO ** bold asterisks or ## headers).

Write a persuasive 1-page audit in {output_lang} ready to paste directly into Zalo or Messenger:
1. 3 LỖ HỔNG ĐANG LÀM TĂNG CHI PHÍ QUẢNG CÁO (3 AD & FUNNEL LEAKS):
   - Address their reported pain point ({payload.pain_point or "rising ad costs"}) first.
   - If scenario is "both_website_and_fanpage" or "website_only": cite the exact mobile performance score, LCP load speed (if not N/A), and missing tracking tags (Meta Pixel, GTM, GA4, Zalo widget) above, explaining how they inflate CPL/CPA.
   - If scenario is "fanpage_only": explain the conversion and retargeting leak of running Click-to-Messenger/Zalo ads without a tracked landing page or Meta Pixel (losing 95%+ of non-messaging visitors and relying solely on manual inbox closing).
   - If live ad copy or active ads count is provided: critique the hook, offer clarity, or ad fatigue risk.
2. 3 GỢI Ý HOOK VIDEO NGẮN ĐỂ QUAY DỰNG NGAY (3 PERFORMANCE VIDEO HOOKS):
   - Write 3 specific 30-second video opening hooks tailored to this exact business and industry that an in-house media production team can shoot immediately.
3. BƯỚC TIẾP THEO (15 PHÚT SOI TRỰC TIẾP TRÌNH QUẢNG CÁO):
   - A 2-sentence invitation to hop on a 15-minute screen-share to inspect their Ads Manager bidding, audience overlap, and CPL together.
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
    raw_web = (payload.website_url or "").strip()
    raw_fb = (payload.fb_page_url or "").strip()

    clean_web = ""
    clean_fb = ""

    for item in [raw_web, raw_fb]:
        if not item:
            continue
        if is_social_link(item) and not clean_fb:
            clean_fb = item
        elif not is_social_link(item) and not clean_web:
            clean_web = item

    payload.website_url = clean_web or None
    payload.fb_page_url = clean_fb or None

    if clean_web and clean_fb:
        scenario = "both_website_and_fanpage"
    elif clean_web:
        scenario = "website_only"
    elif clean_fb:
        scenario = "fanpage_only"
    else:
        scenario = "no_url_niche_only"

    if clean_web:
        psi_data = fetch_pagespeed_signals(clean_web)
        psi_data["funnel_scenario"] = scenario
    else:
        psi_data = {
            "ok": True,
            "funnel_scenario": scenario,
            "note": "SME runs Click-to-Messenger/Zalo ads on Fanpage without an external website or Pixel landing page.",
        }

    audit_report = generate_prospect_audit(payload, psi_data)

    ad_lib_url = (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&q="
        + requests.utils.quote(payload.business_name)
    )

    lines = [
        f"🔍 PROSPECT AUDIT READY [{scenario.upper()}]",
        f"Client: {payload.business_name}",
        f"Zalo Direct: {build_zalo_link(payload.contact_info)}",
        f"Pain Point: {payload.pain_point or 'N/A'} | Budget: {payload.monthly_budget or 'N/A'}",
        f"Website: {clean_web or 'None'}",
        f"Fanpage: {clean_fb or 'None'}",
    ]
    if clean_web:
        lines.append(
            f"Speed: Mobile {psi_data.get('mobile_score', 'N/A')}/100 | LCP {psi_data.get('lcp_load_time', 'N/A')}"
        )
        lines.append(
            f"Tags: MetaPixel={psi_data.get('has_meta_pixel')} | GTM={psi_data.get('has_gtm')} | Zalo={psi_data.get('has_zalo_widget')}"
        )
    if clean_fb or scenario == "no_url_niche_only":
        lines.append(f"Check Live Ads (15s): {ad_lib_url}")

    header = "\n".join(lines) + "\n━━━━━━━━━━━━━━━━━━━━\n\n"
    telegram_status = dispatch_prospect_telegram(header + audit_report)

    return {
        "status": "processed",
        "funnel_scenario": scenario,
        "zalo_link": build_zalo_link(payload.contact_info),
        "pagespeed_signals": psi_data,
        "telegram_status": telegram_status,
        "audit_report": audit_report,
    }
