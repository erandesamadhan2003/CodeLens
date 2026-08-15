import os
import json
import yaml
from typing import List
from app.schemas.discovery import InfrastructureDiscovery, DetectedService

class AppDetector:
    def __init__(self, files: List[str], file_reader):
        self.files = files
        self.file_reader = file_reader

    def detect(self, discovery: InfrastructureDiscovery):
        self._detect_languages(discovery)
        self._detect_services_from_compose(discovery)
        # More advanced package parsing can be added here
        
        # Ensure uniqueness
        discovery.languages = list(set(discovery.languages))
        discovery.frameworks = list(set(discovery.frameworks))

    def _detect_languages(self, discovery: InfrastructureDiscovery):
        for file in self.files:
            basename = os.path.basename(file).lower()
            
            if basename == 'package.json':
                discovery.languages.append('Node.js')
                self._parse_package_json(file, discovery)
                
            elif basename in ('requirements.txt', 'pyproject.toml', 'pipfile'):
                discovery.languages.append('Python')
                if basename == 'requirements.txt':
                    self._parse_requirements_txt(file, discovery)

            elif basename == 'go.mod':
                discovery.languages.append('Go')
                
            elif basename in ('pom.xml', 'build.gradle'):
                discovery.languages.append('Java')
                
            elif basename.endswith('.csproj'):
                discovery.languages.append('.NET')
                
            elif basename == 'gemfile':
                discovery.languages.append('Ruby')

    def _parse_package_json(self, rel_path: str, discovery: InfrastructureDiscovery):
        content = self.file_reader(rel_path)
        if not content:
            return
            
        try:
            data = json.loads(content)
            deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
            
            # Frameworks
            if 'express' in deps:
                discovery.frameworks.append('Express')
            if 'react' in deps:
                discovery.frameworks.append('React')
            if 'next' in deps:
                discovery.frameworks.append('Next.js')
            if 'nestjs' in deps or '@nestjs/core' in deps:
                discovery.frameworks.append('NestJS')
                
            # Services
            if 'pg' in deps or 'typeorm' in deps or 'sequelize' in deps:
                self._add_service(discovery, 'PostgreSQL', 'database', 'postgresql')
            if 'redis' in deps or 'ioredis' in deps:
                self._add_service(discovery, 'Redis', 'cache', 'redis')
            if 'amqplib' in deps or 'bullmq' in deps:
                self._add_service(discovery, 'RabbitMQ/BullMQ', 'queue', 'queue')
                
        except json.JSONDecodeError:
            pass

    def _parse_requirements_txt(self, rel_path: str, discovery: InfrastructureDiscovery):
        content = self.file_reader(rel_path)
        if not content:
            return
        content = content.lower()
        if 'psycopg' in content:
            self._add_service(discovery, 'PostgreSQL', 'database', 'postgresql')
        if 'redis' in content:
            self._add_service(discovery, 'Redis', 'cache', 'redis')
        if 'fastapi' in content:
            discovery.frameworks.append('FastAPI')
        if 'django' in content:
            discovery.frameworks.append('Django')
        if 'flask' in content:
            discovery.frameworks.append('Flask')

    def _detect_services_from_compose(self, discovery: InfrastructureDiscovery):
        for file in self.files:
            basename = os.path.basename(file).lower()
            if basename in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'):
                content = self.file_reader(file)
                if not content:
                    continue
                try:
                    compose = yaml.safe_load(content)
                    if not isinstance(compose, dict) or 'services' not in compose:
                        continue
                        
                    for svc_name, svc_conf in compose['services'].items():
                        image = svc_conf.get('image', '').lower()
                        ports_str = svc_conf.get('ports', [])
                        ports = []
                        for p in ports_str:
                            if isinstance(p, str) and ':' in p:
                                try:
                                    ports.append(int(p.split(':')[-1].split('/')[0]))
                                except ValueError:
                                    pass
                        
                        if 'postgres' in image:
                            self._add_service(discovery, svc_name, 'database', 'postgresql', ports, [file])
                        elif 'redis' in image:
                            self._add_service(discovery, svc_name, 'cache', 'redis', ports, [file])
                        elif 'mysql' in image:
                            self._add_service(discovery, svc_name, 'database', 'mysql', ports, [file])
                        elif 'mongo' in image:
                            self._add_service(discovery, svc_name, 'database', 'mongodb', ports, [file])
                        else:
                            self._add_service(discovery, svc_name, 'app', 'docker', ports, [file])
                except yaml.YAMLError:
                    pass

    def _add_service(self, discovery: InfrastructureDiscovery, name: str, svc_type: str, technology: str, ports: List[int] = None, files: List[str] = None):
        ports = ports or []
        files = files or []
        
        # Check if already exists
        for svc in discovery.detected_services:
            if svc.technology == technology and svc.type == svc_type:
                # Merge
                svc.ports = list(set(svc.ports + ports))
                svc.files = list(set(svc.files + files))
                return
                
        discovery.detected_services.append(
            DetectedService(name=name, type=svc_type, technology=technology, ports=ports, files=files)
        )
