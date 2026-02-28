import os
import sys
import time
import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Callable
import threading
import signal

from .state_manager import StateManager, Task, TaskStatus, CheckpointType
from .scheduler import TaskScheduler, SchedulingStrategy
from .enhanced_agent import (
    EnhancedAgent, AgentState,
    ArchitectAgentV2, DeveloperAgentV2, TesterAgentV2, ReviewerAgentV2
)
from .git_manager import GitManager


class WorkflowOrchestratorV2:
    def __init__(
        self,
        work_dir: str,
        config_path: str = None,
        max_concurrent_tasks: int = 4,
        scheduling_strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY
    ):
        self.work_dir = work_dir
        self.config = self._load_config(config_path)
        
        self.state_manager = StateManager(work_dir)
        self.scheduler = TaskScheduler(
            state_manager=self.state_manager,
            strategy=scheduling_strategy,
            max_concurrent_tasks=max_concurrent_tasks
        )
        self.git_manager = GitManager(work_dir)
        
        self.agents: Dict[str, EnhancedAgent] = {}
        self._init_agents()
        
        self.iteration = 0
        self.running = False
        self._shutdown_event = threading.Event()
        
        self.log_file = os.path.join(work_dir, "logs", "orchestrator_v2.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        self._setup_signal_handlers()
    
    def _load_config(self, config_path: str) -> dict:
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {
            "workflow": {"max_iterations": 100, "auto_commit": True},
            "git": {"branch": "main"}
        }
    
    def _init_agents(self):
        self.agents = {
            "architect": ArchitectAgentV2(self.state_manager, self.work_dir),
            "developer": DeveloperAgentV2(self.state_manager, self.work_dir),
            "tester": TesterAgentV2(self.state_manager, self.work_dir),
            "reviewer": ReviewerAgentV2(self.state_manager, self.work_dir)
        }
    
    def _setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.log("收到停止信号，正在优雅关闭...")
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [OrchestratorV2] {message}\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(log_entry.strip())
    
    def add_task(
        self,
        title: str,
        description: str,
        agent_type: str,
        priority: int = 5,
        dependencies: List[str] = None
    ) -> Task:
        task = Task(
            id=f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}",
            title=title,
            description=description,
            assigned_agent=agent_type,
            priority=priority,
            dependencies=dependencies or []
        )
        
        self.scheduler.add_task(task)
        self.log(f"添加任务: {task.id} - {title}")
        
        return task
    
    def add_tasks_from_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for task_data in data.get("pending", []):
            task = Task.from_dict(task_data)
            self.scheduler.add_task(task)
        
        self.log(f"从文件加载任务: {filepath}")
    
    def get_agent_for_task(self, task: Task) -> Optional[EnhancedAgent]:
        agent_type = task.assigned_agent
        agent = self.agents.get(agent_type)
        
        if agent and agent.context.state in [AgentState.IDLE, AgentState.ERROR]:
            if agent.context.state == AgentState.ERROR:
                if not agent.recover():
                    return None
            return agent
        
        return None
    
    def process_task(self, task: Task) -> bool:
        agent = self.get_agent_for_task(task)
        if not agent:
            self.log(f"没有可用的智能体处理任务: {task.id}", "WARNING")
            return False
        
        def execute():
            try:
                agent.accept_task(task)
                result = agent.execute_task(task)
                
                if result.get("success"):
                    self.scheduler.complete_task(task.id, result)
                    
                    if self.config.get("workflow", {}).get("auto_commit", True):
                        commit_msg = f"Complete: {task.title} by {agent.agent_type}"
                        self.git_manager.auto_commit(commit_msg, "[AI-Agent-V2]")
                else:
                    self.scheduler.fail_task(task.id, result.get("error", "Unknown error"))
                    
            except Exception as e:
                self.log(f"任务执行异常: {task.id} - {str(e)}", "ERROR")
                self.scheduler.fail_task(task.id, str(e))
        
        return self.scheduler.start_task(task, execute)
    
    def run_iteration(self) -> bool:
        self.iteration += 1
        self.log(f"========== 迭代 #{self.iteration} ==========")
        
        status = self.scheduler.get_status()
        self.log(f"调度状态: 队列={status['queued']}, 运行中={status['running']}, 完成={status['completed']}")
        
        self._save_system_checkpoint()
        
        task = self.scheduler.get_next_task()
        if task:
            return self.process_task(task)
        
        return False
    
    def _save_system_checkpoint(self):
        self.state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.SYSTEM_STATE,
            state_data={
                "iteration": self.iteration,
                "scheduler_status": self.scheduler.get_status(),
                "agents_status": {aid: a.get_status() for aid, a in self.agents.items()}
            }
        )
    
    def run_continuous(
        self,
        interval: float = 1.0,
        max_iterations: int = None,
        on_complete: Callable = None
    ):
        max_iter = max_iterations or self.config.get("workflow", {}).get("max_iterations", 100)
        
        self.log(f"启动持续工作流，最大迭代次数: {max_iter}")
        self.running = True
        
        if not self.git_manager.is_git_repo():
            self.git_manager.init_repo()
            self.log("初始化Git仓库")
        
        while self.running and self.iteration < max_iter:
            if self._shutdown_event.is_set():
                break
            
            has_work = self.run_iteration()
            
            if not has_work:
                status = self.scheduler.get_status()
                if status['queued'] == 0 and status['running'] == 0:
                    self.log("所有任务已完成")
                    if on_complete:
                        on_complete()
                    break
            
            time.sleep(interval)
        
        self.running = False
        self.log(f"工作流结束，迭代次数: {self.iteration}")
        
        return self.scheduler.get_status()
    
    def run_parallel(
        self,
        interval: float = 1.0,
        max_iterations: int = None
    ):
        max_iter = max_iterations or self.config.get("workflow", {}).get("max_iterations", 100)
        
        self.log(f"启动并行工作流，最大并发: {self.scheduler.max_concurrent_tasks}")
        self.running = True
        
        if not self.git_manager.is_git_repo():
            self.git_manager.init_repo()
        
        while self.running and self.iteration < max_iter:
            if self._shutdown_event.is_set():
                break
            
            self.iteration += 1
            
            status = self.scheduler.get_status()
            self.log(f"迭代 #{self.iteration}: 队列={status['queued']}, 运行中={status['running']}")
            
            while status['running'] < self.scheduler.max_concurrent_tasks:
                task = self.scheduler.get_next_task()
                if not task:
                    break
                self.process_task(task)
                status = self.scheduler.get_status()
            
            self._save_system_checkpoint()
            
            if status['queued'] == 0 and status['running'] == 0:
                self.log("所有任务已完成")
                break
            
            time.sleep(interval)
        
        self.running = False
        return self.scheduler.get_status()
    
    def shutdown(self):
        self.log("正在关闭工作流...")
        self.running = False
        self._shutdown_event.set()
        
        self.scheduler.shutdown(wait=False)
        
        self._save_system_checkpoint()
        self.log("工作流已关闭")
    
    def get_status_report(self) -> dict:
        return {
            "iteration": self.iteration,
            "running": self.running,
            "scheduler": self.scheduler.get_status(),
            "agents": {aid: a.get_status() for aid, a in self.agents.items()},
            "shared_memory_keys": list(self.state_manager.shared_memory.get("global_context", {}).keys()),
            "knowledge_base_keys": list(self.state_manager.shared_memory.get("knowledge_base", {}).keys()),
            "git_branch": self.git_manager.get_current_branch(),
            "last_commit": self.git_manager.get_log(1)
        }
    
    def recover_from_checkpoint(self, checkpoint_id: str = None):
        if checkpoint_id:
            checkpoint = self.state_manager.get_checkpoint(checkpoint_id)
        else:
            checkpoint = self.state_manager.get_latest_checkpoint()
        
        if not checkpoint:
            self.log("没有找到恢复点", "WARNING")
            return False
        
        self.log(f"从检查点恢复: {checkpoint.checkpoint_id}")
        
        if checkpoint.checkpoint_type == CheckpointType.SYSTEM_STATE:
            state_data = checkpoint.state_data
            self.iteration = state_data.get("iteration", 0)
            self.log(f"恢复到迭代 #{self.iteration}")
        
        return True


def main():
    work_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(work_dir, "config", "settings.yaml")
    tasks_file = os.path.join(work_dir, "tasks", "queue.json")
    
    print("=" * 70)
    print("  无限AI工作流系统 V2 - 文字生成像素图片模型")
    print("  基于 Long-Running Agents 调度编排框架")
    print("=" * 70)
    
    orchestrator = WorkflowOrchestratorV2(
        work_dir=work_dir,
        config_path=config_path,
        max_concurrent_tasks=4,
        scheduling_strategy=SchedulingStrategy.PRIORITY
    )
    
    if os.path.exists(tasks_file):
        orchestrator.add_tasks_from_file(tasks_file)
    
    print(f"工作目录: {work_dir}")
    print(f"配置文件: {config_path}")
    print("-" * 70)
    
    try:
        status = orchestrator.run_parallel(interval=1.0)
        
        print("-" * 70)
        print("工作流执行完成!")
        print(f"最终状态: {json.dumps(status, ensure_ascii=False, indent=2)}")
        
    except KeyboardInterrupt:
        print("\n用户中断，正在优雅关闭...")
        orchestrator.shutdown()


if __name__ == "__main__":
    main()
