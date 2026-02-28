# 无限AI工作流系统 - 文字生成像素图片模型

## 项目概述

这是一个多智能体协作开发的AI工作流系统，用于构建文字生成像素图片的模型。

## 系统架构

### 智能体角色

| 角色 | 职责 |
|------|------|
| 架构师 | 系统架构设计和模块规划 |
| 开发者 | 代码实现和功能开发 |
| 测试员 | 测试验证和质量保证 |
| 审查员 | 代码审查和优化建议 |

### 模型架构

```
Text -> TextEncoder (CLIP) -> DiffusionModel (UNet) -> ImageDecoder (VQGAN) -> PixelImage
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行工作流

```bash
python main.py
```

### 运行无限循环模式

```bash
python scripts/infinite_loop.py
```

## 目录结构

```
像素生成模型/
├── config/                 # 配置文件
│   ├── agents.yaml        # 智能体配置
│   └── settings.yaml      # 系统设置
├── models/                 # 模型代码
│   ├── text_encoder.py    # 文本编码器
│   ├── diffusion.py       # 扩散模型
│   ├── decoder.py         # 图像解码器
│   └── generator.py       # 生成器主类
├── workflow/              # 工作流系统
│   ├── task_manager.py    # 任务管理
│   ├── git_manager.py     # Git管理
│   ├── agent_base.py      # 智能体基类
│   └── orchestrator.py    # 编排器
├── tasks/                 # 任务队列
│   ├── queue.json         # 待处理任务
│   └── completed.json     # 已完成任务
├── tests/                 # 测试文件
├── docs/                  # 文档
├── logs/                  # 日志
├── scripts/               # 脚本
│   └── infinite_loop.py   # 无限循环脚本
├── main.py                # 主入口
└── requirements.txt       # 依赖
```

## 使用示例

```python
from models import create_pixel_art_generator

# 创建生成器
generator = create_pixel_art_generator(device="cuda")

# 生成像素图片
image = generator.generate("a cute pixel art cat", num_steps=50)

# 保存图片
generator.save_image(image, "output.png")
```

## Git提交规范

所有自动提交使用 `[AI-Agent]` 前缀：

```
[AI-Agent] 完成任务: 实现文本编码器模块 by 开发者 - 2026-02-28 12:00:00
```
