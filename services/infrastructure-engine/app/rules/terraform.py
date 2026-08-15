import re
from typing import List, Dict, Any, Tuple
from app.schemas.finding import InfrastructureFinding
from app.architecture.models import CloudResourceNode

def check_tf_001_public_db(resource_type: str, resource_name: str, config: dict, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    if resource_type == 'aws_db_instance' or resource_type == 'aws_rds_cluster':
        publicly_accessible = config.get('publicly_accessible', False)
        if publicly_accessible == True or str(publicly_accessible).lower() == 'true':
            findings.append(InfrastructureFinding(
                ruleId="TF-001",
                category="security",
                severity="CRITICAL",
                title="Publicly accessible database",
                description=f"Database '{resource_name}' is set to be publicly accessible.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"publicly_accessible = {publicly_accessible}",
                recommendation="Set publicly_accessible = false to restrict database access to the private network."
            ))
    return findings

def check_tf_002_hardcoded_credentials(block_type: str, block_name: str, config: dict, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    # Check common credential fields in any block (provider or resource)
    credential_keys = ['password', 'master_password', 'access_key', 'secret_key', 'token']
    
    for key, val in config.items():
        if any(k in key.lower() for k in credential_keys):
            if isinstance(val, str) and not val.startswith('${') and not val.startswith('var.') and val != '':
                findings.append(InfrastructureFinding(
                    ruleId="TF-002",
                    category="security",
                    severity="CRITICAL",
                    title="Hardcoded credentials",
                    description=f"Hardcoded credential found in '{key}' for {block_type} '{block_name}'.",
                    filePath=file_path,
                    lineNumber=0,
                    evidence=f"{key} = {val[:3]}...",
                    recommendation="Use variables, a secrets manager, or dynamic secrets instead of hardcoding credentials in HCL."
                ))
    return findings

def check_tf_003_006_public_ingress(resource_type: str, resource_name: str, config: dict, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    sensitive_ports = [22, 3306, 5432, 27017, 6379]
    
    ingress_blocks = []
    if resource_type == 'aws_security_group':
        if 'ingress' in config:
            ingress_data = config['ingress']
            if isinstance(ingress_data, list):
                ingress_blocks.extend(ingress_data)
            else:
                ingress_blocks.append(ingress_data)
    elif resource_type == 'aws_security_group_rule' and config.get('type') == 'ingress':
        ingress_blocks.append(config)
        
    for idx, rule in enumerate(ingress_blocks):
        if not isinstance(rule, dict):
            continue
            
        cidr_blocks = rule.get('cidr_blocks', [])
        if isinstance(cidr_blocks, list) and '0.0.0.0/0' in cidr_blocks:
            
            # General dangerous ingress (TF-006)
            findings.append(InfrastructureFinding(
                ruleId="TF-006",
                category="security",
                severity="HIGH",
                title="Dangerous 0.0.0.0/0 ingress",
                description=f"Security group/rule '{resource_name}' allows ingress from 0.0.0.0/0.",
                filePath=file_path,
                lineNumber=0,
                evidence="cidr_blocks = [\"0.0.0.0/0\"]",
                recommendation="Restrict ingress to specific IP ranges or other security groups."
            ))
            
            # Sensitive port exposed (TF-003)
            from_port = rule.get('from_port')
            to_port = rule.get('to_port')
            
            if from_port is not None and to_port is not None:
                try:
                    f_port = int(from_port)
                    t_port = int(to_port)
                    if any(p >= f_port and p <= t_port for p in sensitive_ports):
                        findings.append(InfrastructureFinding(
                            ruleId="TF-003",
                            category="security",
                            severity="CRITICAL",
                            title="Public security group for sensitive port",
                            description=f"Security group '{resource_name}' exposes a sensitive port (e.g. SSH/DB) to 0.0.0.0/0.",
                            filePath=file_path,
                            lineNumber=0,
                            evidence=f"from_port={f_port}, to_port={t_port} to 0.0.0.0/0",
                            recommendation="Never expose administrative or database ports to the public internet."
                        ))
                except (ValueError, TypeError):
                    pass
    return findings

def check_tf_004_missing_tags(resource_type: str, resource_name: str, config: dict, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    # Resources that typically should have tags in AWS
    taggable = ['aws_instance', 'aws_vpc', 'aws_s3_bucket', 'aws_db_instance', 'aws_security_group']
    if resource_type in taggable:
        if 'tags' not in config:
            findings.append(InfrastructureFinding(
                ruleId="TF-004",
                category="reliability",
                severity="LOW",
                title="Missing resource tags",
                description=f"Resource '{resource_type}.{resource_name}' does not have any tags.",
                filePath=file_path,
                lineNumber=0,
                evidence=f"{resource_type} without tags block",
                recommendation="Add standard tags (e.g. Environment, Owner) to improve cost tracking and resource management."
            ))
    return findings

def check_tf_007_unencrypted_storage(resource_type: str, resource_name: str, config: dict, file_path: str) -> List[InfrastructureFinding]:
    findings = []
    if resource_type == 'aws_db_instance':
        storage_encrypted = config.get('storage_encrypted', False)
        if storage_encrypted == False or str(storage_encrypted).lower() == 'false':
            findings.append(InfrastructureFinding(
                ruleId="TF-007",
                category="security",
                severity="HIGH",
                title="Unencrypted database storage",
                description=f"Database '{resource_name}' has storage_encrypted set to false or missing.",
                filePath=file_path,
                lineNumber=0,
                evidence="storage_encrypted is false/missing",
                recommendation="Set storage_encrypted = true to ensure data at rest is encrypted."
            ))
            
    if resource_type == 'aws_ebs_volume':
        encrypted = config.get('encrypted', False)
        if encrypted == False or str(encrypted).lower() == 'false':
            findings.append(InfrastructureFinding(
                ruleId="TF-007",
                category="security",
                severity="HIGH",
                title="Unencrypted EBS volume",
                description=f"EBS volume '{resource_name}' has encrypted set to false or missing.",
                filePath=file_path,
                lineNumber=0,
                evidence="encrypted is false/missing",
                recommendation="Set encrypted = true."
            ))
            
    return findings

def check_tf_005_remote_state(has_backend: bool) -> List[InfrastructureFinding]:
    findings = []
    if not has_backend:
        findings.append(InfrastructureFinding(
            ruleId="TF-005",
            category="reliability",
            severity="MEDIUM",
            title="Missing remote state recommendation",
            description="The Terraform configuration does not define a remote backend.",
            filePath="Cross-Resource",
            lineNumber=0,
            evidence="Missing 'backend' block in 'terraform' configuration.",
            recommendation="Configure a remote backend (e.g. S3 with DynamoDB locking) for state management to enable collaboration and prevent state corruption."
        ))
    return findings

def extract_cloud_resource(resource_type: str, resource_name: str, provider: str) -> CloudResourceNode:
    return CloudResourceNode(
        id=f"{resource_type}.{resource_name}",
        provider=provider,
        type=resource_type,
        name=resource_name
    )

def analyze_hcl_dict(parsed_hcl: dict, file_path: str) -> Tuple[List[InfrastructureFinding], List[CloudResourceNode], bool, List[str]]:
    findings = []
    resources = []
    has_backend = False
    providers_found = set()
    
    # 1. Check terraform block for backend
    if 'terraform' in parsed_hcl:
        tf_blocks = parsed_hcl['terraform']
        for tf_block in tf_blocks:
            if 'backend' in tf_block:
                has_backend = True
                
    # 2. Check provider blocks for hardcoded creds and extract provider name
    if 'provider' in parsed_hcl:
        for prov_block in parsed_hcl['provider']:
            for prov_name, prov_config in prov_block.items():
                providers_found.add(prov_name)
                if isinstance(prov_config, dict):
                    findings.extend(check_tf_002_hardcoded_credentials('provider', prov_name, prov_config, file_path))
                    
    # 3. Check resource blocks
    if 'resource' in parsed_hcl:
        for res_block in parsed_hcl['resource']:
            for res_type, res_map in res_block.items():
                for res_name, res_config in res_map.items():
                    if not isinstance(res_config, dict):
                        continue
                        
                    # Infer provider from prefix (e.g. aws_vpc -> aws)
                    provider = res_type.split('_')[0] if '_' in res_type else "unknown"
                    
                    # Extract for architecture model
                    resources.append(extract_cloud_resource(res_type, res_name, provider))
                    
                    # Run rules
                    findings.extend(check_tf_001_public_db(res_type, res_name, res_config, file_path))
                    findings.extend(check_tf_002_hardcoded_credentials('resource', res_name, res_config, file_path))
                    findings.extend(check_tf_003_006_public_ingress(res_type, res_name, res_config, file_path))
                    findings.extend(check_tf_004_missing_tags(res_type, res_name, res_config, file_path))
                    findings.extend(check_tf_007_unencrypted_storage(res_type, res_name, res_config, file_path))

    return findings, resources, has_backend, list(providers_found)
