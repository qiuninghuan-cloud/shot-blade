# -*- coding: utf-8 -*-
"""双击自检：逐项检查 GUI 启动所需依赖，把结果打印出来并写入 selftest.log。

用法：双击 run_gui_diagnose.bat。若某项 [FAIL]，把报错发我即可定位。
"""
import os
import sys
import traceback

SD = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(SD, "selftest.log")
lines = []


def rec(ok, msg):
    line = ("[OK]   " if ok else "[FAIL] ") + msg
    lines.append(line)
    print(line)


rec(True, "Python %s  (%s)" % (sys.version.split()[0], sys.executable))

# 1) tkinter 能否创建窗口
try:
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    r.update()
    r.destroy()
    rec(True, "tkinter 可创建窗口 (TkVersion %s)" % tk.TkVersion)
except Exception:
    rec(False, "tkinter 创建窗口失败:\n" + traceback.format_exc())

# 2) split_by_shots 能否导入（导入期不应做任何文件扫描）
m = None
try:
    if SD not in sys.path:
        sys.path.insert(0, SD)
    import split_by_shots as m
    rec(True, "split_by_shots 导入成功（导入期无文件扫描）")
except Exception:
    rec(False, "split_by_shots 导入失败:\n" + traceback.format_exc())

# 3) scenedetect 是否可用
try:
    import scenedetect
    rec(True, "scenedetect 可用 (v%s)" % scenedetect.__version__)
except Exception:
    rec(False, "scenedetect 不可用:\n" + traceback.format_exc())

# 4) ffmpeg / ffprobe 定位（懒加载，此处才真正搜索）
if m is not None:
    try:
        p = m._ffmpeg()
        rec(os.path.exists(p), "ffmpeg 定位: " + str(p))
    except Exception:
        rec(False, "ffmpeg 定位失败:\n" + traceback.format_exc())
    try:
        q = m._ffprobe()
        rec(os.path.exists(q), "ffprobe 定位: " + str(q))
    except Exception:
        rec(False, "ffprobe 定位失败:\n" + traceback.format_exc())

# 5) 是否有上次崩溃记录
cl = os.path.join(SD, "gui_crash.log")
if os.path.exists(cl):
    try:
        txt = open(cl, encoding="utf-8", errors="ignore").read()[:1500]
    except Exception:
        txt = "(读取失败)"
    rec(False, "发现 gui_crash.log（上次 Python 层崩溃）：\n" + txt)
else:
    rec(True, "无 gui_crash.log（Python 层面未记录到崩溃）")

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("")
print("自检结果已写入: " + LOG)
print("请把以上内容截图或复制发给开发者。")
