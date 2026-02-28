import json
import os
import pickle
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import uuid


class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckpointType(Enum):
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILURE = "task_failure"
    AGENT_STATE = "agent_state"
    SYSTEM_STATE = "system_state"


@dataclass
class Checkpoint:
    checkpoint_id: str
    checkpoint_type: CheckpointType
    timestamp: str
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    state_data: Dict = field(default_factory=dict)
    context_snapshot: Dict = field(default_factory=dict)
    recovery_info: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_type": self.checkpoint_type.value,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "state_data": self.state_data,
            "context_snapshot": self.context_snapshot,
            "recovery_info": self.recovery_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Checkpoint':
        return cls(
            checkpoint_id=data["checkpoint_id"],
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            timestamp=data["timestamp"],
            task_id=data.get("task_id"),
            agent_id=data.get("agent_id"),
            state_data=data.get("state_data", {}),
            context_snapshot=data.get("context_snapshot", {}),
            recovery_info=data.get("recovery_info", {})
        )


@dataclass
class Task:
    id: str
    title: str
    description: str
    assigned_agent: str
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Dict = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    context: Dict = field(default_factory=dict)
    checkpoints: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "priority": self.priority,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "context": self.context,
            "checkpoints": self.checkpoints
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            assigned_agent=data["assigned_agent"],
            priority=data.get("priority", 5),
            status=TaskStatus(data.get("status", "pending")),
            dependencies=data.get("dependencies", []),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result", {}),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            context=data.get("context", {}),
            checkpoints=data.get("checkpoints", [])
        )


