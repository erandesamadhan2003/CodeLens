import base64
import re
from typing import List, Dict, Any, Optional
from app.schemas.finding import InfrastructureFinding

def extract_containers(spec: dict) -> List[dict]:
    containers = []
    if 'containers' in spec:
        containers.extend(spec['containers'])
    if 'initContainers' in spec:
        containers.extend(spec['initContainers'])
    return containers

def get_pod_spec(doc: dict) -> Optional[dict]:
    kind = doc.get('kind', '')
    if kind == 'Pod':
        return doc.get('spec', {})
    elif kind in ('Deployment', 'StatefulSet', 'DaemonSet', 'Job'):
        return doc.get('spec', {}).get('template', {}).get('spec', {})
    elif kind == 'CronJob':
        return doc.get('spec', {}).get('jobTemplate', {}).get('spec', {}).get('template', {}).get('spec', {})
    return None

def analyze_kubernetes_doc(doc: dict, file_path: str, doc_index: int) -> List[InfrastructureFinding]:
    findings = []
    if not isinstance(doc, dict):
        return findings
        
    kind = doc.get('kind', '')
    name = doc.get('metadata', {}).get('name', 'unknown')
    
    # Analyze Pod Spec (Probes, Resources, SecurityContext)
    pod_spec = get_pod_spec(doc)
    if pod_spec:
        # Check Pod-level security context
        pod_sec = pod_spec.get('securityContext', {})
        if pod_sec.get('runAsNonRoot') is False or str(pod_sec.get('runAsUser')) == '0':
            findings.append(InfrastructureFinding(
                ruleId="K8S-005",
                category="security",
                severity="HIGH",
                title="Container runs as root",
                description=f"Resource '{name}' explicitly runs as root at the pod level.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"runAsNonRoot: {pod_sec.get('runAsNonRoot')}, runAsUser: {pod_sec.get('runAsUser')}",
                recommendation="Set securityContext.runAsNonRoot to true and specify a non-root runAsUser."
            ))
            
        containers = extract_containers(pod_spec)
        for c in containers:
            c_name = c.get('name', 'unknown')
            c_sec = c.get('securityContext', {})
            
            # K8S-005: Container runs as root
            if c_sec.get('runAsNonRoot') is False or str(c_sec.get('runAsUser')) == '0':
                findings.append(InfrastructureFinding(
                    ruleId="K8S-005",
                    category="security",
                    severity="HIGH",
                    title="Container runs as root",
                    description=f"Container '{c_name}' in resource '{name}' explicitly runs as root.",
                    filePath=file_path,
                    lineNumber=0,
                    evidence=f"runAsNonRoot: {c_sec.get('runAsNonRoot')}, runAsUser: {c_sec.get('runAsUser')}",
                    recommendation="Set securityContext.runAsNonRoot to true and specify a non-root runAsUser."
                ))
                
            # K8S-006: privileged: true
            if c_sec.get('privileged') is True:
                findings.append(InfrastructureFinding(
                    ruleId="K8S-006",
                    category="security",
                    severity="CRITICAL",
                    title="Privileged container",
                    description=f"Container '{c_name}' in resource '{name}' runs in privileged mode.",
                    filePath=file_path,
                    lineNumber=0,
                    evidence="privileged: true",
                    recommendation="Do not run privileged containers. Use specific capabilities instead."
                ))
                
            # Probes (only for regular containers, not initContainers typically, but we'll check both, usually initContainers don't have probes though. Let's just check containers in 'containers')
            if c in pod_spec.get('containers', []):
                if 'readinessProbe' not in c:
                    findings.append(InfrastructureFinding(
                        ruleId="K8S-001",
                        category="reliability",
                        severity="MEDIUM",
                        title="Missing readinessProbe",
                        description=f"Container '{c_name}' in resource '{name}' is missing a readinessProbe.",
                        filePath=file_path,
                        lineNumber=0,
                        evidence=c_name,
                        recommendation="Define a readinessProbe to ensure traffic is only routed when the container is ready."
                    ))
                if 'livenessProbe' not in c:
                    findings.append(InfrastructureFinding(
                        ruleId="K8S-002",
                        category="reliability",
                        severity="MEDIUM",
                        title="Missing livenessProbe",
                        description=f"Container '{c_name}' in resource '{name}' is missing a livenessProbe.",
                        filePath=file_path,
                        lineNumber=0,
                        evidence=c_name,
                        recommendation="Define a livenessProbe to allow Kubernetes to automatically restart unresponsive containers."
                    ))
                if 'startupProbe' not in c:
                    findings.append(InfrastructureFinding(
                        ruleId="K8S-003",
                        category="reliability",
                        severity="LOW",
                        title="Missing startupProbe",
                        description=f"Container '{c_name}' in resource '{name}' is missing a startupProbe.",
                        filePath=file_path,
                        lineNumber=0,
                        evidence=c_name,
                        recommendation="Consider adding a startupProbe for slow-starting applications to prevent them from being killed prematurely by the livenessProbe."
                    ))
                    
                # K8S-004: Missing CPU/memory limits
                resources = c.get('resources', {})
                limits = resources.get('limits', {})
                if 'cpu' not in limits or 'memory' not in limits:
                    findings.append(InfrastructureFinding(
                        ruleId="K8S-004",
                        category="reliability",
                        severity="MEDIUM",
                        title="Missing resource limits",
                        description=f"Container '{c_name}' in resource '{name}' is missing CPU or memory limits.",
                        filePath=file_path,
                        lineNumber=0,
                        evidence=c_name,
                        recommendation="Define both CPU and memory limits to prevent the container from consuming all node resources."
                    ))

    # K8S-007: Only one replica
    if kind in ('Deployment', 'StatefulSet'):
        replicas = doc.get('spec', {}).get('replicas', 1) # Default is 1 if not specified
        if replicas == 1:
            findings.append(InfrastructureFinding(
                ruleId="K8S-007",
                category="reliability",
                severity="LOW",
                title="Only one replica specified",
                description=f"Resource '{name}' specifies only 1 replica, providing no high availability.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"replicas: {replicas}",
                recommendation="Increase replicas to at least 2 for production workloads to ensure high availability."
            ))

    # K8S-009: Service unnecessarily exposed
    if kind == 'Service':
        svc_type = doc.get('spec', {}).get('type', 'ClusterIP')
        if svc_type in ('NodePort', 'LoadBalancer'):
            findings.append(InfrastructureFinding(
                ruleId="K8S-009",
                category="security",
                severity="MEDIUM",
                title="Service unnecessarily exposed",
                description=f"Service '{name}' is exposed as {svc_type}.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"type: {svc_type}",
                recommendation="Use ClusterIP for internal services and expose external traffic through an Ingress controller."
            ))

    # K8S-010: Secret values directly embedded
    if kind == 'Secret':
        secret_pattern = re.compile(r'(?i)(password|key|token|credential|secret)')
        
        # Check stringData
        string_data = doc.get('stringData', {})
        for k, v in string_data.items():
            if v and not v.startswith('${'):
                findings.append(InfrastructureFinding(
                    ruleId="K8S-010",
                    category="security",
                    severity="CRITICAL",
                    title="Secret values directly embedded",
                    description=f"Secret '{name}' contains plaintext value in stringData.",
                    filePath=file_path,
                    lineNumber=0,
                    evidence=f"Key: {k}",
                    recommendation="Do not commit secrets to source control. Use a secret management solution like ExternalSecrets or SOPS."
                ))
                
        # Check base64 encoded data
        data = doc.get('data', {})
        for k, v in data.items():
            if v:
                try:
                    decoded = base64.b64decode(v).decode('utf-8')
                    if not decoded.startswith('${') and not decoded.startswith('<'):
                        findings.append(InfrastructureFinding(
                            ruleId="K8S-010",
                            category="security",
                            severity="CRITICAL",
                            title="Secret values directly embedded (Base64)",
                            description=f"Secret '{name}' contains base64 encoded sensitive value in data block.",
                            filePath=file_path,
                            lineNumber=0,
                            evidence=f"Key: {k}",
                            recommendation="Do not commit secrets to source control. Use a secret management solution like ExternalSecrets or SOPS."
                        ))
                except Exception:
                    pass

    return findings

def evaluate_cross_resource_rules(deployments: List[str], hpas: List[str]) -> List[InfrastructureFinding]:
    """
    Evaluates rules that require cross-resource context.
    - K8S-008: Missing HPA
    """
    findings = []
    
    for dep in deployments:
        if dep not in hpas:
            findings.append(InfrastructureFinding(
                ruleId="K8S-008",
                category="reliability",
                severity="LOW",
                title="Missing HPA",
                description=f"Deployment '{dep}' does not have a corresponding HorizontalPodAutoscaler.",
                filePath="Cross-Resource",
                lineNumber=0,
                evidence=f"Deployment: {dep}",
                recommendation="Consider adding an HPA to automatically scale the deployment based on CPU/Memory utilization."
            ))
            
    return findings
