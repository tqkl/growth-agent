import os
import re
import time
import uuid
import socket
import ipaddress
import threading
from collections import defaultdict, deque
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="AI Growth Agent Engine")

# ==========================================
# CONFIG (environment variables)
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")  # set the same value in setWebhook

PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY")

FORM_API_KEY = os.environ.get("FORM_API_KEY")  # sent by the lead form as X-Api-Key
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "5"))

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")  # leave empty until Brevo is set up
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")  # must be a verified sender in Brevo
SENDER_NAME = os.environ.get("SENDER_NAME", "Hongthaix")
REPLY_TO_EMAIL = os.environ.get("REPLY_TO_EMAIL")

SIGNATURE_NAME = os.environ.get("SIGNATURE_NAME", "Cris")
SIGNATURE_WEBSITE = os.environ.get("SIGNATURE_WEBSITE", "https://hongthaix.com")
SIGNATURE_ZALO = os.environ.get("SIGNATURE_ZALO", "")

SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL")  # Google Apps Script web app URL
SHEET_WEBHOOK_SECRET = os.environ.get("SHEET_WEBHOOK_SECRET", "")

# false = every audit waits for "Approve & email" in Telegram (recommended for the first ~30)
AUTO_SEND = os.environ.get("AUTO_SEND", "false").lower() == "true"

UA_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ==========================================
# PART 1: EXISTING 24/7 CPA & BUDGET GUARD (unchanged)
# ==========================================
class GrowthSignal(BaseModel):
    event_name: str
    campaign_name: str
    adset_id: str
    current_cpa: float
    target_cpa: float
    frequency: float


def send_telegram_alert(adset_id: str, action_summary: str) -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "SKIPPED: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing on Render."

    message = f"🚨 AI GROWTH AGENT ACTION EXECUTED\n\nTarget AdSet: {adset_id}\n\n{action_summary}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
        if response.status_code == 200:
            return "SUCCESS: TELEGRAM_PUSH_ALERT_DISPATCHED"
        return f"FAILED: Telegram API returned {response.status_code} - {response.text}"
    except Exception as e:
        return f"FAILED: {str(e)}"


def call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "ERROR: GEMINI_API_KEY environment variable is missing on Render."
    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                if response.text:
                    return response.text
            except Exception as e:
                if attempt == 2:
                    return f"ERROR: AI generation failed: {str(e)}"
                time.sleep(1)
        return "ERROR: AI generation returned no text."
    except Exception as e:
        return f"ERROR: AI initialisation failed: {str(e)}"


def run_ai_growth_reasoning(signal: GrowthSignal) -> str:
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
    return call_gemini(prompt)


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
# PART 2: PROSPECT AUDIT → APPROVAL → EMAIL (BREVO) → CRM (GOOGLE SHEET)
# ==========================================
class ProspectScanPayload(BaseModel):
    business_name: str
    industry: Optional[str] = None  # what they sell, e.g. "spa", "nhà hàng lẩu", "AI API"
    email: Optional[str] = None
    consent: bool = False  # prospect agreed to be contacted / receive the audit
    website_url: Optional[str] = None
    fb_page_url: Optional[str] = None
    active_ads_count: Optional[int] = None
    ad_copy_sample: Optional[str] = None
    contact_info: Optional[str] = None  # phone / Zalo
    pain_point: Optional[str] = None
    monthly_budget: Optional[str] = None
    language: str = "vi"  # "vi" or "zh"
    source: str = "inbound_form"  # "inbound_form", "outbound", "partner"


