import os
import yaml
from typing import List
from app.schemas.finding import InfrastructureFinding
from app.rules.kubernetes import analyze_kubernetes_doc, evaluate_cross_resource_rules

class KubernetesAnalyzer:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def analyze(self) -> List[InfrastructureFinding]:
        findings = []
        deployments = []
        hpas = []
        
        for root, dirs, files in os.walk(self.workspace_path):
            if any(part in root.split(os.sep) for part in ['.git', 'node_modules']):
                continue
                
            for file in files:
                basename = file.lower()
                if basename.endswith('.yaml') or basename.endswith('.yml'):
                    # To optimize, we can check if it looks like k8s, but safely loading YAML is fine
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.workspace_path)
                    
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            docs = list(yaml.safe_load_all(f))
                            
                        for i, doc in enumerate(docs):
                            if isinstance(doc, dict) and 'apiVersion' in doc and 'kind' in doc:
                                # Run per-document rules
                                doc_findings = analyze_kubernetes_doc(doc, rel_path, i)
                                findings.extend(doc_findings)
                                
                                # Track resources for cross-resource rules
                                kind = doc.get('kind')
                                name = doc.get('metadata', {}).get('name')
                                if kind == 'Deployment' and name:
                                    deployments.append(name)
                                elif kind == 'HorizontalPodAutoscaler':
                                    target_ref = doc.get('spec', {}).get('scaleTargetRef', {})
                                    if target_ref.get('kind') == 'Deployment':
                                        hpas.append(target_ref.get('name'))
                                        
                    except Exception:
                        pass
                        
        # Run cross-resource rules
        findings.extend(evaluate_cross_resource_rules(deployments, hpas))
        
        return findings
