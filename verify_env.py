import torch
import transformers
import yaml
import pytest

print("=" * 50)
print("环境验证成功!")
print("=" * 50)
print(f"Python版本: 3.10.16")
print(f"PyTorch版本: {torch.__version__}")
print(f"Transformers版本: {transformers.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"GPU设备: {torch.cuda.get_device_name(0)}")
print("=" * 50)
