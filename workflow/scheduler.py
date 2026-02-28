import heapq
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import concurrent.futures
import time

from .state_manager import StateManager, Task, TaskStatus, CheckpointType


class SchedulingStrategy(Enum):
    FIFO = "fifo"
    PRIORITY = "priority"
    SHORTEST_JOB_FIRST = "shortest_job_first"
    ROUND_ROBIN = "round_robin"
    DEPENDENCY_AWARE = "dependency_aware"


@dataclass
class ScheduledTask:
    task: Task
    priority_score: float = 0.0
    ready_time: float = field(default_factory=time.time)
    
    def __lt__(self, other):
        if self.priority_score != other.priority_score:
            return self.priority_score > other.priority_score
        return self.ready_time < other.ready_time


class TaskScheduler:
    def __init__(
        self,
        state_manager: StateManager,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY,
        max_concurrent_tasks: int = 4
    ):
        self.state_manager = state_manager
        self.strategy = strategy
        self.max_concurrent_tasks = max_concurrent_tasks
        
        self.task_queue: List[ScheduledTask] = []
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        
        self._lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks)
        self._futures: Dict[str, concurrent.futures.Future] = {}
        
        self.task_callbacks: Dict[str, Callable] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
    
    def add_task(self, task: Task) -> bool:
        with self._lock:
            for dep_id in task.dependencies:
                if dep_id not in self.dependency_graph:
                    self.dependency_graph[dep_id] = []
                self.dependency_graph[dep_id].append(task.id)
            
            priority_score = self._calculate_priority_score(task)
            
            scheduled_task = ScheduledTask(
                task=task,
                priority_score=priority_score
            )
            
            heapq.heappush(self.task_queue, scheduled_task)
            task.status = TaskStatus.QUEUED
            self.state_manager.save_task_state(task)
            
            return True
    
    def _calculate_priority_score(self, task: Task) -> float:
        base_score = 10 - task.priority
        
        if self.strategy == SchedulingStrategy.PRIORITY:
            return base_score
        
        elif self.strategy == SchedulingStrategy.FIFO:
            return -time.time()
        
        elif self.strategy == SchedulingStrategy.SHORTEST_JOB_FIRST:
            estimated_time = len(task.description.split()) * 0.1
            return -estimated_time
        
        elif self.strategy == SchedulingStrategy.DEPENDENCY_AWARE:
            dep_count = len(task.dependencies)
            return base_score - (dep_count * 0.5)
        
        return base_score
    
    def _check_dependencies(self, task: Task) -> bool:
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                dep_task = self.state_manager.load_task_state(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    return False
        return True
    
    def get_next_task(self) -> Optional[Task]:
        with self._lock:
            while self.task_queue:
                scheduled_task = heapq.heappop(self.task_queue)
                task = scheduled_task.task
                
                if not self._check_dependencies(task):
                    scheduled_task.ready_time = time.time() + 5
                    heapq.heappush(self.task_queue, scheduled_task)
                    continue
                
                if task.id in self.running_tasks:
                    continue
                
                return task
            
            return None
    
    def start_task(self, task: Task, executor: Callable) -> bool:
        with self._lock:
            if len(self.running_tasks) >= self.max_concurrent_tasks:
                return False
            
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()
            self.running_tasks[task.id] = task
            
            self.state_manager.create_checkpoint(
                checkpoint_type=CheckpointType.TASK_START,
                task_id=task.id,
                agent_id=task.assigned_agent,
                state_data={"status": "started"}
            )
            
            self.state_manager.save_task_state(task)
            
            future = self._executor.submit(executor, task)
            self._futures[task.id] = future
            
            return True
    
    def complete_task(self, task_id: str, result: Dict = None):
        with self._lock:
            if task_id in self.running_tasks:
                task = self.running_tasks.pop(task_id)
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now().isoformat()
                if result:
                    task.result = result
                
                self.completed_tasks[task_id] = task
                self.state_manager.add_task_to_history(task)
                
                self.state_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.TASK_COMPLETE,
                    task_id=task.id,
                    agent_id=task.assigned_agent,
                    state_data={"result": result}
                )
                
                self.state_manager.save_task_state(task)
                
                self._notify_dependent_tasks(task_id)
    
    def fail_task(self, task_id: str, error: str):
        with self._lock:
            if task_id in self.running_tasks:
                task = self.running_tasks.pop(task_id)
                task.error = error
                task.retry_count += 1
                
                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.PENDING
                    self.add_task(task)
                else:
                    task.status = TaskStatus.FAILED
                    self.failed_tasks[task_id] = task
                
                self.state_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.TASK_FAILURE,
                    task_id=task.id,
                    agent_id=task.assigned_agent,
                    state_data={"error": error, "retry_count": task.retry_count}
                )
                
                self.state_manager.save_task_state(task)
    
    def _notify_dependent_tasks(self, completed_task_id: str):
        if completed_task_id in self.dependency_graph:
            for dependent_id in self.dependency_graph[completed_task_id]:
                pass
    
    def pause_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.PAUSED
                
                self.state_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.AGENT_STATE,
                    task_id=task.id,
                    agent_id=task.assigned_agent,
                    state_data={"status": "paused"}
                )
                
                self.state_manager.save_task_state(task)
                return True
            return False
    
    def resume_task(self, task_id: str) -> bool:
        task = self.state_manager.load_task_state(task_id)
        if task and task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.PENDING
            self.add_task(task)
            return True
        return False
    
    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._futures:
                self._futures[task_id].cancel()
            
            if task_id in self.running_tasks:
                task = self.running_tasks.pop(task_id)
                task.status = TaskStatus.CANCELLED
                self.state_manager.save_task_state(task)
                return True
            
            return False
    
    def get_status(self) -> Dict:
        with self._lock:
            return {
                "queued": len(self.task_queue),
                "running": len(self.running_tasks),
                "completed": len(self.completed_tasks),
                "failed": len(self.failed_tasks),
                "max_concurrent": self.max_concurrent_tasks,
                "strategy": self.strategy.value
            }
    
    def get_running_tasks(self) -> List[Task]:
        with self._lock:
            return list(self.running_tasks.values())
    
    def get_completed_tasks(self) -> List[Task]:
        with self._lock:
            return list(self.completed_tasks.values())
    
    def has_pending_tasks(self) -> bool:
        with self._lock:
            return len(self.task_queue) > 0
    
    def has_running_tasks(self) -> bool:
        with self._lock:
            return len(self.running_tasks) > 0
    
    def rebalance_priorities(self):
        with self._lock:
            new_queue = []
            while self.task_queue:
                scheduled_task = heapq.heappop(self.task_queue)
                scheduled_task.priority_score = self._calculate_priority_score(scheduled_task.task)
                new_queue.append(scheduled_task)
            
            self.task_queue = []
            for st in new_queue:
                heapq.heappush(self.task_queue, st)
    
    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)
