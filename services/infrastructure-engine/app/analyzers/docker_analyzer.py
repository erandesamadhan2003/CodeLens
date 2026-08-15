import os
from typing import List
from app.schemas.finding import InfrastructureFinding
from app.rules.docker import analyze_dockerfile

class DockerAnalyzer:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def analyze(self) -> List[InfrastructureFinding]:
        findings = []
        for root, _, files in os.walk(self.workspace_path):
            # Skip ignored directories
            if any(part in root.split(os.sep) for part in ['.git', 'node_modules']):
                continue
                
            for file in files:
                basename = file.lower()
                if 'dockerfile' in basename or basename.endswith('.dockerfile'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.workspace_path)
                    
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        file_findings = analyze_dockerfile(content, rel_path)
                        findings.extend(file_findings)
                    except Exception:
                        pass
                        
        return findings
