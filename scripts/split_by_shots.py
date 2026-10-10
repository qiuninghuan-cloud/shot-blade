#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频按镜头自动切分 (Video Shot Splitter)
=========================================
把长视频按场景/转场变化切成一段段独立小视频。

检测引擎（自动选择）：
  - PySceneDetect（内容检测，最准）： pip install scenedetect[opencv]
  - 回退 ffmpeg 内置 scene 过滤器（零额外依赖）

用法见同目录 SKILL.md。
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys


def _find_exec(name):
    """定位 ffmpeg / ffprobe：优先 PATH，否则在 WinGet 安装目录动态搜索。

    WinGet 装的 Gyan.FFmpeg 默认不写入系统 PATH（只在 WorkBuddy 等注入的
    PATH 里），双击 bat 启动时找不到，因此这里兜底去 WinGet Packages 下搜。
    """
    p = shutil.which(name)
    if p:
        return p
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        try:
            pattern = os.path.join(base, "Microsoft", "WinGet", "Packages",
                                  "*", "**", name + ".exe")
            hits = glob.glob(pattern, recursive=True)
            if hits:
                return hits[0]
        except OSError:
            # WinGet Packages 下可能有 junction/无权限目录，glob 递归会抛 WinError，
            # 不能让这种异常在模块顶层炸掉整个程序，回退即可。
            pass
    return name  # 仍找不到则保留原名，让 subprocess 报错更直观


_EXEC_CACHE = {}


def _ffmpeg():
    """懒加载 ffmpeg 路径：首次真正需要时才搜索，模块导入期不做任何文件扫描。

    （历史坑）曾在模块顶层直接 `FFMPEG = _find_exec("ffmpeg")`，导致 GUI 启动时
    必须先扫完 WinGet 目录才创建窗口，扫描慢/出错都会表现成"双击闪退"。
    """
    if "ffmpeg" not in _EXEC_CACHE:
        _EXEC_CACHE["ffmpeg"] = _find_exec("ffmpeg")
    return _EXEC_CACHE["ffmpeg"]


def _ffprobe():
    """同上，懒加载 ffprobe 路径。"""
    if "ffprobe" not in _EXEC_CACHE:
        _EXEC_CACHE["ffprobe"] = _find_exec("ffprobe")
    return _EXEC_CACHE["ffprobe"]


def _run(cmd, capture=True):
    """执行命令，返回 (returncode, stdout, stderr)。"""
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        errors="ignore",
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def _probe(input_path):
    """用 ffprobe 取视频时长(秒)与帧率。"""
    rc, out, err = _run([
        _ffprobe(), "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=r_frame_rate,avg_frame_rate",
        "-select_streams", "v:0",
        "-of", "json", input_path,
    ])
    if rc != 0:
        raise RuntimeError("ffprobe 失败: " + err)
    data = json.loads(out)
    dur = float(data.get("format", {}).get("duration", 0) or 0)
    stream = (data.get("streams") or [{}])[0]
    fr = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
    num, den = fr.split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return dur, fps


# 灵敏度档位预设：{档位名: (检测器, 阈值)}
# 经验值：ContentDetector 阈值越小切越碎；27 是官方默认，15~10 能抓出更多硬切。
SENSITIVITY_PRESETS = {
    "coarse":  ("content", 32.0),   # 粗：只抓大场景切换
    "normal":  ("content", 27.0),   # 标准：官方默认
    "fine":    ("content", 15.0),   # 精细：抓更多镜头
    "finest":  ("content", 10.0),   # 极细：几乎每个画面变化都切
    "ultra":   ("multi", 0.0),      # 不漏模式：多阈值融合，所有引擎能看见的转场都切
}

# 不漏模式融合用的阈值序列
MULTI_THRESHOLDS = [27.0, 20.0, 15.0, 12.0, 10.0, 8.0, 6.0]
MERGE_TOL = 0.20   # 相距小于此秒数的切点视为同一个转场，合并


def _build_detector(detector, threshold):
    """按名字构造 PySceneDetect 检测器对象。"""
    from scenedetect import ContentDetector, AdaptiveDetector
    if detector == "adaptive":
        # AdaptiveDetector 量纲与 ContentDetector 不同（默认 3.0），做等比换算
        return AdaptiveDetector(adaptive_threshold=max(0.5, threshold / 9.0))
    return ContentDetector(threshold=threshold)


