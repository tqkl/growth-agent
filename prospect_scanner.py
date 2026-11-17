import os
import re
import httpx
from bs4 import BeautifulSoup
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def fetch_site_signals(url: str) -> dict:
    target = normalize_url(url)
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(target)
            html = resp.text
    except Exception as e:
        return {"reachable": False, "error": str(e), "url": target}

    soup = BeautifulSoup(html, "html.parser")
    gtm_match = re.findall(r"GTM-[A-Z0-9]+", html)

    return {
        "reachable": True,
        "final_url": str(resp.url),
        "title": soup.title.string.strip() if soup.title and soup.title.string else "N/A",
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:3],
        "h2": [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:4],
        "has_meta_pixel": ("fbq(" in html) or ("connect.facebook.net" in html),
        "has_gtm": bool(gtm_match),
        "gtm_ids": list(set(gtm_match)),
        "has_ga4_or_gads": ("gtag(" in html) or ("googletagmanager.com/gtag/js" in html),
        "has_tiktok_pixel": "ttq.load" in html,
        "has_zalo_widget": ("zalo.me" in html) or ("sp.zalo.me" in html),
        "forms_count": len(soup.find_all("form")),
    }


async def fetch_mobile_speed(url: str) -> dict:
    target = normalize_url(url)
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": target, "strategy": "mobile", "category": "performance"}
    if os.getenv("PAGESPEED_API_KEY"):
        params["key"] = os.getenv("PAGESPEED_API_KEY")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(endpoint, params=params)
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


async def build_prospect_audit(business_name: str, website_url: str, fb_page_url: str | None, lang: str) -> tuple[dict, str]:
    site_signals = await fetch_site_signals(website_url)
    speed_signals = await fetch_mobile_speed(website_url)

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

Write a sharp, persuasive 1-page audit in {output_lang} using plain text and bullet points (no complex Markdown tables). Include:
1. TOP 3 AD & CONVERSION LEAKS: Cite the exact missing pixels (Meta Pixel, GTM, GA4, Zalo widget), slow mobile load speed (LCP), or weak H1/form friction discovered above. Explain briefly how each leak wastes paid ad budget.
2. 3 PERFORMANCE VIDEO / AD HOOKS: Write 3 specific 30-second short-form video hooks tailored to this business's industry and offer that a media production team can shoot immediately.
3. NEXT STEP (15-MIN DIAGNOSTIC): A 2-sentence invitation to hop on a 15-minute screen-share to inspect their Ads Manager bidding/targeting together.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return {"site": site_signals, "speed": speed_signals}, response.text
