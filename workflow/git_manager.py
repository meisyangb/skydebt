import subprocess
import os
from datetime import datetime
from typing import Optional, List


class GitManager:
    def __init__(self, repo_path: str, branch: str = "main"):
        self.repo_path = repo_path
        self.branch = branch
    
    def _run_git_command(self, args: List[str]) -> tuple:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def is_git_repo(self) -> bool:
        success, _, _ = self._run_git_command(["rev-parse", "--git-dir"])
        return success
    
    def init_repo(self) -> bool:
        if self.is_git_repo():
            return True
        success, _, _ = self._run_git_command(["init"])
        return success
    
    def get_status(self) -> str:
        success, stdout, _ = self._run_git_command(["status", "--short"])
        return stdout if success else ""
    
    def has_changes(self) -> bool:
        status = self.get_status()
        return len(status.strip()) > 0
    
    def add_all(self) -> bool:
        success, _, stderr = self._run_git_command(["add", "."])
        return success
    
    def commit(self, message: str, prefix: str = "[AI-Agent]") -> bool:
        full_message = f"{prefix} {message} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        success, _, stderr = self._run_git_command(["commit", "-m", full_message])
        return success
    
    def auto_commit(self, message: str, prefix: str = "[AI-Agent]") -> bool:
        if not self.has_changes():
            return False
        if not self.add_all():
            return False
        return self.commit(message, prefix)
    
    def get_log(self, count: int = 5) -> str:
        success, stdout, _ = self._run_git_command(["log", f"-{count}", "--oneline"])
        return stdout if success else ""
    
    def create_branch(self, branch_name: str) -> bool:
        success, _, _ = self._run_git_command(["checkout", "-b", branch_name])
        return success
    
    def switch_branch(self, branch_name: str) -> bool:
        success, _, _ = self._run_git_command(["checkout", branch_name])
        return success
    
    def get_current_branch(self) -> str:
        success, stdout, _ = self._run_git_command(["branch", "--show-current"])
        return stdout.strip() if success else ""
