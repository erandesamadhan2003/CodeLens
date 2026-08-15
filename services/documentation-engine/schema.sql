-- schema.sql — extend existing doc_reports (DO NOT create documentation_reports)
-- Run against live DB: docker exec codelens-db-1 psql -U user -d codelens -f - < schema.sql

ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS repo_url TEXT;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_readme BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS readme_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_license BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_contributing BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS docs_folder_found BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS code_comment_ratio NUMERIC(5,2) NOT NULL DEFAULT 0;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS documented_functions_ratio NUMERIC(5,2);
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS overall_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS grade TEXT NOT NULL DEFAULT 'F';
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS findings JSONB NOT NULL DEFAULT '[]';
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS ai_suggestions JSONB DEFAULT '[]';
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS ai_status TEXT NOT NULL DEFAULT 'skipped';
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS meaningful_changes_undocumented JSONB;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS api_docs_drift_files JSONB;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS api_docs_drift_detected BOOLEAN;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_api_docs BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS api_docs_type TEXT;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_env_example BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_codeowners BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_pr_template BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_issue_template BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_changelog BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_architecture_doc BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS has_ci_config BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS team_readiness_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE doc_reports ADD COLUMN IF NOT EXISTS team_readiness_grade TEXT NOT NULL DEFAULT 'F';
