import os
import glob
from typing import List, Set

# Files we should NEVER read or expose
SENSITIVE_FILES = {
    '.env', '.env.local', '.env.development', '.env.test', '.env.production',
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
    'secret.yaml', 'secrets.yaml',
    'credentials.json',
}

# Directories we should ignore
IGNORE_DIRS = {
    '.git', 'node_modules', 'venv', '.venv', 'env', '__pycache__',
    'dist', 'build', 'out', 'target', '.next', '.nuxt',
    'coverage', '.nyc_output'
}

class FileDetector:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def get_all_files(self) -> List[str]:
        """
        Walks the workspace directory and returns a list of relative file paths.
        Skips sensitive files and ignored directories.
        """
        all_files = []
        for root, dirs, files in os.walk(self.workspace_path):
            # Modify dirs in-place to skip IGNORE_DIRS
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.terraform')]

            for file in files:
                if self.is_sensitive_file(file):
                    continue
                
                # Get path relative to workspace_path
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.workspace_path)
                all_files.append(rel_path)
                
        return all_files

    def is_sensitive_file(self, filename: str) -> bool:
        """
        Checks if a file is sensitive (e.g. .env, private keys).
        """
        if filename in SENSITIVE_FILES:
            return True
        if filename.endswith('.key') or filename.endswith('.pem'):
            return True
        if 'secret' in filename.lower() and (filename.endswith('.json') or filename.endswith('.yaml') or filename.endswith('.yml')):
            return True
        return False

    def read_file_content(self, rel_path: str) -> str:
        """
        Reads the content of a file safely. Returns empty string if sensitive or unreadable.
        """
        filename = os.path.basename(rel_path)
        if self.is_sensitive_file(filename):
            return ""

        full_path = os.path.join(self.workspace_path, rel_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""
