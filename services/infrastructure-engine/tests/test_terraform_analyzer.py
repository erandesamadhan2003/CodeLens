import pytest
import os
import tempfile
from app.analyzers.terraform_analyzer import TerraformAnalyzer
from app.architecture.models import ArchitectureModel

def create_temp_file(dir_path, name, content):
    full_path = os.path.join(dir_path, name)
    with open(full_path, 'w') as f:
        f.write(content)

def test_terraform_analyzer_rules():
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_tf = """
provider "aws" {
  region     = "us-west-2"
  access_key = "my-access-key" # TF-002
}

resource "aws_db_instance" "default" {
  allocated_storage    = 10
  engine               = "mysql"
  instance_class       = "db.t3.micro"
  password             = "supersecret" # TF-002
  publicly_accessible  = true          # TF-001
  storage_encrypted    = false         # TF-007
  # Missing tags (TF-004)
}

resource "aws_security_group" "allow_all" {
  name        = "allow_all"
  
  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # TF-003, TF-006
  }
}
"""
        # Missing backend (TF-005)
        create_temp_file(tmpdir, "main.tf", bad_tf)
        
        arch = ArchitectureModel()
        analyzer = TerraformAnalyzer(tmpdir, arch)
        findings, provider = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "TF-001" in rule_ids
        assert rule_ids.count("TF-002") == 2
        assert "TF-003" in rule_ids
        assert "TF-004" in rule_ids
        assert "TF-005" in rule_ids
        assert "TF-006" in rule_ids
        assert "TF-007" in rule_ids
        
        assert provider == "aws"
        assert len(arch.cloud_resources) == 2
        
def test_terraform_analyzer_good():
    with tempfile.TemporaryDirectory() as tmpdir:
        good_tf = """
terraform {
  backend "s3" {
    bucket = "mybucket"
  }
}

provider "aws" {
  region = "us-west-2"
}

resource "aws_db_instance" "default" {
  allocated_storage   = 10
  engine              = "mysql"
  instance_class      = "db.t3.micro"
  password            = var.db_password
  publicly_accessible = false
  storage_encrypted   = true
  
  tags = {
    Environment = "prod"
  }
}
"""
        create_temp_file(tmpdir, "main.tf", good_tf)
        
        arch = ArchitectureModel()
        analyzer = TerraformAnalyzer(tmpdir, arch)
        findings, provider = analyzer.analyze()
        
        rule_ids = [f.ruleId for f in findings]
        assert "TF-001" not in rule_ids
        assert "TF-002" not in rule_ids
        assert "TF-003" not in rule_ids
        assert "TF-004" not in rule_ids
        assert "TF-005" not in rule_ids
        assert "TF-006" not in rule_ids
        assert "TF-007" not in rule_ids
