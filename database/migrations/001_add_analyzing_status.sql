-- Add 'analyzing' to analysis_status for Infilra stage-1 → AI handoff.
-- Safe to run on databases created before this value existed.
ALTER TYPE analysis_status ADD VALUE IF NOT EXISTS 'analyzing' AFTER 'running';
