#!/usr/bin/env python3
"""
需求文档版本管理脚本
自动追踪需求变更，生成带版本历史的新文档
"""
import os
import re
import hashlib
import json
from datetime import datetime
from pathlib import Path


class VersionManager:
    """需求文档版本管理器"""
    
    def __init__(self, docs_dir="docs", versions_dir="docs/versions"):
        self.docs_dir = Path(docs_dir)
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.versions_dir / "version_history.json"
        self.history = self._load_history()
    
    def _load_history(self):
        """加载版本历史"""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_history(self):
        """保存版本历史"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def _calc_hash(self, content):
        """计算内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
    
    def _get_next_version(self, doc_name):
        """获取下一个版本号"""
        if doc_name not in self.history:
            return "V1.0"
        versions = self.history[doc_name]["versions"]
        if not versions:
            return "V1.0"
        last_version = versions[-1]["version"]
        match = re.match(r'V(\d+)\.(\d+)', last_version)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            return f"V{major}.{minor + 1}"
        return "V1.0"
    
    def commit_version(self, doc_path, changes_description="", author=""):
        """
        提交新版本
        
        Args:
            doc_path: 需求文档路径
            changes_description: 本次变更描述
            author: 变更人
        
        Returns:
            version_info: 版本信息字典
        """
        doc_path = Path(doc_path)
        if not doc_path.exists():
            raise FileNotFoundError(f"文档不存在: {doc_path}")
        
        doc_name = doc_path.stem
        
        # 读取当前内容
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content_hash = self._calc_hash(content)
        
        # 检查是否有变更
        if doc_name in self.history:
            last_version = self.history[doc_name]["versions"][-1]
            if last_version["hash"] == content_hash:
                print(f"[{doc_name}] 内容无变更，跳过版本提交")
                return last_version
        
        # 生成新版本号
        version = self._get_next_version(doc_name)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存版本文件
        version_filename = f"{doc_name}_{version}_{content_hash}.md"
        version_path = self.versions_dir / version_filename
        
        # 添加版本头信息
        version_header = self._generate_version_header(
            version, timestamp, changes_description, author
        )
        version_content = version_header + content
        
        with open(version_path, 'w', encoding='utf-8') as f:
            f.write(version_content)
        
        # 更新历史记录
        version_info = {
            "version": version,
            "hash": content_hash,
            "timestamp": timestamp,
            "changes": changes_description,
            "author": author,
            "file": str(version_path)
        }
        
        if doc_name not in self.history:
            self.history[doc_name] = {
                "created_at": timestamp,
                "versions": []
            }
        
        self.history[doc_name]["versions"].append(version_info)
        self._save_history()
        
        print(f"[{doc_name}] 已提交版本 {version}")
        print(f"  - 变更: {changes_description or '无描述'}")
        print(f"  - 文件: {version_path}")
        
        return version_info
    
    def _generate_version_header(self, version, timestamp, changes, author):
        """生成版本头信息"""
        header = f"""<!--
版本信息
==========
版本号: {version}
生成时间: {timestamp}
变更描述: {changes or '初始版本'}
变更人: {author or '未知'}
-->

"""
        return header
    
    def generate_changelog_doc(self, doc_name, output_path=None):
        """
        生成带完整变更历史的文档
        
        Args:
            doc_name: 文档名称（不含扩展名）
            output_path: 输出路径，默认 docs/{doc_name}_with_changelog.md
        """
        if doc_name not in self.history:
            raise ValueError(f"未找到文档历史: {doc_name}")
        
        doc_history = self.history[doc_name]
        versions = doc_history["versions"]
        
        if not versions:
            raise ValueError(f"文档无版本记录: {doc_name}")
        
        # 获取最新版本内容
        latest_version = versions[-1]
        latest_file = Path(latest_version["file"])
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            # 跳过版本头注释
            content = f.read()
            # 移除HTML注释版本头
            content = re.sub(r'<!--\n版本信息.*?-->\n\n', '', content, flags=re.DOTALL)
        
        # 生成变更历史
        changelog = self._generate_changelog_section(versions)
        
        # 组合最终文档
        final_doc = f"""# {doc_name} - 需求文档

> 本文档包含完整版本变更历史  
> 最新版本: {latest_version['version']}  
> 最后更新: {latest_version['timestamp']}

---

## 目录

1. [变更历史](#变更历史)
2. [需求正文](#需求正文)

---

{changelog}

---

## 需求正文

{content}
"""
        
        # 保存文档
        if output_path is None:
            output_path = self.docs_dir / f"{doc_name}_with_changelog.md"
        else:
            output_path = Path(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_doc)
        
        print(f"已生成变更历史文档: {output_path}")
        return output_path
    
    def _generate_changelog_section(self, versions):
        """生成变更历史章节"""
        lines = ["## 变更历史\n"]
        
        for i, v in enumerate(reversed(versions), 1):
            lines.append(f"### {v['version']} ({v['timestamp']})")
            lines.append(f"- **变更描述**: {v['changes'] or '初始版本'}")
            lines.append(f"- **变更人**: {v['author'] or '未知'}")
            lines.append(f"- **文件**: `{Path(v['file']).name}`")
            lines.append("")
        
        return "\n".join(lines)
    
    def list_versions(self, doc_name=None):
        """列出所有版本"""
        if doc_name:
            if doc_name not in self.history:
                print(f"未找到文档: {doc_name}")
                return
            docs = {doc_name: self.history[doc_name]}
        else:
            docs = self.history
        
        for name, info in docs.items():
            print(f"\n📄 {name}")
            print(f"   创建时间: {info['created_at']}")
            print(f"   版本数量: {len(info['versions'])}")
            for v in info['versions']:
                print(f"   - {v['version']}: {v['changes'] or '初始版本'} ({v['timestamp']})")
    
    def diff_versions(self, doc_name, version1, version2):
        """比较两个版本的差异（简化版，显示变更描述）"""
        if doc_name not in self.history:
            raise ValueError(f"未找到文档: {doc_name}")
        
        versions = self.history[doc_name]["versions"]
        v1_info = next((v for v in versions if v["version"] == version1), None)
        v2_info = next((v for v in versions if v["version"] == version2), None)
        
        if not v1_info or not v2_info:
            raise ValueError(f"版本不存在: {version1} 或 {version2}")
        
        print(f"\n📊 {doc_name} 版本对比: {version1} vs {version2}")
        print(f"\n[{version1}] {v1_info['timestamp']}")
        print(f"  变更: {v1_info['changes'] or '无描述'}")
        print(f"\n[{version2}] {v2_info['timestamp']}")
        print(f"  变更: {v2_info['changes'] or '无描述'}")


