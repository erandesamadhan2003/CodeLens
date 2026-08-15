import yaml
import re
from typing import List, Dict, Any
from app.schemas.finding import InfrastructureFinding

def analyze_compose(content: str, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    
    try:
        compose = yaml.safe_load(content)
    except yaml.YAMLError:
        return findings

    if not isinstance(compose, dict) or 'services' not in compose:
        return findings
        
    services = compose.get('services', {})
    
    secret_pattern = re.compile(r'(?i)(secret|password|key|token|credential)\s*=\s*[^\s$]+')

    for service_name, config in services.items():
        if not isinstance(config, dict):
            continue
            
        image = config.get('image', '').lower()
        ports = config.get('ports', [])
        
        # Check COMPOSE-001 & COMPOSE-002: DB/Redis exposed
        if 'postgres' in image or 'mysql' in image or 'mongo' in image or 'redis' in image:
            is_db = 'redis' not in image
            is_redis = 'redis' in image
            
            for port in ports:
                port_str = str(port)
                # If a port is exposed and doesn't explicitly bind to localhost
                if ':' in port_str and not port_str.startswith('127.0.0.1:'):
                    if is_db:
                        findings.append(InfrastructureFinding(
                            ruleId="COMPOSE-001",
                            category="security",
                            severity="CRITICAL",
                            title="Database publicly exposed",
                            description=f"Service '{service_name}' exposes a database port without binding it to localhost.",
                            filePath=file_path,
                            lineNumber=0,
                            evidence=f"ports: {port_str}",
                            recommendation="Bind database ports exclusively to localhost (e.g., '127.0.0.1:5432:5432') or do not expose them to the host at all."
                        ))
                    if is_redis:
                        findings.append(InfrastructureFinding(
                            ruleId="COMPOSE-002",
                            category="security",
                            severity="CRITICAL",
                            title="Redis publicly exposed",
                            description=f"Service '{service_name}' exposes a Redis port without binding it to localhost.",
                            filePath=file_path,
                            lineNumber=0,
                            evidence=f"ports: {port_str}",
                            recommendation="Bind Redis ports exclusively to localhost (e.g., '127.0.0.1:6379:6379') or do not expose them to the host at all."
                        ))

        # Check COMPOSE-003: Missing healthcheck
        if 'healthcheck' not in config:
            findings.append(InfrastructureFinding(
                ruleId="COMPOSE-003",
                category="reliability",
                severity="LOW",
                title="Missing healthcheck",
                description=f"Service '{service_name}' does not have a healthcheck defined.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"Service: {service_name}",
                recommendation="Define a healthcheck block to ensure the service is actually ready before dependent services start."
            ))

        # Check COMPOSE-004: Missing restart policy
        if 'restart' not in config:
            findings.append(InfrastructureFinding(
                ruleId="COMPOSE-004",
                category="reliability",
                severity="MEDIUM",
                title="Missing restart policy",
                description=f"Service '{service_name}' does not define a restart policy.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"Service: {service_name}",
                recommendation="Add 'restart: always' or 'restart: unless-stopped' to ensure the container recovers from crashes."
            ))

        # Check COMPOSE-005: Missing resource limits
        deploy = config.get('deploy', {})
        resources = deploy.get('resources', {}) if isinstance(deploy, dict) else {}
        limits = resources.get('limits', {}) if isinstance(resources, dict) else {}
        if not limits:
            findings.append(InfrastructureFinding(
                ruleId="COMPOSE-005",
                category="reliability",
                severity="LOW",
                title="Missing resource limits",
                description=f"Service '{service_name}' does not define memory or CPU limits.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"Service: {service_name}",
                recommendation="Define resource limits under the deploy.resources.limits block to prevent a single container from consuming all host resources."
            ))

        # Check COMPOSE-006: Secrets passed directly through environment values
        env = config.get('environment', [])
        if isinstance(env, dict):
            env_list = [f"{k}={v}" for k, v in env.items()]
        elif isinstance(env, list):
            env_list = [str(e) for e in env]
        else:
            env_list = []
            
        for e in env_list:
            if '=' in e:
                val = e.split('=', 1)[1]
                if val and not val.startswith('${') and secret_pattern.search(e):
                    findings.append(InfrastructureFinding(
                        ruleId="COMPOSE-006",
                        category="security",
                        severity="CRITICAL",
                        title="Secrets passed directly in environment",
                        description=f"Service '{service_name}' hardcodes a secret in its environment variables.",
                        filePath=file_path,
                        lineNumber=0,
                        evidence=e,
                        recommendation="Use variable substitution (e.g., '${DB_PASSWORD}') or Docker secrets instead of hardcoding sensitive values."
                    ))
                    
    return findings
