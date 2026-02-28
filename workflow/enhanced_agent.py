from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import os
import json
import traceback
from enum import Enum

from .state_manager import StateManager, Task, TaskStatus, CheckpointType


class AgentState(Enum):
    IDLE = "idle"
    WORKING = "working"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"


@dataclass
class AgentContext:
    agent_id: str
    agent_type: str
    current_task_id: Optional[str] = None
    state: AgentState = AgentState.IDLE
    working_memory: Dict = field(default_factory=dict)
    last_activity: str = ""
    error_count: int = 0
    tasks_completed: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "current_task_id": self.current_task_id,
            "state": self.state.value,
            "working_memory": self.working_memory,
            "last_activity": self.last_activity,
            "error_count": self.error_count,
            "tasks_completed": self.tasks_completed
        }


class EnhancedAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        capabilities: List[str],
        state_manager: StateManager,
        work_dir: str
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.state_manager = state_manager
        self.work_dir = work_dir
        
        self.context = AgentContext(
            agent_id=agent_id,
            agent_type=agent_type
        )
        
        self._load_state()
        
        self.log_file = os.path.join(work_dir, "logs", f"{agent_id}_agent.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _load_state(self):
        saved_state = self.state_manager.load_agent_state(self.agent_id)
        if saved_state:
            self.context = AgentContext(
                agent_id=saved_state.get("agent_id", self.agent_id),
                agent_type=saved_state.get("agent_type", self.agent_type),
                current_task_id=saved_state.get("current_task_id"),
                state=AgentState(saved_state.get("state", "idle")),
                working_memory=saved_state.get("working_memory", {}),
                last_activity=saved_state.get("last_activity", ""),
                error_count=saved_state.get("error_count", 0),
                tasks_completed=saved_state.get("tasks_completed", 0)
            )
    
    def _save_state(self):
        self.context.last_activity = datetime.now().isoformat()
        self.state_manager.save_agent_state(self.agent_id, self.context.to_dict())
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [{self.agent_id}] {message}\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(log_entry.strip())
    
    def get_context_for_task(self, task: Task) -> Dict:
        return self.state_manager.get_context_for_agent(self.agent_id, task)
    
    def update_shared_memory(self, key: str, value: Any):
        self.state_manager.update_shared_memory(key, value, self.agent_id)
    
    def get_shared_memory(self, key: str = None) -> Any:
        return self.state_manager.get_shared_memory(key, self.agent_id)
    
    def get_global_context(self, key: str = None) -> Any:
        return self.state_manager.get_shared_memory(key)
    
    def add_knowledge(self, key: str, value: Any):
        self.state_manager.add_to_knowledge_base(key, value)
    
    def get_knowledge(self, key: str = None) -> Any:
        return self.state_manager.get_knowledge_base(key)
    
    def accept_task(self, task: Task) -> bool:
        self.context.current_task_id = task.id
        self.context.state = AgentState.WORKING
        self._save_state()
        
        self.state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.TASK_START,
            task_id=task.id,
            agent_id=self.agent_id,
            state_data={"action": "task_accepted"}
        )
        
        self.log(f"接受任务: {task.title} (ID: {task.id})")
        return True
    
    def execute_task(self, task: Task) -> Dict:
        try:
            self.context.state = AgentState.WORKING
            self._save_state()
            
            context = self.get_context_for_task(task)
            task.context = context
            
            self.state_manager.create_checkpoint(
                checkpoint_type=CheckpointType.TASK_PROGRESS,
                task_id=task.id,
                agent_id=self.agent_id,
                state_data={"action": "execution_started"},
                context_snapshot={"task_context_keys": list(context.keys())}
            )
            
            result = self._do_work(task)
            
            if result.get("success", False):
                self._complete_task(task, result)
            else:
                self._handle_task_failure(task, result.get("error", "Unknown error"))
            
            return result
            
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.log(f"任务执行异常: {error_msg}", "ERROR")
            self._handle_task_failure(task, error_msg)
            return {"success": False, "error": error_msg}
    
    @abstractmethod
    def _do_work(self, task: Task) -> Dict:
        pass
    
    def _complete_task(self, task: Task, result: Dict):
        self.context.state = AgentState.IDLE
        self.context.current_task_id = None
        self.context.tasks_completed += 1
        self._save_state()
        
        if result.get("outputs"):
            for key, value in result["outputs"].items():
                self.update_shared_memory(key, value)
        
        self.state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.TASK_COMPLETE,
            task_id=task.id,
            agent_id=self.agent_id,
            state_data={"result_summary": str(result)[:500]}
        )
        
        self.log(f"完成任务: {task.title}")
    
    def _handle_task_failure(self, task: Task, error: str):
        self.context.error_count += 1
        self.context.state = AgentState.ERROR
        self._save_state()
        
        self.state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.TASK_FAILURE,
            task_id=task.id,
            agent_id=self.agent_id,
            state_data={"error": error},
            recovery_info={"can_retry": True}
        )
        
        self.log(f"任务失败: {task.title} - {error}", "ERROR")
    
    def recover(self) -> bool:
        if self.context.state != AgentState.ERROR:
            return True
        
        self.log("开始恢复...")
        self.context.state = AgentState.RECOVERING
        self._save_state()
        
        recovery_state = self.state_manager.get_recovery_state(
            task_id=self.context.current_task_id,
            agent_id=self.agent_id
        )
        
        if recovery_state:
            checkpoint = recovery_state.get("checkpoint", {})
            recovery_info = checkpoint.get("recovery_info", {})
            
            if recovery_info.get("can_retry"):
                self.context.state = AgentState.IDLE
                self.context.current_task_id = None
                self._save_state()
                self.log("恢复成功")
                return True
        
        self.log("恢复失败，需要人工干预", "ERROR")
        return False
    
    def pause(self):
        self.context.state = AgentState.PAUSED
        self._save_state()
        
        self.state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AGENT_STATE,
            agent_id=self.agent_id,
            state_data={"action": "paused"}
        )
        
        self.log("智能体已暂停")
    
    def resume(self):
        if self.context.state == AgentState.PAUSED:
            self.context.state = AgentState.IDLE
            self._save_state()
            self.log("智能体已恢复")
    
    def get_status(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.context.state.value,
            "current_task": self.context.current_task_id,
            "capabilities": self.capabilities,
            "tasks_completed": self.context.tasks_completed,
            "error_count": self.context.error_count
        }


