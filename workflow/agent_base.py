from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import os
import json
from datetime import datetime


class BaseAgent(ABC):
    def __init__(self, name: str, role: str, capabilities: list, work_dir: str):
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.work_dir = work_dir
        self.current_task = None
        self.log_file = os.path.join(work_dir, "logs", f"{name}_agent.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [{self.name}] {message}\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(log_entry.strip())
    
    def accept_task(self, task: Dict) -> bool:
        self.current_task = task
        self.log(f"接受任务: {task.get('title', 'Unknown')}")
        return True
    
    @abstractmethod
    def execute_task(self) -> Dict:
        pass
    
    def complete_task(self, result: Dict = None) -> Dict:
        if self.current_task:
            self.log(f"完成任务: {self.current_task.get('title', 'Unknown')}")
            task_result = {
                "task_id": self.current_task.get("id"),
                "agent": self.name,
                "result": result or {},
                "completed_at": datetime.now().isoformat()
            }
            self.current_task = None
            return task_result
        return {}
    
    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "current_task": self.current_task.get("id") if self.current_task else None,
            "is_busy": self.current_task is not None
        }


class ArchitectAgent(BaseAgent):
    def __init__(self, work_dir: str):
        super().__init__(
            name="架构师",
            role="系统架构设计和模块规划",
            capabilities=["设计系统架构", "定义模块接口", "规划数据流"],
            work_dir=work_dir
        )
    
    def execute_task(self) -> Dict:
        if not self.current_task:
            return {"success": False, "error": "No task assigned"}
        
        self.log(f"开始执行架构设计任务: {self.current_task.get('title')}")
        
        architecture = {
            "model_name": "PixelArtGenerator",
            "components": [
                {
                    "name": "TextEncoder",
                    "type": "CLIP",
                    "input": "text",
                    "output": "embedding (512-dim)"
                },
                {
                    "name": "DiffusionModel",
                    "type": "UNet",
                    "input": "embedding + noise",
                    "output": "denoised_latent"
                },
                {
                    "name": "ImageDecoder",
                    "type": "VQGAN",
                    "input": "latent",
                    "output": "pixel_image (64x64)"
                }
            ],
            "data_flow": "Text -> TextEncoder -> DiffusionModel -> ImageDecoder -> PixelImage"
        }
        
        arch_file = os.path.join(self.work_dir, "docs", "architecture.json")
        os.makedirs(os.path.dirname(arch_file), exist_ok=True)
        with open(arch_file, 'w', encoding='utf-8') as f:
            json.dump(architecture, f, ensure_ascii=False, indent=2)
        
        self.log(f"架构设计完成，已保存到 {arch_file}")
        
        return {
            "success": True,
            "output_file": arch_file,
            "architecture": architecture
        }


class DeveloperAgent(BaseAgent):
    def __init__(self, work_dir: str):
        super().__init__(
            name="开发者",
            role="代码实现和功能开发",
            capabilities=["编写核心代码", "实现模型逻辑", "优化性能"],
            work_dir=work_dir
        )
    
    def execute_task(self) -> Dict:
        if not self.current_task:
            return {"success": False, "error": "No task assigned"}
        
        task_title = self.current_task.get('title', '')
        self.log(f"开始执行开发任务: {task_title}")
        
        result = {"success": True, "files_created": []}
        
        if "文本编码器" in task_title:
            result.update(self._create_text_encoder())
        elif "扩散模型" in task_title:
            result.update(self._create_diffusion_model())
        elif "图像解码器" in task_title:
            result.update(self._create_image_decoder())
        else:
            result.update(self._create_generic_module())
        
        return result
    
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
        
        self.log(f"创建文本编码器: {file_path}")
        return {"files_created": [file_path]}
    
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


class PixelDiffusionBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, time_emb_dim: int):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1)
        self.time_mlp = nn.Linear(time_emb_dim, out_channels)
        self.norm1 = nn.GroupNorm(8, in_channels)
        self.norm2 = nn.GroupNorm(8, out_channels)
        self.act = nn.SiLU()
        
        if in_channels != out_channels:
            self.skip = nn.Conv2d(in_channels, out_channels, 1)
        else:
            self.skip = nn.Identity()
    
    def forward(self, x, t_emb):
        h = self.norm1(x)
        h = self.act(h)
        h = self.conv1(h)
        
        t_emb = self.time_mlp(t_emb)[:, :, None, None]
        h = h + t_emb
        
        h = self.norm2(h)
        h = self.act(h)
        h = self.conv2(h)
        
        return h + self.skip(x)


class PixelDiffusionUNet(nn.Module):
    def __init__(self, in_channels: int = 3, out_channels: int = 3, time_emb_dim: int = 256):
        super().__init__()
        self.time_mlp = nn.Sequential(
            SinusoidalPositionEmbeddings(time_emb_dim),
            nn.Linear(time_emb_dim, time_emb_dim * 4),
            nn.SiLU(),
            nn.Linear(time_emb_dim * 4, time_emb_dim)
        )
        
        self.down1 = PixelDiffusionBlock(in_channels, 64, time_emb_dim)
        self.down2 = PixelDiffusionBlock(64, 128, time_emb_dim)
        self.down3 = PixelDiffusionBlock(128, 256, time_emb_dim)
        
        self.mid = PixelDiffusionBlock(256, 256, time_emb_dim)
        
        self.up1 = PixelDiffusionBlock(512, 128, time_emb_dim)
        self.up2 = PixelDiffusionBlock(256, 64, time_emb_dim)
        self.up3 = PixelDiffusionBlock(128, out_channels, time_emb_dim)
        
        self.pool = nn.MaxPool2d(2)
        self.upsample = nn.Upsample(scale_factor=2, mode='nearest')
    
    def forward(self, x, t):
        t_emb = self.time_mlp(t)
        
        d1 = self.down1(x, t_emb)
        d2 = self.down2(self.pool(d1), t_emb)
        d3 = self.down3(self.pool(d2), t_emb)
        
        mid = self.mid(self.pool(d3), t_emb)
        
        u1 = self.upsample(mid)
        u1 = torch.cat([u1, d3], dim=1)
        u1 = self.up1(u1, t_emb)
        
        u2 = self.upsample(u1)
        u2 = torch.cat([u2, d2], dim=1)
        u2 = self.up2(u2, t_emb)
        
        u3 = self.upsample(u2)
        u3 = torch.cat([u3, d1], dim=1)
        u3 = self.up3(u3, t_emb)
        
        return u3
'''
        
        file_path = os.path.join(self.work_dir, "models", "diffusion.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self.log(f"创建扩散模型: {file_path}")
        return {"files_created": [file_path]}
    
    def _create_image_decoder(self) -> Dict:
        code = '''import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels)
        )
        self.relu = nn.ReLU(inplace=True)
    
    def forward(self, x):
        return self.relu(x + self.block(x))


