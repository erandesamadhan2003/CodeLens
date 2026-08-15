import pytest
import os
import tempfile
from app.analyzers.cicd_analyzer import CicdAnalyzer

def create_temp_file(dir_path, name, content):
    full_path = os.path.join(dir_path, name)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(content)

def test_cicd_analyzer_bad():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a bad GitHub Actions workflow
        bad_yml = """
name: Deploy
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: docker build -t myapp .  # CICD-003
      - run: terraform apply -auto-approve  # CICD-004
      - run: aws s3 sync . s3://mybucket
      - run: echo "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" > .env # CICD-006
      # No tests (CICD-001)
      # No security scanning (CICD-002)
      # Deployment with no env separation (CICD-005)
"""
        create_temp_file(tmpdir, ".github/workflows/deploy.yml", bad_yml)
        
        analyzer = CicdAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "CICD-001" in rule_ids
        assert "CICD-002" in rule_ids
        assert "CICD-003" in rule_ids
        assert "CICD-004" in rule_ids
        assert "CICD-005" in rule_ids
        assert "CICD-006" in rule_ids
        
def test_cicd_analyzer_good():
    with tempfile.TemporaryDirectory() as tmpdir:
        good_yml = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest
  scan:
    runs-on: ubuntu-latest
    steps:
      - run: docker build -t myapp .
      - run: trivy image myapp
  deploy_staging:
    environment: staging
    steps:
      - run: terraform plan -out=tfplan
      - run: terraform apply tfplan
"""
        create_temp_file(tmpdir, ".gitlab-ci.yml", good_yml)
        
        analyzer = CicdAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "CICD-001" not in rule_ids
        assert "CICD-002" not in rule_ids
        assert "CICD-003" not in rule_ids
        assert "CICD-004" not in rule_ids
        assert "CICD-005" not in rule_ids
        assert "CICD-006" not in rule_ids
