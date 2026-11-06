# Autonomous AI Growth Agent Engine

An event-driven AI Growth Engineering prototype that automates performance marketing telemetry ingestion, dynamic Gemini LLM decision-making, and real-time push alerting.

---

## 📸 System Live Verification

### 1. Ingestion & AI Decision Engine (FastAPI + Gemini)
*Live Swagger UI processing inbound ad performance telemetry and generating automated pause actions with metric rationales.*

![Swagger API Execution]
<img width="1525" height="614" alt="Screenshot_48" src="https://github.com/user-attachments/assets/6f7730cc-2608-4f4d-994a-8a67113dd0c4" />


---

### 2. Event-Driven Push Notification (Telegram Bot)
*Instant mobile/desktop action alerts dispatched to growth leads upon decision execution.*

![Telegram Push Alert]
<img width="926" height="927" alt="Screenshot_49" src="https://github.com/user-attachments/assets/46b92581-6160-4d67-a3aa-14455af4c08c" />


---

### 3. Autopilot Background Scheduler (GitHub Actions)
*Hands-free cron runner executing automated telemetry checks every 6 hours.*

![GitHub Actions Runner]
<img width="1901" height="916" alt="96ec462a-cd73-42d5-9db1-c201b8fd54c1" src="https://github.com/user-attachments/assets/49166c78-b2fe-46f5-8f95-4abe4ae07cdd" />


---

## 🛠️ Architectural Workflow

```text
 ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
 │  Step 5: Autopilot      │      │  Step 1: Webhook        │      │  Step 2: AI Reasoning   │
 │  GitHub Actions Cron    ├────► │  FastAPI on Render      ├────► │  Google Gemini          │
 │  (Scheduled Telemetry)  │      │  (Type-Safe Ingestion)  │      │  (CPA & Freq Analysis)  │
 └─────────────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                                │
                                  ┌─────────────────────────┐                   │
                                  │  Step 3 & 4: Execution  │                   │
                                  │  • Telegram Push Alert  │◄──────────────────┘
                                  │  • Meta Graph API Body  │
                                  │  • Looker Studio SQL Log│
                                  └─────────────────────────┘
