import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import threading
import base64
import hashlib
from datetime import datetime
from typing import Optional, List
from github.Repository import Repository
from github.ContentFile import ContentFile

from config import Config
from github_manager import GitHubManager


class GitHubRepoManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GitHub 仓库管理工具")
        self.root.geometry("1200x800")
        
        self.config = Config()
        self.github_manager: Optional[GitHubManager] = None
        self.current_repo: Optional[Repository] = None
        self.current_path = ""
        self.file_sha_cache = {}  # 缓存文件的 SHA 值
        
        self.setup_ui()
        self.check_token()
    
    def setup_ui(self):
        """设置UI界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部工具栏
        self.create_toolbar(main_frame)
        
        # 创建分割窗口
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 左侧面板 - 仓库列表
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        self.create_repo_panel(left_frame)
        
        # 右侧面板 - 文件浏览和编辑
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        self.create_file_panel(right_frame)
    
    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # Token 设置
        ttk.Button(toolbar, text="设置 Token", command=self.set_token).pack(side=tk.LEFT, padx=(0, 5))
        
        # 权限检查
        ttk.Button(toolbar, text="检查权限", command=self.check_permissions).pack(side=tk.LEFT, padx=(0, 5))
        
        # 用户信息
        self.user_label = ttk.Label(toolbar, text="未登录")
        self.user_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 刷新按钮
        ttk.Button(toolbar, text="刷新", command=self.refresh_repos).pack(side=tk.RIGHT)
    
    def create_repo_panel(self, parent):
        """创建仓库面板"""
        # 仓库操作按钮
        repo_buttons = ttk.Frame(parent)
        repo_buttons.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(repo_buttons, text="创建仓库", command=self.create_repo).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(repo_buttons, text="删除仓库", command=self.delete_repo).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(repo_buttons, text="编辑仓库", command=self.edit_repo).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(repo_buttons, text="执行代码", command=self.execute_code).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(repo_buttons, text="同步代码", command=self.sync_local_code).pack(side=tk.LEFT)
        
        # 仓库列表
        list_frame = ttk.LabelFrame(parent, text="仓库列表")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建 Treeview
        columns = ('name', 'description', 'private', 'updated')
        self.repo_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # 设置列
        self.repo_tree.heading('#0', text='仓库名')
        self.repo_tree.heading('name', text='全名')
        self.repo_tree.heading('description', text='描述')
        self.repo_tree.heading('private', text='私有')
        self.repo_tree.heading('updated', text='更新时间')
        
        # 设置列宽
        self.repo_tree.column('#0', width=150)
        self.repo_tree.column('name', width=200)
        self.repo_tree.column('description', width=200)
        self.repo_tree.column('private', width=50)
        self.repo_tree.column('updated', width=100)
        
        # 滚动条
        repo_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.repo_tree.yview)
        self.repo_tree.configure(yscrollcommand=repo_scrollbar.set)
        
        self.repo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        repo_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定选择事件
        self.repo_tree.bind('<<TreeviewSelect>>', self.on_repo_select)
    
    def create_file_panel(self, parent):
        """创建文件面板"""
        # 文件操作按钮
        file_buttons = ttk.Frame(parent)
        file_buttons.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_buttons, text="创建文件", command=self.create_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_buttons, text="创建文件夹", command=self.create_directory).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_buttons, text="删除文件", command=self.delete_file).pack(side=tk.LEFT, padx=(0, 5))
        # 创建上传菜单按钮
        upload_menu_button = ttk.Menubutton(file_buttons, text="上传 ▼")
        upload_menu_button.pack(side=tk.LEFT, padx=(0, 5))
        
        upload_menu = tk.Menu(upload_menu_button, tearoff=0)
        upload_menu.add_command(label="上传文件(多选)", command=self.upload_file)
        upload_menu.add_command(label="上传文件夹", command=self.upload_directory)
        upload_menu_button.config(menu=upload_menu)
        ttk.Button(file_buttons, text="下载文件", command=self.download_file).pack(side=tk.LEFT)
        
        # 路径导航
        path_frame = ttk.Frame(parent)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(path_frame, text="当前路径:").pack(side=tk.LEFT)
        self.path_label = ttk.Label(path_frame, text="/", foreground="blue")
        self.path_label.pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(path_frame, text="返回上级", command=self.go_back).pack(side=tk.RIGHT)
        
        # 创建分割窗口 - 文件列表和编辑器
        file_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        file_paned.pack(fill=tk.BOTH, expand=True)
        
        # 文件列表
        file_list_frame = ttk.LabelFrame(file_paned, text="文件列表")
        file_paned.add(file_list_frame, weight=1)
        
        # 文件树
        file_columns = ('type', 'size', 'modified')
        self.file_tree = ttk.Treeview(file_list_frame, columns=file_columns, show='tree headings')
        
        self.file_tree.heading('#0', text='文件名')
        self.file_tree.heading('type', text='类型')
        self.file_tree.heading('size', text='大小')
        self.file_tree.heading('modified', text='修改时间')
        
        self.file_tree.column('#0', width=200)
        self.file_tree.column('type', width=80)
        self.file_tree.column('size', width=100)
        self.file_tree.column('modified', width=150)
        
        file_scrollbar = ttk.Scrollbar(file_list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=file_scrollbar.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件
        self.file_tree.bind('<Double-1>', self.on_file_double_click)
        
        # 文件编辑器
        editor_frame = ttk.LabelFrame(file_paned, text="文件编辑器")
        file_paned.add(editor_frame, weight=1)
        
        # 编辑器工具栏
        editor_toolbar = ttk.Frame(editor_frame)
        editor_toolbar.pack(fill=tk.X, pady=(0, 10))
        
        self.current_file_label = ttk.Label(editor_toolbar, text="未选择文件")
        self.current_file_label.pack(side=tk.LEFT)
        
        ttk.Button(editor_toolbar, text="保存", command=self.save_file).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(editor_toolbar, text="另存为", command=self.save_as_file).pack(side=tk.RIGHT)
        
        # 文本编辑器
        self.text_editor = scrolledtext.ScrolledText(editor_frame, wrap=tk.NONE)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
    
    def check_token(self):
        """检查并验证 Token"""
        token = self.config.get_token()
        if token:
            try:
                self.github_manager = GitHubManager(token)
                user_info = self.github_manager.get_user_info()
                self.user_label.config(text=f"欢迎，{user_info['name']} ({user_info['login']})")
                self.refresh_repos()
            except Exception as e:
                messagebox.showerror("错误", f"Token 验证失败: {e}")
                self.set_token()
        else:
            self.set_token()
    
    def set_token(self):
        """设置 GitHub Token"""
        token = simpledialog.askstring("设置 Token", "请输入您的 GitHub Personal Access Token:", show='*')
        if token:
            try:
                self.github_manager = GitHubManager(token)
                user_info = self.github_manager.get_user_info()
                self.config.set_token(token)
                self.user_label.config(text=f"欢迎，{user_info['name']} ({user_info['login']})")
                self.refresh_repos()
                messagebox.showinfo("成功", "Token 设置成功！")
            except Exception as e:
                messagebox.showerror("错误", f"Token 验证失败: {e}")
    
    def check_permissions(self):
        """检查 Token 权限"""
        if not self.github_manager:
            messagebox.showwarning("警告", "请先设置 Token")
            return
        
        try:
            permissions = self.github_manager.check_token_permissions()
            
            # 创建权限检查结果对话框
            dialog = tk.Toplevel(self.root)
            dialog.title("Token 权限检查")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # 权限状态
            ttk.Label(dialog, text="Token 权限状态", font=("Arial", 12, "bold")).pack(pady=10)
            
            # 仓库访问权限
            repo_status = "✅ 有权限" if permissions['repo_access'] else "❌ 无权限"
            ttk.Label(dialog, text=f"仓库访问权限: {repo_status}").pack(pady=5)
            
            # 写入权限
            write_status = "✅ 有权限" if permissions['write_access'] else "❌ 无权限"
            ttk.Label(dialog, text=f"仓库写入权限: {write_status}").pack(pady=5)
            
            # API 限制信息
            rate_info = permissions['rate_limit']
            ttk.Label(dialog, text=f"API 限制: {rate_info['remaining']}/{rate_info['core']}").pack(pady=5)
            
            # 建议信息
            if not permissions['repo_access'] or not permissions['write_access']:
                ttk.Label(dialog, text="", height=1).pack()  # 空行
                ttk.Label(dialog, text="⚠️ 权限不足！", foreground="red", font=("Arial", 10, "bold")).pack()
                ttk.Label(dialog, text="建议重新生成 Token 并勾选以下权限:", foreground="red").pack(pady=5)
                ttk.Label(dialog, text="• repo (完整仓库访问权限)", foreground="red").pack()
                ttk.Label(dialog, text="• delete_repo (删除仓库权限)", foreground="red").pack()
                ttk.Label(dialog, text="• user (用户信息权限)", foreground="red").pack()
            else:
                ttk.Label(dialog, text="", height=1).pack()  # 空行
                ttk.Label(dialog, text="🎉 权限完整！", foreground="green", font=("Arial", 10, "bold")).pack()
                ttk.Label(dialog, text="您的 Token 具有所需的所有权限", foreground="green").pack()
            
            # 关闭按钮
            ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=20)
            
        except Exception as e:
            messagebox.showerror("错误", f"检查权限失败: {e}")
    
    def refresh_repos(self):
        """刷新仓库列表"""
        if not self.github_manager:
            return
        
        def load_repos():
            try:
                repos = self.github_manager.list_repositories()
                self.root.after(0, lambda: self.update_repo_tree(repos))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"加载仓库失败: {error_msg}"))
        
        threading.Thread(target=load_repos, daemon=True).start()
    
    def update_repo_tree(self, repos: List[Repository]):
        """更新仓库树"""
        # 清空现有项目
        for item in self.repo_tree.get_children():
            self.repo_tree.delete(item)
        
        # 添加仓库
        for repo in repos:
            self.repo_tree.insert('', tk.END, 
                                text=repo.name,
                                values=(
                                    repo.full_name,
                                    repo.description[:50] + "..." if repo.description and len(repo.description) > 50 else (repo.description or ""),
                                    "是" if repo.private else "否",
                                    repo.updated_at.strftime("%Y-%m-%d")
                                ),
                                tags=(repo.name,))
    
    def on_repo_select(self, event):
        """仓库选择事件"""
        selection = self.repo_tree.selection()
        if selection:
            item = selection[0]
            repo_name = self.repo_tree.item(item, 'text')
            self.load_repository(repo_name)
    
    def load_repository(self, repo_name: str):
        """加载仓库文件"""
        if not self.github_manager:
            return
        
        def load_repo():
            try:
                self.current_repo = self.github_manager.get_repository(repo_name)
                self.current_path = ""
                self.config.add_recent_repo(self.current_repo.full_name)
                files = self.github_manager.list_files(self.current_repo, self.current_path)
                self.root.after(0, lambda: self.update_file_tree(files))
                self.root.after(0, lambda: self.path_label.config(text="/"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"加载仓库失败: {error_msg}"))
        
        threading.Thread(target=load_repo, daemon=True).start()
    
    def update_file_tree(self, files: List[ContentFile]):
        """更新文件树"""
        # 清空现有项目
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # 添加文件和文件夹
        for file in files:
            if file.type == "dir":
                icon = "📁"
                size = "-"
            else:
                icon = "📄"
                size = f"{file.size} bytes" if file.size else "0 bytes"
            
            self.file_tree.insert('', tk.END,
                                text=f"{icon} {file.name}",
                                values=(
                                    file.type,
                                    size,
                                    "-"  # GitHub API 不提供文件修改时间
                                ),
                                tags=(file.path, file.type))
    
    def on_file_double_click(self, event):
        """文件双击事件"""
        selection = self.file_tree.selection()
        if selection:
            item = selection[0]
            file_path = self.file_tree.item(item, 'tags')[0]
            file_type = self.file_tree.item(item, 'tags')[1]
            
            if file_type == "dir":
                self.navigate_to_directory(file_path)
            else:
                self.load_file_content(file_path)
    
    def navigate_to_directory(self, path: str):
        """导航到目录"""
        if not self.current_repo:
            return
        
        def load_dir():
            try:
                files = self.github_manager.list_files(self.current_repo, path)
                self.current_path = path
                self.root.after(0, lambda: self.update_file_tree(files))
                self.root.after(0, lambda: self.path_label.config(text=f"/{path}"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"加载目录失败: {error_msg}"))
        
        threading.Thread(target=load_dir, daemon=True).start()
    
    def go_back(self):
        """返回上级目录"""
        if not self.current_repo or not self.current_path:
            return
        
        # 计算父目录路径
        if "/" in self.current_path:
            parent_path = "/".join(self.current_path.split("/")[:-1])
        else:
            parent_path = ""
        
        self.navigate_to_directory(parent_path)
    
    def load_file_content(self, file_path: str):
        """加载文件内容"""
        if not self.current_repo:
            return
        
        def load_file():
            try:
                content, sha = self.github_manager.get_file_content(self.current_repo, file_path)
                self.file_sha_cache[file_path] = sha
                self.root.after(0, lambda: self.show_file_content(file_path, content))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"加载文件失败: {error_msg}"))
        
        threading.Thread(target=load_file, daemon=True).start()
    
    def show_file_content(self, file_path: str, content: str):
        """显示文件内容"""
        self.current_file_label.config(text=f"当前文件: {file_path}")
        self.text_editor.delete(1.0, tk.END)
        self.text_editor.insert(1.0, content)
        self.current_file_path = file_path
    
    def save_file(self):
        """保存当前文件"""
        if not hasattr(self, 'current_file_path') or not self.current_repo:
            messagebox.showwarning("警告", "没有打开的文件")
            return
        
        content = self.text_editor.get(1.0, tk.END).rstrip('\n')
        file_path = self.current_file_path
        
        def save():
            try:
                sha = self.file_sha_cache.get(file_path)
                if sha:
                    self.github_manager.update_file(self.current_repo, file_path, content, sha, "Update file via GUI")
                else:
                    self.github_manager.create_file(self.current_repo, file_path, content, "Create file via GUI")
                
                self.root.after(0, lambda: messagebox.showinfo("成功", "文件保存成功"))
                # 重新加载文件列表
                self.root.after(0, lambda: self.refresh_current_directory())
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"保存文件失败: {error_msg}"))
        
        threading.Thread(target=save, daemon=True).start()
    
    def save_as_file(self):
        """另存为文件"""
        if not self.current_repo:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        # 创建另存为对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("另存为")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 显示当前位置
        current_location = f"{self.current_repo.name}/{self.current_path}" if self.current_path else self.current_repo.name
        ttk.Label(dialog, text=f"保存位置: {current_location}").pack(pady=10)
        
        # 文件名输入
        ttk.Label(dialog, text="文件名:").pack(pady=5)
        filename_entry = ttk.Entry(dialog, width=40)
        filename_entry.pack(pady=5)
        filename_entry.focus()
        
        # 如果有当前文件，提供默认文件名
        if hasattr(self, 'current_file_path'):
            default_name = self.current_file_path.split('/')[-1]
            # 添加 _copy 后缀
            if '.' in default_name:
                name, ext = default_name.rsplit('.', 1)
                default_name = f"{name}_copy.{ext}"
            else:
                default_name = f"{default_name}_copy"
            filename_entry.insert(0, default_name)
        
        def save():
            filename = filename_entry.get().strip()
            if not filename:
                messagebox.showwarning("警告", "请输入文件名")
                return
            
            # 构建完整文件路径
            if self.current_path:
                file_path = f"{self.current_path}/{filename}"
            else:
                file_path = filename
            
            content = self.text_editor.get(1.0, tk.END).rstrip('\n')
            
            def save_file_thread():
                try:
                    self.github_manager.create_or_update_file(self.current_repo, file_path, content, f"Save as {filename} via GUI")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"文件 {filename} 保存成功"))
                    self.root.after(0, lambda: self.refresh_current_directory())
                    self.root.after(0, lambda: dialog.destroy())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"保存文件失败: {error_msg}"))
            
            threading.Thread(target=save_file_thread, daemon=True).start()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="保存", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 绑定回车键
        def on_enter(event):
            save()
        
        dialog.bind('<Return>', on_enter)
    
    def create_file(self):
        """创建新文件"""
        if not self.current_repo:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新文件")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 显示当前位置
        current_location = f"{self.current_repo.name}/{self.current_path}" if self.current_path else self.current_repo.name
        ttk.Label(dialog, text=f"创建位置: {current_location}").pack(pady=10)
        
        # 文件名输入
        ttk.Label(dialog, text="文件名:").pack(pady=5)
        filename_entry = ttk.Entry(dialog, width=40)
        filename_entry.pack(pady=5)
        filename_entry.focus()
        
        # 文件内容（可选）
        ttk.Label(dialog, text="初始内容（可选）:").pack(pady=5)
        content_text = scrolledtext.ScrolledText(dialog, height=6, width=45)
        content_text.pack(pady=5)
        
        def create():
            filename = filename_entry.get().strip()
            if not filename:
                messagebox.showwarning("警告", "请输入文件名")
                return
            
            # 构建完整文件路径
            if self.current_path:
                file_path = f"{self.current_path}/{filename}"
            else:
                file_path = filename
            
            content = content_text.get(1.0, tk.END).rstrip('\n')
            
            def create_file_thread():
                try:
                    self.github_manager.create_or_update_file(self.current_repo, file_path, content, f"Create {filename} via GUI")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"文件 {filename} 创建成功"))
                    self.root.after(0, lambda: self.refresh_current_directory())
                    self.root.after(0, lambda: dialog.destroy())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"创建文件失败: {error_msg}"))
            
            threading.Thread(target=create_file_thread, daemon=True).start()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="创建", command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 绑定回车键
        def on_enter(event):
            create()
        
        dialog.bind('<Return>', on_enter)
    
    def create_directory(self):
        """创建新文件夹"""
        if not self.current_repo:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新文件夹")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 显示当前位置
        current_location = f"{self.current_repo.name}/{self.current_path}" if self.current_path else self.current_repo.name
        ttk.Label(dialog, text=f"创建位置: {current_location}", font=("Arial", 10, "bold")).pack(pady=10)
        
        # 文件夹名输入
        ttk.Label(dialog, text="文件夹名:").pack(pady=5)
        dirname_entry = ttk.Entry(dialog, width=40)
        dirname_entry.pack(pady=5)
        dirname_entry.focus()
        
        # 说明文本
        info_text = "说明：GitHub 不支持空文件夹，程序会在新文件夹中\n自动创建 .gitkeep 文件来保持目录结构。"
        ttk.Label(dialog, text=info_text, font=("Arial", 8), foreground="gray").pack(pady=10)
        
        def create():
            dirname = dirname_entry.get().strip()
            if not dirname:
                messagebox.showwarning("警告", "请输入文件夹名")
                return
            
            # 检查文件夹名是否有效
            if '/' in dirname or '\\' in dirname:
                messagebox.showwarning("警告", "文件夹名不能包含路径分隔符")
                return
            
            # 构建完整文件夹路径
            if self.current_path:
                dir_path = f"{self.current_path}/{dirname}"
            else:
                dir_path = dirname
            
            def create_directory_thread():
                try:
                    self.github_manager.create_directory(self.current_repo, dir_path, f"Create directory {dirname} via GUI")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"文件夹 {dirname} 创建成功"))
                    self.root.after(0, lambda: self.refresh_current_directory())
                    self.root.after(0, lambda: dialog.destroy())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"创建文件夹失败: {error_msg}"))
            
            threading.Thread(target=create_directory_thread, daemon=True).start()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="创建", command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 绑定回车键
        def on_enter(event):
            create()
        
        dialog.bind('<Return>', on_enter)
    
    def delete_file(self):
        """删除选中的文件"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择文件")
            return
        
        item = selection[0]
        file_path = self.file_tree.item(item, 'tags')[0]
        file_type = self.file_tree.item(item, 'tags')[1]
        
        if file_type == "dir":
            messagebox.showwarning("警告", "不能删除目录")
            return
        
        if messagebox.askyesno("确认", f"确定要删除文件 {file_path} 吗？"):
            def delete():
                try:
                    self.github_manager.delete_file(self.current_repo, file_path, "Delete file via GUI")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "文件删除成功"))
                    self.root.after(0, lambda: self.refresh_current_directory())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"删除文件失败: {error_msg}"))
            
            threading.Thread(target=delete, daemon=True).start()
    
    def upload_file(self):
        """上传文件（支持多文件选择）"""
        from tkinter import filedialog
        
        if not self.current_repo:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        file_paths = filedialog.askopenfilenames(
            title="选择要上传的文件（可多选）",
            filetypes=[
                ("所有文件", "*.*"),
                ("文本文件", "*.txt"),
                ("Python文件", "*.py"),
                ("JavaScript文件", "*.js"),
                ("HTML文件", "*.html"),
                ("CSS文件", "*.css"),
                ("Markdown文件", "*.md"),
                ("JSON文件", "*.json"),
                ("XML文件", "*.xml"),
                ("YAML文件", "*.yml;*.yaml"),
                ("配置文件", "*.conf;*.cfg;*.ini")
            ]
        )
        
        if not file_paths:
            return
        
        # 显示上传确认对话框
        self.show_upload_confirmation(file_paths)
    
    def show_upload_confirmation(self, file_paths):
        """显示上传确认对话框"""
        # 创建上传确认对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"上传文件确认 - 共 {len(file_paths)} 个文件")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 当前位置信息
        current_location = f"{self.current_repo.name}/{self.current_path}" if self.current_path else self.current_repo.name
        ttk.Label(dialog, text=f"上传到: {current_location}", font=("Arial", 12, "bold")).pack(pady=10)
        
        # 文件列表框架
        list_frame = ttk.LabelFrame(dialog, text="待上传文件列表")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 创建文件列表树
        columns = ('filename', 'size', 'status')
        file_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)
        
        file_tree.heading('#0', text='文件路径')
        file_tree.heading('filename', text='文件名')
        file_tree.heading('size', text='大小')
        file_tree.heading('status', text='状态')
        
        file_tree.column('#0', width=200)
        file_tree.column('filename', width=150)
        file_tree.column('size', width=80)
        file_tree.column('status', width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=file_tree.yview)
        file_tree.configure(yscrollcommand=scrollbar.set)
        
        file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 准备文件信息
        file_infos = []
        total_size = 0
        valid_files = 0
        
        for file_path in file_paths:
            try:
                # 尝试读取文件
                content = None
                file_size = 0
                status = "待上传"
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    file_size = len(content)
                    
                    # 检查是否会覆盖现有文件
                    filename = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
                    target_path = f"{self.current_path}/{filename}" if self.current_path else filename
                    
                    # 检查文件是否已存在
                    try:
                        existing_file = self.github_manager.get_file_content(self.current_repo, target_path)
                        status = "覆盖现有"
                    except:
                        status = "新建"
                    
                    valid_files += 1
                    total_size += file_size
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                        file_size = len(content)
                        
                        # 检查是否会覆盖现有文件
                        filename = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
                        target_path = f"{self.current_path}/{filename}" if self.current_path else filename
                        
                        try:
                            existing_file = self.github_manager.get_file_content(self.current_repo, target_path)
                            status = "覆盖现有(GBK)"
                        except:
                            status = "新建(GBK)"
                        
                        valid_files += 1
                        total_size += file_size
                    except UnicodeDecodeError:
                        status = "编码错误"
                except Exception as e:
                    status = f"读取失败: {str(e)[:20]}"
                
                filename = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
                
                file_infos.append({
                    'path': file_path,
                    'filename': filename,
                    'content': content,
                    'size': file_size,
                    'status': status
                })
                
                # 添加到树中
                size_str = f"{file_size} 字符" if file_size > 0 else "0"
                file_tree.insert('', tk.END,
                               text=file_path,
                               values=(filename, size_str, status))
                
            except Exception as e:
                filename = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
                file_tree.insert('', tk.END,
                               text=file_path,
                               values=(filename, "0", f"错误: {e}"))
        
        # 统计信息
        info_frame = ttk.Frame(dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"总计: {len(file_paths)} 个文件 | 有效: {valid_files} 个 | 总大小: {total_size} 字符").pack(side=tk.LEFT)
        
        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def start_upload():
            """开始上传"""
            if valid_files == 0:
                messagebox.showwarning("警告", "没有可上传的有效文件")
                return
            
            # 确认上传
            result = messagebox.askyesno(
                "确认上传", 
                f"确定要上传 {valid_files} 个文件吗？\n\n总大小: {total_size} 字符\n目标位置: {current_location}\n\n⚠️ 如果文件已存在，将会被覆盖！"
            )
            
            if result:
                dialog.destroy()
                self.start_batch_upload(file_infos)
        
        ttk.Button(button_frame, text=f"上传 {valid_files} 个文件", command=start_upload).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)
    
    def start_batch_upload(self, file_infos):
        """开始批量上传"""
        # 创建上传进度对话框
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("批量上传进度")
        progress_dialog.geometry("500x300")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # 进度信息
        ttk.Label(progress_dialog, text="正在上传文件...", font=("Arial", 12, "bold")).pack(pady=10)
        
        # 当前上传文件
        current_file_label = ttk.Label(progress_dialog, text="准备中...")
        current_file_label.pack(pady=5)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 统计信息
        stats_label = ttk.Label(progress_dialog, text="")
        stats_label.pack(pady=5)
        
        # 日志框
        log_frame = ttk.LabelFrame(progress_dialog, text="上传日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        log_text = scrolledtext.ScrolledText(log_frame, height=8)
        log_text.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮（初始禁用）
        close_button = ttk.Button(progress_dialog, text="关闭", command=progress_dialog.destroy, state=tk.DISABLED)
        close_button.pack(pady=10)
        
        def upload_files_thread():
            """上传文件的后台线程"""
            total_files = len([f for f in file_infos if f['content'] is not None])
            uploaded = 0
            failed = 0
            
            def update_progress(current, total, filename, status):
                progress = (current / total) * 100
                self.root.after(0, lambda: progress_var.set(progress))
                self.root.after(0, lambda: current_file_label.config(text=f"当前: {filename}"))
                self.root.after(0, lambda: stats_label.config(text=f"进度: {current}/{total} | 成功: {uploaded} | 失败: {failed}"))
                self.root.after(0, lambda: log_text.insert(tk.END, f"{status}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
            
            try:
                current = 0
                for file_info in file_infos:
                    if file_info['content'] is None:
                        continue  # 跳过无效文件
                    
                    current += 1
                    filename = file_info['filename']
                    
                    # 构建目标路径
                    if self.current_path:
                        target_path = f"{self.current_path}/{filename}"
                    else:
                        target_path = filename
                    
                    update_progress(current, total_files, filename, f"正在上传 {filename}...")
                    
                    try:
                        self.github_manager.create_or_update_file(
                            self.current_repo, 
                            target_path, 
                            file_info['content'], 
                            f"Upload {filename} via GUI (batch upload)"
                        )
                        uploaded += 1
                        update_progress(current, total_files, filename, f"✅ {filename} 上传成功")
                    except Exception as e:
                        failed += 1
                        error_msg = str(e)
                        update_progress(current, total_files, filename, f"❌ {filename} 上传失败: {error_msg}")
                
                # 上传完成
                self.root.after(0, lambda: current_file_label.config(text="上传完成"))
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n🎉 批量上传完成！成功: {uploaded}, 失败: {failed}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.refresh_current_directory())
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n💥 批量上传失败: {error_msg}\n"))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
        
        # 启动上传线程
        threading.Thread(target=upload_files_thread, daemon=True).start()
    
    def upload_directory(self):
        """上传文件夹"""
        from tkinter import filedialog
        import os
        
        if not self.current_repo:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        # 选择文件夹
        directory_path = filedialog.askdirectory(title="选择要上传的文件夹")
        
        if not directory_path:
            return
        
        # 扫描文件夹中的所有文件
        file_paths = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_paths.append(file_path)
        
        if not file_paths:
            messagebox.showinfo("提示", "选择的文件夹为空")
            return
        
        # 确认上传
        folder_name = os.path.basename(directory_path)
        result = messagebox.askyesno(
            "确认上传文件夹", 
            f"确定要上传文件夹 '{folder_name}' 吗？\n\n包含 {len(file_paths)} 个文件\n\n文件夹结构将保持不变"
        )
        
        if result:
            self.upload_directory_files(directory_path, file_paths, folder_name)
    
    def upload_directory_files(self, base_path, file_paths, folder_name):
        """上传文件夹中的所有文件"""
        import os
        
        # 创建上传进度对话框
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(f"上传文件夹: {folder_name}")
        progress_dialog.geometry("500x300")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # 进度信息
        ttk.Label(progress_dialog, text=f"正在上传文件夹: {folder_name}", font=("Arial", 12, "bold")).pack(pady=10)
        
        # 当前上传文件
        current_file_label = ttk.Label(progress_dialog, text="准备中...")
        current_file_label.pack(pady=5)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 统计信息
        stats_label = ttk.Label(progress_dialog, text="")
        stats_label.pack(pady=5)
        
        # 日志框
        log_frame = ttk.LabelFrame(progress_dialog, text="上传日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        log_text = scrolledtext.ScrolledText(log_frame, height=8)
        log_text.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮（初始禁用）
        close_button = ttk.Button(progress_dialog, text="关闭", command=progress_dialog.destroy, state=tk.DISABLED)
        close_button.pack(pady=10)
        
        def upload_directory_thread():
            """上传文件夹的后台线程"""
            uploaded = 0
            failed = 0
            total_files = len(file_paths)
            
            def update_progress(current, total, filename, status):
                progress = (current / total) * 100
                self.root.after(0, lambda: progress_var.set(progress))
                self.root.after(0, lambda: current_file_label.config(text=f"当前: {filename}"))
                self.root.after(0, lambda: stats_label.config(text=f"进度: {current}/{total} | 成功: {uploaded} | 失败: {failed}"))
                self.root.after(0, lambda: log_text.insert(tk.END, f"{status}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
            
            try:
                for i, file_path in enumerate(file_paths, 1):
                    try:
                        # 读取文件内容
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            try:
                                with open(file_path, 'r', encoding='gbk') as f:
                                    content = f.read()
                            except UnicodeDecodeError:
                                failed += 1
                                filename = os.path.basename(file_path)
                                update_progress(i, total_files, filename, f"❌ {filename} 编码错误，跳过")
                                continue
                        
                        # 计算相对路径，保持目录结构
                        rel_path = os.path.relpath(file_path, base_path)
                        rel_path = rel_path.replace('\\', '/')  # 转换为 Unix 路径格式
                        
                        # 构建目标路径
                        if self.current_path:
                            target_path = f"{self.current_path}/{folder_name}/{rel_path}"
                        else:
                            target_path = f"{folder_name}/{rel_path}"
                        
                        filename = os.path.basename(file_path)
                        update_progress(i, total_files, filename, f"正在上传 {rel_path}...")
                        
                        # 上传文件
                        self.github_manager.create_or_update_file(
                            self.current_repo, 
                            target_path, 
                            content, 
                            f"Upload {rel_path} from folder {folder_name} via GUI"
                        )
                        uploaded += 1
                        update_progress(i, total_files, filename, f"✅ {rel_path} 上传成功")
                        
                    except Exception as e:
                        failed += 1
                        filename = os.path.basename(file_path)
                        error_msg = str(e)
                        update_progress(i, total_files, filename, f"❌ {filename} 上传失败: {error_msg}")
                
                # 上传完成
                self.root.after(0, lambda: current_file_label.config(text="上传完成"))
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n🎉 文件夹上传完成！成功: {uploaded}, 失败: {failed}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.refresh_current_directory())
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n💥 文件夹上传失败: {error_msg}\n"))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
        
        # 启动上传线程
        threading.Thread(target=upload_directory_thread, daemon=True).start()
    
    def download_file(self):
        """下载选中的文件"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择文件")
            return
        
        item = selection[0]
        file_path = self.file_tree.item(item, 'tags')[0]
        file_type = self.file_tree.item(item, 'tags')[1]
        
        if file_type == "dir":
            messagebox.showwarning("警告", "不能下载目录")
            return
        
        from tkinter import filedialog
        save_path = filedialog.asksaveasfilename(initialvalue=file_path.split('/')[-1])
        
        if save_path:
            def download():
                try:
                    content, _ = self.github_manager.get_file_content(self.current_repo, file_path)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.root.after(0, lambda: messagebox.showinfo("成功", "文件下载成功"))
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"下载文件失败: {error_msg}"))
            
            threading.Thread(target=download, daemon=True).start()
    
    def refresh_current_directory(self):
        """刷新当前目录"""
        if self.current_repo:
            def refresh():
                try:
                    files = self.github_manager.list_files(self.current_repo, self.current_path)
                    self.root.after(0, lambda: self.update_file_tree(files))
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"刷新目录失败: {error_msg}"))
            
            threading.Thread(target=refresh, daemon=True).start()
    
    def create_repo(self):
        """创建新仓库"""
        if not self.github_manager:
            messagebox.showwarning("警告", "请先设置 Token")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("创建仓库")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 仓库名称
        ttk.Label(dialog, text="仓库名称:").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=5)
        
        # 描述
        ttk.Label(dialog, text="描述:").pack(pady=5)
        desc_entry = ttk.Entry(dialog, width=40)
        desc_entry.pack(pady=5)
        
        # 私有仓库
        private_var = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="私有仓库", variable=private_var).pack(pady=5)
        
        # 初始化仓库
        init_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="使用 README 初始化", variable=init_var).pack(pady=5)
        
        def create():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("警告", "请输入仓库名称")
                return
            
            def create_repo_thread():
                try:
                    self.github_manager.create_repository(
                        name=name,
                        description=desc_entry.get().strip(),
                        private=private_var.get(),
                        auto_init=init_var.get()
                    )
                    self.root.after(0, lambda: messagebox.showinfo("成功", "仓库创建成功"))
                    self.root.after(0, lambda: self.refresh_repos())
                    self.root.after(0, lambda: dialog.destroy())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"创建仓库失败: {error_msg}"))
            
            threading.Thread(target=create_repo_thread, daemon=True).start()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="创建", command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def delete_repo(self):
        """删除选中的仓库"""
        selection = self.repo_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        item = selection[0]
        repo_name = self.repo_tree.item(item, 'text')
        
        if messagebox.askyesno("确认", f"确定要删除仓库 {repo_name} 吗？\n注意：此操作不可恢复！"):
            def delete():
                try:
                    self.github_manager.delete_repository(repo_name)
                    self.root.after(0, lambda: messagebox.showinfo("成功", "仓库删除成功"))
                    self.root.after(0, lambda: self.refresh_repos())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"删除仓库失败: {error_msg}"))
            
            threading.Thread(target=delete, daemon=True).start()
    
    def edit_repo(self):
        """编辑选中的仓库"""
        selection = self.repo_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择仓库")
            return
        
        item = selection[0]
        repo_name = self.repo_tree.item(item, 'text')
        
        # 获取当前仓库信息
        try:
            repo = self.github_manager.get_repository(repo_name)
            repo_info = self.github_manager.get_repository_info(repo)
        except Exception as e:
            messagebox.showerror("错误", f"获取仓库信息失败: {e}")
            return
        
        # 创建编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑仓库 - {repo_name}")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 描述
        ttk.Label(dialog, text="描述:").pack(pady=5)
        desc_entry = ttk.Entry(dialog, width=50)
        desc_entry.pack(pady=5)
        desc_entry.insert(0, repo_info['description'])
        
        # 私有仓库
        private_var = tk.BooleanVar(value=repo_info['private'])
        ttk.Checkbutton(dialog, text="私有仓库", variable=private_var).pack(pady=5)
        
        def save():
            def update_repo_thread():
                try:
                    self.github_manager.update_repository(
                        repo_name,
                        description=desc_entry.get().strip(),
                        private=private_var.get()
                    )
                    self.root.after(0, lambda: messagebox.showinfo("成功", "仓库更新成功"))
                    self.root.after(0, lambda: self.refresh_repos())
                    self.root.after(0, lambda: dialog.destroy())
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"更新仓库失败: {error_msg}"))
            
            threading.Thread(target=update_repo_thread, daemon=True).start()
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="保存", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def execute_code(self):
        """执行选中仓库的代码"""
        selection = self.repo_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个仓库")
            return
        
        if not self.github_manager:
            messagebox.showerror("错误", "请先设置 GitHub Token")
            return
        
        item = selection[0]
        repo_name = self.repo_tree.item(item, 'text')
        
        try:
            repo = self.github_manager.get_repository(repo_name)
            self.show_execute_dialog(repo)
        except Exception as e:
            messagebox.showerror("错误", f"获取仓库失败: {e}")
    
    def show_execute_dialog(self, repo):
        """显示代码执行对话框"""
        import os
        import subprocess
        import platform
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"执行代码 - {repo.name}")
        dialog.geometry("800x700")  # 增加窗口大小
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # 创建主框架
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 仓库信息
        info_frame = ttk.LabelFrame(main_frame, text="仓库信息")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"仓库名: {repo.name}").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(info_frame, text=f"描述: {repo.description or '无描述'}").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(info_frame, text=f"语言: {repo.language or '未知'}").pack(anchor=tk.W, padx=10, pady=5)
        
        # 下载进度
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        progress_label = ttk.Label(progress_frame, text="准备下载...")
        progress_label.pack(anchor=tk.W, padx=10, pady=5)
        
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # 文件选择
        file_frame = ttk.LabelFrame(main_frame, text="选择要执行的文件")
        file_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 操作提示
        tip_label = ttk.Label(file_frame, text="请等待文件扫描完成...", foreground="blue")
        tip_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # 文件列表 - 减少高度以留出空间给按钮
        file_listbox = tk.Listbox(file_frame, height=8)
        file_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 下载选项
        download_frame = ttk.LabelFrame(main_frame, text="下载选项")
        download_frame.pack(fill=tk.X, pady=(5, 5))
        
        download_mode_var = tk.StringVar(value="smart")
        
        mode_frame = ttk.Frame(download_frame)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Radiobutton(mode_frame, text="🧠 智能模式 (推荐)", variable=download_mode_var, 
                       value="smart").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mode_frame, text="⚡ 增量更新", variable=download_mode_var, 
                       value="incremental").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mode_frame, text="🔄 完整下载", variable=download_mode_var, 
                       value="full").pack(side=tk.LEFT)
        
        ttk.Label(download_frame, text="智能模式：自动选择最优下载方式 | 增量更新：只下载变更文件 | 完整下载：重新下载所有文件", 
                 font=("TkDefaultFont", 8)).pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        # 执行命令输入
        cmd_frame = ttk.LabelFrame(main_frame, text="执行命令 (可选)")
        cmd_frame.pack(fill=tk.X, pady=(5, 5))
        
        cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=cmd_var)
        cmd_entry.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(cmd_frame, text="留空将使用默认命令执行选中文件", font=("TkDefaultFont", 8)).pack(anchor=tk.W, padx=10)
        
        # 主要操作按钮 - 放在显眼位置
        main_button_frame = ttk.LabelFrame(main_frame, text="🚀 执行操作")
        main_button_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 主执行按钮 - 更大更显眼
        execute_button = ttk.Button(main_button_frame, text="🚀 开始执行", state=tk.DISABLED)
        execute_button.pack(side=tk.LEFT, padx=10, pady=10, ipadx=20, ipady=5)
        
        # 执行状态标签
        execute_status = ttk.Label(main_button_frame, text="等待选择文件...", foreground="gray")
        execute_status.pack(side=tk.LEFT, padx=10)
        
        # 辅助功能按钮
        aux_button_frame = ttk.LabelFrame(main_frame, text="🔧 辅助功能")
        aux_button_frame.pack(fill=tk.X, pady=(0, 5))
        
        refresh_button = ttk.Button(aux_button_frame, text="🔄 重新扫描", state=tk.DISABLED)
        refresh_button.pack(side=tk.LEFT, padx=(10, 5), pady=5)
        
        test_button = ttk.Button(aux_button_frame, text="🧪 测试选择", state=tk.DISABLED)
        test_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        
        debug_button = ttk.Button(aux_button_frame, text="🔍 调试信息", state=tk.DISABLED)
        debug_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        
        # 状态日志区域 - 移到底部
        log_frame = ttk.LabelFrame(main_frame, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))
        
        log_text = scrolledtext.ScrolledText(log_frame, height=4, wrap=tk.WORD)
        log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        def add_log(message):
            """添加日志消息"""
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_message = f"[{timestamp}] {message}\n"
            log_text.insert(tk.END, log_message)
            log_text.see(tk.END)
        
        # 关闭按钮
        close_frame = ttk.Frame(main_frame)
        close_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(close_frame, text="❌ 关闭", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
        
        # 存储本地路径
        local_repo_path = None
        
        def update_progress(message):
            """更新进度显示"""
            dialog.after(0, lambda: progress_label.config(text=message))
            dialog.after(0, lambda: add_log(message))
        
        def download_and_scan():
            """下载仓库并扫描可执行文件"""
            nonlocal local_repo_path
            
            try:
                # 确定下载路径
                current_dir = os.getcwd()
                execute_dir = os.path.join(current_dir, "执行代码")
                local_repo_path = os.path.join(execute_dir, repo.name)
                
                # 开始下载
                progress_bar.start()
                
                # 根据用户选择的下载模式进行下载
                download_mode = download_mode_var.get()
                if download_mode == "smart":
                    self.github_manager.download_repository(repo, local_repo_path, update_progress)
                elif download_mode == "incremental":
                    self.github_manager.download_repository_incremental(repo, local_repo_path, update_progress)
                elif download_mode == "full":
                    self.github_manager.download_repository_full(repo, local_repo_path, update_progress)
                
                # 扫描可执行文件
                update_progress("扫描可执行文件...")
                executable_files = self.github_manager.get_executable_files(local_repo_path)
                
                # 更新文件列表
                def update_file_list():
                    file_listbox.delete(0, tk.END)
                    for file_path in executable_files:
                        file_listbox.insert(tk.END, file_path)
                    
                    if executable_files:
                        file_listbox.selection_set(0)  # 选中第一个文件
                        execute_button.config(state=tk.NORMAL)
                        refresh_button.config(state=tk.NORMAL)
                        debug_button.config(state=tk.NORMAL)
                        test_button.config(state=tk.NORMAL)
                        execute_status.config(text="✅ 准备就绪，可以执行", foreground="green")
                        tip_label.config(text="✅ 请从上方列表中选择要运行的文件，然后点击 '🚀 开始执行' 按钮", foreground="green")
                        update_progress(f"✅ 找到 {len(executable_files)} 个可执行文件，已准备就绪！")
                        add_log("📋 可执行文件列表:")
                        for i, file_path in enumerate(executable_files, 1):
                            add_log(f"  {i}. {file_path}")
                        add_log("🎯 请选择文件后点击 '🚀 开始执行' 按钮")
                        # 强制刷新界面以确保按钮显示
                        dialog.update_idletasks()
                        dialog.update()
                    else:
                        execute_status.config(text="❌ 未找到可执行文件", foreground="red")
                        tip_label.config(text="❌ 未找到可执行文件", foreground="red")
                        update_progress("未找到可执行文件")
                    
                    progress_bar.stop()
                
                dialog.after(0, update_file_list)
                
            except Exception as e:
                error_msg = str(e)  # 捕获异常信息
                def show_error():
                    progress_bar.stop()
                    
                    # 检查是否是文件锁定错误
                    if "WinError 32" in error_msg or "另一个程序正在使用此文件" in error_msg:
                        error_title = "文件被占用"
                        error_detail = f"""文件锁定错误: {error_msg}

🔧 解决方案:
1. 关闭可能打开该目录文件的程序 (如文本编辑器、资源管理器)
2. 等待几秒后重试
3. 重启程序
4. 选择 '🔄 完整下载' 模式重新下载

💡 提示: 这通常是 Windows 系统的文件锁定问题，稍后重试即可解决。"""
                    else:
                        error_title = "下载失败"
                        error_detail = f"下载仓库失败: {error_msg}"
                    
                    messagebox.showerror(error_title, error_detail)
                    progress_label.config(text="下载失败")
                
                dialog.after(0, show_error)
        
        def refresh_files():
            """重新扫描文件"""
            if local_repo_path and os.path.exists(local_repo_path):
                try:
                    executable_files = self.github_manager.get_executable_files(local_repo_path)
                    file_listbox.delete(0, tk.END)
                    for file_path in executable_files:
                        file_listbox.insert(tk.END, file_path)
                    
                    if executable_files:
                        file_listbox.selection_set(0)
                        progress_label.config(text=f"找到 {len(executable_files)} 个可执行文件")
                    else:
                        progress_label.config(text="未找到可执行文件")
                        
                except Exception as e:
                    messagebox.showerror("错误", f"扫描文件失败: {e}")
        
        def execute_selected_file():
            """执行选中的文件"""
            selection = file_listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请选择要执行的文件")
                return
            
            if not local_repo_path or not os.path.exists(local_repo_path):
                messagebox.showerror("错误", "本地仓库路径不存在")
                return
            
            selected_file = file_listbox.get(selection[0])
            file_path = os.path.join(local_repo_path, selected_file)
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                messagebox.showerror("错误", f"文件不存在: {file_path}")
                return
            
            def do_execute():
                """在后台线程中执行命令，避免UI卡死"""
                try:
                    dialog.after(0, lambda: add_log(f"📝 开始准备执行文件: {selected_file}"))
                    
                    # 获取自定义命令或使用默认命令
                    custom_cmd = cmd_var.get().strip()
                    
                    if custom_cmd:
                        # 使用自定义命令
                        cmd = custom_cmd.replace("{file}", f'"{file_path}"')
                        dialog.after(0, lambda: add_log(f"🔧 使用自定义命令: {cmd}"))
                    else:
                        # 根据文件扩展名确定默认命令
                        file_ext = os.path.splitext(selected_file)[1].lower()
                        dialog.after(0, lambda: add_log(f"🔍 检测文件类型: {file_ext}"))
                        
                        if file_ext == '.py':
                            cmd = f'python "{file_path}"'
                        elif file_ext == '.js':
                            cmd = f'node "{file_path}"'
                        elif file_ext in ['.java']:
                            # Java需要编译，这里简化处理
                            dialog.after(0, lambda: add_log("⚠️ Java文件需要先编译"))
                            dialog.after(0, lambda: messagebox.showinfo("提示", "Java文件需要先编译，建议使用自定义命令"))
                            return
                        elif file_ext in ['.sh']:
                            if platform.system() == "Windows":
                                cmd = f'bash "{file_path}"'
                            else:
                                cmd = f'bash "{file_path}"'
                        elif file_ext in ['.bat', '.cmd']:
                            cmd = f'"{file_path}"'
                        else:
                            dialog.after(0, lambda: add_log(f"❌ 不支持的文件类型: {file_ext}"))
                            dialog.after(0, lambda: messagebox.showinfo("提示", f"不支持的文件类型 {file_ext}，请使用自定义命令"))
                            return
                        
                        dialog.after(0, lambda: add_log(f"⚡ 生成默认命令: {cmd}"))
                    
                    # 在主线程中显示确认对话框
                    def show_confirm():
                        add_log("❓ 等待用户确认执行...")
                        result = messagebox.askyesno("确认执行", 
                            f"将要执行以下命令:\n{cmd}\n\n在目录: {local_repo_path}\n\n是否继续？")
                        
                        if result:
                            add_log("✅ 用户确认执行，正在启动...")
                            # 在后台线程中执行
                            threading.Thread(target=lambda: execute_command(cmd), daemon=True).start()
                        else:
                            add_log("❌ 用户取消执行")
                    
                    dialog.after(0, show_confirm)
                    
                except Exception as e:
                    error_msg = str(e)
                    dialog.after(0, lambda: add_log(f"💥 准备执行失败: {error_msg}"))
                    dialog.after(0, lambda: messagebox.showerror("错误", f"准备执行失败: {error_msg}"))
            
            def execute_command(cmd):
                """实际执行命令"""
                try:
                    dialog.after(0, lambda: add_log(f"🚀 开始执行命令: {cmd}"))
                    dialog.after(0, lambda: add_log(f"📂 工作目录: {local_repo_path}"))
                    dialog.after(0, lambda: add_log(f"💻 操作系统: {platform.system()}"))
                    
                    # 创建新的终端窗口执行命令
                    if platform.system() == "Windows":
                        # Windows 系统 - 使用更可靠的方式
                        import shlex
                        dialog.after(0, lambda: add_log("🪟 检测到Windows系统，使用CMD执行"))
                        
                        # 转换路径中的反斜杠，避免命令行解析问题
                        safe_path = local_repo_path.replace('\\', '/')
                        safe_file_path = file_path.replace('\\', '/')
                        
                        # 使用更简单的命令格式
                        terminal_cmd = f'cmd /k "cd /d "{local_repo_path}" && {cmd} && pause"'
                        dialog.after(0, lambda: add_log(f"📋 终端命令: {terminal_cmd}"))
                        
                        process = subprocess.Popen(terminal_cmd, shell=True, cwd=local_repo_path)
                        dialog.after(0, lambda: add_log(f"🆔 进程ID: {process.pid}"))
                        
                    elif platform.system() == "Darwin":
                        # macOS 系统
                        dialog.after(0, lambda: add_log("🍎 检测到macOS系统，使用Terminal执行"))
                        applescript = f'''
                        tell application "Terminal"
                            do script "cd '{local_repo_path}' && {cmd}"
                            activate
                        end tell
                        '''
                        subprocess.Popen(['osascript', '-e', applescript])
                        
                    else:
                        # Linux 系统
                        dialog.after(0, lambda: add_log("🐧 检测到Linux系统，使用gnome-terminal执行"))
                        subprocess.Popen([
                            'gnome-terminal', 
                            '--working-directory', local_repo_path,
                            '--', 'bash', '-c', f'{cmd}; echo "按任意键继续..."; read'
                        ])
                    
                    dialog.after(0, lambda: add_log("🎉 命令启动成功！请查看新打开的终端窗口"))
                    dialog.after(0, lambda: messagebox.showinfo("成功", "已在新终端窗口中启动程序"))
                    
                except Exception as e:
                    error_msg = str(e)
                    dialog.after(0, lambda: add_log(f"💥 执行失败: {error_msg}"))
                    dialog.after(0, lambda: messagebox.showerror("错误", f"执行失败: {error_msg}"))
            
            # 在后台线程中处理，避免UI卡死
            threading.Thread(target=do_execute, daemon=True).start()
        
        def show_debug_info():
            """显示调试信息"""
            selection = file_listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请先选择一个文件")
                return
            
            selected_file = file_listbox.get(selection[0])
            file_path = os.path.join(local_repo_path, selected_file)
            
            debug_info = f"""调试信息:
            
仓库名: {repo.name}
本地路径: {local_repo_path}
选中文件: {selected_file}
完整路径: {file_path}
文件存在: {os.path.exists(file_path)}
操作系统: {platform.system()}
Python版本: {platform.python_version()}
当前工作目录: {os.getcwd()}

文件列表:
"""
            
            if os.path.exists(local_repo_path):
                for root, dirs, files in os.walk(local_repo_path):
                    level = root.replace(local_repo_path, '').count(os.sep)
                    indent = ' ' * 2 * level
                    debug_info += f"{indent}{os.path.basename(root)}/\n"
                    subindent = ' ' * 2 * (level + 1)
                    for file in files:
                        debug_info += f"{subindent}{file}\n"
            
            # 创建调试信息窗口
            debug_window = tk.Toplevel(dialog)
            debug_window.title("调试信息")
            debug_window.geometry("600x400")
            
            debug_text = scrolledtext.ScrolledText(debug_window, wrap=tk.WORD)
            debug_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            debug_text.insert(tk.END, debug_info)
            debug_text.config(state=tk.DISABLED)
        
        def test_selection():
            """测试当前选择的文件"""
            selection = file_listbox.curselection()
            if not selection:
                add_log("⚠️ 请先选择一个文件")
                messagebox.showwarning("警告", "请先选择一个文件")
                return
            
            selected_file = file_listbox.get(selection[0])
            file_path = os.path.join(local_repo_path, selected_file)
            file_ext = os.path.splitext(selected_file)[1].lower()
            
            add_log(f"🧪 测试选择的文件: {selected_file}")
            add_log(f"📁 完整路径: {file_path}")
            add_log(f"📄 文件类型: {file_ext}")
            add_log(f"✅ 文件存在: {os.path.exists(file_path)}")
            
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                add_log(f"📊 文件大小: {file_size} 字节")
                
                # 预览命令
                custom_cmd = cmd_var.get().strip()
                if custom_cmd:
                    cmd = custom_cmd.replace("{file}", f'"{file_path}"')
                    add_log(f"🔧 将使用自定义命令: {cmd}")
                else:
                    if file_ext == '.py':
                        cmd = f'python "{file_path}"'
                    elif file_ext == '.js':
                        cmd = f'node "{file_path}"'
                    elif file_ext in ['.sh']:
                        cmd = f'bash "{file_path}"'
                    elif file_ext in ['.bat', '.cmd']:
                        cmd = f'"{file_path}"'
                    else:
                        cmd = "需要设置自定义命令"
                    add_log(f"⚡ 将使用默认命令: {cmd}")
                
                messagebox.showinfo("测试结果", f"文件选择正常！\n\n文件: {selected_file}\n路径: {file_path}\n命令: {cmd}")
            else:
                add_log("❌ 文件不存在！")
                messagebox.showerror("错误", f"文件不存在: {file_path}")
        
        # 绑定按钮事件
        execute_button.config(command=execute_selected_file)
        refresh_button.config(command=refresh_files)
        debug_button.config(command=show_debug_info)
        test_button.config(command=test_selection)
        
        # 初始化日志
        add_log(f"🚀 开始执行代码功能")
        add_log(f"📦 仓库: {repo.name}")
        add_log(f"🏠 本地目录: 执行代码/{repo.name}")
        
        # 启动下载线程
        threading.Thread(target=download_and_scan, daemon=True).start()
    
    def sync_local_code(self):
        """同步本地代码到GitHub仓库"""
        selection = self.repo_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个仓库")
            return
        
        if not self.github_manager:
            messagebox.showerror("错误", "请先设置 GitHub Token")
            return
        
        item = selection[0]
        repo_name = self.repo_tree.item(item, 'text')
        
        try:
            repo = self.github_manager.get_repository(repo_name)
            self.show_sync_dialog(repo)
        except Exception as e:
            messagebox.showerror("错误", f"获取仓库失败: {e}")
    
    def show_sync_dialog(self, repo):
        """显示同步代码对话框"""
        import os
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"同步代码 - {repo.name}")
        dialog.geometry("900x750")  # 增加窗口大小以确保所有元素可见
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # 创建主框架
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 仓库信息
        info_frame = ttk.LabelFrame(main_frame, text="仓库信息")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"仓库名: {repo.name}").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(info_frame, text=f"描述: {repo.description or '无描述'}").pack(anchor=tk.W, padx=10, pady=5)
        
        # 本地路径检测
        current_dir = os.getcwd()
        execute_dir = os.path.join(current_dir, "执行代码")
        local_repo_path = os.path.join(execute_dir, repo.name)
        
        path_frame = ttk.LabelFrame(main_frame, text="本地路径")
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(path_frame, text=f"本地仓库路径: {local_repo_path}").pack(anchor=tk.W, padx=10, pady=5)
        
        # 检查本地路径是否存在
        if os.path.exists(local_repo_path):
            status_text = "✅ 本地仓库存在"
            status_color = "green"
        else:
            status_text = "❌ 本地仓库不存在"
            status_color = "red"
        
        status_label = ttk.Label(path_frame, text=status_text, foreground=status_color)
        status_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # 🚀 同步操作按钮 - 放在页面顶部方便操作
        top_button_frame = ttk.LabelFrame(main_frame, text="🚀 同步操作")
        top_button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 添加一个内部框架来更好地组织按钮
        top_button_inner_frame = ttk.Frame(top_button_frame)
        top_button_inner_frame.pack(fill=tk.X, padx=10, pady=10)
        
        sync_button = ttk.Button(top_button_inner_frame, text="🚀 开始同步", state=tk.DISABLED)
        sync_button.pack(side=tk.LEFT, padx=(0, 15), ipadx=20, ipady=5)
        
        sync_status_label = ttk.Label(top_button_inner_frame, text="请先扫描文件", foreground="gray")
        sync_status_label.pack(side=tk.LEFT, padx=10)
        
        # 同步选项
        options_frame = ttk.LabelFrame(main_frame, text="同步选项")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 同步方向选择
        direction_frame = ttk.LabelFrame(options_frame, text="🔄 同步方向")
        direction_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        sync_direction_var = tk.StringVar(value="local_to_remote")
        direction_inner_frame = ttk.Frame(direction_frame)
        direction_inner_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Radiobutton(direction_inner_frame, text="📤 本地 → 远程 (上传)", variable=sync_direction_var, 
                       value="local_to_remote").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(direction_inner_frame, text="📥 远程 → 本地 (下载)", variable=sync_direction_var, 
                       value="remote_to_local").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(direction_inner_frame, text="🔄 双向同步 (智能)", variable=sync_direction_var, 
                       value="bidirectional").pack(side=tk.LEFT)
        
        # 同步模式
        sync_mode_var = tk.StringVar(value="smart")
        mode_frame = ttk.LabelFrame(options_frame, text="⚙️ 同步模式")
        mode_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        mode_inner_frame = ttk.Frame(mode_frame)
        mode_inner_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Radiobutton(mode_inner_frame, text="🧠 智能同步 (推荐)", variable=sync_mode_var, 
                       value="smart").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mode_inner_frame, text="🔄 强制覆盖", variable=sync_mode_var, 
                       value="force").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mode_inner_frame, text="📋 仅预览", variable=sync_mode_var, 
                       value="preview").pack(side=tk.LEFT)
        
        ttk.Label(mode_frame, text="智能：只同步有变化的文件 | 强制：同步所有文件 | 预览：查看将要同步的文件", 
                 font=("TkDefaultFont", 8)).pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        # 忽略文件设置
        ignore_frame = ttk.LabelFrame(options_frame, text="忽略文件配置")
        ignore_frame.pack(fill=tk.X, padx=10, pady=5)
        
        default_ignore = "*.pyc\n__pycache__/\n*.log\n.DS_Store\n.vscode/\n.idea/\nnode_modules/\n*.tmp\n*.bak"
        ignore_text = scrolledtext.ScrolledText(ignore_frame, height=4, width=70)
        ignore_text.pack(fill=tk.X, padx=5, pady=5)
        ignore_text.insert(tk.END, default_ignore)
        
        # 扫描和预览区域
        scan_frame = ttk.LabelFrame(main_frame, text="文件扫描结果")
        scan_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 扫描按钮
        scan_button_frame = ttk.Frame(scan_frame)
        scan_button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        scan_button = ttk.Button(scan_button_frame, text="🔍 扫描文件")
        scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 文件选择控制按钮
        select_all_button = ttk.Button(scan_button_frame, text="✅ 全选")
        select_all_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        select_none_button = ttk.Button(scan_button_frame, text="❌ 全不选")
        select_none_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        select_modified_button = ttk.Button(scan_button_frame, text="🔄 选择已修改")
        select_modified_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        scan_status = ttk.Label(scan_button_frame, text="点击扫描按钮开始检测文件")
        scan_status.pack(side=tk.LEFT)
        
        # 文件列表 - 添加勾选框和双向比较
        file_tree = ttk.Treeview(scan_frame, columns=('selected', 'sync_direction', 'status', 'size', 'modified'), show='tree headings', height=6)
        file_tree.heading('#0', text='文件路径')
        file_tree.heading('selected', text='✓')
        file_tree.heading('sync_direction', text='方向')
        file_tree.heading('status', text='状态')
        file_tree.heading('size', text='大小')
        file_tree.heading('modified', text='修改时间')
        
        file_tree.column('#0', width=250)
        file_tree.column('selected', width=30)
        file_tree.column('sync_direction', width=50)
        file_tree.column('status', width=100)
        file_tree.column('size', width=80)
        file_tree.column('modified', width=120)
        
        # 添加滚动条
        tree_scrollbar = ttk.Scrollbar(scan_frame, orient=tk.VERTICAL, command=file_tree.yview)
        file_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)
        
        # 绑定双击事件来切换选择状态
        def toggle_file_selection(event):
            """双击切换文件选择状态"""
            item = file_tree.selection()[0] if file_tree.selection() else None
            if item:
                current_selected = file_tree.set(item, 'selected')
                new_selected = "❌" if current_selected == "✅" else "✅"
                file_tree.set(item, 'selected', new_selected)
                update_selection_count()
        
        file_tree.bind('<Double-1>', toggle_file_selection)
        
        # 关闭按钮
        close_frame = ttk.Frame(main_frame)
        close_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(close_frame, text="❌ 关闭", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
        
        # 存储扫描结果
        scan_results = []
        
        def update_selection_count():
            """更新选择数量统计"""
            try:
                total_files = len(file_tree.get_children())
                selected_files = len([item for item in file_tree.get_children() 
                                    if file_tree.set(item, 'selected') == "✅"])
                
                scan_status.config(text=f"✅ 扫描完成：共 {total_files} 个文件，已选择 {selected_files} 个")
                
                if selected_files > 0:
                    sync_status_label.config(text=f"已选择 {selected_files} 个文件进行同步", foreground="blue")
                else:
                    sync_status_label.config(text="未选择任何文件", foreground="orange")
            except:
                pass
        
        def select_all_files():
            """全选文件"""
            for item in file_tree.get_children():
                file_tree.set(item, 'selected', "✅")
            update_selection_count()
        
        def select_none_files():
            """取消全选"""
            for item in file_tree.get_children():
                file_tree.set(item, 'selected', "❌")
            update_selection_count()
        
        def select_modified_files():
            """只选择已修改的文件"""
            for item in file_tree.get_children():
                status = file_tree.set(item, 'status')
                if status.startswith("🔄") or status.startswith("➕"):
                    file_tree.set(item, 'selected', "✅")
                else:
                    file_tree.set(item, 'selected', "❌")
            update_selection_count()
        
        # 绑定按钮事件
        select_all_button.config(command=select_all_files)
        select_none_button.config(command=select_none_files)
        select_modified_button.config(command=select_modified_files)
        
        def should_ignore_file(file_path, ignore_patterns):
            """检查文件是否应该被忽略"""
            import fnmatch
            
            patterns = [p.strip() for p in ignore_patterns.split('\n') if p.strip()]
            filename = os.path.basename(file_path)
            
            for pattern in patterns:
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(file_path, pattern):
                    return True
                # 检查目录匹配
                if pattern.endswith('/') and pattern[:-1] in file_path:
                    return True
            return False
        
        def scan_files():
            """扫描并比较本地和远程文件"""
            nonlocal scan_results
            
            try:
                scan_status.config(text="🔍 正在扫描和比较文件...")
                scan_button.config(state=tk.DISABLED)
                
                # 清空之前的结果
                for item in file_tree.get_children():
                    file_tree.delete(item)
                scan_results = []
                
                ignore_patterns = ignore_text.get(1.0, tk.END).strip()
                sync_direction = sync_direction_var.get()
                
                # 获取远程文件列表
                remote_files = {}
                remote_file_details = {}
                try:
                    scan_status.config(text="🔍 获取远程文件列表...")
                    def get_all_files(repo, path=""):
                        """递归获取所有远程文件"""
                        contents = repo.get_contents(path)
                        if not isinstance(contents, list):
                            contents = [contents]
                        
                        for content in contents:
                            if content.type == "dir":
                                get_all_files(repo, content.path)
                            else:
                                remote_files[content.path] = content.sha
                                remote_file_details[content.path] = {
                                    'size': content.size,
                                    'sha': content.sha
                                }
                    
                    get_all_files(repo)
                except Exception as e:
                    print(f"获取远程文件列表失败: {e}")
                
                scan_status.config(text="🔍 扫描本地文件...")
                
                # 存储所有文件信息（本地+远程）
                all_files = {}
                
                # 扫描本地文件
                if os.path.exists(local_repo_path):
                    for root, dirs, files in os.walk(local_repo_path):
                        for file in files:
                            local_file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(local_file_path, local_repo_path)
                            relative_path = relative_path.replace('\\', '/')
                            
                            # 检查是否应该忽略
                            if should_ignore_file(relative_path, ignore_patterns):
                                continue
                            
                            try:
                                file_stat = os.stat(local_file_path)
                                file_size = file_stat.st_size
                                file_mtime = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                                
                                # 计算本地文件SHA
                                try:
                                    with open(local_file_path, 'rb') as f:
                                        content = f.read()
                                    local_sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                                except Exception:
                                    local_sha = None
                                
                                all_files[relative_path] = {
                                    'local_path': local_file_path,
                                    'local_size': file_size,
                                    'local_mtime': file_mtime,
                                    'local_sha': local_sha,
                                    'remote_sha': remote_files.get(relative_path),
                                    'remote_size': remote_file_details.get(relative_path, {}).get('size', 0),
                                    'exists_local': True,
                                    'exists_remote': relative_path in remote_files
                                }
                            except Exception as e:
                                print(f"处理本地文件 {relative_path} 时出错: {e}")
                
                # 添加只存在于远程的文件
                for remote_path in remote_files:
                    if remote_path not in all_files and not should_ignore_file(remote_path, ignore_patterns):
                        all_files[remote_path] = {
                            'local_path': os.path.join(local_repo_path, remote_path),
                            'local_size': 0,
                            'local_mtime': '',
                            'local_sha': None,
                            'remote_sha': remote_files[remote_path],
                            'remote_size': remote_file_details.get(remote_path, {}).get('size', 0),
                            'exists_local': False,
                            'exists_remote': True
                        }
                
                scan_status.config(text="🔍 分析文件差异...")
                
                # 分析每个文件的状态和建议的同步方向
                for relative_path, file_info in all_files.items():
                    exists_local = file_info['exists_local']
                    exists_remote = file_info['exists_remote']
                    local_sha = file_info['local_sha']
                    remote_sha = file_info['remote_sha']
                    
                    # 确定文件状态和同步方向
                    if exists_local and exists_remote:
                        if local_sha == remote_sha:
                            status = "✅ 相同"
                            suggested_direction = "="
                        else:
                            status = "🔄 已修改"
                            if sync_direction == "local_to_remote":
                                suggested_direction = "↑"
                            elif sync_direction == "remote_to_local":
                                suggested_direction = "↓"
                            else:  # bidirectional
                                suggested_direction = "↕"
                    elif exists_local and not exists_remote:
                        status = "➕ 仅本地"
                        suggested_direction = "↑" if sync_direction != "remote_to_local" else "×"
                    elif not exists_local and exists_remote:
                        status = "📥 仅远程"
                        suggested_direction = "↓" if sync_direction != "local_to_remote" else "×"
                    else:
                        continue  # 不应该发生
                    
                    # 确定显示的文件大小和修改时间
                    if exists_local:
                        display_size = file_info['local_size']
                        display_mtime = file_info['local_mtime']
                    else:
                        display_size = file_info['remote_size']
                        display_mtime = "远程文件"
                    
                    # 添加到结果
                    file_data = {
                        'relative_path': relative_path,
                        'local_path': file_info['local_path'],
                        'status': status,
                        'sync_direction': suggested_direction,
                        'size': display_size,
                        'mtime': display_mtime,
                        'exists_local': exists_local,
                        'exists_remote': exists_remote,
                        'local_sha': local_sha,
                        'remote_sha': remote_sha
                    }
                    scan_results.append(file_data)
                    
                    # 添加到树视图
                    size_str = f"{display_size} bytes" if display_size < 1024 else f"{display_size/1024:.1f} KB"
                    
                    # 默认选择状态：相同的文件不选择，其他的选择
                    default_selected = "❌" if status.startswith("✅") else "✅"
                    
                    item = file_tree.insert('', tk.END,
                                           text=relative_path,
                                           values=(default_selected, suggested_direction, status, size_str, display_mtime))
                
                # 更新统计信息
                update_selection_count()
                
                # 始终启用同步按钮
                sync_button.config(state=tk.NORMAL)
                scan_button.config(state=tk.NORMAL)
                
                # 扫描完成
                files_to_sync = [f for f in scan_results if not f['status'].startswith("✅")]
                
            except Exception as e:
                scan_status.config(text="❌ 扫描失败")
                scan_button.config(state=tk.NORMAL)
                messagebox.showerror("错误", f"扫描文件失败: {e}")
        
        # 当同步方向改变时重新扫描
        def on_direction_change():
            """同步方向改变时的处理"""
            if scan_results:  # 如果已经扫描过，重新分析
                scan_files()
        
        sync_direction_var.trace('w', lambda *args: on_direction_change())
        
        def start_sync():
            """开始同步"""
            if not scan_results:
                messagebox.showwarning("警告", "请先扫描文件")
                return
            
            # 获取选中的文件
            selected_files = []
            for item in file_tree.get_children():
                if file_tree.set(item, 'selected') == "✅":
                    file_path = file_tree.item(item, 'text')
                    # 从扫描结果中找到对应的文件信息
                    for file_data in scan_results:
                        if file_data['relative_path'] == file_path:
                            selected_files.append(file_data)
                            break
            
            if not selected_files:
                messagebox.showwarning("警告", "请选择要同步的文件")
                return
            
            sync_mode = sync_mode_var.get()
            sync_direction = sync_direction_var.get()
            
            # 预览模式
            if sync_mode == "preview":
                self.show_enhanced_sync_preview(selected_files, repo, sync_direction)
                return
            
            # 过滤需要同步的文件
            if sync_mode == "smart":
                # 智能模式：只同步有差异的文件
                files_to_sync = [f for f in selected_files if not f['status'].startswith("✅")]
            else:  # force
                # 强制模式：同步所有选中的文件
                files_to_sync = selected_files
            
            if not files_to_sync:
                messagebox.showinfo("提示", "选中的文件都是最新版本，无需同步")
                return
            
            # 确认同步
            direction_name = {
                "local_to_remote": "本地 → 远程",
                "remote_to_local": "远程 → 本地",
                "bidirectional": "双向智能同步"
            }[sync_direction]
            
            mode_name = {"smart": "智能同步", "force": "强制覆盖"}[sync_mode]
            
            result = messagebox.askyesno("确认同步", 
                f"将要同步 {len(files_to_sync)} 个文件\n\n"
                f"同步方向: {direction_name}\n"
                f"同步模式: {mode_name}\n"
                f"仓库: {repo.name}\n\n"
                f"⚠️ 此操作将修改文件内容！\n\n"
                f"是否继续？")
            
            if result:
                dialog.destroy()
                self.execute_enhanced_sync(repo, files_to_sync, local_repo_path, sync_direction)
        
        # 绑定事件
        scan_button.config(command=scan_files)
        sync_button.config(command=start_sync)
        
        # 自动扫描文件
        dialog.after(500, scan_files)  # 延迟执行，等待界面加载完成
    
    def show_enhanced_sync_preview(self, selected_files, repo, sync_direction):
        """显示增强的同步预览"""
        preview_dialog = tk.Toplevel(self.root)
        preview_dialog.title(f"同步预览 - {repo.name}")
        preview_dialog.geometry("800x600")
        preview_dialog.transient(self.root)
        preview_dialog.grab_set()
        
        # 创建预览内容
        ttk.Label(preview_dialog, text=f"同步预览 - {repo.name}", font=("Arial", 14, "bold")).pack(pady=10)
        
        # 同步信息
        direction_name = {
            "local_to_remote": "本地 → 远程 (上传)",
            "remote_to_local": "远程 → 本地 (下载)",
            "bidirectional": "双向智能同步"
        }[sync_direction]
        
        info_frame = ttk.Frame(preview_dialog)
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(info_frame, text=f"同步方向: {direction_name}", font=("Arial", 12)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"选中文件: {len(selected_files)} 个", font=("Arial", 12)).pack(anchor=tk.W)
        
        # 统计信息
        stats = {
            "相同": len([f for f in selected_files if f['status'].startswith("✅")]),
            "已修改": len([f for f in selected_files if f['status'].startswith("🔄")]),
            "仅本地": len([f for f in selected_files if f['status'].startswith("➕")]),
            "仅远程": len([f for f in selected_files if f['status'].startswith("📥")])
        }
        
        stats_frame = ttk.Frame(preview_dialog)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        stats_text = " | ".join([f"{k}: {v}" for k, v in stats.items() if v > 0])
        ttk.Label(stats_frame, text=f"文件状态: {stats_text}").pack()
        
        # 详细列表
        list_frame = ttk.LabelFrame(preview_dialog, text="文件详情")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        preview_text = scrolledtext.ScrolledText(list_frame, wrap=tk.NONE)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 生成预览内容
        preview_content = f"同步预览报告\n{'='*60}\n\n"
        preview_content += f"同步方向: {direction_name}\n"
        preview_content += f"总文件数: {len(selected_files)}\n\n"
        
        for category, emoji in [("✅", "相同文件"), ("🔄", "已修改文件"), ("➕", "仅本地文件"), ("📥", "仅远程文件")]:
            category_files = [f for f in selected_files if f['status'].startswith(category)]
            if category_files:
                preview_content += f"{category} {emoji} ({len(category_files)} 个):\n"
                for f in category_files:
                    direction_symbol = f['sync_direction']
                    preview_content += f"   {direction_symbol} {f['relative_path']}\n"
                preview_content += "\n"
        
        preview_text.insert(tk.END, preview_content)
        preview_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        ttk.Button(preview_dialog, text="关闭", command=preview_dialog.destroy).pack(pady=10)
    
    def show_sync_preview(self, scan_results, repo):
        """显示同步预览"""
        preview_dialog = tk.Toplevel(self.root)
        preview_dialog.title(f"同步预览 - {repo.name}")
        preview_dialog.geometry("700x500")
        preview_dialog.transient(self.root)
        preview_dialog.grab_set()
        
        # 创建预览内容
        ttk.Label(preview_dialog, text=f"同步预览 - {repo.name}", font=("Arial", 14, "bold")).pack(pady=10)
        
        # 统计信息
        total_files = len(scan_results)
        new_files = len([f for f in scan_results if f['status'].startswith("➕")])
        modified_files = len([f for f in scan_results if f['status'].startswith("🔄")])
        unchanged_files = len([f for f in scan_results if f['status'].startswith("✅")])
        
        stats_frame = ttk.Frame(preview_dialog)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(stats_frame, text=f"总文件数: {total_files} | 新文件: {new_files} | 已修改: {modified_files} | 未变化: {unchanged_files}").pack()
        
        # 详细列表
        list_frame = ttk.LabelFrame(preview_dialog, text="文件详情")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        preview_text = scrolledtext.ScrolledText(list_frame, wrap=tk.NONE)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 生成预览内容
        preview_content = "同步预览报告\n" + "="*50 + "\n\n"
        
        if new_files > 0:
            preview_content += "➕ 新文件:\n"
            for f in scan_results:
                if f['status'].startswith("➕"):
                    preview_content += f"   {f['relative_path']}\n"
            preview_content += "\n"
        
        if modified_files > 0:
            preview_content += "🔄 已修改文件:\n"
            for f in scan_results:
                if f['status'].startswith("🔄"):
                    preview_content += f"   {f['relative_path']}\n"
            preview_content += "\n"
        
        if unchanged_files > 0:
            preview_content += "✅ 未变化文件:\n"
            for f in scan_results:
                if f['status'].startswith("✅"):
                    preview_content += f"   {f['relative_path']}\n"
        
        preview_text.insert(tk.END, preview_content)
        preview_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        ttk.Button(preview_dialog, text="关闭", command=preview_dialog.destroy).pack(pady=10)
    
    def execute_sync(self, repo, files_to_sync, local_repo_path):
        """执行同步操作"""
        # 创建同步进度对话框
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(f"同步进度 - {repo.name}")
        progress_dialog.geometry("600x400")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # 进度信息
        ttk.Label(progress_dialog, text=f"正在同步到仓库: {repo.name}", font=("Arial", 12, "bold")).pack(pady=10)
        
        # 当前操作文件
        current_file_label = ttk.Label(progress_dialog, text="准备中...")
        current_file_label.pack(pady=5)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 统计信息
        stats_label = ttk.Label(progress_dialog, text="")
        stats_label.pack(pady=5)
        
        # 日志框
        log_frame = ttk.LabelFrame(progress_dialog, text="同步日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        log_text = scrolledtext.ScrolledText(log_frame, height=10)
        log_text.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮（初始禁用）
        close_button = ttk.Button(progress_dialog, text="关闭", command=progress_dialog.destroy, state=tk.DISABLED)
        close_button.pack(pady=10)
        
        def sync_files_thread():
            """同步文件的后台线程"""
            uploaded = 0
            failed = 0
            total_files = len(files_to_sync)
            
            def update_progress(current, total, filename, status):
                progress = (current / total) * 100
                self.root.after(0, lambda: progress_var.set(progress))
                self.root.after(0, lambda: current_file_label.config(text=f"当前: {filename}"))
                self.root.after(0, lambda: stats_label.config(text=f"进度: {current}/{total} | 成功: {uploaded} | 失败: {failed}"))
                self.root.after(0, lambda: log_text.insert(tk.END, f"{status}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
            
            try:
                for i, file_info in enumerate(files_to_sync, 1):
                    try:
                        relative_path = file_info['relative_path']
                        local_file_path = file_info['local_path']
                        
                        update_progress(i, total_files, relative_path, f"正在同步 {relative_path}...")
                        
                        # 读取文件内容
                        try:
                            with open(local_file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            try:
                                with open(local_file_path, 'r', encoding='gbk') as f:
                                    content = f.read()
                            except UnicodeDecodeError:
                                # 尝试二进制模式读取并转换为base64
                                with open(local_file_path, 'rb') as f:
                                    content = base64.b64encode(f.read()).decode('utf-8')
                                    update_progress(i, total_files, relative_path, f"⚠️ {relative_path} 使用二进制模式上传")
                        
                        # 上传文件
                        self.github_manager.create_or_update_file(
                            repo, 
                            relative_path, 
                            content, 
                            f"Sync {relative_path} from local via GUI"
                        )
                        uploaded += 1
                        update_progress(i, total_files, relative_path, f"✅ {relative_path} 同步成功")
                        
                    except Exception as e:
                        failed += 1
                        error_msg = str(e)
                        update_progress(i, total_files, relative_path, f"❌ {relative_path} 同步失败: {error_msg}")
                
                # 同步完成
                self.root.after(0, lambda: current_file_label.config(text="同步完成"))
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n🎉 代码同步完成！成功: {uploaded}, 失败: {failed}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
                
                # 刷新当前目录显示
                if self.current_repo and self.current_repo.name == repo.name:
                    self.root.after(0, lambda: self.refresh_current_directory())
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n💥 同步失败: {error_msg}\n"))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
        
        # 启动同步线程
        threading.Thread(target=sync_files_thread, daemon=True).start()
    
    def execute_enhanced_sync(self, repo, files_to_sync, local_repo_path, sync_direction):
        """执行增强的同步操作"""
        # 创建同步进度对话框
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(f"同步进度 - {repo.name}")
        progress_dialog.geometry("700x500")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # 进度信息
        direction_name = {
            "local_to_remote": "本地 → 远程",
            "remote_to_local": "远程 → 本地",
            "bidirectional": "双向智能同步"
        }[sync_direction]
        
        ttk.Label(progress_dialog, text=f"正在同步: {direction_name}", font=("Arial", 12, "bold")).pack(pady=10)
        ttk.Label(progress_dialog, text=f"仓库: {repo.name}").pack(pady=5)
        
        # 当前操作文件
        current_file_label = ttk.Label(progress_dialog, text="准备中...")
        current_file_label.pack(pady=5)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 统计信息
        stats_label = ttk.Label(progress_dialog, text="")
        stats_label.pack(pady=5)
        
        # 日志框
        log_frame = ttk.LabelFrame(progress_dialog, text="同步日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        log_text = scrolledtext.ScrolledText(log_frame, height=12)
        log_text.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮（初始禁用）
        close_button = ttk.Button(progress_dialog, text="关闭", command=progress_dialog.destroy, state=tk.DISABLED)
        close_button.pack(pady=10)
        
        def enhanced_sync_thread():
            """增强的同步线程"""
            import os
            
            uploaded = 0
            downloaded = 0
            failed = 0
            total_files = len(files_to_sync)
            
            def update_progress(current, total, filename, status):
                progress = (current / total) * 100
                self.root.after(0, lambda: progress_var.set(progress))
                self.root.after(0, lambda: current_file_label.config(text=f"当前: {filename}"))
                self.root.after(0, lambda: stats_label.config(text=f"进度: {current}/{total} | 上传: {uploaded} | 下载: {downloaded} | 失败: {failed}"))
                self.root.after(0, lambda: log_text.insert(tk.END, f"{status}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
            
            try:
                for i, file_info in enumerate(files_to_sync, 1):
                    try:
                        relative_path = file_info['relative_path']
                        local_file_path = file_info['local_path']
                        exists_local = file_info['exists_local']
                        exists_remote = file_info['exists_remote']
                        
                        update_progress(i, total_files, relative_path, f"正在处理 {relative_path}...")
                        
                        # 根据同步方向和文件状态决定操作
                        if sync_direction == "local_to_remote":
                            # 本地到远程：上传文件
                            if exists_local:
                                self._upload_file_to_remote(repo, relative_path, local_file_path, update_progress, i, total_files)
                                uploaded += 1
                            else:
                                update_progress(i, total_files, relative_path, f"⚠️ {relative_path} 本地文件不存在，跳过")
                        
                        elif sync_direction == "remote_to_local":
                            # 远程到本地：下载文件
                            if exists_remote:
                                self._download_file_from_remote(repo, relative_path, local_file_path, update_progress, i, total_files)
                                downloaded += 1
                            else:
                                update_progress(i, total_files, relative_path, f"⚠️ {relative_path} 远程文件不存在，跳过")
                        
                        elif sync_direction == "bidirectional":
                            # 双向同步：智能判断
                            if exists_local and exists_remote:
                                # 都存在，比较修改时间或让用户选择
                                if file_info['status'].startswith("🔄"):
                                    # 默认上传本地版本（可以后续增加更智能的判断）
                                    self._upload_file_to_remote(repo, relative_path, local_file_path, update_progress, i, total_files)
                                    uploaded += 1
                                else:
                                    update_progress(i, total_files, relative_path, f"✅ {relative_path} 文件相同，无需同步")
                            elif exists_local and not exists_remote:
                                # 只有本地，上传
                                self._upload_file_to_remote(repo, relative_path, local_file_path, update_progress, i, total_files)
                                uploaded += 1
                            elif not exists_local and exists_remote:
                                # 只有远程，下载
                                self._download_file_from_remote(repo, relative_path, local_file_path, update_progress, i, total_files)
                                downloaded += 1
                        
                    except Exception as e:
                        failed += 1
                        error_msg = str(e)
                        update_progress(i, total_files, relative_path, f"❌ {relative_path} 同步失败: {error_msg}")
                
                # 同步完成
                self.root.after(0, lambda: current_file_label.config(text="同步完成"))
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n🎉 同步完成！上传: {uploaded}, 下载: {downloaded}, 失败: {failed}\n"))
                self.root.after(0, lambda: log_text.see(tk.END))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
                
                # 刷新当前目录显示
                if self.current_repo and self.current_repo.name == repo.name:
                    self.root.after(0, lambda: self.refresh_current_directory())
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n💥 同步失败: {error_msg}\n"))
                self.root.after(0, lambda: close_button.config(state=tk.NORMAL))
        
        # 启动同步线程
        threading.Thread(target=enhanced_sync_thread, daemon=True).start()
    
    def _upload_file_to_remote(self, repo, relative_path, local_file_path, update_progress, current, total):
        """上传文件到远程"""
        try:
            with open(local_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(local_file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(local_file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                    update_progress(current, total, relative_path, f"⚠️ {relative_path} 使用二进制模式上传")
        
        self.github_manager.create_or_update_file(
            repo, 
            relative_path, 
            content, 
            f"Upload {relative_path} via enhanced sync"
        )
        update_progress(current, total, relative_path, f"📤 {relative_path} 上传成功")
    
    def _download_file_from_remote(self, repo, relative_path, local_file_path, update_progress, current, total):
        """从远程下载文件"""
        import os
        
        try:
            # 获取远程文件内容
            content, _ = self.github_manager.get_file_content(repo, relative_path)
            
            # 确保本地目录存在
            local_dir = os.path.dirname(local_file_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            
            # 写入本地文件
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            update_progress(current, total, relative_path, f"📥 {relative_path} 下载成功")
            
        except Exception as e:
            raise Exception(f"下载失败: {e}")
    
    def quick_download_repo(self, repo, parent_dialog):
        """快速下载仓库到本地"""
        import os
        
        try:
            # 确定下载路径
            current_dir = os.getcwd()
            execute_dir = os.path.join(current_dir, "执行代码")
            local_repo_path = os.path.join(execute_dir, repo.name)
            
            # 创建下载进度对话框
            progress_dialog = tk.Toplevel(parent_dialog)
            progress_dialog.title(f"快速下载 - {repo.name}")
            progress_dialog.geometry("500x300")
            progress_dialog.transient(parent_dialog)
            progress_dialog.grab_set()
            
            # 进度信息
            ttk.Label(progress_dialog, text=f"正在下载仓库: {repo.name}", font=("Arial", 12, "bold")).pack(pady=10)
            
            progress_label = ttk.Label(progress_dialog, text="准备下载...")
            progress_label.pack(pady=5)
            
            # 进度条
            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            
            # 日志框
            log_frame = ttk.LabelFrame(progress_dialog, text="下载日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            
            log_text = scrolledtext.ScrolledText(log_frame, height=8)
            log_text.pack(fill=tk.BOTH, expand=True)
            
            # 关闭按钮
            close_button = ttk.Button(progress_dialog, text="关闭", command=progress_dialog.destroy, state=tk.DISABLED)
            close_button.pack(pady=10)
            
            def update_progress(message):
                """更新进度显示"""
                progress_dialog.after(0, lambda: progress_label.config(text=message))
                progress_dialog.after(0, lambda: log_text.insert(tk.END, f"{message}\n"))
                progress_dialog.after(0, lambda: log_text.see(tk.END))
            
            def download_thread():
                """下载线程"""
                try:
                    progress_bar.start()
                    
                    # 下载仓库
                    self.github_manager.download_repository(repo, local_repo_path, update_progress)
                    
                    # 下载完成
                    progress_dialog.after(0, lambda: progress_bar.stop())
                    progress_dialog.after(0, lambda: progress_label.config(text="下载完成！"))
                    progress_dialog.after(0, lambda: log_text.insert(tk.END, "🎉 仓库下载完成！请关闭此窗口并重新打开同步对话框。\n"))
                    progress_dialog.after(0, lambda: log_text.see(tk.END))
                    progress_dialog.after(0, lambda: close_button.config(state=tk.NORMAL))
                    
                    # 显示成功消息
                    progress_dialog.after(0, lambda: messagebox.showinfo("成功", 
                        f"仓库 {repo.name} 下载完成！\n\n"
                        f"本地路径: {local_repo_path}\n\n"
                        f"请关闭同步对话框并重新打开以刷新状态。"))
                    
                except Exception as e:
                    error_msg = str(e)
                    progress_dialog.after(0, lambda: progress_bar.stop())
                    progress_dialog.after(0, lambda: progress_label.config(text="下载失败"))
                    progress_dialog.after(0, lambda: log_text.insert(tk.END, f"❌ 下载失败: {error_msg}\n"))
                    progress_dialog.after(0, lambda: log_text.see(tk.END))
                    progress_dialog.after(0, lambda: close_button.config(state=tk.NORMAL))
                    progress_dialog.after(0, lambda: messagebox.showerror("错误", f"下载仓库失败: {error_msg}"))
            
            # 启动下载线程
            threading.Thread(target=download_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动下载失败: {e}")
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


if __name__ == "__main__":
    app = GitHubRepoManager()
    app.run() 