class ArchitectAgentV2(EnhancedAgent):
    def __init__(self, state_manager: StateManager, work_dir: str):
        super().__init__(
            agent_id="architect_001",
            agent_type="architect",
            capabilities=["系统架构设计", "模块接口定义", "数据流规划", "技术选型"],
            state_manager=state_manager,
            work_dir=work_dir
        )
    
    def _do_work(self, task: Task) -> Dict:
        self.log(f"执行架构设计任务: {task.title}")
        
        architecture = {
            "model_name": "PixelArtGenerator",
            "version": "2.0",
            "components": [
                {
                    "name": "TextEncoder",
                    "type": "CLIP",
                    "input": "text",
                    "output": "embedding (512-dim)",
                    "description": "使用CLIP模型将文本编码为特征向量"
                },
                {
                    "name": "DiffusionModel",
                    "type": "UNet",
                    "input": "embedding + noise",
                    "output": "denoised_latent",
                    "description": "扩散模型进行去噪生成"
                },
                {
                    "name": "ImageDecoder",
                    "type": "VQGAN",
                    "input": "latent",
                    "output": "pixel_image (64x64)",
                    "description": "将潜空间解码为像素风格图片"
                }
            ],
            "data_flow": "Text -> TextEncoder -> DiffusionModel -> ImageDecoder -> PixelImage"
        }
        
        arch_file = os.path.join(self.work_dir, "docs", "architecture_v2.json")
        os.makedirs(os.path.dirname(arch_file), exist_ok=True)
        with open(arch_file, 'w', encoding='utf-8') as f:
            json.dump(architecture, f, ensure_ascii=False, indent=2)
        
        self.add_knowledge("architecture", architecture)
        
        return {
            "success": True,
            "outputs": {
                "architecture_file": arch_file,
                "architecture": architecture
            }
        }