LANG = {
    "vi": {
        "name": "Vietnamese",
        "intro": "Chào anh/chị, tôi là {sig}, chuyên gia chiến lược tăng trưởng marketing tại Hongthaix.",
        "h1": "1. 3 ĐIỂM ĐANG LÀM TĂNG CHI PHÍ QUẢNG CÁO",
        "h2": "2. 3 GỢI Ý MỞ ĐẦU VIDEO NGẮN CÓ THỂ QUAY NGAY",
        "h3": "3. BƯỚC TIẾP THEO: 15 PHÚT CÙNG XEM TÀI KHOẢN QUẢNG CÁO",
        "subject": "Bản audit quảng cáo nhanh cho {business}",
        "no_website": "Chưa thấy website/landing page có gắn mã theo dõi.",
    },
    "zh": {
        "name": "Simplified Chinese",
        "intro": "您好，我是 Hongthaix 的营销增长策略顾问 {sig}。",
        "h1": "1. 正在推高广告成本的 3 个问题",
        "h2": "2. 3 个可以立即拍摄的短视频开头",
        "h3": "3. 下一步：15 分钟一起查看您的广告账户",
        "subject": "{business} 的快速广告诊断报告",
        "no_website": "暂未发现带有追踪代码的网站或落地页。",
    },
}


def lang_pack(code: Optional[str]) -> dict:
    return LANG.get((code or "vi").lower(), LANG["vi"])


def signature_block() -> str:
    lines = ["—", SIGNATURE_NAME, f"Hongthaix – {SIGNATURE_WEBSITE}"]
    if SIGNATURE_ZALO:
        lines.append(f"Zalo: {SIGNATURE_ZALO}")
    return "\n".join(lines)


# ---------- rate limit (per IP, in memory) ----------
_rate_lock = threading.Lock()
_rate_hits: dict = defaultdict(deque)