def detect_multi(input_path, thresholds=None, tol=MERGE_TOL):
    """不漏模式：跑多个阈值，把各阈值检出的转场点合并去重。

    单一阈值检出不稳定（阈值一变边界就漂），融合后凡是任一阈值认为
    是转场的位置都切一刀 —— 宁可多切，也不漏镜头。
    """
    try:
        from scenedetect import detect, ContentDetector
    except Exception:
        return None

    thresholds = thresholds or MULTI_THRESHOLDS
    cuts = set()
    for t in thresholds:
        try:
            scene_list = detect(input_path, ContentDetector(threshold=t))
        except Exception:
            continue
        for (start_tc, _end_tc) in scene_list:
            if start_tc.seconds > 0.05:
                cuts.add(round(start_tc.seconds, 2))

    merged = []
    for c in sorted(cuts):
        if not merged or c - merged[-1] > tol:
            merged.append(c)

    dur, _ = _probe(input_path)
    bounds = [0.0] + merged + [dur]
    scenes = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e - s > 0.01:
            scenes.append((s, e))
    return scenes


def detect_scenedetect(input_path, threshold, detector="content"):
    """用 PySceneDetect 检测场景，返回 [(start_s, end_s), ...]。"""
    if detector == "multi":
        return detect_multi(input_path)

    try:
        from scenedetect import detect
    except Exception:
        return None  # 让上层回退

    try:
        scene_list = detect(input_path, _build_detector(detector, threshold))
    except Exception as e:
        print(f"[warn] PySceneDetect 检测异常，回退 ffmpeg: {e}")
        return None

    scenes = []
    for (start_tc, end_tc) in scene_list:
        scenes.append((start_tc.seconds, end_tc.seconds))
    return scenes


def detect_ffmpeg(input_path, threshold):
    """用 ffmpeg scene 过滤器检测，返回 [(start_s, end_s), ...]。"""
    rc, out, err = _run([
        _ffmpeg(), "-i", input_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ], capture=True)
    # 边界时间点在 stderr 的 showinfo 里
    log = out + err
    cuts = []
    for line in log.splitlines():
        idx = line.find("pts_time:")
        if idx != -1 and "showinfo" in line.lower():
            try:
                t = float(line[idx + len("pts_time:"):].split()[0])
                cuts.append(t)
            except ValueError:
                pass
    cuts = sorted(set(round(c, 3) for c in cuts))
    dur, _ = _probe(input_path)
    boundaries = [0.0] + cuts + [dur]
    scenes = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        if e - s > 0.01:
            scenes.append((s, e))
    return scenes


def detect_scenes(input_path, method, threshold, detector="content"):
    # 阈值缺省兜底（GUI 留空时传 None 也要安全）：两引擎量纲不同，各自给默认
    if threshold is None:
        threshold = 0.4 if method == "ffmpeg" else 27.0
    if method in ("auto", "scenedetect"):
        scenes = detect_scenedetect(input_path, threshold, detector)
        if scenes:
            return scenes, "scenedetect"
        if method == "scenedetect":
            print("[warn] 未检测到 PySceneDetect，请 pip install scenedetect[opencv]")
            return [], "none"
        print("[info] PySceneDetect 不可用，回退 ffmpeg 场景检测")
        if threshold > 1:
            # scenedetect 量级阈值(如27)不适用于 ffmpeg(0~1)，回退时重置
            threshold = 0.4
    scenes = detect_ffmpeg(input_path, threshold)
    return scenes, "ffmpeg"


def scenes_by_interval(duration, interval):
    """按固定时长切分：每 interval 秒一段，适合无硬切转场的连续运镜视频。"""
    interval = max(0.5, float(interval))
    scenes = []
    t = 0.0
    while t < duration - 0.05:
        scenes.append((t, min(t + interval, duration)))
        t += interval
    return scenes


def filter_short_scenes(scenes, min_dur):
    """丢弃/合并短于 min_dur 秒的碎渣镜头，保证时间线连续。

    策略：把过短的镜头并入其下一段（扩展下一段起点）；
    若已是最后一段则并入上一段；若全程都短则兜底保留。
    返回 (新场景列表, 被合并掉的片段列表)。
    """
    if min_dur <= 0:
        return scenes, []
    out = []
    dropped = []
    i = 0
    n = len(scenes)
    while i < n:
        s, e = scenes[i]
        if (e - s) < min_dur:
            if i + 1 < n:
                ns, ne = scenes[i + 1]
                scenes[i + 1] = (s, ne)      # 并入下一段
                dropped.append((s, e))
            elif out:
                out[-1] = (out[-1][0], e)    # 末段并入上一段
                dropped.append((s, e))
            else:
                out.append((s, e))            # 兜底
            i += 1
            continue
        out.append((s, e))
        i += 1
    return out, dropped