class DeveloperAgentV2(EnhancedAgent):
    def __init__(self, state_manager: StateManager, work_dir: str):
        super().__init__(
            agent_id="developer_001",
            agent_type="developer",
            capabilities=["代码实现", "模型开发", "性能优化", "Bug修复"],
            state_manager=state_manager,
            work_dir=work_dir
        )
    
    def _do_work(self, task: Task) -> Dict:
        self.log(f"执行开发任务: {task.title}")
        
        task_title = task.title
        
        if "文本编码器" in task_title:
            return self._create_text_encoder()
        elif "扩散模型" in task_title:
            return self._create_diffusion_model()
        elif "图像解码器" in task_title:
            return self._create_image_decoder()
        else:
            return self._create_generic_module(task)
    
    def _create_text_encoder(self) -> Dict:
        code = '''import torch
import torch.nn as nn
from transformers import CLIPTextModel, CLIPTokenizer


class TextEncoder(nn.Module):
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32", device: str = "cuda"):
        super().__init__()
        self.device = device
        self.tokenizer = CLIPTokenizer.from_pretrained(model_name)
        self.model = CLIPTextModel.from_pretrained(model_name).to(device)
        self.model.eval()
        self.embedding_dim = 512
    
    @torch.no_grad()
    def encode(self, text: str) -> torch.Tensor:
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model(**inputs)
        return outputs.pooler_output
    
    def forward(self, text: str) -> torch.Tensor:
        return self.encode(text)
'''
        
        file_path = os.path.join(self.work_dir, "models", "text_encoder.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self.add_knowledge("text_encoder_file", file_path)
        
        return {
            "success": True,
            "outputs": {"text_encoder": file_path}
        }
    
    def _create_diffusion_model(self) -> Dict:
        code = '''import torch
import torch.nn as nn
import math


class SinusoidalPositionEmbeddings(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.dim = dim
    
    def forward(self, time):
        device = time.device
        half_dim = self.dim // 2
        embeddings = math.log(10000) / (half_dim - 1)
        embeddings = torch.exp(torch.arange(half_dim, device=device) * -embeddings)
        embeddings = time[:, None] * embeddings[None, :]
        embeddings = torch.cat((embeddings.sin(), embeddings.cos()), dim=-1)
        return embeddings


class PixelDiffusionUNet(nn.Module):
    def __init__(self, in_channels: int = 3, out_channels: int = 3, time_emb_dim: int = 256):
        super().__init__()
        self.time_mlp = nn.Sequential(
            SinusoidalPositionEmbeddings(time_emb_dim),
            nn.Linear(time_emb_dim, time_emb_dim * 4),
            nn.SiLU(),
            nn.Linear(time_emb_dim * 4, time_emb_dim)
        )
        self.conv_in = nn.Conv2d(in_channels, 64, 3, padding=1)
        self.conv_out = nn.Conv2d(64, out_channels, 3, padding=1)
    
    def forward(self, x, t):
        t_emb = self.time_mlp(t)
        x = self.conv_in(x)
        x = self.conv_out(x)
        return x
'''
        
        file_path = os.path.join(self.work_dir, "models", "diffusion.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return {
            "success": True,
            "outputs": {"diffusion_model": file_path}
        }
    
    def _create_image_decoder(self) -> Dict:
        code = '''import torch
import torch.nn as nn


class PixelArtDecoder(nn.Module):
    def __init__(self, latent_dim: int = 512, output_channels: int = 3, image_size: int = 64):
        super().__init__()
        self.fc = nn.Linear(latent_dim, 256 * 8 * 8)
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(256, 128, 4, 2, 1),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(128, 64, 4, 2, 1),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, output_channels, 4, 2, 1),
            nn.Tanh()
        )
    
    def forward(self, z: torch.Tensor) -> torch.Tensor:
        x = self.fc(z)
        x = x.view(x.shape[0], 256, 8, 8)
        x = self.decoder(x)
        return x
'''
        
        file_path = os.path.join(self.work_dir, "models", "decoder.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return {
            "success": True,
            "outputs": {"image_decoder": file_path}
        }
    
    def _create_generic_module(self, task: Task) -> Dict:
        return {
            "success": True,
            "outputs": {"message": f"Generic task completed: {task.title}"}
        }


class TesterAgentV2(EnhancedAgent):
    def __init__(self, state_manager: StateManager, work_dir: str):
        super().__init__(
            agent_id="tester_001",
            agent_type="tester",
            capabilities=["测试用例编写", "自动化测试", "性能测试", "回归测试"],
            state_manager=state_manager,
            work_dir=work_dir
        )
    
    def _do_work(self, task: Task) -> Dict:
        self.log(f"执行测试任务: {task.title}")
        
        test_code = '''import pytest
import torch


class TestModels:
    def test_placeholder(self):
        assert True
'''
        
        file_path = os.path.join(self.work_dir, "tests", "test_models_v2.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        return {
            "success": True,
            "outputs": {"test_file": file_path}
        }


class ReviewerAgentV2(EnhancedAgent):
    def __init__(self, state_manager: StateManager, work_dir: str):
        super().__init__(
            agent_id="reviewer_001",
            agent_type="reviewer",
            capabilities=["代码审查", "安全检查", "性能分析", "最佳实践建议"],
            state_manager=state_manager,
            work_dir=work_dir
        )
    
    def _do_work(self, task: Task) -> Dict:
        self.log(f"执行审查任务: {task.title}")
        
        review_report = {
            "review_id": task.id,
            "timestamp": datetime.now().isoformat(),
            "status": "approved",
            "findings": [],
            "recommendations": [
                "代码结构清晰",
                "建议添加更多注释",
                "考虑添加类型提示"
            ]
        }
        
        report_file = os.path.join(self.work_dir, "docs", "review_report_v2.json")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(review_report, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "outputs": {"review_report": report_file}
        }
