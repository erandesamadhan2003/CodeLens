import pytest
import os
import tempfile
from app.analyzers.kubernetes_analyzer import KubernetesAnalyzer

def create_temp_file(dir_path, name, content):
    full_path = os.path.join(dir_path, name)
    with open(full_path, 'w') as f:
        f.write(content)

def test_kubernetes_analyzer_deployment():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a bad Deployment
        bad_deploy = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: web
          image: nginx
          securityContext:
            privileged: true
          # missing probes, resources
"""
        create_temp_file(tmpdir, "deploy.yaml", bad_deploy)
        
        analyzer = KubernetesAnalyzer(tmpdir)
        findings = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "K8S-001" in rule_ids # Missing readinessProbe
        assert "K8S-002" in rule_ids # Missing livenessProbe
        assert "K8S-003" in rule_ids # Missing startupProbe
        assert "K8S-004" in rule_ids # Missing resources
        assert "K8S-006" in rule_ids # privileged: true
        assert "K8S-007" in rule_ids # 1 replica
        assert "K8S-008" in rule_ids # Missing HPA (no HPA created)

def test_kubernetes_analyzer_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_svc = """
apiVersion: v1
kind: Service
metadata:
  name: my-svc
spec:
  type: LoadBalancer
  ports:
    - port: 80
"""
        create_temp_file(tmpdir, "svc.yaml", bad_svc)
        
        analyzer = KubernetesAnalyzer(tmpdir)
        findings = analyzer.analyze()
        rule_ids = [f.ruleId for f in findings]
        assert "K8S-009" in rule_ids # Unnecessarily exposed

def test_kubernetes_analyzer_secret():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_secret = """
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
stringData:
  password: my-plaintext-password
data:
  key: bXktYmFzZTY0LXNlY3JldA== # base64 for 'my-base64-secret'
"""
        create_temp_file(tmpdir, "secret.yaml", bad_secret)
        
        analyzer = KubernetesAnalyzer(tmpdir)
        findings = analyzer.analyze()
        rule_ids = [f.ruleId for f in findings]
        # Should flag both stringData and data
        assert rule_ids.count("K8S-010") == 2 
