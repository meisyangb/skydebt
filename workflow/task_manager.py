import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import uuid


class TaskManager:
    def __init__(self, queue_file: str, completed_file: str):
        self.queue_file = queue_file
        self.completed_file = completed_file
        self.queue_data = self._load_queue()
        self.completed_data = self._load_completed()
    
    def _load_queue(self) -> Dict:
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"pending": [], "in_progress": [], "completed": []}
    
    def _load_completed(self) -> Dict:
        if os.path.exists(self.completed_file):
            with open(self.completed_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"tasks": [], "total_completed": 0}
    
    def _save_queue(self):
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(self.queue_data, f, ensure_ascii=False, indent=2)
    
    def _save_completed(self):
        os.makedirs(os.path.dirname(self.completed_file), exist_ok=True)
        with open(self.completed_file, 'w', encoding='utf-8') as f:
            json.dump(self.completed_data, f, ensure_ascii=False, indent=2)
    
    def get_next_task(self, agent_type: str) -> Optional[Dict]:
        pending = self.queue_data.get("pending", [])
        for i, task in enumerate(pending):
            if task.get("assigned_agent") == agent_type and task.get("status") == "pending":
                task["status"] = "in_progress"
                task["started_at"] = datetime.now().isoformat()
                self.queue_data["in_progress"].append(task)
                self.queue_data["pending"].pop(i)
                self._save_queue()
                return task
        return None
    
    def get_any_pending_task(self) -> Optional[Dict]:
        pending = self.queue_data.get("pending", [])
        if pending:
            task = pending.pop(0)
            task["status"] = "in_progress"
            task["started_at"] = datetime.now().isoformat()
            self.queue_data["in_progress"].append(task)
            self._save_queue()
            return task
        return None
    
    def complete_task(self, task_id: str, result: Dict = None):
        in_progress = self.queue_data.get("in_progress", [])
        for i, task in enumerate(in_progress):
            if task.get("id") == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                if result:
                    task["result"] = result
                self.queue_data["completed"].append(task)
                self.queue_data["in_progress"].pop(i)
                self.completed_data["tasks"].append(task)
                self.completed_data["total_completed"] += 1
                self._save_queue()
                self._save_completed()
                return True
        return False
    
    def add_task(self, title: str, description: str, assigned_agent: str, priority: int = 5) -> Dict:
        task = {
            "id": f"task_{uuid.uuid4().hex[:8]}",
            "title": title,
            "description": description,
            "assigned_agent": assigned_agent,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        self.queue_data["pending"].append(task)
        self._save_queue()
        return task
    
    def get_status(self) -> Dict:
        return {
            "pending": len(self.queue_data.get("pending", [])),
            "in_progress": len(self.queue_data.get("in_progress", [])),
            "completed": len(self.queue_data.get("completed", [])),
            "total_completed": self.completed_data.get("total_completed", 0)
        }
    
    def has_pending_tasks(self) -> bool:
        return len(self.queue_data.get("pending", [])) > 0
    
    def has_in_progress_tasks(self) -> bool:
        return len(self.queue_data.get("in_progress", [])) > 0