def split_scenes(input_path, scenes, out_dir, copy, crf):
    os.makedirs(out_dir, exist_ok=True)
    results = []
    total = len(scenes)
    for i, (start, end) in enumerate(scenes, 1):
        dur = end - start
        out_name = f"shot_{i:03d}.mp4"
        out_path = os.path.join(out_dir, out_name)
        cmd = [_ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", input_path]
        if copy:
            cmd += ["-t", f"{dur:.3f}", "-c", "copy", out_path]
        else:
            cmd += ["-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", out_path]
        rc, _, err = _run(cmd)
        if rc != 0:
            print(f"[error] 切片失败 {out_name}: {err[-300:]}")
            continue
        results.append({"file": out_name, "start": round(start, 3),
                        "end": round(end, 3), "duration": round(dur, 3)})
        print(f"  [{i:>3}/{total}] {out_name}  {start:7.2f}s - {end:7.2f}s  ({dur:6.2f}s)")
    return results


def main():
    ap = argparse.ArgumentParser(description="视频按镜头自动切分")
    ap.add_argument("input", help="输入视频路径")
    ap.add_argument("--out", default=None, help="输出目录（默认: 输入名_shots/）")
    ap.add_argument("--method", choices=["auto", "scenedetect", "ffmpeg"],
                    default="auto", help="检测引擎（默认 auto）")
    ap.add_argument("--sensitivity", choices=list(SENSITIVITY_PRESETS.keys()),
                    default=None,
                    help="灵敏度档位: coarse粗 / normal标准 / fine精细 / finest极细")
    ap.add_argument("--threshold", type=float, default=None,
                    help="灵敏度：scenedetect 默认 27，ffmpeg 默认 0.4（越小越碎）")
    ap.add_argument("--detector", choices=["content", "adaptive"], default="content",
                    help="PySceneDetect 检测器（默认 content；渐变转场可试 adaptive）")
    ap.add_argument("--interval", type=float, default=None,
                    help="按固定时长切分（秒），如 --interval 3 每3秒一段；跳过场景检测，适合无硬切的运镜视频")
    ap.add_argument("--copy", action="store_true", help="流拷贝模式（极快，切点吸附关键帧）")
    ap.add_argument("--crf", type=int, default=18, help="重编码画质(0-51, 默认18)")
    ap.add_argument("--list", action="store_true", help="只列出镜头，不切片")
    ap.add_argument("--min-duration", type=float, default=0.0,
                    help="丢弃/合并短于此秒数的碎渣镜头（默认0=不过滤，建议0.5）")
    ap.add_argument("--json", default=None, help="导出镜头清单 JSON 路径")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[error] 文件不存在: {args.input}")
        sys.exit(1)

    # 固定时长切分模式：跳过场景检测
    if args.interval:
        dur, _ = _probe(args.input)
        scenes = scenes_by_interval(dur, args.interval)
        used = f"interval({args.interval}s)"
    else:
        # 档位优先：--sensitivity 会覆盖阈值；未指定时按引擎给默认
        detector = args.detector
        if args.sensitivity:
            detector, args.threshold = SENSITIVITY_PRESETS[args.sensitivity]
        elif args.threshold is None:
            args.threshold = 27.0 if args.method != "ffmpeg" else 0.4

        print(f"[info] 检测引擎: {args.method}  检测器: {detector}  阈值: {args.threshold}")
        scenes, used = detect_scenes(args.input, args.method, args.threshold, detector)
    if not scenes:
        print("[error] 未检测到任何镜头边界，请调整 --threshold")
        sys.exit(1)

    print(f"[info] 实际引擎: {used}  共 {len(scenes)} 个镜头")

    # 碎渣过滤（合并入相邻镜头，保持时间线连续）
    if args.min_duration > 0:
        scenes, dropped = filter_short_scenes(scenes, args.min_duration)
        if dropped:
            print(f"[info] 已合并 {len(dropped)} 个碎渣镜头(<{args.min_duration}s) -> 余 {len(scenes)} 段")

    for i, (s, e) in enumerate(scenes, 1):
        print(f"  {i:>3}. {s:7.2f}s - {e:7.2f}s  ({e-s:6.2f}s)")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([{"index": i, "start": round(s, 3), "end": round(e, 3),
                        "duration": round(e - s, 3)}
                       for i, (s, e) in enumerate(scenes, 1)], f, ensure_ascii=False, indent=2)
        print(f"[info] 镜头清单已导出: {args.json}")

    if args.list:
        print("[info] --list 模式，已跳过切片")
        return

    out_dir = args.out or (os.path.splitext(os.path.basename(args.input))[0] + "_shots")
    if _ffmpeg() == "ffmpeg":
        print("[error] 未找到 ffmpeg，无法切片。请确认已安装（WinGet: Gyan.FFmpeg）并加入 PATH。")
        sys.exit(1)
    print(f"[info] 开始切片 -> {out_dir}  ({'copy' if args.copy else 're-encode'})")
    split_scenes(args.input, scenes, out_dir, args.copy, args.crf)
    print("[done] 切片完成")


if __name__ == "__main__":
    main()
