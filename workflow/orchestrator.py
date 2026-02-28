import os
import sys
import time
import json
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_manager import TaskManager
from git_manager import GitManager
from agent_base import ArchitectAgent, DeveloperAgent, TesterAgent, ReviewerAgent


class WorkflowOrchestrator:
    def __init__(self, work_dir: str, config_path: str = None):
        self.work_dir = work_dir
        self.config = self._load_config(config_path)
        self.task_manager = TaskManager(
            os.path.join(work_dir, "tasks", "queue.json"),
            os.path.join(work_dir, "tasks", "completed.json")
        )
        self.git_manager = GitManager(work_dir)
        self.agents = self._init_agents()
        self.iteration = 0
        self.log_file = os.path.join(work_dir, "logs", "workflow.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _load_config(self, config_path: str) -> dict:
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {
            "workflow": {"max_iterations": 100, "auto_commit": True},
            "git": {"branch": "main"}
        }
    
    def _init_agents(self) -> dict:
        return {
            "architect": ArchitectAgent(self.work_dir),
            "developer": DeveloperAgent(self.work_dir),
            "tester": TesterAgent(self.work_dir),
            "reviewer": ReviewerAgent(self.work_dir)
        }
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [Orchestrator] {message}\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(log_entry.strip())
    
    def get_agent_for_task(self, task: dict):
        agent_type = task.get("assigned_agent", "developer")
        return self.agents.get(agent_type)
    
    def process_single_task(self) -> bool:
        task = self.task_manager.get_any_pending_task()
        if not task:
            self.log("没有待处理的任务")
            return False
        
        agent = self.get_agent_for_task(task)
        if not agent:
            self.log(f"找不到任务 {task.get('id')} 对应的智能体: {task.get('assigned_agent')}")
            return False
        
        self.log(f"分配任务 [{task.get('id')}] {task.get('title')} 给 {agent.name}")
        
        agent.accept_task(task)
        result = agent.execute_task()
        
        if result.get("success", False):
            self.task_manager.complete_task(task.get("id"), result)
            self.log(f"任务 [{task.get('id')}] 完成")
            
            if self.config.get("workflow", {}).get("auto_commit", True):
                commit_msg = f"完成任务: {task.get('title')} by {agent.name}"
                self.git_manager.auto_commit(commit_msg, "[AI-Agent]")
                self.log(f"已提交代码: {commit_msg}")
        else:
            self.log(f"任务 [{task.get('id')}] 执行失败: {result.get('error', 'Unknown error')}", "ERROR")
        
        return True
    
    def run_iteration(self) -> bool:
        self.iteration += 1
        self.log(f"========== 迭代 #{self.iteration} ==========")
        
        status = self.task_manager.get_status()
        self.log(f"任务状态: 待处理={status['pending']}, 进行中={status['in_progress']}, 已完成={status['completed']}")
        
        return self.process_single_task()
    
    def run_continuous(self, interval: float = 1.0, max_iterations: int = None):
        max_iter = max_iterations or self.config.get("workflow", {}).get("max_iterations", 100)
        
        self.log(f"启动持续工作流，最大迭代次数: {max_iter}")
        
        if not self.git_manager.is_git_repo():
            self.git_manager.init_repo()
            self.log("初始化Git仓库")
        
        while self.iteration < max_iter:
            has_work = self.run_iteration()
            
            if not has_work:
                status = self.task_manager.get_status()
                if status['pending'] == 0 and status['in_progress'] == 0:
                    self.log("所有任务已完成，工作流结束")
                    break
            
            time.sleep(interval)
        
        self.log(f"工作流结束，共完成 {self.task_manager.completed_data.get('total_completed', 0)} 个任务")
        return self.task_manager.get_status()
    
    def add_new_task(self, title: str, description: str, agent_type: str, priority: int = 5):
        task = self.task_manager.add_task(title, description, agent_type, priority)
        self.log(f"添加新任务: {task.get('id')} - {title}")
        return task
    
    def get_status_report(self) -> dict:
        return {
            "iteration": self.iteration,
            "task_status": self.task_manager.get_status(),
            "git_status": self.git_manager.get_status(),
            "git_branch": self.git_manager.get_current_branch(),
            "last_commit": self.git_manager.get_log(1)
        }


def main():
    work_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(work_dir, "config", "settings.yaml")
    
    orchestrator = WorkflowOrchestrator(work_dir, config_path)
    
    print("=" * 60)
    print("  无限AI工作流系统 - 文字生成像素图片模型")
    print("=" * 60)
    print(f"工作目录: {work_dir}")
    print(f"配置文件: {config_path}")
    print("-" * 60)
    
    status = orchestrator.run_continuous(interval=0.5)
    
    print("-" * 60)
    print("工作流执行完成!")
    print(f"最终状态: {json.dumps(status, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