class StateManager:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.state_dir = os.path.join(work_dir, "state")
        self.checkpoint_dir = os.path.join(self.state_dir, "checkpoints")
        self.shared_memory_file = os.path.join(self.state_dir, "shared_memory.json")
        self.agent_states_dir = os.path.join(self.state_dir, "agent_states")
        self.task_states_dir = os.path.join(self.state_dir, "task_states")
        
        self._ensure_dirs()
        self._lock = threading.Lock()
        
        self.shared_memory = self._load_shared_memory()
        self.checkpoints: Dict[str, Checkpoint] = {}
        self._load_checkpoints()
    
    def _ensure_dirs(self):
        for d in [self.state_dir, self.checkpoint_dir, self.agent_states_dir, self.task_states_dir]:
            os.makedirs(d, exist_ok=True)
    
    def _load_shared_memory(self) -> Dict:
        if os.path.exists(self.shared_memory_file):
            with open(self.shared_memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "global_context": {},
            "agent_outputs": {},
            "task_history": [],
            "knowledge_base": {},
            "session_info": {
                "session_id": str(uuid.uuid4()),
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        }
    
    def _save_shared_memory(self):
        self.shared_memory["session_info"]["last_updated"] = datetime.now().isoformat()
        with open(self.shared_memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.shared_memory, f, ensure_ascii=False, indent=2)
    
    def _load_checkpoints(self):
        for filename in os.listdir(self.checkpoint_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.checkpoint_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    cp_data = json.load(f)
                    cp = Checkpoint.from_dict(cp_data)
                    self.checkpoints[cp.checkpoint_id] = cp
    
    def create_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        task_id: str = None,
        agent_id: str = None,
        state_data: Dict = None,
        context_snapshot: Dict = None,
        recovery_info: Dict = None
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            checkpoint_id=f"cp_{uuid.uuid4().hex[:8]}",
            checkpoint_type=checkpoint_type,
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            agent_id=agent_id,
            state_data=state_data or {},
            context_snapshot=context_snapshot or {},
            recovery_info=recovery_info or {}
        )
        
        self.checkpoints[checkpoint.checkpoint_id] = checkpoint
        self._save_checkpoint(checkpoint)
        
        return checkpoint
    
    def _save_checkpoint(self, checkpoint: Checkpoint):
        filepath = os.path.join(self.checkpoint_dir, f"{checkpoint.checkpoint_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self.checkpoints.get(checkpoint_id)
    
    def get_latest_checkpoint(self, task_id: str = None, agent_id: str = None) -> Optional[Checkpoint]:
        relevant_checkpoints = []
        for cp in self.checkpoints.values():
            if task_id and cp.task_id != task_id:
                continue
            if agent_id and cp.agent_id != agent_id:
                continue
            relevant_checkpoints.append(cp)
        
        if relevant_checkpoints:
            return max(relevant_checkpoints, key=lambda x: x.timestamp)
        return None
    
    def update_shared_memory(self, key: str, value: Any, agent_id: str = None):
        with self._lock:
            if agent_id:
                if "agent_outputs" not in self.shared_memory:
                    self.shared_memory["agent_outputs"] = {}
                if agent_id not in self.shared_memory["agent_outputs"]:
                    self.shared_memory["agent_outputs"][agent_id] = {}
                self.shared_memory["agent_outputs"][agent_id][key] = value
            else:
                self.shared_memory["global_context"][key] = value
            self._save_shared_memory()
    
    def get_shared_memory(self, key: str = None, agent_id: str = None) -> Any:
        if agent_id:
            agent_outputs = self.shared_memory.get("agent_outputs", {})
            agent_data = agent_outputs.get(agent_id, {})
            if key:
                return agent_data.get(key)
            return agent_data
        else:
            if key:
                return self.shared_memory["global_context"].get(key)
            return self.shared_memory["global_context"]
    
    def add_to_knowledge_base(self, key: str, value: Any):
        with self._lock:
            self.shared_memory["knowledge_base"][key] = value
            self._save_shared_memory()
    
    def get_knowledge_base(self, key: str = None) -> Any:
        if key:
            return self.shared_memory["knowledge_base"].get(key)
        return self.shared_memory["knowledge_base"]
    
    def add_task_to_history(self, task: Task):
        with self._lock:
            self.shared_memory["task_history"].append({
                "task_id": task.id,
                "title": task.title,
                "agent": task.assigned_agent,
                "status": task.status.value,
                "timestamp": datetime.now().isoformat()
            })
            if len(self.shared_memory["task_history"]) > 100:
                self.shared_memory["task_history"] = self.shared_memory["task_history"][-100:]
            self._save_shared_memory()
    
    def save_agent_state(self, agent_id: str, state: Dict):
        filepath = os.path.join(self.agent_states_dir, f"{agent_id}.json")
        state["saved_at"] = datetime.now().isoformat()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load_agent_state(self, agent_id: str) -> Optional[Dict]:
        filepath = os.path.join(self.agent_states_dir, f"{agent_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_task_state(self, task: Task):
        filepath = os.path.join(self.task_states_dir, f"{task.id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
    
    def load_task_state(self, task_id: str) -> Optional[Task]:
        filepath = os.path.join(self.task_states_dir, f"{task_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return Task.from_dict(json.load(f))
        return None
    
    def get_context_for_agent(self, agent_id: str, task: Task = None) -> Dict:
        context = {
            "global_context": dict(self.shared_memory["global_context"]),
            "knowledge_base": dict(self.shared_memory["knowledge_base"]),
            "agent_outputs": {}
        }
        
        for aid, outputs in self.shared_memory.get("agent_outputs", {}).items():
            if aid != agent_id:
                context["agent_outputs"][aid] = outputs
        
        if task:
            context["current_task"] = task.to_dict()
            context["task_context"] = task.context
            
            if task.checkpoints:
                latest_cp = self.get_latest_checkpoint(task_id=task.id)
                if latest_cp:
                    context["recovery_checkpoint"] = latest_cp.to_dict()
        
        return context
    
    def get_recovery_state(self, task_id: str = None, agent_id: str = None) -> Optional[Dict]:
        checkpoint = self.get_latest_checkpoint(task_id=task_id, agent_id=agent_id)
        if checkpoint:
            return {
                "checkpoint": checkpoint.to_dict(),
                "agent_state": self.load_agent_state(agent_id) if agent_id else None,
                "task_state": self.load_task_state(task_id).to_dict() if task_id else None
            }
        return None
    
    def cleanup_old_checkpoints(self, max_age_hours: int = 24):
        now = datetime.now()
        to_remove = []
        
        for cp_id, cp in self.checkpoints.items():
            cp_time = datetime.fromisoformat(cp.timestamp)
            age_hours = (now - cp_time).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_remove.append(cp_id)
        
        for cp_id in to_remove:
            filepath = os.path.join(self.checkpoint_dir, f"{cp_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            del self.checkpoints[cp_id]
