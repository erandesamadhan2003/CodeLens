-- ============================================================
-- AMALGAM — Complete PostgreSQL Schema
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE analysis_status   AS ENUM ('queued','running','analyzing','completed','failed','cancelled');
CREATE TYPE engine_name_enum  AS ENUM ('infraq','infilra','depra','devora','docryx');
CREATE TYPE webhook_status    AS ENUM ('received','processing','processed','failed');
CREATE TYPE cloud_provider    AS ENUM ('aws','gcp','azure','unknown','none');

-- ── Users (GitHub OAuth) ─────────────────────────────────────
CREATE TABLE users (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_id            VARCHAR(64)  UNIQUE NOT NULL,
    username             VARCHAR(128) NOT NULL,
    email                VARCHAR(256),
    avatar_url           TEXT,
    github_access_token  TEXT,          -- encrypted at application level
    github_token_scope   TEXT,
    plan                 VARCHAR(32)  DEFAULT 'free',
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_github_id ON users(github_id);

-- ── API keys (platform access, not GitHub) ───────────────────
CREATE TABLE api_keys (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          VARCHAR(128) NOT NULL,
    key_prefix    VARCHAR(8)   NOT NULL,
    key_hash      VARCHAR(256) UNIQUE NOT NULL,   -- SHA-256
    scopes        TEXT[]       DEFAULT '{"read"}',
    last_used_at  TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Repositories ─────────────────────────────────────────────
CREATE TABLE repositories (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    github_repo_id   VARCHAR(64)  UNIQUE NOT NULL,
    owner            VARCHAR(128) NOT NULL,
    name             VARCHAR(256) NOT NULL,
    full_name        VARCHAR(512) NOT NULL,    -- "owner/name"
    description      TEXT,
    default_branch   VARCHAR(128) DEFAULT 'main',
    is_private       BOOLEAN      NOT NULL DEFAULT false,
    clone_url        TEXT         NOT NULL,
    language         VARCHAR(64),
    webhook_id       VARCHAR(64),
    webhook_secret   VARCHAR(256),             -- encrypted
    webhook_active   BOOLEAN      DEFAULT false,
    last_analyzed_at TIMESTAMPTZ,
    last_commit_sha  VARCHAR(64),
    is_active        BOOLEAN      DEFAULT true,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_repositories_user_id    ON repositories(user_id);
CREATE INDEX idx_repositories_full_name  ON repositories(full_name);

-- ── Webhook events (raw GitHub payloads, idempotency) ────────
CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id         UUID         REFERENCES repositories(id) ON DELETE SET NULL,
    github_repo_id  VARCHAR(64),
    event_type      VARCHAR(64)  NOT NULL,     -- 'push', 'pull_request'
    delivery_id     VARCHAR(64)  UNIQUE NOT NULL,  -- X-GitHub-Delivery
    commit_sha      VARCHAR(64),
    branch          VARCHAR(256),
    pusher_email    VARCHAR(256),
    payload         JSONB        NOT NULL,
    status          webhook_status NOT NULL DEFAULT 'received',
    run_id          UUID,
    received_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX idx_webhook_events_repo_id     ON webhook_events(repo_id);
CREATE INDEX idx_webhook_events_delivery_id ON webhook_events(delivery_id);

-- ── Analysis runs (one per push / manual trigger) ────────────
CREATE TABLE analysis_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id             UUID   NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    webhook_event_id    UUID   REFERENCES webhook_events(id),
    commit_sha          VARCHAR(64)  NOT NULL,
    commit_message      TEXT,
    branch              VARCHAR(256),
    author_name         VARCHAR(256),
    author_email        VARCHAR(256),
    triggered_by        VARCHAR(32)  DEFAULT 'webhook',  -- 'webhook'|'manual'|'api'
    status              analysis_status NOT NULL DEFAULT 'queued',
    engines_requested   engine_name_enum[] DEFAULT '{infraq,infilra,depra,devora,docryx}',
    engines_completed   engine_name_enum[] DEFAULT '{}',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_analysis_runs_repo_id ON analysis_runs(repo_id);
CREATE INDEX idx_analysis_runs_status  ON analysis_runs(status);

-- ── Engine results envelope (one row per engine per run) ─────
CREATE TABLE engine_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID   NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    engine          engine_name_enum NOT NULL,
    status          analysis_status  NOT NULL DEFAULT 'queued',
    result_data     JSONB,
    error_message   TEXT,
    duration_ms     INTEGER,
    ai_tokens_used  INTEGER,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    UNIQUE(run_id, engine)
);
CREATE INDEX idx_engine_results_run_id ON engine_results(run_id);

-- ── INFRAQ — Infrastructure analysis ─────────────────────────
CREATE TABLE infra_analyses (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                  UUID UNIQUE NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,

    -- Detection flags
    has_dockerfile          BOOLEAN DEFAULT false,
    has_docker_compose      BOOLEAN DEFAULT false,
    has_k8s_manifests       BOOLEAN DEFAULT false,
    has_terraform           BOOLEAN DEFAULT false,
    has_helm_charts         BOOLEAN DEFAULT false,
    has_ci_config           BOOLEAN DEFAULT false,
    has_pulumi              BOOLEAN DEFAULT false,
    has_ansible             BOOLEAN DEFAULT false,
    cloud_provider          cloud_provider DEFAULT 'unknown',

    -- Parsed architecture
    detected_services       JSONB DEFAULT '[]',
    
    architecture_graph      JSONB DEFAULT '{}',
    
    k8s_resources           JSONB DEFAULT '[]',
    
    terraform_resources     JSONB DEFAULT '[]',

    -- Cost modeling
    estimated_monthly_cost  DECIMAL(10,2),
    cost_breakdown          JSONB DEFAULT '{}',

    -- AI recommendations
    recommendations         JSONB DEFAULT '[]',

    -- Generated IaC (when nothing detected)
    generated_terraform     TEXT,
    generated_helm_values   TEXT,
    generated_compose       TEXT,
    architecture_summary    TEXT,
    detected_files          JSONB DEFAULT '[]',
    ai_tokens_used          INTEGER,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── INFILRA — DAST security scan ─────────────────────────────
CREATE TABLE security_scans (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID UNIQUE NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,

    critical_count      INTEGER DEFAULT 0,
    high_count          INTEGER DEFAULT 0,
    medium_count        INTEGER DEFAULT 0,
    low_count           INTEGER DEFAULT 0,

    vulnerabilities     JSONB DEFAULT '[]',

    ssl_results         JSONB DEFAULT '{}',

    port_scan_results   JSONB DEFAULT '[]',

    headers_analysis    JSONB DEFAULT '{}',

    endpoints_crawled   INTEGER DEFAULT 0,
    endpoints           JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── DEPRA — Dependency CVE intelligence ──────────────────────
CREATE TABLE dependency_reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID UNIQUE NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,

    total_dependencies  INTEGER DEFAULT 0,
    vulnerable_count    INTEGER DEFAULT 0,
    outdated_count      INTEGER DEFAULT 0,
    critical_cves       INTEGER DEFAULT 0,
    ecosystems          TEXT[] DEFAULT '{}',  -- ['npm','pip','maven']

    dependencies        JSONB DEFAULT '[]',

    cve_details         JSONB DEFAULT '[]',

    ai_summary          TEXT,
    ai_tokens_used      INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── DEVORA — Developer skills & growth ───────────────────────
CREATE TABLE developer_profiles (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                UUID  NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    author_email          VARCHAR(256) NOT NULL,
    author_name           VARCHAR(256),

    skill_scores          JSONB DEFAULT '{}',

    commit_velocity       JSONB DEFAULT '{}',

    language_distribution JSONB DEFAULT '{}',

    growth_vectors        JSONB DEFAULT '[]',

    ai_summary            TEXT,
    ai_tokens_used        INTEGER,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(run_id, author_email)
);

-- ── DOCRYX — Documentation reports ───────────────────────────
CREATE TABLE doc_reports (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                      UUID UNIQUE NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,

    files_analyzed              INTEGER DEFAULT 0,
    outdated_docs_count         INTEGER DEFAULT 0,
    missing_docs_count          INTEGER DEFAULT 0,
    functions_without_docstring INTEGER DEFAULT 0,

    changed_files               JSONB DEFAULT '[]',

    doc_suggestions             JSONB DEFAULT '[]',

    generated_diff              TEXT,
    pr_description              TEXT,
    ai_tokens_used              INTEGER,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Notifications ─────────────────────────────────────────────
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    run_id      UUID   REFERENCES analysis_runs(id) ON DELETE CASCADE,
    type        VARCHAR(64)  NOT NULL,  -- 'run_complete'|'critical_vuln'|'new_repo'
    title       VARCHAR(256) NOT NULL,
    body        TEXT,
    is_read     BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);

-- ── updated_at trigger ────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_repositories_updated_at
    BEFORE UPDATE ON repositories FOR EACH ROW EXECUTE FUNCTION set_updated_at();
