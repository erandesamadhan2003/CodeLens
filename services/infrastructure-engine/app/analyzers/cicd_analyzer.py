import os
import re
from typing import List, Dict
from app.schemas.finding import InfrastructureFinding
from app.rules.cicd import check_cicd_rules

class CicdAnalyzer:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        
        self.test_keywords = [r'pytest', r'npm test', r'npm run test', r'jest', r'go test', r'rspec', r'mvn test', r'gradle test']
        self.security_keywords = [r'trivy', r'snyk', r'sonar', r'bandit', r'dependabot', r'codeql', r'checkov', r'tfsec']
        self.docker_build_keywords = [r'docker build', r'buildx']
        self.tf_apply_keywords = [r'terraform apply', r'tofu apply']
        self.tf_plan_keywords = [r'terraform plan', r'tofu plan']
        self.deploy_keywords = [r'deploy', r'serverless deploy', r'kubectl apply', r'helm upgrade', r'eb deploy']
        self.env_keywords = [r'environment:', r'environments:', r'staging', r'prod', r'production', r'approval']

    def _matches_any(self, content: str, keywords: List[str]) -> bool:
        content_lower = content.lower()
        for kw in keywords:
            if re.search(kw, content_lower):
                return True
        return False

    def analyze(self) -> List[InfrastructureFinding]:
        capabilities = {
            'has_tests': False,
            'has_security_scan': False,
            'has_docker_build': False,
            'has_tf_apply': False,
            'has_tf_plan': False,
            'has_deploy': False,
            'has_env_separation': False
        }
        
        raw_contents = {}
        files_found = 0
        
        # Discover CI/CD files
        # .github/workflows/*.yml, .gitlab-ci.yml, Jenkinsfile
        
        for root, dirs, files in os.walk(self.workspace_path):
            if any(part in root.split(os.sep) for part in ['.git', 'node_modules']):
                continue
                
            for file in files:
                basename = file.lower()
                rel_path = os.path.relpath(os.path.join(root, file), self.workspace_path)
                
                is_cicd = False
                if '.github/workflows' in rel_path.replace('\\', '/') and (basename.endswith('.yml') or basename.endswith('.yaml')):
                    is_cicd = True
                elif basename == '.gitlab-ci.yml':
                    is_cicd = True
                elif basename == 'jenkinsfile':
                    is_cicd = True
                    
                if is_cicd:
                    files_found += 1
                    try:
                        with open(os.path.join(self.workspace_path, rel_path), 'r', encoding='utf-8') as f:
                            content = f.read()
                            raw_contents[rel_path] = content
                            
                            if self._matches_any(content, self.test_keywords):
                                capabilities['has_tests'] = True
                            if self._matches_any(content, self.security_keywords):
                                capabilities['has_security_scan'] = True
                            if self._matches_any(content, self.docker_build_keywords):
                                capabilities['has_docker_build'] = True
                            if self._matches_any(content, self.tf_apply_keywords):
                                capabilities['has_tf_apply'] = True
                            if self._matches_any(content, self.tf_plan_keywords):
                                capabilities['has_tf_plan'] = True
                            if self._matches_any(content, self.deploy_keywords):
                                capabilities['has_deploy'] = True
                            if self._matches_any(content, self.env_keywords):
                                capabilities['has_env_separation'] = True
                                
                    except Exception:
                        pass
                        
        # Execute global rules
        return check_cicd_rules(capabilities, files_found, raw_contents)
