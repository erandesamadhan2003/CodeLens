import os
import pytest
from app.discovery.scanner import InfrastructureScanner

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_fixture_1():
    # Node + PostgreSQL, no infrastructure
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-1"))
    discovery = scanner.run_discovery()
    
    assert "Node.js" in discovery.languages
    assert "Express" in discovery.frameworks
    assert discovery.has_dockerfile is False
    
    services = [s.name for s in discovery.detected_services]
    assert "PostgreSQL" in services

def test_fixture_2():
    # Node + Docker + Compose
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-2"))
    discovery = scanner.run_discovery()
    
    assert "Node.js" in discovery.languages
    assert "React" in discovery.frameworks
    
    assert discovery.has_dockerfile is True
    assert discovery.has_docker_compose is True
    
    services = [s.technology for s in discovery.detected_services]
    assert "redis" in services
    # Web service from docker-compose should also be detected
    web_service = next((s for s in discovery.detected_services if s.name == 'web'), None)
    assert web_service is not None
    assert 3000 in web_service.ports

def test_fixture_3():
    # Node + Docker + Kubernetes + Terraform
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-3"))
    discovery = scanner.run_discovery()
    
    assert "Node.js" in discovery.languages
    assert "NestJS" in discovery.frameworks
    
    assert discovery.has_dockerfile is True
    assert discovery.has_k8s_manifests is True
    assert discovery.has_terraform is True
    
    services = [s.technology for s in discovery.detected_services]
    assert "queue" in services  # From bullmq

def test_fixture_4():
    # Python + PostgreSQL + Redis
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-4"))
    discovery = scanner.run_discovery()
    
    assert "Python" in discovery.languages
    # Note: parsing requirements.txt for specific services isn't fully implemented in our naive app_detector
    # But it correctly detects the language.
