import os
import hcl2
from typing import List, Tuple
from app.schemas.finding import InfrastructureFinding
from app.architecture.models import ArchitectureModel
from app.rules.terraform import analyze_hcl_dict, check_tf_005_remote_state

class TerraformAnalyzer:
    def __init__(self, workspace_path: str, arch_model: ArchitectureModel):
        self.workspace_path = workspace_path
        self.arch_model = arch_model

    def analyze(self) -> Tuple[List[InfrastructureFinding], str]:
        findings = []
        global_has_backend = False
        primary_provider = "unknown"
        provider_counts = {}

        for root, dirs, files in os.walk(self.workspace_path):
            if any(part in root.split(os.sep) for part in ['.git', 'node_modules', '.terraform']):
                continue
                
            for file in files:
                if file.endswith('.tf'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.workspace_path)
                    
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            parsed = hcl2.load(f)
                            
                        file_findings, resources, has_backend, providers = analyze_hcl_dict(parsed, rel_path)
                        findings.extend(file_findings)
                        
                        # Add resources to architecture model
                        if resources:
                            self.arch_model.cloud_resources.extend(resources)
                            
                        if has_backend:
                            global_has_backend = True
                            
                        for p in providers:
                            provider_counts[p] = provider_counts.get(p, 0) + 1
                            
                    except Exception as e:
                        # Parsing error or other failure
                        pass
                        
        # Cross-file rules
        if provider_counts or self.arch_model.cloud_resources:
            # Only trigger TF-005 if Terraform is actually being used
            findings.extend(check_tf_005_remote_state(global_has_backend))
            
        # Determine primary cloud provider
        if provider_counts:
            # e.g., {'aws': 3, 'google': 1} -> 'aws'
            primary_provider = max(provider_counts, key=provider_counts.get)
        elif self.arch_model.cloud_resources:
            # Fallback to the provider of the most resources
            res_provs = {}
            for r in self.arch_model.cloud_resources:
                res_provs[r.provider] = res_provs.get(r.provider, 0) + 1
            primary_provider = max(res_provs, key=res_provs.get)
            
        return findings, primary_provider
