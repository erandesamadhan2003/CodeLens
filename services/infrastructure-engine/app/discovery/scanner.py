from typing import Optional
import os
from app.schemas.discovery import InfrastructureDiscovery
from app.discovery.file_detector import FileDetector
from app.discovery.infra_detector import InfraDetector
from app.discovery.app_detector import AppDetector
import logging

logger = logging.getLogger(__name__)

class InfrastructureScanner:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def run_discovery(self) -> InfrastructureDiscovery:
        """
        Runs the full discovery pipeline on the repository.
        """
        logger.info(f"Starting infrastructure discovery for workspace: {self.workspace_path}")
        
        discovery = InfrastructureDiscovery()
        
        # 1. Detect Files (filter out sensitive ones)
        file_detector = FileDetector(self.workspace_path)
        all_files = file_detector.get_all_files()
        
        # 2. Infra Detection
        infra_detector = InfraDetector(all_files)
        infra_detector.detect(discovery)
        
        # 3. App Detection
        app_detector = AppDetector(all_files, file_detector.read_file_content)
        app_detector.detect(discovery)
        
        logger.info(f"Discovery complete. Found languages: {discovery.languages}, services: {[s.name for s in discovery.detected_services]}")
        return discovery
