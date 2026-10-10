#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频按镜头切片 - 图形界面版 (Video Shot Splitter GUI)
====================================================
双击/启动即可打开窗口，选视频 -> 设参数 -> 点"开始切片"。
底层复用 split_by_shots.py 的检测与切片逻辑。
依赖：tkinter（Python 自带）+ ffmpeg（系统 PATH）+ 可选 scenedetect。
"""

import os
import sys
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _crash_handler(exc_type, exc_value, exc_tb):
    """全局未捕获异常兜底：写日志 + 弹窗，避免 pythonw 静默闪退。"""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        logp = os.path.join(SCRIPT_DIR, "gui_crash.log")
        with open(logp, "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass
    # 优先用 tk 弹窗；若 tk 自身未初始化则回退 ctypes 系统弹窗
    try:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("程序崩溃", "视频切片工具启动失败：\n\n" + msg[-1500:])
        r.destroy()
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "程序崩溃：\n" + msg[-1500:], "视频切片工具", 0x10)
        except Exception:
            pass


sys.excepthook = _crash_handler

from split_by_shots import (  # noqa: E402
    detect_scenes, filter_short_scenes, split_scenes, SENSITIVITY_PRESETS,
    scenes_by_interval, _probe,
)

# 档位中文标签 -> (preset_key, 说明)
SENS_OPTIONS = [
    ("粗 - 只抓大场景切换", "coarse"),
    ("标准 - 推荐先用这个", "normal"),
    ("精细 - 镜头切得不够碎时选", "fine"),
    ("极细 - 几乎每个画面变化都切", "finest"),
    ("不漏 - 每个转场都单独切(段数最多)", "ultra"),
]
SENS_LABEL_TO_KEY = {label: key for label, key in SENS_OPTIONS}


class LogRedirect:
    """把 print() 输出重定向到 GUI 日志区（通过队列线程安全更新）。"""

    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, text):
        if text:
            self.log_queue.put(text)

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("视频按镜头切片工具")
        self.root.geometry("640x560")
        self.root.resizable(True, True)

        self.log_queue = queue.Queue()
        self.running = False

        self._build_ui()
        self.root.after(120, self._poll_log)

    # ---------------- UI ----------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        f = ttk.Frame(self.root)
        f.pack(fill=tk.BOTH, expand=True, **pad)

        # 输入视频
        ttk.Label(f, text="视频文件").grid(row=0, column=0, sticky=tk.W, **pad)
        self.in_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.in_var, width=48).grid(row=0, column=1, **pad)
        ttk.Button(f, text="浏览…", command=self._pick_input).grid(row=0, column=2, **pad)

        # 输出目录
        ttk.Label(f, text="输出目录").grid(row=1, column=0, sticky=tk.W, **pad)
        self.out_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.out_var, width=48).grid(row=1, column=1, **pad)
        ttk.Button(f, text="浏览…", command=self._pick_output).grid(row=1, column=2, **pad)
        ttk.Label(f, text="留空=视频同目录建 视频名_shots/", font=("微软雅黑", 8), foreground="#888").grid(row=2, column=1, sticky=tk.W)

        # 检测引擎
        ttk.Label(f, text="检测引擎").grid(row=3, column=0, sticky=tk.W, **pad)
        self.method_var = tk.StringVar(value="auto")
        ttk.Combobox(f, textvariable=self.method_var, width=20,
                     values=["auto", "scenedetect", "ffmpeg"],
                     state="readonly").grid(row=3, column=1, sticky=tk.W, **pad)
        ttk.Label(f, text="auto=优先scenedetect", font=("微软雅黑", 8), foreground="#888").grid(row=4, column=1, sticky=tk.W)

        # 灵敏度档位（用档位替代裸数字，避免两引擎量纲混淆）
        ttk.Label(f, text="切分灵敏度").grid(row=5, column=0, sticky=tk.W, **pad)
        self.sens_var = tk.StringVar(value=SENS_OPTIONS[1][0])
        ttk.Combobox(f, textvariable=self.sens_var, width=28,
                     values=[label for label, _ in SENS_OPTIONS],
                     state="readonly").grid(row=5, column=1, sticky=tk.W, **pad)
        ttk.Label(f, text="嫌切得不够碎 -> 改选「精细」或「极细」",
                  font=("微软雅黑", 8), foreground="#888").grid(row=6, column=1, sticky=tk.W)

        # 最小时长
        ttk.Label(f, text="碎渣过滤(秒)").grid(row=7, column=0, sticky=tk.W, **pad)
        self.min_var = tk.StringVar(value="0.5")
        ttk.Entry(f, textvariable=self.min_var, width=20).grid(row=7, column=1, sticky=tk.W, **pad)
        ttk.Label(f, text="短于此秒数的镜头并入相邻段；0=不过滤", font=("微软雅黑", 8), foreground="#888").grid(row=8, column=1, sticky=tk.W)

        # 固定时长切分（对无硬切转场的运镜视频，比场景检测更实用）
        ttk.Label(f, text="固定时长切分(秒)").grid(row=9, column=0, sticky=tk.W, **pad)
        self.iv_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.iv_var, width=20).grid(row=9, column=1, sticky=tk.W, **pad)
        ttk.Label(f, text="留空=按镜头检测；填数字如 3 = 每3秒一段（转场不明显的视频用这个）",
                  font=("微软雅黑", 8), foreground="#888").grid(row=10, column=1, sticky=tk.W)

        # 选项
        self.copy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="极速模式(流拷贝，切点吸附关键帧)", variable=self.copy_var).grid(row=11, column=1, sticky=tk.W, **pad)
        self.list_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="仅预览镜头清单，不切片", variable=self.list_var).grid(row=12, column=1, sticky=tk.W, **pad)

        # 开始按钮
        self.start_btn = ttk.Button(f, text="开始切片", command=self._on_start)
        self.start_btn.grid(row=13, column=1, sticky=tk.W, **pad)

        # 日志
        ttk.Label(f, text="运行日志").grid(row=14, column=0, sticky=tk.NW, **pad)
        self.log = scrolledtext.ScrolledText(f, width=72, height=16, font=("Consolas", 9))
        self.log.grid(row=15, column=0, columnspan=3, sticky=tk.NSEW, **pad)
        f.rowconfigure(15, weight=1)
        f.columnconfigure(1, weight=1)

    # ---------------- 交互 ----------------
    def _pick_input(self):
        p = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频", "*.mp4 *.mkv *.mov *.avi *.flv *.wmv *.m4v *.ts"), ("全部", "*.*")])
        if p:
            self.in_var.set(p)
            if not self.out_var.get():
                self.out_var.set(os.path.splitext(p)[0] + "_shots")

    def _pick_output(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p:
            self.out_var.set(p)

    def _poll_log(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                if text == "__DONE__":
                    continue
                self.log.insert(tk.END, text)
                self.log.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_log)

    def _log(self, text):
        self.log_queue.put(text)

    def _on_start(self):
        if self.running:
            return
        in_path = self.in_var.get().strip()
        if not in_path or not os.path.exists(in_path):
            messagebox.showerror("错误", "请先选择有效的视频文件")
            return

        method = self.method_var.get()
        # 档位 -> (detector, threshold)，避免用户直接面对 27/0.4 两种量纲
        sens_key = SENS_LABEL_TO_KEY.get(self.sens_var.get(), "normal")
        detector, threshold = SENSITIVITY_PRESETS[sens_key]
        try:
            min_dur = float(self.min_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("错误", "碎渣过滤必须是一个数字(秒)")
            return

        # 防呆：不漏模式下碎渣过滤会把短镜头合并进邻段，与"每个转场都切"冲突
        if sens_key == "ultra" and min_dur > 0:
            min_dur = 0.0
            self.min_var.set("0")
            print("[info] 不漏模式已自动把碎渣过滤置 0（否则短镜头会被合并）")
        out_dir = self.out_var.get().strip() or None
        copy_mode = self.copy_var.get()
        list_only = self.list_var.get()
        try:
            interval = float(self.iv_var.get().strip()) if self.iv_var.get().strip() else None
        except ValueError:
            messagebox.showerror("错误", "固定时长切分必须是一个数字(秒)，或留空")
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.log.delete("1.0", tk.END)
        t = threading.Thread(
            target=self._worker,
            args=(in_path, out_dir, method, threshold, min_dur, copy_mode,
                  list_only, detector, interval),
            daemon=True)
        t.start()

    # ---------------- 工作线程 ----------------
    def _worker(self, in_path, out_dir, method, threshold, min_dur, copy_mode,
                list_only, detector="content", interval=None):
        self.success = False
        old_stdout = sys.stdout
        sys.stdout = LogRedirect(self.log_queue)
        try:
            if interval:
                dur, _ = _probe(in_path)
                scenes = scenes_by_interval(dur, interval)
                used = f"interval({interval}s)"
                print(f"[info] 固定时长切分: 每 {interval}s 一段  共 {len(scenes)} 段")
            else:
                print(f"[info] 灵敏度档位: {self.sens_var.get()}  -> 检测器={detector} 阈值={threshold}")
                scenes, used = detect_scenes(in_path, method, threshold, detector)
            if not scenes:
                print("[error] 未检测到任何镜头，请调整阈值或换引擎")
                return
            print(f"[info] 实际引擎: {used}  共 {len(scenes)} 个镜头")

            if min_dur > 0:
                scenes, dropped = filter_short_scenes(scenes, min_dur)
                if dropped:
                    print(f"[info] 已合并 {len(dropped)} 个碎渣镜头(<{min_dur}s) -> 余 {len(scenes)} 段")

            for i, (s, e) in enumerate(scenes, 1):
                print(f"  {i:>3}. {s:7.2f}s - {e:7.2f}s  ({e-s:6.2f}s)")

            if list_only:
                print("[info] 仅预览模式，已跳过切片")
                return

            if not out_dir:
                out_dir = os.path.splitext(os.path.basename(in_path))[0] + "_shots"
            print(f"[info] 开始切片 -> {out_dir}  ({'copy' if copy_mode else 're-encode'})")
            results = split_scenes(in_path, scenes, out_dir, copy_mode, 18)
            ok = len(results)
            print(f"\n[done] 切片完成: 成功 {ok}/{len(scenes)} 段 -> {out_dir}")
            if ok < len(scenes):
                print(f"[warn] 有 {len(scenes) - ok} 段失败，请看上方 [error] 行")
            self.success = ok > 0
        except Exception as e:  # noqa: BLE001
            print(f"[error] 运行出错: {e}")
        finally:
            sys.stdout = old_stdout
            self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        if self.success:
            messagebox.showinfo("完成", "切片完成！")
        else:
            messagebox.showwarning("结束", "未生成切片，请查看上方日志。")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.3)
    except Exception:
        pass
    App(root)
    root.mainloop()
