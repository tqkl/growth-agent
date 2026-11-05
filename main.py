from fastapi import FastAPI, BackgroundTasks

app = FastAPI(title="AI Growth Agent Engine")

def evaluate_growth_action(payload: dict) -> dict:
    """
    Step 2: Decision Engine (Rules + AI Logic)
    Analyzes inbound marketing metrics and outputs structured actions.
    """
    event_name = payload.get("event_name")
    
    # Logic Branch 1: High CPA / Creative Fatigue Alert
    if event_name == "ad_performance_alert":
        cpa = payload.get("current_cpa", 0)
        target_cpa = payload.get("target_cpa", 0)
        frequency = payload.get("frequency", 0)
        
        if cpa > (target_cpa * 1.3) or frequency > 4.5:
            return {
                "action": "PAUSE_ADSET",
                "target_id": payload.get("adset_id"),
                "reason": f"CPA (${cpa}) exceeded ceiling (${target_cpa * 1.3}) or frequency ({frequency}) spiked.",
                "execution_status": "QUEUED_FOR_META_API"
            }
        elif cpa <= target_cpa * 0.8:
            return {
                "action": "SCALE_BUDGET_15_PERCENT",
                "target_id": payload.get("adset_id"),
                "reason": f"CPA (${cpa}) is well below target (${target_cpa}). Scaling spend.",
                "execution_status": "QUEUED_FOR_META_API"
            }

    # Logic Branch 2: Unqualified Lead Filtering
    elif event_name == "lead_form_submitted":
        investment_budget = payload.get("stated_budget", 0)
        if investment_budget < 10000:
            return {
                "action": "EXCLUDE_FROM_CRM_SALES_QUEUE",
                "user_id": payload.get("user_id"),
                "reason": "Budget below high-ticket qualification threshold.",
                "execution_status": "AUTO_TAGGED_LOW_PRIORITY"
            }

    return {"action": "NO_ACTION_REQUIRED", "reason": "Metrics within normal variance."}

async def process_growth_signal(payload: dict):
    decision = evaluate_growth_action(payload)
    print("--- AI AGENT DECISION RESULT ---")
    print(decision)

@app.get("/")
def health_check():
    return {"status": "online", "system": "AI Growth Agent Ingestion & Decision Layer"}

@app.post("/webhooks/mmp-event")
async def handle_mmp_event(payload: dict, background_tasks: BackgroundTasks):
    # Evaluate signal and pass background task
    decision = evaluate_growth_action(payload)
    background_tasks.add_task(process_growth_signal, payload)
    
    return {
        "status": "processed",
        "received_event": payload.get("event_name", "unknown"),
        "agent_decision": decision
    }
