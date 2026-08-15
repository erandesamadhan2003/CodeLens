import re
from typing import List
from app.schemas.finding import InfrastructureFinding

def analyze_dockerfile(content: str, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    lines = content.splitlines()
    
    has_user = False
    has_healthcheck = False
    from_count = 0
    from_lines = []
    
    # Simple regexes for parsing
    secret_pattern = re.compile(r'(?i)(secret|password|key|token|credential)\s*[=:]\s*[\'"]?[^\s\'"]+')

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()
        
        # Skip comments
        if stripped.startswith('#') or not stripped:
            continue
            
        # Count FROMs for multi-stage
        if stripped.upper().startswith('FROM '):
            from_count += 1
            from_lines.append(stripped)
            
            # Check DOCKER-002: Uses :latest image tag
            if ':latest' in stripped.lower():
                findings.append(InfrastructureFinding(
                    ruleId="DOCKER-002",
                    category="reliability",
                    severity="HIGH",
                    title="Uses :latest image tag",
                    description="Using the :latest tag makes builds unpredictable as the base image can change without warning.",
                    filePath=file_path,
                    lineNumber=line_num,
                    evidence=stripped,
                    recommendation="Pin the base image to a specific version tag (e.g. node:18.16.0-alpine)."
                ))
                
            # Check DOCKER-006: Large/unoptimized base image
            lower_line = stripped.lower()
            if 'ubuntu' in lower_line or 'debian' in lower_line or 'node' in lower_line:
                if 'alpine' not in lower_line and 'slim' not in lower_line and 'distroless' not in lower_line:
                    findings.append(InfrastructureFinding(
                        ruleId="DOCKER-006",
                        category="performance",
                        severity="MEDIUM",
                        title="Large base image",
                        description="Using full OS distributions or heavy base images increases image size and attack surface.",
                        filePath=file_path,
                        lineNumber=line_num,
                        evidence=stripped,
                        recommendation="Consider using an alpine, slim, or distroless variant of the base image."
                    ))

        # Check DOCKER-001: Container runs as root
        if stripped.upper().startswith('USER '):
            user = stripped[5:].strip()
            if user.lower() != 'root' and user != '0':
                has_user = True
                
        # Check DOCKER-003: Missing HEALTHCHECK
        if stripped.upper().startswith('HEALTHCHECK '):
            has_healthcheck = True
            
        # Check DOCKER-004: Potential secret in Dockerfile
        if stripped.upper().startswith('ENV ') or stripped.upper().startswith('ARG '):
            if secret_pattern.search(stripped):
                findings.append(InfrastructureFinding(
                    ruleId="DOCKER-004",
                    category="security",
                    severity="CRITICAL",
                    title="Potential secret in Dockerfile",
                    description="Hardcoding secrets in ENV or ARG instructions exposes them in the image history.",
                    filePath=file_path,
                    lineNumber=line_num,
                    evidence=stripped,
                    recommendation="Pass secrets at runtime using environment variables or a secrets manager. Do not embed them in the image."
                ))

    # Evaluate file-wide rules
    if not has_user:
        findings.append(InfrastructureFinding(
            ruleId="DOCKER-001",
            category="security",
            severity="HIGH",
            title="Container runs as root",
            description="The Dockerfile does not specify a non-root USER. By default, the container will run as root.",
            filePath=file_path,
            lineNumber=0,
            evidence="Missing USER instruction",
            recommendation="Add a 'USER <username>' instruction after installing required system packages."
        ))
        
    if not has_healthcheck:
        findings.append(InfrastructureFinding(
            ruleId="DOCKER-003",
            category="reliability",
            severity="MEDIUM",
            title="Missing HEALTHCHECK",
            description="The Dockerfile lacks a HEALTHCHECK instruction, making it harder for orchestrators to determine if the application is healthy.",
            filePath=file_path,
            lineNumber=0,
            evidence="Missing HEALTHCHECK instruction",
            recommendation="Add a HEALTHCHECK instruction to probe your application's health endpoint."
        ))
        
    # Check DOCKER-005: Missing multi-stage build (simple heuristic)
    if from_count == 1:
        base_image = from_lines[0].lower()
        if any(lang in base_image for lang in ['node', 'go', 'java', 'maven', 'gradle', 'rust']):
            findings.append(InfrastructureFinding(
                ruleId="DOCKER-005",
                category="performance",
                severity="MEDIUM",
                title="Missing multi-stage build",
                description="The Dockerfile uses a compiler/build-heavy base image but does not use a multi-stage build. This includes build tools in the final image.",
                filePath=file_path,
                lineNumber=0,
                evidence=from_lines[0],
                recommendation="Use a multi-stage build to compile the application and copy only the final artifacts to a minimal runtime image."
            ))

    return findings
