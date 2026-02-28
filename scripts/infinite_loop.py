import os
import sys
import time
import json
import subprocess
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORK_DIR, "workflow"))

from task_manager import TaskManager
from git_manager import GitManager


def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    log_dir = os.path.join(WORK_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "infinite_workflow.log"), 'a', encoding='utf-8') as f:
        f.write(log_entry + "\n")


def run_trae_agent(task: dict) -> dict:
    log(f"调用Trae AI处理任务: {task.get('title')}")
    
    agent_type = task.get("assigned_agent", "developer")
    
    prompt_map = {
        "architect": f"""
请作为架构师，完成以下任务：
任务ID: {task.get('id')}
任务标题: {task.get('title')}
任务描述: {task.get('description')}

请设计相关架构并创建必要的文档文件。
完成后请提交git。
""",
        "developer": f"""
请作为开发者，完成以下任务：
任务ID: {task.get('id')}
任务标题: {task.get('title')}
任务描述: {task.get('description')}

请实现相关代码，确保代码质量和功能正确。
完成后请提交git。
""",
        "tester": f"""
请作为测试员，完成以下任务：
任务ID: {task.get('id')}
任务标题: {task.get('title')}
任务描述: {task.get('description')}

请编写测试用例并验证代码功能。
完成后请提交git。
""",
        "reviewer": f"""
请作为审查员，完成以下任务：
任务ID: {task.get('id')}
任务标题: {task.get('title')}
任务描述: {task.get('description')}

请审查代码并提供改进建议。
完成后请提交git。
"""
    }
    
    log(f"任务提示词已生成，等待Trae AI处理...")
    
    return {
        "success": True,
        "message": f"任务 {task.get('id')} 已准备好由 {agent_type} 处理",
        "prompt": prompt_map.get(agent_type, prompt_map["developer"])
    }


def commit_all_changes(git_manager: GitManager, message: str):
    if git_manager.has_changes():
        git_manager.add_all()
        git_manager.commit(message, "[Infinite-Workflow]")
        log(f"Git提交: {message}")
        return True
    return False


def infinite_workflow_loop(interval: float = 5.0, max_iterations: int = None):
    log("=" * 60)
    log("  无限AI工作流系统启动")
    log("  文字生成像素图片模型开发项目")
    log("=" * 60)
    
    task_manager = TaskManager(
        os.path.join(WORK_DIR, "tasks", "queue.json"),
        os.path.join(WORK_DIR, "tasks", "completed.json")
    )
    git_manager = GitManager(WORK_DIR)
    
    if not git_manager.is_git_repo():
        git_manager.init_repo()
        log("初始化Git仓库")
    
    iteration = 0
    
    while True:
        iteration += 1
        log(f"\n{'='*20} 迭代 #{iteration} {'='*20}")
        
        status = task_manager.get_status()
        log(f"任务状态: 待处理={status['pending']}, 进行中={status['in_progress']}, 已完成={status['completed']}")
        
        if max_iterations and iteration > max_iterations:
            log(f"达到最大迭代次数 {max_iterations}，停止工作流")
            break
        
        task = task_manager.get_any_pending_task()
        
        if task:
            log(f"\n处理任务: [{task.get('id')}] {task.get('title')}")
            log(f"分配给: {task.get('assigned_agent')}")
            
            result = run_trae_agent(task)
            
            if result.get("success"):
                task_manager.complete_task(task.get("id"), result)
                log(f"任务 {task.get('id')} 已标记为完成")
                
                commit_all_changes(git_manager, f"完成任务: {task.get('title')}")
            else:
                log(f"任务执行失败: {result.get('error')}", "ERROR")
        else:
            if not task_manager.has_in_progress_tasks():
                log("\n所有任务已完成!")
                log(f"总计完成: {task_manager.completed_data.get('total_completed', 0)} 个任务")
                
                log("\n等待新任务... (按Ctrl+C退出)")
                time.sleep(interval * 2)
                task_manager._load_queue()
        
        log(f"等待 {interval} 秒后进入下一次迭代...")
        time.sleep(interval)
    
    log("\n工作流结束")
    return task_manager.get_status()


def add_new_task(title: str, description: str, agent_type: str = "developer", priority: int = 5):
    task_manager = TaskManager(
        os.path.join(WORK_DIR, "tasks", "queue.json"),
        os.path.join(WORK_DIR, "tasks", "completed.json")
    )
    task = task_manager.add_task(title, description, agent_type, priority)
    log(f"添加新任务: {task.get('id')} - {title}")
    return task


if __name__ == "__main__":
    try:
        infinite_workflow_loop(interval=3.0)
    except KeyboardInterrupt:
        log("\n用户中断，工作流停止")
    except Exception as e:
        log(f"工作流异常: {str(e)}", "ERROR")
        raise
