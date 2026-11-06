# Autonomous AI Growth Agent Engine

An end-to-end, event-driven AI Growth Engineering prototype that automates performance marketing decisioning, programmatic ad platform execution, and real-time operational alerting.

## 🚀 System Architecture

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
