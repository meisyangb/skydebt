import os
import sys

WORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORK_DIR)

from workflow.orchestrator import WorkflowOrchestrator


def main():
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         无限AI工作流系统 - 文字生成像素图片模型           ║
    ╠════════════════════════════════════════════════════════════╣
    ║  多智能体协作开发系统                                      ║
    ║  - 架构师: 系统架构设计和模块规划                          ║
    ║  - 开发者: 代码实现和功能开发                              ║
    ║  - 测试员: 测试验证和质量保证                              ║
    ║  - 审查员: 代码审查和优化建议                              ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    config_path = os.path.join(WORK_DIR, "config", "settings.yaml")
    orchestrator = WorkflowOrchestrator(WORK_DIR, config_path)
    
    print(f"工作目录: {WORK_DIR}")
    print(f"配置文件: {config_path}")
    print("-" * 60)
    
    status = orchestrator.run_continuous(interval=1.0)
    
    print("-" * 60)
    print("工作流执行完成!")
    print(f"最终状态: 待处理={status['pending']}, 已完成={status['completed']}")


if __name__ == "__main__":
    main()
