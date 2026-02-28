import os
import sys
import time
import json
import signal
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORK_DIR)

from workflow import (
    WorkflowOrchestratorV2,
    SchedulingStrategy,
    TaskStatus
)


class InfiniteWorkflowRunner:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.orchestrator = None
        self.running = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        def handler(signum, frame):
            print("\n收到停止信号，正在优雅关闭...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    
    def start(self, parallel: bool = True, interval: float = 1.0):
        print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║           无限AI工作流系统 V2 - Long-Running Agents               ║
    ╠════════════════════════════════════════════════════════════════════╣
    ║  核心特性:                                                         ║
    ║  ✓ 状态管理和检查点恢复                                            ║
    ║  ✓ 共享记忆系统 (Shared Memory)                                    ║
    ║  ✓ 智能体自动恢复机制                                              ║
    ║  ✓ 精准上下文管理 (Context Engineering)                            ║
    ║  ✓ 并行执行和优先级调度                                            ║
    ║  ✓ 任务依赖管理                                                    ║
    ╚════════════════════════════════════════════════════════════════════╝
        """)
        
        config_path = os.path.join(self.work_dir, "config", "settings.yaml")
        tasks_file = os.path.join(self.work_dir, "tasks", "queue.json")
        
        self.orchestrator = WorkflowOrchestratorV2(
            work_dir=self.work_dir,
            config_path=config_path,
            max_concurrent_tasks=4,
            scheduling_strategy=SchedulingStrategy.PRIORITY
        )
        
        if os.path.exists(tasks_file):
            self.orchestrator.add_tasks_from_file(tasks_file)
        
        print(f"工作目录: {self.work_dir}")
        print(f"调度策略: PRIORITY")
        print(f"最大并发: 4")
        print("-" * 70)
        
        self.running = True
        
        while self.running:
            try:
                if parallel:
                    status = self.orchestrator.run_parallel(interval=interval, max_iterations=1000)
                else:
                    status = self.orchestrator.run_continuous(interval=interval, max_iterations=1000)
                
                if status['queued'] == 0 and status['running'] == 0:
                    print("\n所有任务已完成，等待新任务...")
                    time.sleep(5)
                    self.orchestrator.iteration = 0
                    self.orchestrator.add_tasks_from_file(tasks_file)
                else:
                    break
                    
            except Exception as e:
                print(f"工作流异常: {e}")
                time.sleep(5)
    
    def stop(self):
        self.running = False
        if self.orchestrator:
            self.orchestrator.shutdown()
    
    def add_task(self, title: str, description: str, agent_type: str, priority: int = 5):
        if self.orchestrator:
            return self.orchestrator.add_task(title, description, agent_type, priority)
        return None
    
    def get_status(self) -> dict:
        if self.orchestrator:
            return self.orchestrator.get_status_report()
        return {}


def main():
    runner = InfiniteWorkflowRunner(WORK_DIR)
    runner.start(parallel=True, interval=1.0)


if __name__ == "__main__":
    main()
