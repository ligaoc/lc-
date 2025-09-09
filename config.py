import os
import json
from typing import Optional


class Config:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"保存配置失败: {e}")
    
    def get_token(self) -> Optional[str]:
        """获取 GitHub Token"""
        return self.config.get('github_token')
    
    def set_token(self, token: str) -> None:
        """设置 GitHub Token"""
        self.config['github_token'] = token
        self.save_config()
    
    def get_recent_repos(self) -> list:
        """获取最近访问的仓库列表"""
        return self.config.get('recent_repos', [])
    
    def add_recent_repo(self, repo_full_name: str) -> None:
        """添加到最近访问的仓库"""
        recent = self.get_recent_repos()
        if repo_full_name in recent:
            recent.remove(repo_full_name)
        recent.insert(0, repo_full_name)
        # 只保留最近 10 个
        self.config['recent_repos'] = recent[:10]
        self.save_config() 