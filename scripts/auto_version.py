#!/usr/bin/env python3
"""
代码改动自动触发需求文档版本管理
监听指定文件变更，自动生成新版本
"""
import os
import sys
import hashlib
import json
from pathlib import Path
from datetime import datetime

# 需要监听的文件配置
WATCH_CONFIG = {
    "docs/requirements.md": {
        "version_type": "manual",  # 手动触发，通过commit命令
        "auto_bump": False
    },
    # 代码文件映射到需求变更描述
    "app/routes/income_order.py": {
        "version_type": "auto",
        "change_pattern": {
            "batch.*unaudit": "批量反审核功能优化",
            "fail_messages": "批量操作失败提示优化",
            "receipt": "收款单相关功能调整",
            "audit": "审核功能调整",
        },
        "default_change": "其他收入单模块代码更新"
    },
    "app/routes/receipt_order.py": {
        "version_type": "auto",
        "default_change": "收款单模块代码更新"
    },
    "app/templates/income_order/list.html": {
        "version_type": "auto",
        "default_change": "其他收入单页面交互优化"
    },
    "app/templates/receipt_order/list.html": {
        "version_type": "auto",
        "default_change": "收款单页面交互优化"
    },
    "app/templates/base/index.html": {
        "version_type": "auto",
        "default_change": "首页流程图优化"
    },
    "tests/test_erp.py": {
        "version_type": "auto",
        "default_change": "单元测试用例更新"
    },
    "tests/test_erp_qa.py": {
        "version_type": "auto",
        "default_change": "QA测试用例更新"
    },
    "tests/test_erp_smoke.py": {
        "version_type": "auto",
        "default_change": "冒烟测试用例更新"
    }
}

STATE_FILE = Path("docs/versions/auto_version_state.json")


def load_state():
    """加载状态文件"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    """保存状态文件"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def calc_file_hash(filepath):
    """计算文件哈希"""
    if not Path(filepath).exists():
        return None
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def detect_change_type(filepath, old_content=None, new_content=None):
    """检测变更类型"""
    config = WATCH_CONFIG.get(filepath, {})
    patterns = config.get("change_pattern", {})
    
    # 如果提供了内容，尝试匹配变更模式
    if old_content and new_content:
        for pattern, desc in patterns.items():
            import re
            # 检查新内容中是否包含模式
            if re.search(pattern, new_content, re.IGNORECASE):
                return desc
    
    return config.get("default_change", "代码更新")


def check_and_trigger_version(filepath, author="系统自动"):
    """
    检查文件变更并触发生成新版本
    
    Returns:
        (triggered: bool, message: str)
    """
    filepath = str(filepath).replace("\\", "/")
    
    if filepath not in WATCH_CONFIG:
        return False, f"未配置监听: {filepath}"
    
    config = WATCH_CONFIG[filepath]
    
    # 手动触发的文件不自动处理
    if config.get("version_type") == "manual":
        return False, f"手动管理版本: {filepath}"
    
    # 计算当前哈希
    current_hash = calc_file_hash(filepath)
    if not current_hash:
        return False, f"文件不存在: {filepath}"
    
    # 加载状态
    state = load_state()
    
    # 检查是否有变更
    last_hash = state.get(filepath, {}).get("hash")
    if last_hash == current_hash:
        return False, f"无变更: {filepath}"
    
    # 检测变更类型
    change_desc = detect_change_type(filepath)
    
    # 更新状态
    state[filepath] = {
        "hash": current_hash,
        "last_check": datetime.now().isoformat(),
        "last_change": change_desc
    }
    save_state(state)
    
    # 触发版本提交
    try:
        from version_manager import VersionManager
        manager = VersionManager()
        
        # 检查requirements.md是否有未提交的变更
        req_path = "docs/requirements.md"
        if not Path(req_path).exists():
            return False, "需求文档不存在"
        
        # 提交新版本（若需求文档内容无变化则自动跳过）
        version_info = manager.commit_version(req_path, change_desc, author)
        
        # 判断是否真正新建了版本（通过比较版本号变化）
        all_versions = manager.history.get("requirements", {}).get("versions", [])
        is_new = len(all_versions) > 0 and all_versions[-1]["changes"] == change_desc and all_versions[-1]["author"] == author
        
        # 自动生成变更历史文档
        manager.generate_changelog_doc("requirements")
        
        return True, f"已处理版本 {version_info['version']}: {change_desc}"
        
    except Exception as e:
        return False, f"版本生成失败: {str(e)}"


def scan_all():
    """扫描所有配置的文件"""
    results = []
    for filepath in WATCH_CONFIG:
        triggered, message = check_and_trigger_version(filepath)
        results.append({
            "file": filepath,
            "triggered": triggered,
            "message": message
        })
    return results


def main():
    """命令行入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("""
代码改动自动版本管理工具

用法:
  python auto_version.py check <文件路径> [作者]
    检查指定文件变更并触发生成版本
    
  python auto_version.py scan
    扫描所有配置的文件
    
  python auto_version.py status
    查看当前状态

示例:
  python auto_version.py check app/routes/income_order.py "张三"
  python auto_version.py scan
        """)
        return
    
    command = sys.argv[1]
    
    if command == "check":
        if len(sys.argv) < 3:
            print("错误: 请指定文件路径")
            return
        filepath = sys.argv[2]
        author = sys.argv[3] if len(sys.argv) > 3 else "系统自动"
        triggered, message = check_and_trigger_version(filepath, author)
        print(message)
    
    elif command == "scan":
        results = scan_all()
        print("\n扫描结果:")
        for r in results:
            status = "✓" if r["triggered"] else "-"
            print(f"  {status} {r['file']}: {r['message']}")
    
    elif command == "status":
        state = load_state()
        print("\n当前监听状态:")
        for filepath, info in state.items():
            print(f"\n  {filepath}")
            print(f"    哈希: {info.get('hash', 'N/A')}")
            print(f"    最后变更: {info.get('last_change', 'N/A')}")
            print(f"    检查时间: {info.get('last_check', 'N/A')}")
    
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