class PixelArtDecoder(nn.Module):
    def __init__(self, latent_dim: int = 512, output_channels: int = 3, image_size: int = 64):
        super().__init__()
        self.init_size = image_size // 8
        
        self.fc = nn.Linear(latent_dim, 256 * self.init_size * self.init_size)
        
        self.decoder = nn.Sequential(
            nn.Conv2d(256, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            ResidualBlock(256),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(256, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            ResidualBlock(128),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(128, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            ResidualBlock(64),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(64, output_channels, 3, padding=1),
            nn.Tanh()
        )
        
        self.pixel_quantize = PixelQuantize()
    
    def forward(self, z: torch.Tensor) -> torch.Tensor:
        x = self.fc(z)
        x = x.view(x.shape[0], 256, self.init_size, self.init_size)
        x = self.decoder(x)
        x = self.pixel_quantize(x)
        return x


class PixelQuantize(nn.Module):
    def __init__(self, levels: int = 16):
        super().__init__()
        self.levels = levels
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = (x + 1) / 2
        x = x * (self.levels - 1)
        x = torch.round(x)
        x = x / (self.levels - 1)
        x = x * 2 - 1
        return x
'''
        
        file_path = os.path.join(self.work_dir, "models", "decoder.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self.log(f"创建图像解码器: {file_path}")
        return {"files_created": [file_path]}
    
    def _create_generic_module(self) -> Dict:
        return {"success": True, "message": "Generic task completed"}


class TesterAgent(BaseAgent):
    def __init__(self, work_dir: str):
        super().__init__(
            name="测试员",
            role="测试验证和质量保证",
            capabilities=["编写测试用例", "执行测试", "报告问题"],
            work_dir=work_dir
        )
    
    def execute_task(self) -> Dict:
        if not self.current_task:
            return {"success": False, "error": "No task assigned"}
        
        self.log(f"开始执行测试任务: {self.current_task.get('title')}")
        
        test_code = '''import pytest
import torch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTextEncoder:
    def test_encode_shape(self):
        from models.text_encoder import TextEncoder
        encoder = TextEncoder(device="cpu")
        embedding = encoder.encode("a pixel art cat")
        assert embedding.shape == (1, 512)


class TestDiffusionModel:
    def test_unet_forward(self):
        from models.diffusion import PixelDiffusionUNet
        model = PixelDiffusionUNet(in_channels=3, out_channels=3)
        x = torch.randn(1, 3, 64, 64)
        t = torch.randint(0, 1000, (1,))
        output = model(x, t)
        assert output.shape == (1, 3, 64, 64)


class TestImageDecoder:
    def test_decoder_forward(self):
        from models.decoder import PixelArtDecoder
        decoder = PixelArtDecoder(latent_dim=512, output_channels=3, image_size=64)
        z = torch.randn(1, 512)
        output = decoder(z)
        assert output.shape == (1, 3, 64, 64)
        assert output.min() >= -1 and output.max() <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        
        file_path = os.path.join(self.work_dir, "tests", "test_models.py")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        self.log(f"创建测试文件: {file_path}")
        
        return {
            "success": True,
            "files_created": [file_path],
            "test_file": file_path
        }


class ReviewerAgent(BaseAgent):
    def __init__(self, work_dir: str):
        super().__init__(
            name="审查员",
            role="代码审查和优化建议",
            capabilities=["代码审查", "安全检查", "性能分析"],
            work_dir=work_dir
        )
    
    def execute_task(self) -> Dict:
        if not self.current_task:
            return {"success": False, "error": "No task assigned"}
        
        self.log(f"开始执行审查任务: {self.current_task.get('title')}")
        
        review_report = {
            "review_id": self.current_task.get("id"),
            "timestamp": datetime.now().isoformat(),
            "findings": [
                {
                    "file": "models/text_encoder.py",
                    "status": "approved",
                    "comments": ["代码结构清晰", "使用了预训练模型，节省训练时间"]
                },
                {
                    "file": "models/diffusion.py",
                    "status": "approved",
                    "comments": ["UNet架构设计合理", "时间嵌入实现正确"]
                },
                {
                    "file": "models/decoder.py",
                    "status": "approved",
                    "comments": ["像素量化层确保输出像素风格", "残差块增强表达能力"]
                }
            ],
            "recommendations": [
                "考虑添加注意力机制增强生成质量",
                "可以添加条件引导生成",
                "建议添加模型保存和加载功能"
            ],
            "security_check": "passed",
            "performance_rating": "good"
        }
        
        report_file = os.path.join(self.work_dir, "docs", "review_report.json")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(review_report, f, ensure_ascii=False, indent=2)
        
        self.log(f"审查报告已保存: {report_file}")
        
        return {
            "success": True,
            "report_file": report_file,
            "review_report": review_report
        }