def allow_request(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        hits = _rate_hits[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_HOUR:
            return False
        hits.append(now)
        return True


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------- URL helpers + SSRF guard ----------
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


def is_public_host(host: str) -> bool:
    """Block localhost, private, link-local and reserved addresses."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def safe_get(url: str, timeout: int = 10, max_redirects: int = 3) -> requests.Response:
    """GET a user-supplied URL, checking every redirect hop is a public host."""
    for _ in range(max_redirects + 1):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Unsupported URL")
        if not is_public_host(parsed.hostname):
            raise ValueError("Blocked non-public address")
        resp = requests.get(url, timeout=timeout, allow_redirects=False, headers=UA_HEADERS)
        if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
            url = urljoin(url, resp.headers["Location"])
            continue
        return resp
    raise ValueError("Too many redirects")


# ---------- website signals ----------
def fetch_pagespeed_signals(url: str) -> dict:
    target = normalize_url(url)
    signals = {
        "website_reachable": False,
        "has_meta_pixel": False,
        "has_gtm": False,
        "has_ga4_or_gads": False,
        "has_zalo_widget": False,
        "mobile_score": "N/A",
        "lcp_load_time": "N/A",
        "fcp_load_time": "N/A",
    }

    # 1. Direct HTML tag scan
    try:
        html_resp = safe_get(target)
        raw_html = html_resp.text.lower()
        signals["website_reachable"] = html_resp.status_code < 400
        signals["has_meta_pixel"] = (
            "fbq(" in raw_html or "connect.facebook.net" in raw_html or "fbevents.js" in raw_html
        )
        signals["has_gtm"] = (
            "googletagmanager.com/gtm.js" in raw_html or bool(re.search(r"gtm-[a-z0-9]{4,}", raw_html))
        )
        signals["has_ga4_or_gads"] = "gtag(" in raw_html or "googletagmanager.com/gtag/js" in raw_html
        signals["has_zalo_widget"] = "zalo.me" in raw_html
    except Exception:
        return signals  # unreachable or blocked: don't call PageSpeed either

    # 2. Google PageSpeed Insights (mobile speed + tags loaded at runtime)
    params = {"url": target, "strategy": "mobile", "category": "performance"}
    if PAGESPEED_API_KEY:
        params["key"] = PAGESPEED_API_KEY
    try:
        r = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params, timeout=45
        )
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
            if "facebook.com/tr" in req_urls or "fbevents.js" in req_urls:
                signals["has_meta_pixel"] = True
            if "googletagmanager.com/gtm.js" in req_urls:
                signals["has_gtm"] = True
            if "googletagmanager.com/gtag/js" in req_urls or "google-analytics.com" in req_urls:
                signals["has_ga4_or_gads"] = True
            if "zalo.me" in req_urls:
                signals["has_zalo_widget"] = True
    except Exception:
        pass

    return signals


# ---------- AI audit ----------
def generate_prospect_audit(payload: ProspectScanPayload, signals: dict, scenario: str) -> str:
    lp = lang_pack(payload.language)
    intro = lp["intro"].format(sig=SIGNATURE_NAME)

    prompt = f"""
You are a marketing growth strategist at Hongthaix, writing a short, useful pre-call audit for a business in Vietnam.

Business name: {payload.business_name}
What they sell / industry: {payload.industry or "Not provided"}
Funnel scenario: {scenario}
Website: {payload.website_url or "Not provided"}
Facebook page: {payload.fb_page_url or "Not provided"}
Main pain point (from the business): {payload.pain_point or "Not provided"}
Number of live Meta ads (if checked): {payload.active_ads_count if payload.active_ads_count is not None else "Not provided"}
Live ad copy sample (if provided):
\"\"\"{payload.ad_copy_sample or "Not provided"}\"\"\"

Confirmed technical signals (the ONLY facts you may cite):
{signals}

STRICT RULES:
- Write the whole audit in {lp["name"]}.
- Start with exactly this sentence: "{intro}"
- Use exactly these three section headings, in this order:
  {lp["h1"]}
  {lp["h2"]}
  {lp["h3"]}
- Only use numbers that appear in the confirmed technical signals. NEVER invent statistics or percentages.
- NEVER promise results (no "cut costs in half", "double sales", guaranteed outcomes). Use careful wording such as "có thể" / "可能".
- Base the business type ONLY on "What they sell / industry". If it is not provided, keep the advice general; do not guess their product.
- If no website is provided, say: "{lp["no_website"]}" Do NOT assume which ad format they run.
- Only comment on their ads if ad copy or an ad count is provided.
- Never mention APIs, technical errors or missing form fields.
- Plain text with "-" bullets only. No ** bold and no ## headers.
- Proofread: no spelling mistakes and no repeated words.
- Do NOT add a signature; it is added automatically.

CONTENT:
Section 1: start with their pain point ({payload.pain_point or "chi phí quảng cáo"}). Give 3 concrete issues. If a website was scanned, cite the mobile score, LCP and which tags are missing (Meta Pixel, GTM, GA4, Zalo widget) and explain simply how each can raise the cost per lead.
Section 2: 3 opening lines (first 3 seconds) for short videos that fit THIS business and what it sells.
Section 3: a 2-sentence invitation to a 15-minute screen-share to look at their ad account together.
"""
    return call_gemini(prompt)


# ---------- Telegram ----------
def tg_api(method: str, body: dict) -> requests.Response:
    return requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", json=body, timeout=15
    )


def dispatch_prospect_telegram(text: str, buttons: Optional[list] = None) -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "SKIPPED: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing."
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)] or [""]
    statuses = []
    for idx, chunk in enumerate(chunks):
        body = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "disable_web_page_preview": True}
        if buttons and idx == len(chunks) - 1:
            body["reply_markup"] = {"inline_keyboard": [buttons]}
        try:
            r = tg_api("sendMessage", body)
            statuses.append("SUCCESS" if r.status_code == 200 else f"FAILED ({r.status_code})")
        except Exception as e:
            statuses.append(f"EXCEPTION: {e}")
    return " | ".join(statuses)


# ---------- Google Sheet CRM (via Apps Script web app) ----------
def sheet_upsert_lead(lead: dict) -> str:
    if not SHEET_WEBHOOK_URL:
        return "SKIPPED: SHEET_WEBHOOK_URL missing."
    try:
        r = requests.post(
            SHEET_WEBHOOK_URL,
            json={"secret": SHEET_WEBHOOK_SECRET, "action": "upsert_lead", "lead": lead},
            timeout=20,
        )
        return "SUCCESS" if r.ok and '"ok":true' in r.text.replace(" ", "") else f"FAILED: {r.text[:200]}"
    except Exception as e:
        return f"EXCEPTION: {e}"


def sheet_set_status(lead_id: str, status: str) -> str:
    if not SHEET_WEBHOOK_URL:
        return "SKIPPED"
    try:
        r = requests.post(
            SHEET_WEBHOOK_URL,
            json={"secret": SHEET_WEBHOOK_SECRET, "action": "set_status", "lead_id": lead_id, "status": status},
            timeout=20,
        )
        return "SUCCESS" if r.ok else f"FAILED: {r.text[:200]}"
    except Exception as e:
        return f"EXCEPTION: {e}"


def sheet_get_lead(lead_id: str) -> Optional[dict]:
    if not SHEET_WEBHOOK_URL:
        return None
    try:
        r = requests.get(
            SHEET_WEBHOOK_URL,
            params={"secret": SHEET_WEBHOOK_SECRET, "action": "get", "lead_id": lead_id},
            timeout=20,
        )
        data = r.json()
        return data.get("lead") if data.get("ok") else None
    except Exception:
        return None


# ---------- Brevo email ----------
def send_audit_email(lead: dict) -> str:
    if not BREVO_API_KEY or not SENDER_EMAIL:
        return "SKIPPED: Brevo not configured (BREVO_API_KEY / SENDER_EMAIL)."
    email = (lead.get("email") or "").strip()
    if not EMAIL_RE.match(email):
        return "SKIPPED: no valid prospect email."
    lp = lang_pack(lead.get("language"))
    body = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": email, "name": lead.get("business_name") or email}],
        "subject": lp["subject"].format(business=lead.get("business_name") or ""),
        "textContent": lead.get("audit") or "",
    }
    if REPLY_TO_EMAIL:
        body["replyTo"] = {"email": REPLY_TO_EMAIL, "name": SENDER_NAME}
    try:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "accept": "application/json", "content-type": "application/json"},
            json=body,
            timeout=20,
        )
        return "SUCCESS" if r.status_code in (200, 201, 202) else f"FAILED ({r.status_code}): {r.text[:300]}"
    except Exception as e:
        return f"EXCEPTION: {e}"


# ---------- in-memory lead store (Sheet is optional) ----------
# Drafts live here until approved. A Render restart clears them; then just re-run the scan.
LEADS: dict = {}


def get_lead(lead_id: str) -> Optional[dict]:
    return LEADS.get(lead_id) or sheet_get_lead(lead_id)


def set_status(lead_id: str, status: str) -> None:
    if lead_id in LEADS:
        LEADS[lead_id]["status"] = status
    sheet_set_status(lead_id, status)


# ---------- main flow (runs in the background) ----------
def process_prospect(lead_id: str, payload: ProspectScanPayload) -> None:
    raw_web = (payload.website_url or "").strip()
    raw_fb = (payload.fb_page_url or "").strip()
    clean_web, clean_fb = "", ""
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
        signals = fetch_pagespeed_signals(clean_web)
    else:
        signals = {"website_provided": False, "note": "No website provided. Ad format unknown."}

    audit = generate_prospect_audit(payload, signals, scenario)
    ai_failed = audit.startswith("ERROR")
    full_audit = audit if ai_failed else f"{audit.strip()}\n\n{signature_block()}"

    has_email = bool(payload.email) and payload.consent
    if ai_failed:
        status = "error"
    elif AUTO_SEND and has_email:
        status = "sending"
    elif has_email:
        status = "awaiting_approval"
    else:
        status = "manual_followup"  # no email: send by Zalo/Messenger yourself

    lead = {
        "lead_id": lead_id,
        "source": payload.source,
        "business_name": payload.business_name,
        "industry": payload.industry or "",
        "email": payload.email or "",
        "consent": "yes" if payload.consent else "no",
        "contact_info": payload.contact_info or "",
        "zalo_link": build_zalo_link(payload.contact_info),
        "website_url": clean_web,
        "fb_page_url": clean_fb,
        "monthly_budget": payload.monthly_budget or "",
        "pain_point": payload.pain_point or "",
        "language": (payload.language or "vi").lower(),
        "scenario": scenario,
        "status": status,
        "audit": full_audit,
    }
    LEADS[lead_id] = lead  # in-memory copy, so Approve works without the Sheet
    sheet_status = sheet_upsert_lead(lead)

    email_note = ""
    if status == "sending":
        result = send_audit_email(lead)
        new_status = "audit_sent" if result == "SUCCESS" else "email_failed"
        set_status(lead_id, new_status)
        email_note = f"Email: {result}"

    ad_lib_url = (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&q="
        + requests.utils.quote(payload.business_name)
    )
    header = [
        f"🔍 PROSPECT AUDIT [{scenario.upper()}] · {status.upper()}",
        f"Lead ID: {lead_id} · Source: {payload.source}",
        f"Client: {payload.business_name} ({payload.industry or 'industry n/a'})",
        f"Email: {payload.email or 'N/A'} · Zalo: {lead['zalo_link']}",
        f"Pain point: {payload.pain_point or 'N/A'} | Budget: {payload.monthly_budget or 'N/A'}",
        f"Website: {clean_web or 'None'} · Fanpage: {clean_fb or 'None'}",
    ]
    if clean_web:
        header.append(
            f"Speed: mobile {signals.get('mobile_score')}/100 | LCP {signals.get('lcp_load_time')} | "
            f"Pixel={signals.get('has_meta_pixel')} GTM={signals.get('has_gtm')} "
            f"GA4={signals.get('has_ga4_or_gads')} Zalo={signals.get('has_zalo_widget')}"
        )
    if clean_fb or scenario == "no_url_niche_only":
        header.append(f"Check live ads: {ad_lib_url}")
    if email_note:
        header.append(email_note)
    text = "\n".join(header) + "\n━━━━━━━━━━━━━━━━━━━━\n\n" + full_audit

    buttons = None
    if status == "awaiting_approval":
        buttons = [
            {"text": "✅ Approve & email", "callback_data": f"approve:{lead_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{lead_id}"},
        ]
    dispatch_prospect_telegram(text, buttons)


@app.post("/scan-prospect", status_code=202)
def scan_prospect(
    payload: ProspectScanPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(default=None),
):
    if FORM_API_KEY and x_api_key != FORM_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not allow_request(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    if not payload.business_name.strip():
        raise HTTPException(status_code=422, detail="business_name is required.")
    if payload.email and not EMAIL_RE.match(payload.email.strip()):
        raise HTTPException(status_code=422, detail="Invalid email.")
    if payload.email and not payload.consent:
        raise HTTPException(status_code=422, detail="Consent is required to email the audit.")

    lead_id = uuid.uuid4().hex[:10]
    background_tasks.add_task(process_prospect, lead_id, payload)
    message = (
        "Bản audit sẽ được gửi qua email trong vài phút."
        if (payload.language or "vi").lower() == "vi"
        else "诊断报告将在几分钟内发送到您的邮箱。"
    )
    return {"status": "accepted", "lead_id": lead_id, "message": message}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if TELEGRAM_WEBHOOK_SECRET and x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    update = await request.json()
    cq = update.get("callback_query")
    if not cq:
        return {"ok": True}

    chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
    if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
        return {"ok": True}  # ignore buttons pressed outside the team chat

    action, _, lead_id = (cq.get("data") or "").partition(":")
    lead = get_lead(lead_id)
    reply = "Lead not found (the server may have restarted). Please re-run the scan."

    if lead:
        if lead.get("status") in ("audit_sent", "rejected"):
            reply = f"Already {lead.get('status')} – nothing done."
        elif action == "approve":
            result = send_audit_email(lead)
            new_status = "audit_sent" if result == "SUCCESS" else "email_failed"
            set_status(lead_id, new_status)
            reply = f"{lead.get('business_name')}: {new_status} ({result})"
        elif action == "reject":
            set_status(lead_id, "rejected")
            reply = f"{lead.get('business_name')}: rejected, not emailed."

    try:
        tg_api("answerCallbackQuery", {"callback_query_id": cq.get("id"), "text": reply[:190]})
        tg_api("sendMessage", {"chat_id": TELEGRAM_CHAT_ID, "text": f"[{lead_id}] {reply}"})
    except Exception:
        pass
    return {"ok": True}
