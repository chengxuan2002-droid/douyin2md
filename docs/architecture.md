# 结构与流水线

## 分层

```
agent 框架（只读 SKILL.md）
        │  自然语言触发
        ▼
bin/douyin2md  ──►  douyin2md/cli.py  ──►  douyin2md/config.py
  自定位技能根         子命令 + 配置注入        默认值/JSON/环境变量
        │                    │
        │                    └──► douyin2md/sources.py
        │                           来源判定 / 状态契约（纯逻辑、不联网）
        ▼  subprocess（sys.executable + 绝对路径）
scripts/*.py   原始实现（可单独调用）+ wx_fetch.py 来源适配器
```

- **接口层**（`douyin2md/`）：只做参数归并、配置读取、环境体检与来源判定，不含网络业务
  逻辑、不安装依赖；`doctor` 仍为只读。
- **实现层**（`scripts/`）：原有脚本继续可单独调用，命令行参数与抖音产物格式保持兼容。
  本版为来源分流对 `dy.py` / `dy_fetch.py` / `dy_tomd.py` 做了增量修改，并新增
  `wx_fetch.py`；历史笔记里的 `python3 scripts/dy.py ...` 依然有效。
- **文档层**（`docs/`）：框架接入、配置、排障与架构；环境相关的踩坑与本机路径都放这里，
  不污染 `SKILL.md`。

## 来源适配（`url` / `batch` 入口）

`douyin2md/sources.py::detect_source()` 是**唯一判定源**（纯标准库、不联网、可离线单测）。
cli 层先给出来源提示，`dy.py::fetch_one()` 按结果分流：

| 来源 | 适配器 | 产物 | 结果状态 |
| --- | --- | --- | --- |
| 抖音 | `dy_fetch.py` → `dy_transcribe.py` → `dy_tomd.py` | 逐字稿 | `ok` |
| 微信视频号 | `wx_fetch.py` → `dy_tomd.py` | 元数据 + 高清封面，`metadata_only` 文稿 | `metadata_only` / `media_blocked_by_platform` |
| 未知来源 | 不调用任何抓取脚本 | 可解释的错误提示 | `unsupported_source` / `need_login` |

`wx_fetch.py` 只做只读提取：按短链规则还原落地页 → 桌面 UA 浏览器渲染 →
拦截 `get_feed_info` 响应 → 压缩成统一 `meta.json` 契约（`source` / `source_id` /
`extraction_status` / `playability` / `missing` / `evidence`）→ 下载去缩图参数的高清封面。
**不尝试下载视频流**：平台在预览端不下发播放地址，裸 HTTP 请求还会被
`permission verification failed` 拒绝。

批量模式按条记录状态，降级条目无音频、不参与转写，但仍生成 Markdown；
结束由 `_print_status_summary()` 输出分级清单，单条失败不中断整批。

## 三段式流水线（抖音，`url` / `batch`）

```
dy.py
 ├─ 1. dy_fetch.py        链接/分享文案 → 元数据 JSON + 音频（yt-dlp + cookie）
 ├─ 2. dy_transcribe.py   音频 → 带 segments 时间戳的转写 JSON
 │        ├─ sherpa       本地离线（默认，模型在 ~/.douyin2md/models/）
 │        └─ siliconflow / openai 兼容接口（需 API Key）
 └─ 3. dy_tomd.py         元数据 + 转写 → Markdown（frontmatter + 元信息表 + [mm:ss] 正文）
```

批量模式（>1 个链接）先把音频集中到 `<输出目录>/.artifacts/audio_batch/`，
再一次性调用 `dy_transcribe.py <目录>`，**本地模型只加载一次**；单条失败不中断整批，
结束时给出成功/失败清单。中间产物在 `.artifacts/`，除非 `--keep-audio` 否则自动清理。

本地文件模式（`transcribe`）跳过抖音获取链路，**不需要 cookie**：
`dy_transcribe.py` 递归扫描目录里的 `mp3/wav/m4a/flac/mp4/mov/mkv…`，
每文件输出一个 `<文件名>.json`。

## 风控兜底路径（`capture`）

抖音 web 端对 `aweme/v1/web/aweme/detail` 有 Argus 风控，后来又加了
msToken + `a_bogus` 签名校验，静态 cookie 可能仍返回 403。`dy_browser_capture.py`
不自己实现签名，而是用真实浏览器加载页面并**拦截 detail 响应**取元数据，
再用 `ffmpeg -headers "Referer: https://www.douyin.com/"` 直接拉 `play_addr` 存 mp4，
最后交给 `dy_transcribe.py`。详见 `docs/troubleshooting.md`。

## 数据边界

| 位置 | 内容 | 是否进仓库 |
| --- | --- | --- |
| `~/.douyin2md/` | cookie、浏览器 profile、ASR 模型 | 否（`.gitignore`） |
| `<输出目录>/.artifacts/` | 中间音频、元数据、转写 JSON | 否 |
| `./notes/`（可配置） | 最终 Markdown 与视频号高清封面 | 否 |
| 仓库内 | 代码、文档、示例、测试、配置模板 | 是 |

## 设计约束

- 不改写第三方/原始脚本：兼容层只转发，参数与原 argparse 定义一一对应。
- 不含机器专属路径：`SKILL.md` 与 `bin/douyin2md` 都用自身位置解析。
- 配置单一来源：`douyin2md/config.py`，密钥只走环境变量。
- 体检只读：`doctor` 用 `importlib.util.find_spec` 和 `shutil.which` 检查，
  不 import 可选模块、不联网、不安装。
- 来源判定单一实现：`cli.py` 与 `scripts/` 共用 `douyin2md/sources.py`，脚本通过
  把仓库根插入 `sys.path` 导入，因此 `scripts/*.py` 仍可脱离入口单独调用。
- 降级是一等契约：`extraction_status=metadata_only` 由 `meta.json` 驱动，
  `dy_tomd.py` 自动输出缺失清单；旧抖音 meta 不新增任何字段，产物保持兼容。
- 视频号适配器只读：不绕过鉴权、客户端校验或 DRM，不尝试构造播放地址。
