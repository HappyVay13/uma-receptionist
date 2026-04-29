from sqlalchemy import text

from db.database import engine


def ensure_call_logs_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS call_logs (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT,
                    channel TEXT,
                    intent TEXT,
                    service TEXT,
                    datetime_iso TEXT,
                    status TEXT,
                    raw_text TEXT,
                    ai_reply TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS ai_reply TEXT"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_tenant_created_at ON call_logs (tenant_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_user_id ON call_logs (user_id)"))


def ensure_phone_routes_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS phone_routes (
                    id BIGSERIAL PRIMARY KEY,
                    phone_number TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_phone_routes_tenant_id ON phone_routes (tenant_id)"))


def ensure_usage_events_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT,
                    channel TEXT,
                    usage_type TEXT NOT NULL,
                    usage_units INTEGER NOT NULL DEFAULT 1,
                    billable BOOLEAN NOT NULL DEFAULT TRUE,
                    source TEXT,
                    status TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS source TEXT"))
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS status TEXT"))
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS usage_units INTEGER NOT NULL DEFAULT 1"))
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS billable BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS channel TEXT"))
        conn.execute(text("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS user_id TEXT"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_created_at ON usage_events (tenant_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_billable_created_at ON usage_events (tenant_id, billable, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_events_user_id ON usage_events (user_id)"))
