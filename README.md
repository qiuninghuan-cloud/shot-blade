# 分镜刀 ShotBlade

**一刀下去就是一个镜头。**

把一整个视频按「镜头 / 场景转场」自动切成一段段独立的小视频文件——录像、课程、直播回放、产品素材带，一次拆成一堆干净片段，方便逐段剪辑、分发、二次加工。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![ffmpeg](https://img.shields.io/badge/requires-ffmpeg-orange)

---

## 它解决什么问题

| 痛点 | 分镜刀的答案 |
|---|---|
| 手动在剪辑软件里一帧帧找切点，一小时素材要抠一下午 | 自动检测转场，秒级输出所有片段 |
| 渐变 / 叠化 / 一镜到底的视频，检测算法看不见边界 | 固定时长切分兜底，想多碎就多碎 |
| 漏掉一个转场就得重来 | **不漏模式**：多阈值融合，宁可多切绝不漏 |
| 不想敲命令行 | 自带 tkinter 图形界面，双击即用 |

## 三种切分模式

| 模式 | 适用场景 | 用法 |
|---|---|---|
| **镜头检测** | 常规硬切转场 | `--sensitivity normal`（及 `fine` / `finest`） |
| **不漏模式** | 每个转场都必须单独成片，宁可多切不能漏 | `--sensitivity ultra` |
| **固定时长** | 渐变 / 叠化 / 连续运镜，算法看不见转场 | `--interval 3`（每 3 秒一段） |

> **怎么选**：先用 `--list` 跑一遍看段数。如果反复调低阈值段数几乎不变、或切点位置乱漂（阈值一变边界就变），说明这个视频没有硬切转场 → 直接换 `--interval`。

## 快速开始

### 1. 装依赖

```bash
# 必须：ffmpeg
#   Windows : winget install Gyan.FFmpeg
#   macOS   : brew install ffmpeg
#   Ubuntu  : sudo apt install ffmpeg

# 推荐：PySceneDetect（检测更准；不装会自动回退 ffmpeg 内置 scene 过滤器）
pip install "scenedetect[opencv]"
```

### 2. 先看镜头清单，不切割

```bash
python scripts/split_by_shots.py input.mp4 --list
```

确认段数和时间戳符合预期，再正式切。

### 3. 正式切分

```bash
# 常规（0.5 秒以下的碎渣并入邻段）
python scripts/split_by_shots.py input.mp4 --min-duration 0.5

# 每个转场都单独成片（不漏模式；不要再叠加 --min-duration）
python scripts/split_by_shots.py input.mp4 --sensitivity ultra

# 无硬切转场的视频：每 3 秒一段
python scripts/split_by_shots.py input.mp4 --interval 3

# 指定输出目录 + 导出时间戳清单
python scripts/split_by_shots.py input.mp4 --out ./shots --json shots.json
```

输出：`shot_001.mp4`、`shot_002.mp4`… 以及可选的 `shots.json`（每段的起止时间与时长）。

## 参数表

| 参数 | 说明 |
|---|---|
| `--sensitivity` | `coarse` 粗 / `normal` 标准（默认）/ `fine` 精细 / `finest` 极细 / `ultra` 不漏 |
| `--threshold` | 手动阈值，越小切越碎（PySceneDetect 为 27 量级，ffmpeg 为 0~1 量级） |
| `--detector` | `content` 对突变敏感（默认）/ `adaptive` 对渐变敏感 |
| `--interval N` | 固定时长切分，每 N 秒一段，跳过检测 |
| `--min-duration N` | 短于 N 秒的段并入邻段（保证时间线连续）。**ultra 模式不要用** |
| `--copy` | 流拷贝极速模式（切点吸附到关键帧，不重编码） |
| `--out` / `--json` | 输出目录 / 镜头时间戳清单 |
| `--list` | 只检测、不切片 |

## 图形界面（不敲命令的用法）

双击 `scripts/run_gui.bat`（Windows）→ 选视频 → 选灵敏度档位 → 开始切片。

首次使用先准备环境：

```bat
<你的 Python 路径>\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install "scenedetect[opencv]"
```

然后把 `run_gui.bat` 里的 python 路径改成该 venv 的 `pythonw.exe`。

**界面选项**：视频文件 / 输出目录（留空则在视频同目录建 `视频名_shots/`）、切分灵敏度（粗 / 标准 / 精细 / 极细 / 不漏）、固定时长切分（秒）、碎渣过滤（秒）、极速模式、仅预览清单。

> 选了「不漏」档位时，碎渣过滤要改成 `0` 或留空，否则碎段会被合并，违背「不漏」的初衷。

**环境自检**：双击 `scripts/run_gui_diagnose.bat`，逐项检查 tkinter / 依赖导入 / PySceneDetect / ffmpeg 定位，结果写入 `scripts/selftest.log`。

## 实测参考

同一素材、不同档位切出的段数：

| 视频 | normal | fine | finest | ultra |
|---|---|---|---|---|
| 48s 产品视频 | 18 段 | 21 段 | 22 段 | **57 段** |
| 15s 渐变转场视频 | 2 段 | 2 段 | 6 段 | **12 段** |

可以看到：常规视频用 `normal` 就够；渐变转场视频在常规档位几乎切不出来，`ultra` 或 `--interval` 才是正解。

## 工作原理

1. **镜头检测**：PySceneDetect `ContentDetector` 定位画面内容突变时刻；未安装则回退 ffmpeg 内置 `scene` 过滤器。
2. **不漏模式（ultra）**：单一阈值检出不稳定（阈值一变边界就漂），因此依次跑 `27 / 20 / 15 / 12 / 10 / 8 / 6` 七个阈值，**任一阈值认定为转场的位置都切一刀**，去重时相距 <0.2s 的切点视为同一转场。
3. **固定时长（--interval N）**：跳过场景检测，按固定时长硬切，适合一镜到底、转场全叠化的视频。
4. **切片**：ffmpeg 按边界导出。默认重新编码（切点精准）；`--copy` 走流拷贝（极速，但切点会吸附到最近关键帧）。

## Windows 踩坑记录

这份代码在 Windows 上踩过的坑，都已在代码里规避，记录下来给后来人：

- **bat 启动器必须纯 ASCII** —— UTF-8 中文注释在 cmd 的 GBK 代码页下会变成乱码字节流，撕碎命令解析，表现成「双击闪退」且 Python 根本没启动过。
- **ffmpeg 常不在系统 PATH** —— WinGet 装的只在部分注入的 PATH 里；用户双击 bat 时找不到，就会出现「检测出了镜头数但切片全失败」。脚本内置动态搜索 `LOCALAPPDATA\Microsoft\WinGet\Packages`，且必须懒加载（模块顶层扫描会拖慢启动甚至崩溃）。
- **pythonw 静默吞异常** —— 无控制台时任何未捕获错误都是「窗口一闪就没」。GUI 已装 `sys.excepthook` 兜底：写 `gui_crash.log` + 弹窗提示。
- **原生 ffmpeg 不认 Unix 路径** —— 不认 Git Bash 的 `/tmp/...`，跨盘绝对路径也不稳。稳妥做法是把视频放到工作目录用相对路径处理。
- **GUI 不要暴露量纲不统一的裸数值** —— 两个引擎阈值量纲不同（27 vs 0~1），让用户填数字必然填错，所以对外只暴露语义化档位。

## 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 双击 bat 闪退、无任何提示 | bat 编码炸了 / pythonw 静默异常 | 确认 bat 是纯 ASCII；查 `scripts/gui_crash.log`；用 `run_gui_debug.bat` 看真实报错 |
| GUI 能开，但日志显示「共 1 个镜头」 | 阈值没传或量纲错 | 已修复（阈值缺省兜底 + 回退时重置量纲）；改代码后务必关掉旧窗口重开 |
| 切片阶段报「切片失败」 | ffmpeg 找不到 / 跨盘路径 | 脚本已动态搜 WinGet；跨盘时先复制到工作目录 |
| 段数远少于预期 | 灵敏度不够 / 视频没有硬切转场 | 换档位；仍不行就用 `--interval` |
| 日志显示检测正常但「未生成切片」 | 切片环节部分失败 | 新版会打印「成功 N/总 M 段」，看具体 `[error]` 行 |

## 目录结构

```
README.md                          项目说明
SKILL.md                           技能文档（完整调参 / 排障指南）
scripts/
  split_by_shots.py                核心 CLI（检测 + 切片）
  video_shot_splitter_gui.py       tkinter 图形界面
  run_gui.bat                      双击启动器（无黑窗）
  run_gui_debug.bat                调试版（带控制台，看得到报错）
  run_gui_diagnose.bat             环境自检
  _selftest.py                     自检脚本
```

## 验收清单

- [ ] 段数与预期吻合（先用 `--list` 核对时间戳再切）
- [ ] 每段 `shot_xxx.mp4` 可独立播放、画面完整、无黑场截断
- [ ] 各段时长之和 ≈ 原片时长（容器取整会有 ±0.5s 累计误差，属正常）
- [ ] 交付前用 ffprobe 逐段校验，不要只看日志里的成功提示

---

有问题欢迎提 Issue，附上视频的大致特征（时长、是否硬切转场）和脚本输出的段数，定位会快很多。
