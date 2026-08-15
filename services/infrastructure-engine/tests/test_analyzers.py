import pytest
import os
import tempfile
from app.analyzers.docker_analyzer import DockerAnalyzer
from app.analyzers.compose_analyzer import ComposeAnalyzer

def create_temp_file(dir_path, name, content):
    full_path = os.path.join(dir_path, name)
    with open(full_path, 'w') as f:
        f.write(content)

def test_docker_analyzer():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a bad Dockerfile
        bad_dockerfile = """
FROM ubuntu:latest
ENV DB_PASSWORD=supersecret
RUN apt-get update
# Missing USER, Missing HEALTHCHECK
"""
        create_temp_file(tmpdir, "Dockerfile", bad_dockerfile)
        
        analyzer = DockerAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "DOCKER-001" in rule_ids # Container runs as root
        assert "DOCKER-002" in rule_ids # Uses :latest image tag
        assert "DOCKER-003" in rule_ids # Missing HEALTHCHECK
        assert "DOCKER-004" in rule_ids # Potential secret
        assert "DOCKER-006" in rule_ids # Large/unoptimized base image (ubuntu)

def test_docker_multi_stage():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Build-heavy language without multi-stage
        bad_dockerfile = """
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
USER node
HEALTHCHECK CMD curl -f http://localhost/ || exit 1
CMD ["npm", "start"]
"""
        create_temp_file(tmpdir, "Dockerfile", bad_dockerfile)
        
        analyzer = DockerAnalyzer(tmpdir)
        findings = analyzer.analyze()
        rule_ids = [f.ruleId for f in findings]
        assert "DOCKER-005" in rule_ids # Missing multi-stage build

def test_compose_analyzer():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_compose = """
version: '3.8'
services:
  db:
    image: postgres:14
    ports:
      - "5432:5432" # Exposed without localhost
    environment:
      - POSTGRES_PASSWORD=mysecretpassword
  web:
    image: myweb
    ports:
      - "3000:3000"
    # missing restart, healthcheck, resource limits
"""
        create_temp_file(tmpdir, "docker-compose.yml", bad_compose)
        
        analyzer = ComposeAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "COMPOSE-001" in rule_ids # Database publicly exposed
        assert "COMPOSE-003" in rule_ids # Missing healthcheck
        assert "COMPOSE-004" in rule_ids # Missing restart policy
        assert "COMPOSE-005" in rule_ids # Missing resource limits
        assert "COMPOSE-006" in rule_ids # Secrets passed directly

def test_compose_analyzer_good():
    with tempfile.TemporaryDirectory() as tmpdir:
        good_compose = """
version: '3.8'
services:
  db:
    image: postgres:14
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 50M
"""
        create_temp_file(tmpdir, "docker-compose.yml", good_compose)
        
        analyzer = ComposeAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "COMPOSE-001" not in rule_ids 
        assert "COMPOSE-003" not in rule_ids 
        assert "COMPOSE-004" not in rule_ids 
        assert "COMPOSE-005" not in rule_ids 
        assert "COMPOSE-006" not in rule_ids 