def main():
    """命令行入口"""
    import sys
    
    manager = VersionManager()
    
    if len(sys.argv) < 2:
        print("""
需求文档版本管理工具

用法:
  python version_manager.py commit <文档路径> ["变更描述"] [作者]
    提交新版本
    
  python version_manager.py changelog <文档名> [输出路径]
    生成带变更历史的文档
    
  python version_manager.py list [文档名]
    列出版本历史
    
  python version_manager.py diff <文档名> <版本1> <版本2>
    比较版本差异

示例:
  python version_manager.py commit docs/requirements.md "新增收款单功能" "张三"
  python version_manager.py changelog requirements
  python version_manager.py list requirements
  python version_manager.py auto "代码变更描述" "作者"  # 自动模式（由auto_version调用）
        """)
        return
    
    command = sys.argv[1]
    
    if command == "commit":
        if len(sys.argv) < 3:
            print("错误: 请指定文档路径")
            return
        doc_path = sys.argv[2]
        changes = sys.argv[3] if len(sys.argv) > 3 else ""
        author = sys.argv[4] if len(sys.argv) > 4 else ""
        manager.commit_version(doc_path, changes, author)
    
    elif command == "changelog":
        if len(sys.argv) < 3:
            print("错误: 请指定文档名")
            return
        doc_name = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else None
        manager.generate_changelog_doc(doc_name, output)
    
    elif command == "list":
        doc_name = sys.argv[2] if len(sys.argv) > 2 else None
        manager.list_versions(doc_name)
    
    elif command == "diff":
        if len(sys.argv) < 5:
            print("错误: 请指定文档名和两个版本号")
            return
        manager.diff_versions(sys.argv[2], sys.argv[3], sys.argv[4])
    
    elif command == "auto":
        """自动根据代码变更生成版本（由auto_version.py调用）"""
        if len(sys.argv) < 4:
            print("错误: 请指定变更描述和作者")
            return
        changes = sys.argv[2]
        author = sys.argv[3]
        doc_path = "docs/requirements.md"
        if Path(doc_path).exists():
            manager.commit_version(doc_path, changes, author)
            manager.generate_changelog_doc("requirements")
        else:
            print(f"错误: 需求文档不存在 {doc_path}")
    
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
