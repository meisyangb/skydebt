# 无限AI工作流系统 V2 - 文字生成像素图片模型

## 项目概述

这是一个基于 **Long-Running Agents 调度编排框架** 的多智能体协作开发系统，用于构建文字生成像素图片的模型。

## V2 核心特性

基于《长时间运行智能体的有效调度，编排，框架》论文的核心概念：

### 1. 状态管理和检查点恢复
- **Checkpoint System**: 任务执行过程中自动创建检查点
- **State Persistence**: 智能体状态持久化存储
- **Recovery Mechanism**: 支持从任意检查点恢复执行

### 2. 共享记忆系统 (Shared Memory)
- **Global Context**: 全局共享上下文，所有智能体可访问
- **Agent Outputs**: 智能体输出共享，实现信息同步
- **Knowledge Base**: 知识库累积，长期记忆存储

### 3. 智能体自动恢复
- **Auto-Recovery**: 错误状态自动检测和恢复
- **State Tracking**: 实时追踪智能体状态
- **Graceful Degradation**: 优雅降级处理

### 4. 精准上下文管理 (Context Engineering)
- **Minimal Context**: 每个智能体只获取必要的上下文
- **Context Isolation**: 避免上下文污染
- **Efficient Retrieval**: 按需获取相关信息

### 5. 并行执行和优先级调度
- **Multi-Threading**: 支持多任务并行执行
- **Priority Queue**: 基于优先级的任务调度
- **Dependency Aware**: 任务依赖感知调度

### 6. 任务依赖管理
- **DAG Support**: 支持有向无环图任务依赖
- **Dependency Resolution**: 自动解析依赖关系
- **Execution Order**: 智能排序执行顺序

## 系统架构

### 智能体角色

| 角色 | 职责 | 状态管理 |
|------|------|----------|
| 架构师 | 系统架构设计和模块规划 | 独立工作记忆 |
| 开发者 | 代码实现和功能开发 | 独立工作记忆 |
| 测试员 | 测试验证和质量保证 | 独立工作记忆 |
| 审查员 | 代码审查和优化建议 | 独立工作记忆 |

### 模型架构

```
Text -> TextEncoder (CLIP) -> DiffusionModel (UNet) -> ImageDecoder (VQGAN) -> PixelImage
```

### 工作流架构

```
┌─────────────────────────────────────────────────────────────┐
│                    WorkflowOrchestratorV2                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Scheduler  │  │StateManager │  │   Shared Memory     │  │
│  │  (Priority) │  │ (Checkpoint)│  │   (Global Context)  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴──────┐     │
│  │                    Agents Pool                      │     │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │     │
│  │  │Architect│ │Developer│ │ Tester │ │Reviewer│       │     │
│  │  └────────┘ └────────┘ └────────┘ └────────┘       │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行 V2 工作流 (推荐)

```bash
python scripts/infinite_loop_v2.py
```

### 运行 V1 工作流

```bash
python main.py
```

## 目录结构

```
像素生成模型/
├── config/                    # 配置文件
│   ├── agents.yaml           # 智能体配置
│   └── settings.yaml         # 系统设置
├── models/                    # 模型代码
│   ├── text_encoder.py       # 文本编码器
│   ├── diffusion.py          # 扩散模型
│   ├── decoder.py            # 图像解码器
│   └── generator.py          # 生成器主类
├── workflow/                  # 工作流系统
│   ├── state_manager.py      # 状态管理和检查点 ★NEW
│   ├── scheduler.py          # 任务调度器 ★NEW
│   ├── enhanced_agent.py     # 增强智能体 ★NEW
│   ├── orchestrator_v2.py    # V2编排器 ★NEW
│   ├── task_manager.py       # 任务管理
│   ├── git_manager.py        # Git管理
│   └── agent_base.py         # 智能体基类
├── state/                     # 状态存储 ★NEW
│   ├── checkpoints/          # 检查点文件
│   ├── agent_states/         # 智能体状态
│   ├── task_states/          # 任务状态
│   └── shared_memory.json    # 共享记忆
├── tasks/                     # 任务队列
│   ├── queue.json            # 待处理任务
│   └── completed.json        # 已完成任务
├── tests/                     # 测试文件
├── docs/                      # 文档
├── logs/                      # 日志
├── scripts/                   # 脚本
│   ├── infinite_loop_v2.py   # V2无限循环 ★NEW
│   └── infinite_loop.py      # V1无限循环
├── main.py                    # 主入口
└── requirements.txt           # 依赖
```

## 使用示例

### V2 API

```python
from workflow import WorkflowOrchestratorV2, SchedulingStrategy

# 创建编排器
orchestrator = WorkflowOrchestratorV2(
    work_dir="./",
    max_concurrent_tasks=4,
    scheduling_strategy=SchedulingStrategy.PRIORITY
)

# 添加任务（支持依赖）
orchestrator.add_task(
    title="实现文本编码器",
    description="使用CLIP实现文本编码",
    agent_type="developer",
    priority=1,
    dependencies=[]  # 可指定依赖任务ID
)

# 并行运行
status = orchestrator.run_parallel(interval=1.0)

# 获取状态报告
report = orchestrator.get_status_report()
```

### 从检查点恢复

```python
# 恢复到最新检查点
orchestrator.recover_from_checkpoint()

# 恢复到指定检查点
orchestrator.recover_from_checkpoint("cp_abc12345")
```

### 生成像素图片

```python
from models import create_pixel_art_generator

# 创建生成器
generator = create_pixel_art_generator(device="cuda")

# 生成像素图片
image = generator.generate("a cute pixel art cat", num_steps=50)

# 保存图片
generator.save_image(image, "output.png")
```

## 调度策略

| 策略 | 描述 |
|------|------|
| `PRIORITY` | 按优先级调度（默认） |
| `FIFO` | 先进先出 |
| `SHORTEST_JOB_FIRST` | 最短任务优先 |
| `DEPENDENCY_AWARE` | 依赖感知调度 |

## Git提交规范

所有自动提交使用 `[AI-Agent]` 或 `[AI-Agent-V2]` 前缀：

```
[AI-Agent-V2] Complete: 实现文本编码器模块 by developer - 2026-02-28 12:00:00
```

## 技术参考

本项目基于以下论文和文章的核心概念：

1. **Long-Running Agents**: 从Cursor和Anthropic的探索看AI研发的未来
2. **Context Engineering**: 精准上下文管理比海量上下文更有效
3. **Shared Memory**: Multi-Agent协作的关键是共享记忆机制
4. **State Tracking**: 状态追踪实现长期记忆穿透

## License

MIT
