from github import Github
from github.Repository import Repository
from github.ContentFile import ContentFile
from typing import List, Optional, Tuple, Dict, Any
import base64
from datetime import datetime
import json
import hashlib
import time


class GitHubManager:
    def __init__(self, token: str):
        self.github = Github(token)
        self.user = self.github.get_user()
    
    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            return {
                'login': self.user.login,
                'name': self.user.name or self.user.login,
                'email': self.user.email,
                'public_repos': self.user.public_repos,
                'private_repos': self.user.total_private_repos,
                'followers': self.user.followers,
                'following': self.user.following
            }
        except Exception as e:
            raise Exception(f"获取用户信息失败: {e}")
    
    def check_token_permissions(self) -> Dict[str, Any]:
        """检查 Token 权限"""
        try:
            # 获取当前 Token 的权限范围
            rate_limit = self.github.get_rate_limit()
            
            # 尝试访问用户仓库来测试权限
            try:
                repos = list(self.github.get_user().get_repos())[:1]  # 只获取一个仓库测试
                repo_access = True
            except Exception:
                repo_access = False
            
            # 尝试创建测试内容来检查写权限
            write_access = False
            if repos:
                try:
                    # 这里不实际创建，只是检查是否有权限
                    test_repo = repos[0]
                    # 检查是否有 push 权限
                    permissions = test_repo.permissions
                    write_access = permissions.push if hasattr(permissions, 'push') else False
                except Exception:
                    write_access = False
            
            return {
                'repo_access': repo_access,
                'write_access': write_access,
                'rate_limit': {
                    'core': rate_limit.core.limit,
                    'remaining': rate_limit.core.remaining,
                    'reset': rate_limit.core.reset
                }
            }
        except Exception as e:
            raise Exception(f"检查权限失败: {e}")
    
    def list_repositories(self) -> List[Repository]:
        """获取用户所有仓库"""
        try:
            repos = []
            # 获取用户自己的仓库
            for repo in self.user.get_repos():
                repos.append(repo)
            return sorted(repos, key=lambda x: x.updated_at, reverse=True)
        except Exception as e:
            raise Exception(f"获取仓库列表失败: {e}")
    
    def get_repository(self, repo_name: str) -> Repository:
        """获取指定仓库"""
        try:
            return self.user.get_repo(repo_name)
        except Exception as e:
            raise Exception(f"获取仓库失败: {e}")
    
    def create_repository(self, name: str, description: str = "", private: bool = False, 
                         auto_init: bool = True) -> Repository:
        """创建新仓库"""
        try:
            return self.user.create_repo(
                name=name,
                description=description,
                private=private,
                auto_init=auto_init
            )
        except Exception as e:
            raise Exception(f"创建仓库失败: {e}")
    
    def delete_repository(self, repo_name: str) -> bool:
        """删除仓库"""
        try:
            repo = self.get_repository(repo_name)
            repo.delete()
            return True
        except Exception as e:
            raise Exception(f"删除仓库失败: {e}")
    
    def update_repository(self, repo_name: str, **kwargs) -> Repository:
        """更新仓库信息"""
        try:
            repo = self.get_repository(repo_name)
            repo.edit(**kwargs)
            return repo
        except Exception as e:
            raise Exception(f"更新仓库失败: {e}")
    
    def list_files(self, repo: Repository, path: str = "") -> List[ContentFile]:
        """列出仓库文件"""
        try:
            contents = repo.get_contents(path)
            if isinstance(contents, list):
                return contents
            else:
                return [contents]
        except Exception as e:
            raise Exception(f"获取文件列表失败: {e}")
    
    def get_file_content(self, repo: Repository, path: str) -> Tuple[str, str]:
        """获取文件内容"""
        try:
            file = repo.get_contents(path)
            if file.type == "file":
                content = base64.b64decode(file.content).decode('utf-8')
                return content, file.sha
            else:
                raise Exception("不是文件类型")
        except Exception as e:
            raise Exception(f"获取文件内容失败: {e}")
    
    def create_file(self, repo: Repository, path: str, content: str, 
                   message: str = "Add new file") -> bool:
        """创建新文件，如果文件已存在则更新"""
        try:
            repo.create_file(path, message, content)
            return True
        except Exception as e:
            # 如果文件已存在，尝试更新
            if "already exists" in str(e) or "sha" in str(e).lower():
                try:
                    return self.create_or_update_file(repo, path, content, message)
                except Exception as update_e:
                    raise Exception(f"创建/更新文件失败: {update_e}")
            else:
                raise Exception(f"创建文件失败: {e}")
    
    def create_or_update_file(self, repo: Repository, path: str, content: str, 
                             message: str = "Create or update file") -> bool:
        """创建或更新文件（智能判断）"""
        try:
            # 先尝试获取现有文件
            try:
                existing_file = repo.get_contents(path)
                # 文件存在，进行更新
                repo.update_file(path, message, content, existing_file.sha)
                return True
            except Exception:
                # 文件不存在，创建新文件
                repo.create_file(path, message, content)
                return True
        except Exception as e:
            raise Exception(f"创建/更新文件失败: {e}")
    
    def create_directory(self, repo: Repository, dir_path: str, 
                        message: str = "Create directory") -> bool:
        """创建目录（通过创建 .gitkeep 文件）"""
        try:
            # GitHub 不能直接创建空目录，需要在目录中创建一个文件
            # 使用 .gitkeep 是一个常见的约定
            gitkeep_path = f"{dir_path}/.gitkeep" if dir_path else ".gitkeep"
            repo.create_file(gitkeep_path, message, "# 此文件用于保持目录结构\n# This file is used to maintain directory structure")
            return True
        except Exception as e:
            raise Exception(f"创建目录失败: {e}")
    
    def update_file(self, repo: Repository, path: str, content: str, 
                   sha: str, message: str = "Update file") -> bool:
        """更新文件"""
        try:
            repo.update_file(path, message, content, sha)
            return True
        except Exception as e:
            raise Exception(f"更新文件失败: {e}")
    
    def delete_file(self, repo: Repository, path: str, 
                   message: str = "Delete file") -> bool:
        """删除文件"""
        try:
            file = repo.get_contents(path)
            repo.delete_file(path, message, file.sha)
            return True
        except Exception as e:
            raise Exception(f"删除文件失败: {e}")
    
    def get_repository_info(self, repo: Repository) -> Dict[str, Any]:
        """获取仓库详细信息"""
        try:
            return {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description or "无描述",
                'private': repo.private,
                'fork': repo.fork,
                'created_at': repo.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': repo.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                'size': repo.size,
                'language': repo.language or "未知",
                'forks_count': repo.forks_count,
                'stargazers_count': repo.stargazers_count,
                'watchers_count': repo.watchers_count,
                'open_issues_count': repo.open_issues_count,
                'default_branch': repo.default_branch,
                'clone_url': repo.clone_url,
                'html_url': repo.html_url
            }
        except Exception as e:
            raise Exception(f"获取仓库信息失败: {e}")
    
    def download_repository(self, repo: Repository, local_path: str, progress_callback=None, force_full_download=False) -> bool:
        """智能下载仓库（自动选择增量或全量下载）"""
        try:
            if force_full_download:
                if progress_callback:
                    progress_callback("🔄 强制全量下载...")
                return self.download_repository_full(repo, local_path, progress_callback)
            
            # 检查仓库大小，决定下载策略
            repo_size_mb = getattr(repo, 'size', 0) / 1024  # GitHub API 返回的 size 是 KB
            
            if repo_size_mb < 10:  # 小于10MB的仓库直接全量下载
                if progress_callback:
                    progress_callback(f"📊 仓库大小 {repo_size_mb:.1f}MB < 10MB，使用全量下载")
                return self.download_repository_full(repo, local_path, progress_callback)
            else:
                if progress_callback:
                    progress_callback(f"📊 仓库大小 {repo_size_mb:.1f}MB >= 10MB，尝试增量下载")
                return self.download_repository_incremental(repo, local_path, progress_callback)
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ 智能下载失败: {e}")
            raise e
    
    def get_executable_files(self, repo_path: str) -> List[str]:
        """获取仓库中可执行的文件列表"""
        import os
        
        executable_files = []
        executable_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.pl', '.sh', '.bat', '.cmd']
        
        try:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if file_ext in executable_extensions:
                        # 返回相对于仓库根目录的路径
                        rel_path = os.path.relpath(file_path, repo_path)
                        executable_files.append(rel_path)
            
            return sorted(executable_files)
            
        except Exception as e:
            raise Exception(f"获取可执行文件列表失败: {e}")
    
    def get_repo_cache_info(self, local_path: str) -> Dict[str, Any]:
        """获取本地仓库缓存信息"""
        cache_file = os.path.join(local_path, '.repo_cache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_repo_cache_info(self, local_path: str, cache_info: Dict[str, Any]) -> None:
        """保存仓库缓存信息"""
        import os
        cache_file = os.path.join(local_path, '.repo_cache.json')
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存缓存信息失败: {e}")
    
    def calculate_file_sha(self, file_path: str) -> str:
        """计算文件的SHA1哈希值"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha1(f.read()).hexdigest()
        except:
            return ""
    
    def safe_remove_directory(self, directory_path: str, max_retries=3, delay=1.0) -> bool:
        """安全删除目录，处理 Windows 文件锁定问题"""
        import os
        import shutil
        import gc
        
        if not os.path.exists(directory_path):
            return True
        
        for attempt in range(max_retries):
            try:
                # 强制垃圾回收，释放可能的文件句柄
                gc.collect()
                
                # 尝试删除目录
                shutil.rmtree(directory_path)
                return True
                
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"删除目录失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay)
                    delay *= 2  # 指数退避
                else:
                    print(f"删除目录最终失败: {e}")
                    return False
            except Exception as e:
                print(f"删除目录时发生未知错误: {e}")
                return False
        
        return False
    
    def safe_create_directory(self, directory_path: str, clear_existing=False) -> bool:
        """安全创建目录"""
        import os
        
        try:
            if clear_existing and os.path.exists(directory_path):
                if not self.safe_remove_directory(directory_path):
                    return False
            
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)
            
            return True
            
        except Exception as e:
            print(f"创建目录失败: {e}")
            return False
    
    def should_update_repository(self, repo: Repository, local_path: str) -> Tuple[bool, str]:
        """检查是否需要更新仓库"""
        if not os.path.exists(local_path):
            return True, "本地目录不存在，需要全量下载"
        
        cache_info = self.get_repo_cache_info(local_path)
        
        # 检查仓库更新时间
        repo_updated_at = repo.updated_at.isoformat()
        cached_updated_at = cache_info.get('repo_updated_at', '')
        
        if repo_updated_at != cached_updated_at:
            return True, f"仓库有更新 (本地: {cached_updated_at}, 远程: {repo_updated_at})"
        
        # 检查是否有基本文件
        if not cache_info.get('files_sha'):
            return True, "缺少文件缓存信息，需要重新下载"
        
        return False, "仓库已是最新版本"
    
    def download_repository_incremental(self, repo: Repository, local_path: str, progress_callback=None) -> bool:
        """增量下载仓库"""
        import os
        import requests
        
        try:
            # 检查是否需要更新
            need_update, reason = self.should_update_repository(repo, local_path)
            
            if progress_callback:
                if need_update:
                    progress_callback(f"📋 {reason}")
                else:
                    progress_callback(f"✅ {reason}")
                    return True
            
            # 安全创建本地目录
            if not self.safe_create_directory(local_path):
                raise Exception(f"无法创建目录: {local_path}")
            
            cache_info = self.get_repo_cache_info(local_path)
            
            # 获取仓库文件树
            if progress_callback:
                progress_callback("🔍 获取仓库文件列表...")
            
            try:
                tree = repo.get_git_tree(sha=repo.default_branch, recursive=True)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ 无法获取文件树，回退到全量下载: {e}")
                return self.download_repository_full(repo, local_path, progress_callback)
            
            # 分析需要更新的文件
            files_to_download = []
            files_to_delete = []
            
            remote_files = {item.path: item.sha for item in tree.tree if item.type == 'blob'}
            local_files = cache_info.get('files_sha', {})
            
            # 找出需要下载的文件（新增或修改）
            for file_path, remote_sha in remote_files.items():
                local_file_path = os.path.join(local_path, file_path)
                local_sha = local_files.get(file_path, '')
                
                if remote_sha != local_sha:
                    files_to_download.append((file_path, remote_sha))
            
            # 找出需要删除的文件（远程已删除）
            for file_path in local_files:
                if file_path not in remote_files:
                    local_file_path = os.path.join(local_path, file_path)
                    if os.path.exists(local_file_path):
                        files_to_delete.append(file_path)
            
            total_operations = len(files_to_download) + len(files_to_delete)
            
            if total_operations == 0:
                if progress_callback:
                    progress_callback("✅ 所有文件都是最新的")
                return True
            
            # 判断是否使用增量更新
            file_change_ratio = total_operations / max(len(remote_files), 1)
            
            if file_change_ratio > 0.5:  # 超过50%的文件需要更新
                if progress_callback:
                    progress_callback(f"📊 变更文件比例 {file_change_ratio:.1%} > 50%，使用全量下载")
                return self.download_repository_full(repo, local_path, progress_callback)
            
            if progress_callback:
                progress_callback(f"📊 增量更新: {len(files_to_download)} 个文件下载, {len(files_to_delete)} 个文件删除")
            
            # 删除本地多余的文件
            for file_path in files_to_delete:
                local_file_path = os.path.join(local_path, file_path)
                try:
                    os.remove(local_file_path)
                    if progress_callback:
                        progress_callback(f"🗑️ 删除文件: {file_path}")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"⚠️ 删除文件失败 {file_path}: {e}")
            
            # 下载需要更新的文件
            completed = 0
            for file_path, remote_sha in files_to_download:
                try:
                    # 使用 GitHub API 下载单个文件
                    file_content = repo.get_contents(file_path)
                    
                    local_file_path = os.path.join(local_path, file_path)
                    local_dir = os.path.dirname(local_file_path)
                    
                    # 创建目录
                    if local_dir and not os.path.exists(local_dir):
                        os.makedirs(local_dir)
                    
                    # 写入文件
                    if hasattr(file_content, 'decoded_content'):
                        with open(local_file_path, 'wb') as f:
                            f.write(file_content.decoded_content)
                    else:
                        # 如果是文本文件
                        content = base64.b64decode(file_content.content).decode('utf-8')
                        with open(local_file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    
                    completed += 1
                    if progress_callback:
                        progress = (completed / len(files_to_download)) * 100
                        progress_callback(f"📥 下载文件 ({completed}/{len(files_to_download)}) {progress:.1f}%: {file_path}")
                        
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"❌ 下载文件失败 {file_path}: {e}")
            
            # 更新缓存信息
            new_cache_info = {
                'repo_updated_at': repo.updated_at.isoformat(),
                'download_method': 'incremental',
                'last_update': datetime.now().isoformat(),
                'files_sha': remote_files
            }
            
            self.save_repo_cache_info(local_path, new_cache_info)
            
            if progress_callback:
                progress_callback("✅ 增量更新完成！")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ 增量更新失败，回退到全量下载: {e}")
            return self.download_repository_full(repo, local_path, progress_callback)
    
    def download_repository_full(self, repo: Repository, local_path: str, progress_callback=None) -> bool:
        """全量下载仓库（原有方法重命名）"""
        import os
        import zipfile
        import tempfile
        import shutil
        import requests
        
        try:
            # 安全创建本地目录
            if not self.safe_create_directory(local_path):
                raise Exception(f"无法创建目录: {local_path}")
            
            # 使用 GitHub API 获取下载链接，这样更可靠
            if progress_callback:
                progress_callback("正在获取下载链接...")
            
            # 先尝试使用 PyGithub 获取 tarball URL（更可靠）
            try:
                download_url = repo.get_archive_link("zipball")
                if progress_callback:
                    progress_callback("正在下载仓库...")
                response = requests.get(download_url, stream=True, allow_redirects=True)
            except Exception:
                # 如果 API 方法失败，回退到直接URL方式
                import urllib.parse
                encoded_repo_name = urllib.parse.quote(repo.full_name, safe='/')
                encoded_branch = urllib.parse.quote(repo.default_branch)
                download_url = f"https://github.com/{encoded_repo_name}/archive/refs/heads/{encoded_branch}.zip"
                
                if progress_callback:
                    progress_callback(f"使用备用方式下载... URL: {download_url}")
                
                response = requests.get(download_url, stream=True)
                
                # 如果主分支下载失败，尝试其他常见分支
                if response.status_code == 404:
                    common_branches = ['master', 'main', 'develop', 'dev']
                    for branch in common_branches:
                        if branch != repo.default_branch:
                            encoded_branch_alt = urllib.parse.quote(branch)
                            alt_url = f"https://github.com/{encoded_repo_name}/archive/refs/heads/{encoded_branch_alt}.zip"
                            if progress_callback:
                                progress_callback(f"尝试分支 {branch}...")
                            response = requests.get(alt_url, stream=True)
                            if response.status_code == 200:
                                download_url = alt_url
                                break
            
            response.raise_for_status()
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                temp_zip_path = temp_file.name
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(f"下载进度: {progress:.1f}%")
            
            if progress_callback:
                progress_callback("正在解压文件...")
            
            # 解压 ZIP 文件
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                # 获取ZIP中的根目录名
                zip_contents = zip_ref.namelist()
                root_folder = zip_contents[0].split('/')[0] if zip_contents else ""
                
                # 解压到临时目录
                temp_extract_dir = tempfile.mkdtemp()
                zip_ref.extractall(temp_extract_dir)
                
                # 移动文件到目标目录
                if root_folder:
                    source_dir = os.path.join(temp_extract_dir, root_folder)
                    if os.path.exists(source_dir):
                        # 安全清空目标目录（全量替换）
                        if not self.safe_create_directory(local_path, clear_existing=True):
                            raise Exception(f"无法清空并重建目录: {local_path}")
                        
                        for item in os.listdir(source_dir):
                            source_item = os.path.join(source_dir, item)
                            dest_item = os.path.join(local_path, item)
                            
                            if os.path.isdir(source_item):
                                shutil.copytree(source_item, dest_item)
                            else:
                                shutil.copy2(source_item, dest_item)
                
                # 清理临时目录
                shutil.rmtree(temp_extract_dir)
            
            # 删除临时ZIP文件
            os.unlink(temp_zip_path)
            
            # 保存缓存信息
            try:
                # 计算所有文件的SHA
                files_sha = {}
                for root, dirs, files in os.walk(local_path):
                    for file in files:
                        if file == '.repo_cache.json':
                            continue
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, local_path).replace('\\', '/')
                        files_sha[rel_path] = self.calculate_file_sha(file_path)
                
                cache_info = {
                    'repo_updated_at': repo.updated_at.isoformat(),
                    'download_method': 'full',
                    'last_update': datetime.now().isoformat(),
                    'files_sha': files_sha
                }
                
                self.save_repo_cache_info(local_path, cache_info)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ 保存缓存信息失败: {e}")
            
            if progress_callback:
                progress_callback("下载完成！")
            
            return True
            
        except Exception as e:
            # 清理可能创建的临时文件
            try:
                if 'temp_zip_path' in locals() and os.path.exists(temp_zip_path):
                    os.unlink(temp_zip_path)
                if 'temp_extract_dir' in locals() and os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
            except:
                pass
            raise Exception(f"下载仓库失败: {e}") 