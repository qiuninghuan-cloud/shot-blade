# Video Shot Splitter

把一整个视频按「镜头 / 场景转场」自动切成一段段独立的小视频文件。

三种切分模式：

| 模式 | 适用 | 参数 |
|---|---|---|
| **镜头检测** | 常规切镜头 | `--sensitivity normal` |
| **不漏模式** | 每个转场都要单独成片，宁可多切不漏 | `--sensitivity ultra` |
| **固定时长** | 渐变/叠化/连续运镜，算法看不见转场 | `--interval 3` |

实测同一素材：48s 视频常规 18 段 → 不漏模式 57 段；15s 渐变转场视频常规 2 段 → 不漏模式 12 段。

## 安装

```bash
# 必须：ffmpeg（Windows 推荐 WinGet: winget install Gyan.FFmpeg）
# 推荐（检测更准）：
pip install scenedetect[opencv]
```

图形界面版额外需要 `tkinter`（Python 官方安装包自带）。

## 命令行用法

```bash
# 先看镜头清单不切割（建议第一步）
python scripts/split_by_shots.py input.mp4 --list

# 常规切分（0.5s 以下碎渣并入邻段）
python scripts/split_by_shots.py input.mp4 --min-duration 0.5

# 不够碎：提高灵敏度档位（fine / finest）
python scripts/split_by_shots.py input.mp4 --sensitivity fine

# 每个转场都单独成片（不漏模式；不要再叠加 --min-duration）
python scripts/split_by_shots.py input.mp4 --sensitivity ultra

# 无硬切转场视频：按固定时长切，每 3 秒一段
python scripts/split_by_shots.py input.mp4 --interval 3

# 指定输出目录 + 导出时间戳清单
python scripts/split_by_shots.py input.mp4 --out ./shots --json shots.json
```

### 主要参数

| 参数 | 说明 |
|---|---|
| `--sensitivity` | `coarse` / `normal` / `fine` / `finest` / `ultra`（不漏） |
| `--threshold` | 手动阈值，越小切越碎（scenedetect 27 量级） |
| `--detector` | `content`（突变敏感，默认）/ `adaptive`（渐变敏感） |
| `--interval N` | 固定时长切分，每 N 秒一段 |
| `--min-duration N` | 短于 N 秒的段并入邻段；**ultra 模式不要用** |
| `--copy` | 流拷贝极速模式（切点吸附关键帧） |

输出：`shot_001.mp4`、`shot_002.mp4`… 以及可选的 `shots.json`（起止时间、时长）。

## 图形界面

不想敲命令可以双击 `scripts/run_gui.bat`（Windows），选视频 → 选灵敏度档位 → 开始切片。

首次使用需准备环境（GUI 依赖 tkinter 与 scenedetect）：

```bat
<你的Python路径>\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install "scenedetect[opencv]"
```

再把 `run_gui.bat` 里的 python 路径改成该 venv 的 `pythonw.exe`。

## 工作原理

1. **镜头检测**：PySceneDetect `ContentDetector` 定位画面内容突变时刻；未安装则回退 ffmpeg 内置 `scene` 过滤器。
2. **不漏模式**：单一阈值检出不稳定（阈值一变边界就漂），因此依次跑 `27/20/15/12/10/8/6` 七个阈值，任一阈值认定为转场的位置都切一刀，去重时相距 <0.2s 的切点视为同一转场。
3. **切片**：ffmpeg 按边界导出，默认重新编码（切点精准），`--copy` 走流拷贝（极速）。

## Windows 踩坑记录

这份代码在 Windows 上踩过的坑，都已在代码里规避：

- **bat 启动器必须纯 ASCII** —— UTF-8 中文注释在 cmd 的 GBK 代码页下会撕碎命令解析，表现成"双击闪退"且 Python 根本没启动。
- **ffmpeg 常不在系统 PATH** —— WinGet 版只在部分注入的 PATH 里。脚本内置动态搜索 `LOCALAPPDATA\Microsoft\WinGet\Packages`，且为懒加载（模块顶层扫描会导致启动变慢甚至崩溃）。
- **pythonw 静默吞异常** —— 无控制台，任何未捕获错误都是窗口一闪就没。GUI 已装 `sys.excepthook` 兜底（写 `gui_crash.log` + 弹窗）。
- **原生 ffmpeg 不认 Unix 路径** —— 不认 Git Bash 的 `/tmp/...`；跨盘绝对路径也不稳。
- **GUI 不要暴露量纲不统一的裸数值** —— 两个引擎阈值量纲不同（27 vs 0~1），用户填数字必然填错，要用语义化档位。

## 目录结构

```
SKILL.md                       技能文档（完整调参 / 排障指南）
scripts/split_by_shots.py      核心 CLI（检测 + 切片）
scripts/video_shot_splitter_gui.py   tkinter 图形界面
scripts/run_gui.bat            双击启动器（无黑窗）
scripts/run_gui_debug.bat      调试版（带控制台，看得到报错）
scripts/run_gui_diagnose.bat   环境自检
scripts/_selftest.py           自检脚本
```
