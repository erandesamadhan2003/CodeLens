import os
import pytest
from app.discovery.scanner import InfrastructureScanner
from app.architecture.builder import build_architecture
from app.architecture.graph import build_graph

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_architecture_fixture_1():
    # Node + PostgreSQL, no infrastructure
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-1"))
    discovery = scanner.run_discovery()
    
    model = build_architecture(discovery)
    assert "Node.js" in model.application.languages
    assert len(model.databases) == 1
    assert model.databases[0].type == "postgresql"
    assert "containerization" in model.gaps
    assert "deployment" in model.gaps
    assert "infrastructure_as_code" in model.gaps
    
    build_graph(model)
    assert len(model.architecture_graph.nodes) > 0
    assert any(n.type == "database" for n in model.architecture_graph.nodes)
    assert any(n.type == "backend" or n.type == "frontend" for n in model.architecture_graph.nodes)
    
    assert model.complexity > 0

def test_architecture_fixture_2():
    # Node + Docker + Compose
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-2"))
    discovery = scanner.run_discovery()
    
    model = build_architecture(discovery)
    assert model.infrastructure.docker is True
    assert model.infrastructure.compose is True
    assert "containerization" not in model.gaps
    
    build_graph(model)
    # Since Docker is present, a container node should exist
    assert any(n.type == "container" for n in model.architecture_graph.nodes)
    # Cache node (redis) should exist
    assert any(n.type == "cache" for n in model.architecture_graph.nodes)

def test_architecture_fixture_3():
    # Node + Docker + Kubernetes + Terraform
    scanner = InfrastructureScanner(os.path.join(FIXTURES_DIR, "fixture-3"))
    discovery = scanner.run_discovery()
    
    model = build_architecture(discovery)
    assert model.infrastructure.docker is True
    assert model.infrastructure.kubernetes is True
    assert model.infrastructure.terraform is True
    assert "infrastructure_as_code" not in model.gaps
    
    build_graph(model)
    assert any(n.type == "Kubernetes resource" for n in model.architecture_graph.nodes)
    assert any(e.type == "deploys_to" for e in model.architecture_graph.edges)
