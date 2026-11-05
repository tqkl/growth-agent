from fastapi import FastAPI, Request, BackgroundTasks

app = FastAPI(title="AI Growth Agent Listener")

async def process_growth_signal(payload: dict):
    # Step 2 AI decision engine & automation logic will connect here
    print("Processing incoming webhook signal:", payload)

@app.get("/")
def health_check():
    return {"status": "online", "system": "AI Growth Agent Ingestion Layer"}

@app.post("/webhooks/mmp-event")
async def handle_mmp_event(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_growth_signal, payload)
    return {"status": "received", "event": payload.get("event_name", "unknown")}
