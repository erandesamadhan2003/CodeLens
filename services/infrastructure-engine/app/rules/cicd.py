import re
from typing import List, Dict, Any
from app.schemas.finding import InfrastructureFinding

def check_cicd_rules(capabilities: Dict[str, bool], files_found: int, raw_contents: Dict[str, str]) -> List[InfrastructureFinding]:
    findings = []
    
    has_tests = capabilities.get('has_tests', False)
    has_security_scan = capabilities.get('has_security_scan', False)
    has_docker_build = capabilities.get('has_docker_build', False)
    has_tf_apply = capabilities.get('has_tf_apply', False)
    has_tf_plan = capabilities.get('has_tf_plan', False)
    has_deploy = capabilities.get('has_deploy', False)
    has_env_separation = capabilities.get('has_env_separation', False)
    
    # CICD-001: No automated tests
    if not has_tests:
        findings.append(InfrastructureFinding(
            ruleId="CICD-001",
            category="reliability",
            severity="MEDIUM" if files_found > 0 else "LOW",
            title="No automated tests",
            description="The CI/CD pipeline does not appear to run any automated tests.",
            filePath="Repository Context",
            lineNumber=0,
            evidence="No test commands (e.g., pytest, npm test, jest) found in CI/CD configuration.",
            recommendation="Add automated testing to your CI/CD pipeline to ensure code quality and prevent regressions."
        ))
        
    # CICD-002: No security scanning
    if not has_security_scan:
        findings.append(InfrastructureFinding(
            ruleId="CICD-002",
            category="security",
            severity="HIGH" if files_found > 0 else "MEDIUM",
            title="No security scanning",
            description="The CI/CD pipeline does not appear to include security or dependency scanning.",
            filePath="Repository Context",
            lineNumber=0,
            evidence="No security scanning tools (e.g., trivy, snyk, sonar, dependabot) found in CI/CD configuration.",
            recommendation="Integrate security scanning (e.g., Trivy for containers, Snyk for dependencies, or SonarQube for SAST) into your CI/CD pipeline."
        ))
        
    # CICD-003: Docker image built without security scanning
    if has_docker_build and not has_security_scan:
        findings.append(InfrastructureFinding(
            ruleId="CICD-003",
            category="security",
            severity="CRITICAL",
            title="Docker image built without security scanning",
            description="Docker images are being built in the CI/CD pipeline, but no security scanning is performed.",
            filePath="Repository Context",
            lineNumber=0,
            evidence="Found 'docker build' but no security scanning tools.",
            recommendation="Integrate a container security scanner (e.g., Trivy) to scan Docker images before pushing them to a registry."
        ))
        
    # CICD-004: Terraform apply without plan
    if has_tf_apply and not has_tf_plan:
        findings.append(InfrastructureFinding(
            ruleId="CICD-004",
            category="reliability",
            severity="HIGH",
            title="Terraform apply without plan",
            description="The CI/CD pipeline runs 'terraform apply' without a prior 'terraform plan' validation.",
            filePath="Repository Context",
            lineNumber=0,
            evidence="Found 'terraform apply' but no 'terraform plan'.",
            recommendation="Always run and review 'terraform plan' before 'terraform apply' in automated environments, or use plan artifacts."
        ))
        
    # CICD-005: Deployment without environment separation
    if has_deploy and not has_env_separation:
        findings.append(InfrastructureFinding(
            ruleId="CICD-005",
            category="reliability",
            severity="MEDIUM",
            title="Deployment without environment separation",
            description="The CI/CD pipeline appears to deploy code without distinct environment separation or approvals.",
            filePath="Repository Context",
            lineNumber=0,
            evidence="Found deployment steps but no environment references (e.g., staging, prod) or approval gates.",
            recommendation="Implement environment separation (e.g., deploy to staging first, then require approval for production)."
        ))

    # CICD-006: Secrets exposed directly
    secret_regex = re.compile(r'(ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|[a-zA-Z0-9_]*password[a-zA-Z0-9_]*\s*[:=]\s*["\'][a-zA-Z0-9]{8,}["\'])', re.IGNORECASE)
    
    for filepath, content in raw_contents.items():
        for i, line in enumerate(content.split('\n')):
            match = secret_regex.search(line)
            if match and not any(safe in line for safe in ['${', 'secrets.', 'env.']):
                findings.append(InfrastructureFinding(
                    ruleId="CICD-006",
                    category="security",
                    severity="CRITICAL",
                    title="Secrets exposed directly in CI/CD",
                    description="Hardcoded secrets or tokens were found directly in the CI/CD configuration.",
                    filePath=filepath,
                    lineNumber=i + 1,
                    evidence=line.strip()[:100],
                    recommendation="Remove hardcoded secrets from CI/CD files. Use the CI/CD platform's built-in secrets management (e.g., GitHub Secrets)."
                ))

    return findings
