-- PostgreSQL DDL for Executive Audit Log Table (Supabase/Looker Studio Pipeline)
CREATE TABLE ai_growth_audit_logs (
    event_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp_utc TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    campaign_name VARCHAR(255) NOT NULL,
    adset_id VARCHAR(100) NOT NULL,
    current_cpa NUMERIC(10, 2),
    target_cpa NUMERIC(10, 2),
    cpa_variance_pct NUMERIC(6, 2),
    ad_frequency NUMERIC(4, 2),
    ai_decision VARCHAR(50) NOT NULL,
    ai_reasoning TEXT,
    meta_api_endpoint TEXT,
    meta_api_status VARCHAR(50)
);
