import os
import re
from typing import List
from app.schemas.discovery import InfrastructureDiscovery

class InfraDetector:
    def __init__(self, files: List[str]):
        self.files = files

    def detect(self, discovery: InfrastructureDiscovery):
        """
        Populates infrastructure detection flags based on files.
        """
        for file in self.files:
            basename = os.path.basename(file).lower()
            dirname = os.path.dirname(file).lower()
            parts = file.lower().split(os.sep)

            # Docker
            if 'dockerfile' in basename or basename.endswith('.dockerfile'):
                discovery.has_dockerfile = True
                discovery.infrastructure_files.append(file)

            # Docker Compose
            if basename in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'):
                discovery.has_docker_compose = True
                discovery.infrastructure_files.append(file)

            # Kubernetes
            if 'k8s' in parts or 'kubernetes' in parts:
                if basename.endswith('.yml') or basename.endswith('.yaml'):
                    discovery.has_k8s_manifests = True
                    discovery.infrastructure_files.append(file)

            # Helm
            if basename == 'chart.yaml' or 'helm' in parts:
                discovery.has_helm_charts = True
                if basename.endswith('.yaml') or basename.endswith('.yml'):
                    discovery.infrastructure_files.append(file)

            # Terraform
            if basename.endswith('.tf') or 'terraform' in parts:
                discovery.has_terraform = True
                if basename.endswith('.tf'):
                    discovery.infrastructure_files.append(file)

            # Pulumi
            if basename.startswith('pulumi.') or 'pulumi' in parts:
                discovery.has_pulumi = True
                discovery.infrastructure_files.append(file)

            # Ansible
            if 'ansible' in parts or 'playbook' in basename:
                if basename.endswith('.yml') or basename.endswith('.yaml'):
                    discovery.has_ansible = True
                    discovery.infrastructure_files.append(file)

            # CI/CD
            if '.github/workflows' in file.lower():
                discovery.has_ci_config = True
                discovery.infrastructure_files.append(file)
            if basename == '.gitlab-ci.yml':
                discovery.has_ci_config = True
                discovery.infrastructure_files.append(file)
            if basename == 'jenkinsfile':
                discovery.has_ci_config = True
                discovery.infrastructure_files.append(file)
                
        # Deduplicate files list
        discovery.infrastructure_files = list(set(discovery.infrastructure_files))
