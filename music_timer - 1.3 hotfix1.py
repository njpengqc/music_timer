import os
import time
import glob
import threading
import datetime
import pygame
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from ttkthemes import ThemedStyle


class MusicPlayer:
    def __init__(self):
        pygame.mixer.init()
        self.current_volume = 0.7
        self.stop_event = threading.Event()
        
    def load(self, file_path):
        pygame.mixer.music.load(file_path)
        self.set_volume(self.current_volume)
        
    def play(self):
        pygame.mixer.music.play()
        
    def stop(self):
        pygame.mixer.music.stop()
        
    def set_volume(self, volume):
        self.current_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.current_volume)
        
    def is_playing(self):
        return pygame.mixer.music.get_busy()


class MusicTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("定时音乐播放器")
        self.root.geometry("900x700")
        # 设置窗口最小尺寸
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        
        # 设置窗口图标
        try:
            self.root.iconbitmap(default='music_icon.ico')
        except:
            pass
        
        # 设置主题
        self.style = ThemedStyle(self.root)
        self.style.set_theme("arc")
        
        # 自定义样式
        self.style.configure("Accent.TButton", font=("微软雅黑", 10, "bold"), foreground="#2c6fbb")
        self.style.configure("Statusbar.TFrame", background="#e0e0e0")
        self.style.configure("Statusbar.TLabel", background="#e0e0e0", font=("微软雅黑", 9))
        self.style.configure("Toolbutton", font=("微软雅黑", 9), foreground="#666666")
        self.style.configure("Readonly.TEntry", fieldbackground="#f8f8f8", foreground="#555555")
        
        # 音乐播放器实例
        self.player = MusicPlayer()
        
        # 应用状态
        self.music_files = []
        self.scheduled_tasks = []
        self.current_task = None
        self.is_playing = False
        self.current_file = ""
        self.current_remaining = 0
        self.total_duration = 0
        self.playback_thread = None
        
        # 创建UI
        self.create_widgets()
        
        # 启动定时检查线程
        self.scheduler_thread = threading.Thread(target=self.check_schedule, daemon=True)
        self.scheduler_thread.start()
        
        # 设置关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 启动状态更新时间
        self.update_status()
    
    def create_widgets(self):
        # 设置全局字体为微软雅黑，并指定默认大小
        default_font = ("微软雅黑", 10)
        self.root.option_add("*Font", default_font)
        
        # 主框架 - 添加padding确保内容不会贴边
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部控制栏
        control_bar = ttk.Frame(main_frame)
        control_bar.pack(fill=tk.X, pady=(0, 10))
        
        # 音乐文件夹选择
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=5)
        ttk.Label(folder_frame, text="音乐文件夹:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar()
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=50, 
                               state='readonly', style="Readonly.TEntry")
        folder_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(folder_frame, text="浏览", command=self.browse_folder).pack(side=tk.LEFT)
        
        # 播放设置
        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill=tk.X, pady=5)
        
        # 播放时间设置 - 使用grid布局更精确控制
        time_frame = ttk.Frame(settings_frame)
        time_frame.grid(row=0, column=0, padx=5, sticky="w")
        ttk.Label(time_frame, text="播放时间 (HH:MM:SS):").pack(side=tk.LEFT)
        now = datetime.datetime.now()
        default_time = now.strftime("%H:%M:%S")
        self.time_var = tk.StringVar(value=default_time)
        time_entry = ttk.Entry(time_frame, textvariable=self.time_var, width=10)
        time_entry.pack(side=tk.LEFT, padx=5)
        
        # 音量控制 - 使用grid布局
        volume_frame = ttk.Frame(settings_frame)
        volume_frame.grid(row=0, column=1, padx=20, sticky="w")
        ttk.Label(volume_frame, text="音量:").pack(side=tk.LEFT)
        self.volume_var = tk.DoubleVar(value=70)
        volume_scale = ttk.Scale(volume_frame, from_=0, to=100, variable=self.volume_var, 
                               orient=tk.HORIZONTAL, length=100, command=self.update_volume,
                               style="Horizontal.TScale")
        volume_scale.pack(side=tk.LEFT, padx=5)
        self.volume_label = ttk.Label(volume_frame, text="70%")
        self.volume_label.pack(side=tk.LEFT)
        
        # 播放时长设置
        duration_frame = ttk.Frame(main_frame)
        duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(duration_frame, text="播放时长 (HH:MM:SS):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="00:10:00")
        duration_entry = ttk.Entry(duration_frame, textvariable=self.duration_var, width=10)
        duration_entry.pack(side=tk.LEFT, padx=5)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="添加定时", command=self.add_schedule, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="立即播放", command=self.start_play_now).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="停止播放", command=self.stop_playback).pack(side=tk.LEFT, padx=5)
        
        # 将"关于"按钮移到控制按钮行的最右端
        ttk.Button(button_frame, text="关于", command=self.show_about, style="Toolbutton").pack(side=tk.RIGHT, padx=5)
        
        # 创建笔记本式布局 - 添加weight使它可以扩展
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 5))
        
        # 首先添加音乐文件标签页（位置调换）
        music_frame = ttk.Frame(notebook)
        notebook.add(music_frame, text="音乐文件", padding=5)
        
        # 音乐文件列表
        columns = ("filename", "duration")
        self.music_tree = ttk.Treeview(music_frame, columns=columns, show="headings", style="Treeview")
        self.music_tree.heading("filename", text="音乐文件")
        self.music_tree.heading("duration", text="时长")
        self.music_tree.column("filename", width=500, anchor=tk.W)
        self.music_tree.column("duration", width=150, anchor=tk.CENTER)
        
        # 添加滚动条 - 使用grid布局
        music_scrollbar = ttk.Scrollbar(music_frame, orient=tk.VERTICAL, command=self.music_tree.yview)
        self.music_tree.configure(yscrollcommand=music_scrollbar.set)
        
        # 使用grid布局并设置权重
        self.music_tree.grid(row=0, column=0, sticky="nsew")
        music_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # 设置frame的grid行列权重
        music_frame.grid_rowconfigure(0, weight=1)
        music_frame.grid_columnconfigure(0, weight=1)
        
        # 然后添加定时任务标签页（位置调换）
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="定时任务", padding=5)
        
        # 定时任务列表
        columns = ("time", "duration", "status")
        self.schedule_tree = ttk.Treeview(schedule_frame, columns=columns, show="headings", style="Treeview")
        self.schedule_tree.heading("time", text="播放时间")
        self.schedule_tree.heading("duration", text="播放时长")
        self.schedule_tree.heading("status", text="状态")
        self.schedule_tree.column("time", width=200, anchor=tk.CENTER)
        self.schedule_tree.column("duration", width=150, anchor=tk.CENTER)
        self.schedule_tree.column("status", width=150, anchor=tk.CENTER)
        
        # 添加滚动条 - 使用grid布局更精确
        tree_scrollbar = ttk.Scrollbar(schedule_frame, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # 使用grid布局并设置权重
        self.schedule_tree.grid(row=0, column=0, sticky="nsew")
        tree_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # 设置frame的grid行列权重
        schedule_frame.grid_rowconfigure(0, weight=1)
        schedule_frame.grid_columnconfigure(0, weight=1)
        
        # 创建右键菜单
        self.create_context_menus()
        
        # 底部状态栏 - 使用固定高度
        status_bar = ttk.Frame(self.root, height=24, style="Statusbar.TFrame")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="就绪 | 系统时间: " + datetime.datetime.now().strftime('%H:%M:%S'))
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var, 
                                    relief=tk.SUNKEN, anchor=tk.W, padding=(3, 3, 3, 3),
                                    style="Statusbar.TLabel")
        self.status_label.pack(fill=tk.X, expand=True)
        
        # 设置主框架内部元素的权重
        main_frame.grid_rowconfigure(0, weight=0)  # 控制栏
        main_frame.grid_rowconfigure(1, weight=0)  # 文件夹选择
        main_frame.grid_rowconfigure(2, weight=0)  # 设置区域
        main_frame.grid_rowconfigure(3, weight=0)  # 时长设置
        main_frame.grid_rowconfigure(4, weight=0)  # 按钮区域
        main_frame.grid_rowconfigure(5, weight=1)  # 笔记本区域
    
    def create_context_menus(self):
        # 音乐文件列表右键菜单
        self.music_context_menu = tk.Menu(self.root, tearoff=0)
        self.music_context_menu.add_command(label="上移", command=lambda: self.move_item(self.music_tree, -1))
        self.music_context_menu.add_command(label="下移", command=lambda: self.move_item(self.music_tree, 1))
        self.music_context_menu.add_separator()
        self.music_context_menu.add_command(label="删除", command=lambda: self.delete_item(self.music_tree))
        
        # 定时任务列表右键菜单
        self.schedule_context_menu = tk.Menu(self.root, tearoff=0)
        self.schedule_context_menu.add_command(label="删除", command=lambda: self.delete_item(self.schedule_tree))
        
        # 绑定右键事件
        self.music_tree.bind("<Button-3>", self.show_music_context_menu)
        self.schedule_tree.bind("<Button-3>", self.show_schedule_context_menu)
    
    def show_music_context_menu(self, event):
        item = self.music_tree.identify_row(event.y)
        if item:
            self.music_tree.selection_set(item)
            self.music_context_menu.post(event.x_root, event.y_root)
    
    def show_schedule_context_menu(self, event):
        item = self.schedule_tree.identify_row(event.y)
        if item:
            self.schedule_tree.selection_set(item)
            self.schedule_context_menu.post(event.x_root, event.y_root)
    
    def move_item(self, treeview, direction):
        selected = treeview.selection()
        if not selected:
            return
            
        selected_item = selected[0]
        items = list(treeview.get_children())
        
        try:
            index = items.index(selected_item)
            new_index = index + direction
            
            if 0 <= new_index < len(items):
                # 移动列表中的项目
                if treeview == self.music_tree:
                    self.music_files[index], self.music_files[new_index] = \
                        self.music_files[new_index], self.music_files[index]
                
                # 移动Treeview中的项目
                treeview.move(selected_item, "", new_index)
        except ValueError:
            pass
    
    def delete_item(self, treeview):
        selected = treeview.selection()
        if not selected:
            return
            
        selected_item = selected[0]
        items = list(treeview.get_children())
        index = items.index(selected_item)
        
        if treeview == self.music_tree and index < len(self.music_files):
            del self.music_files[index]
        
        treeview.delete(selected_item)
    
    def update_volume(self, value):
        volume = float(value) / 100.0
        self.player.set_volume(volume)
        self.volume_label.config(text=f"{int(self.volume_var.get())}%")
    
    def update_status(self):
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        
        if self.is_playing:
            hours, remainder = divmod(self.current_remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            status_text = (f"播放中: {self.current_file} | "
                          f"剩余时间: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d} | "
                          f"系统时间: {current_time}")
        else:
            status_text = f"就绪 | 系统时间: {current_time}"
            
        self.status_var.set(status_text)
        self.root.after(1000, self.update_status)
    
    def browse_folder(self):
        folder_path = filedialog.askdirectory(title="选择音乐文件夹")
        if folder_path:
            self.folder_var.set(folder_path)
            self.scan_music_folder(folder_path)
    
    def scan_music_folder(self, folder_path):
        self.music_files = []
        supported_extensions = ('*.mp3', '*.flac', '*.wav')
        
        for ext in supported_extensions:
            self.music_files.extend(glob.glob(os.path.join(folder_path, ext)))
        
        if not self.music_files:
            self.show_error(f"在 '{folder_path}' 中未找到支持的音乐文件")
            return
        
        # 清空当前列表
        for item in self.music_tree.get_children():
            self.music_tree.delete(item)
        
        # 加载有效音乐文件
        valid_files = []
        for i, file_path in enumerate(self.music_files):
            duration = self.get_music_duration(file_path)
            if duration is not None:
                filename = os.path.basename(file_path)
                formatted_duration = self.format_duration(duration)
                # 添加条纹效果
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                self.music_tree.insert("", "end", values=(filename, formatted_duration), tags=(tag,))
                valid_files.append(file_path)
        
        self.music_files = valid_files
        
        if len(valid_files) < len(self.music_files):
            self.show_warning("部分文件不支持或已损坏，已自动过滤")
    
    def get_music_duration(self, file_path):
        try:
            if file_path.lower().endswith('.mp3'):
                audio = MP3(file_path)
            elif file_path.lower().endswith('.flac'):
                audio = FLAC(file_path)
            elif file_path.lower().endswith('.wav'):
                audio = WAVE(file_path)
            else:
                return None
            return int(audio.info.length)
        except Exception:
            return None
    
    def format_duration(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def parse_time(self, time_str):
        try:
            h, m, s = map(int, time_str.split(':'))
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                raise ValueError
            return h, m, s
        except (ValueError, AttributeError):
            self.show_error("时间格式错误，请使用 HH:MM:SS 格式")
            return None
    
    def parse_duration(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 2:  # 只有分:秒
                h, m, s = 0, parts[0], parts[1]
            elif len(parts) == 3:  # 时:分:秒
                h, m, s = parts
            else:
                raise ValueError
            
            if not (0 <= m <= 59 and 0 <= s <= 59):
                raise ValueError
                
            return h * 3600 + m * 60 + s
        except (ValueError, AttributeError):
            self.show_error("时长格式错误，请使用 HH:MM:SS 或 MM:SS 格式")
            return None
    
    def add_schedule(self):
        if not self.music_files:
            self.show_error("请先选择音乐文件夹并扫描音乐文件!")
            return
            
        time_parts = self.parse_time(self.time_var.get())
        if time_parts is None:
            return
            
        duration_seconds = self.parse_duration(self.duration_var.get())
        if duration_seconds is None:
            return
            
        # 计算目标时间
        now = datetime.datetime.now()
        target_time = now.replace(hour=time_parts[0], minute=time_parts[1], second=time_parts[2])
        
        # 如果目标时间已经过去，设置为明天
        if target_time < now:
            target_time += datetime.timedelta(days=1)
            
        # 添加到任务列表
        task_id = len(self.scheduled_tasks) + 1
        task = {
            'id': task_id,
            'time': target_time.strftime("%H:%M:%S"),
            'date': target_time.strftime("%Y-%m-%d"),
            'datetime': target_time,
            'duration': self.format_duration(duration_seconds),
            'duration_seconds': duration_seconds,
            'status': '等待中'
        }
        self.scheduled_tasks.append(task)
        
        # 更新UI
        # 添加条纹效果
        tag = 'evenrow' if len(self.scheduled_tasks) % 2 == 0 else 'oddrow'
        self.schedule_tree.insert("", "end", 
                                values=(f"{task['date']} {task['time']}", 
                                        task['duration'], 
                                        task['status']),
                                tags=(tag,))
        
        self.show_info(f"已添加定时任务: {task['date']} {task['time']} 播放 {task['duration']}")
    
    def check_schedule(self):
        while True:
            now = datetime.datetime.now()
            
            for task in self.scheduled_tasks[:]:  # 使用副本遍历
                if task['status'] == '等待中' and now >= task['datetime']:
                    task['status'] = '执行中'
                    self.current_task = task
                    
                    # 更新UI
                    for item in self.schedule_tree.get_children():
                        if self.schedule_tree.item(item, 'values')[0] == f"{task['date']} {task['time']}":
                            self.schedule_tree.item(item, values=(
                                f"{task['date']} {task['time']}", 
                                task['duration'], 
                                task['status']))
                            break
                    
                    # 开始播放
                    self.start_playback(task['duration_seconds'])
            
            # 清理已完成的任务
            self.scheduled_tasks = [t for t in self.scheduled_tasks if t['status'] != '已完成']
            time.sleep(1)
    
    def start_play_now(self):
        if not self.music_files:
            self.show_error("请先选择音乐文件夹并扫描音乐文件!")
            return
            
        if self.is_playing:
            self.show_error("音乐正在播放中!")
            return
            
        duration_seconds = self.parse_duration(self.duration_var.get())
        if duration_seconds is None:
            return
            
        self.start_playback(duration_seconds)
    
    def start_playback(self, duration_seconds):
        # 重置播放状态
        self.player.stop_event.clear()
        
        self.total_duration = duration_seconds
        self.current_remaining = duration_seconds
        self.is_playing = True
        
        # 在后台线程中播放音乐
        self.playback_thread = threading.Thread(target=self.play_music_sequence, args=(duration_seconds,), daemon=True)
        self.playback_thread.start()
    
    def play_music_sequence(self, duration_seconds):
        try:
            total_played = 0
            start_time = time.time()
            
            for file_path in self.music_files:
                if self.player.stop_event.is_set() or total_played >= duration_seconds:
                    break
                    
                # 获取音乐时长
                music_duration = self.get_music_duration(file_path)
                if music_duration is None:
                    continue
                
                # 计算剩余时间和本次播放时长
                remaining_time = duration_seconds - total_played
                play_duration = min(music_duration, remaining_time)
                
                # 设置当前播放文件
                self.current_file = os.path.basename(file_path)
                
                # 加载并播放音乐
                self.player.load(file_path)
                self.player.play()
                
                # 更新播放状态
                while (time.time() - start_time) < total_played + play_duration:
                    if self.player.stop_event.is_set():
                        self.player.stop()
                        return
                    
                    elapsed = time.time() - start_time
                    self.current_remaining = max(0, duration_seconds - elapsed)
                    time.sleep(0.1)
                
                total_played += play_duration
            
            # 播放完成
            if not self.player.stop_event.is_set():
                self.show_info("播放完成")
            
        except Exception as e:
            self.show_error(f"播放时出现错误: {str(e)}")
            
        finally:
            self.stop_playback()
    
    def stop_playback(self):
        self.is_playing = False
        self.player.stop_event.set()
        self.player.stop()
        self.current_remaining = 0
        
        # 更新当前任务状态
        if self.current_task:
            self.current_task['status'] = '已完成'
            self.current_task = None
    
    def show_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("关于")
        about_window.geometry("500x600")
        about_window.resizable(False, False)
        
        # 应用相同主题
        ThemedStyle(about_window).set_theme("arc")
        
        # 主框架
        main_frame = ttk.Frame(about_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 应用图标和标题
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 添加应用图标（使用标签代替）
        icon_label = ttk.Label(header_frame, text="🎵", font=("Arial", 24))
        icon_label.pack(side=tk.LEFT, padx=(0, 15))
        
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(title_frame, text="定时音乐播放器", font=("微软雅黑", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(title_frame, text="版本 1.3 hotfix1", font=("微软雅黑", 10), foreground="#666666").pack(anchor=tk.W)
        
        # 信息卡片
        card = ttk.LabelFrame(main_frame, text="应用信息", padding=10)
        card.pack(fill=tk.X, pady=5)
        
        # 信息行
        def create_info_row(parent, label, value):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label + ":", width=10, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(row, text=value, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
            return row
        
        create_info_row(card, "作者", "luckypqc")
        create_info_row(card, "版权", "© 2020-2025")
        create_info_row(card, "邮箱", "njpengyo@qq.com")
        
        # 更新日志卡片
        log_card = ttk.LabelFrame(main_frame, text="更新日志(仅展示版本内日志)", padding=10)
        log_card.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建文本框用于显示日志
        log_frame = ttk.Frame(log_card)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_text = tk.Text(log_frame, wrap=tk.WORD, height=10, padx=5, pady=5,
                          font=("微软雅黑", 9), bg="#f8f8f8", relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(log_frame, command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        logs = [
            "版本 1.3 hotfix1:",
            "  - 适配了全新的现代化主题",
            "",
            "版本 1.3:",
            "  - 重构了UI界面",
            "  - 添加了右键绑定",
            "  - 优化了操作逻辑",
            "  - 更改了ICO样式",
            "  - 增加了一点屎山代码",
            "  - 修复了一些已知问题"
        ]
        
        log_text.insert(tk.END, "\n".join(logs))
        log_text.configure(state=tk.DISABLED)  # 设置为只读
        
        ttk.Label(main_frame, text="祝你在这个版本能用得开心 (˘•ω•˘)◞⁽˙³˙⁾", 
                 font=("微软雅黑", 9), foreground="#2c6fbb").pack(pady=(10, 5))
        
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=about_window.destroy, width=15).pack(pady=10)
        
        # 窗口居中
        about_window.update_idletasks()
        width = about_window.winfo_width()
        height = about_window.winfo_height()
        x = (about_window.winfo_screenwidth() // 2) - (width // 2)
        y = (about_window.winfo_screenheight() // 2) - (height // 2)
        about_window.geometry(f"+{x}+{y}")
    
    def show_error(self, message):
        messagebox.showerror("错误", message)
    
    def show_info(self, message):
        messagebox.showinfo("信息", message)
    
    def show_warning(self, message):
        messagebox.showwarning("警告", message)
    
    def on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出定时音乐播放器吗？"):
            self.stop_playback()
            pygame.mixer.quit()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicTimerApp(root)
    root.mainloop()
