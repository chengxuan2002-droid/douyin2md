---
name: douyin2md
description: 把抖音视频或本地音视频转成 Markdown 文稿。用户发抖音链接（v.douyin.com 短链、www.douyin.com/video/<id>、或含链接的分享文案）要求"转文字/提取文案/整理成笔记/存成 md/生成逐字稿/总结一下"时使用；一次发多个链接或整个列表/收藏夹要求"批量/全部转成 md"时也使用；发本地音视频文件或目录要求转录时同样适用。自动区分单条与批量，无需用户选择脚本。支持元数据提取、语音转写（本地离线或云端）、带时间戳正文、YAML frontmatter。发微信视频号链接（weixin.qq.com/sph/...）时自动按来源降级为元数据+高清封面摘要，并明确标注缺失项。抖音直连被风控拦截时自动切换浏览器拦截兜底，仍产出完整逐字稿。
license: MIT
---

# douyin2md — 视频转 Markdown 文稿

这是一个标准 **Agent Skill**：只要某个 agent 框架支持 Agent Skills，
把本目录放进它的 skills 目录即可识别并调用，**无需修改任何文件**。
`SKILL.md` 位于仓库根，frontmatter 只使用标准字段；脚本引用全部是相对路径，
不含任何机器专属的绝对路径、解释器路径或本机目录。

## 调用约定

所有能力收敛到**一个入口**：`bin/douyin2md`。它用自身位置定位技能根目录，
因此从任意工作目录调用都有效。以下命令默认 cwd 为 `SKILL.md` 所在目录；
若不是，请先 `cd` 到技能目录，或写成绝对路径：

```bash
bash bin/douyin2md --help          # 查看全部子命令
python3 -m douyin2md --help        # 等价写法（需 PYTHONPATH 指向技能根）
douyin2md --help                   # pip install -e . 之后的等价命令
```

统一接口表：

| 子命令 | 作用 |
| --- | --- |
| `url <链接或文案>` | 单个链接 → Markdown（自动按来源分流：抖音全链路含风控自动兜底 / 视频号元数据降级） |
| `batch <links.txt>` | 批量链接，每条一篇 Markdown，单条失败不中断，结束输出状态清单 |
| `transcribe <文件/目录>` | 本地音视频 → 转写 JSON（无需 cookie） |
| `to-md --meta <json>` | 元数据 + 转写 JSON → Markdown |
| `capture <链接> [--fresh]` | 手动风控兜底：浏览器拦截 detail 响应并下载 mp4（`--fresh` 用全新游客会话） |
| `model <list\|status\|download\|path>` | 本地 ASR 模型管理 |
| `cookie [--check]` | 浏览器登录导出 cookie |
| `doctor` | 只读环境体检（不联网、不安装） |
| `config` | 打印生效配置（密钥只显示 set/not set） |

## 模式自动选择（先读这一段）

**不要问用户要单条还是批量，更不要让用户自己选脚本。** 按输入形态直接执行：

| 用户给的东西 | 执行 |
| --- | --- |
| 1 个抖音链接 / 1 段分享文案 | `bash bin/douyin2md url "<链接或文案>" -o ./notes` |
| 1 个微信视频号链接 | `bash bin/douyin2md url "<链接>" -o ./notes`（自动降级，见下节） |
| 多个链接 / 列表 / 收藏夹 / "全部" | 逐行写入临时文件，再 `bash bin/douyin2md batch urls.txt -o ./notes` |
| 1 个本地音视频文件 | `bash bin/douyin2md transcribe ./录音.mp4 -o 录音.json` |
| 本地一个目录 / 一批文件 | `bash bin/douyin2md transcribe ./访谈集/ -o ./访谈转录/`（模型只加载一次） |
| 抖音直连被风控（`Fresh cookies` / Argus） | **无需手动干预**：`url` 自动切浏览器拦截兜底；仅在要单独取 mp4 时才用 `capture "<链接>" -o ./.artifacts --fresh` |

判断不清时按「能直接跑的最小范围」执行，完成后补问是否需要处理更多。
批量输出自动带 `序号-作者-标题.md` 前缀，避免同名覆盖；批量逐条串行，不要高并发以免限流。

## 首次准备

```bash
bash bin/douyin2md doctor                 # 先看缺什么，纯只读
bash bin/douyin2md model download         # 下载本地中文模型（约 60MB，一次性）
bash bin/douyin2md cookie                 # 弹浏览器登录，导出 cookie（一次性）
bash bin/douyin2md cookie --check         # 校验 cookie 是否仍有效
```

依赖与配置统一由 `pyproject.toml` / `requirements.txt` / `config.example.json` 声明，
详见 `docs/configuration.md` 与各框架的 `docs/agent-compatibility.md`。

## 统一配置

优先级：命令行参数 > `DOUYIN2MD_*` 环境变量 > `DOUYIN2MD_CONFIG` 指定的 JSON >
`~/.douyin2md/config.json` > 仓库根 `config.json` > 内置默认值。

| 目的 | 环境变量 | 默认值 |
| --- | --- | --- |
| 运行时数据目录 | `DOUYIN2MD_HOME` | `~/.douyin2md` |
| 输出目录 | `DOUYIN2MD_OUTPUT_DIR` | `./notes` |
| 转写引擎 | `DOUYIN2MD_ENGINE` | `auto` |
| 语言 | `DOUYIN2MD_LANGUAGE` | `zh` |
| 模型 / 设备 / provider | `DOUYIN2MD_MODEL` / `DOUYIN2MD_DEVICE` / `DOUYIN2MD_PROVIDER` | 空 / `auto` / 空 |
| cookie 文件 | `DOUYIN2MD_COOKIES` | 空 |
| 云端 Key | `SILICONFLOW_API_KEY` / `OPENAI_API_KEY` | 不设置则走本地引擎 |

**密钥只走环境变量，不写配置文件、不写仓库、不打印值。**

## 引擎与模型

`--engine` 默认 `auto`：sherpa（本地中文）> siliconflow（云端）> openai（云端）。
`local` 是 `sherpa` 的兼容别名；faster-whisper 已移除，旧 whisper 档位自动映射到 sherpa。
`bash bin/douyin2md model list` 查看可选模型：`sense-voice-int8`（默认）/ `paraformer-zh-int8` /
`paraformer-zh` / `zipformer-zh-int8`。中文内容显式保持 `language=zh`。

## 输出形态

默认产出**逐字稿**：YAML frontmatter + 元信息表 + 视频文案 `desc` + 带时间戳转写正文
（格式见 `examples/示例输出.md`）。视频描述文案与口播转写是两种不同来源，都要保留，不要互相替代。

用户说「提取核心内容 / 总结 / 讲的是什么 / 有哪些方法和步骤」时，要的是**结构化总结文档**，
不是逐字稿。常用骨架：主题 → 核心方法（配表格）→ 实施步骤 → 横向对比 → 进阶点 → 转写来源说明。
`desc` / 作者 / 时长 / 统计信息可从 detail.json 直取，自行写 frontmatter 更灵活。

**专名核实（必须做）**：口播里的英文/品牌专名易错，三级校验依次是
① 换一档模型重跑交叉校验 → ② `ffmpeg` 抽帧读画面字幕定案 → ③ 查项目官网/仓库核对拼写。
两个模型一致也可能都错，不能据此下结论。抽帧看片头标题、结构切换处、结尾念产品名处。

## 抖音直连风控：自动兜底（2026-11-20 实测）

抖音 `aweme/detail` 的 Argus / `a_bogus` 签名风控会让 yt-dlp 直连稳定报
`Fresh cookies (not necessarily logged in) are needed`；短链跳转目标
`www.iesdouyin.com` 在部分网络下还会 TLS 不可达。**`url` / `batch` 会自动处理，不要让用户自己选脚本**：

1. `dy_fetch.py` 先把 `v.douyin.com` 短链只读解析成 `www.douyin.com/video/<id>` 长链；
2. 直连仍失败时自动调用 `dy_browser_capture.py`，由真实浏览器渲染页面并拦截
   `aweme/detail` 响应，取得元数据与 mp4；
3. 把 detail 映射成与 yt-dlp **完全相同**的 `meta.json` 契约，照常进入
   `transcribe` → `to-md`，最终产出带时间戳的完整逐字稿。

兜底默认使用**全新空 Chrome profile 的游客态**（`--fresh`）。2026-11-20 对照实测：
复用旧 profile + 1028 条登录 cookie 会命中「验证码中间页」，而全新游客会话稳定拿到
`aweme/detail`；用户显式传 `--cookies` 时优先尊重其登录态，失败再回退 fresh。
兜底成功时日志会出现「已自动由浏览器拦截兜底取得真实媒体」，`meta.json` 带
`capture_fallback: true` 与 `extractor: browser-capture (aweme/detail)`，
**文稿格式与直连成功时逐字一致**，不新增任何区块。

| 开关 | 用途 |
| --- | --- |
| （默认） | 直连失败自动兜底；视频号与未知来源不受影响 |
| `--no-capture-fallback` | 禁用自动兜底，保留旧行为（只报诊断并失败） |
| `--force-capture` | 已知直连必失败时跳过 yt-dlp，直接用浏览器拦截，省一次请求 |
| `--no-audio` | 兜底时只取元数据（透传 `--no-download`，不下载 mp4） |

对应配置 `no_capture_fallback` / `force_capture` 与环境变量
`DOUYIN2MD_NO_CAPTURE_FALLBACK` / `DOUYIN2MD_FORCE_CAPTURE`。
单独取 mp4 用 `bash bin/douyin2md capture "<链接>" -o ./.artifacts --fresh`。

遇到验证码中间页时脚本会明确打印 `[risk]` 诊断并自动换会话重试一次，
**不破解验证码、不伪造签名、不绕过鉴权**；若两次都失败，如实报平台限制，不要反复高并发重试。

## 非抖音来源：微信视频号（只读降级）

**自动按来源分流，不要让用户选脚本，也不要把视频号链接当成抖音抓取失败去反复重试。**

| 来源 | 判定 | 行为 |
| --- | --- | --- |
| 抖音 | `v.douyin.com` / `www.douyin.com/video/<id>` | 原三段式流水线，产出逐字稿 |
| 微信视频号 | `weixin.qq.com/sph/<id>` / `channels.weixin.qq.com` | 只读提取元数据 + 高清封面，产出 `metadata_only` 文稿 |
| 其它链接 | 未知来源 | 返回 `unsupported_source` 并提示改用 `transcribe`，不丢给 yt-dlp |

平台在预览页**不下发视频流**（接口 `get_feed_info` 无 `videoUrl` / `h264` / 时长字段，页面提示「可扫码前往微信观看」）。这是平台侧策略，不是抓取失败；补 cookie、换 UA、重试都不会改变结果。因此：

- 文稿会自动带 `extraction_status: metadata_only`、frontmatter 的 `missing` 清单，以及正文顶部的「摘要说明（请先读）」区块；模板**不会编造**转写正文、字幕或视频内时间戳。
- 可用信息只有：官方描述 `desc`、作者、发布时间、互动数、高清封面画面文字。外部资料必须单列章节并标注「非视频内容」，不要冒充视频转写。
- 需要逐字稿时走 Tier 3：请用户在微信客户端保存视频或录屏 → 提供本地文件 →
  `bash bin/douyin2md transcribe <文件> -o t.json` →
  `bash bin/douyin2md to-md --meta <同一份 meta.json> --transcript t.json -o ./notes`。
  传入非空转写后模板自动升级为完整文稿，不再显示降级说明。
- 批量混合来源时单条降级不中断，结束按 `ok / metadata_only / media_blocked_by_platform /
  need_login / unsupported_source` 输出状态清单。

**可选：封面文字 OCR（`--ocr`）**：默认关闭。`url` / `batch` 加 `--ocr` 后对高清封面做本地
OCR（macOS 用系统 Vision，其它平台可选 `tesseract`；`--ocr-backend auto|macos-vision|tesseract|none`），
结果写入 `meta.json` 的 `cover_ocr`，并在文稿里单列「封面文字（OCR，须人工核对）」。低于
`--ocr-min-confidence`（默认 0.8）的行标记「⚠️ 低置信度」。后端缺失/失败时自动降级为
`available=false`，不影响 `metadata_only` 文稿正常产出。**封面文字不是口播内容、字幕或时间戳**，
必须人工核对，不得据此推断视频内容。

**可选：带会话字段差异验证（`scripts/wx_session_check.py`）**：仅在用户显式提供登录态
（Netscape cookie 文件）并加 `--authorize` 时才会发出带会话请求；未授权时直接退出、不联网。
工具只比对带会话前后的接口字段差异并输出脱敏报告，**不下载视频、不构造播放地址、不绕过鉴权**。
2026-11-19 实测：带会话后仍未出现视频流字段；用非微信 cookie 完成的仅是链路连通性验证，
报告会明确标注「不能用于判定登录态假设」。

- 合规：不绕过鉴权、客户端校验或 DRM；仅用于自己创作或已获授权的内容。

## 注意事项

- **禁止臆造**：转写失败或为空时如实说明，绝不编造视频内容；视频号 `metadata_only` 文稿尤其不得编造时间戳。
- **封面 OCR 不等于转写**：OCR 文字须人工核对，只作画面文字证据，不得写入转写正文或当作视频内时间点。
- **视频号链接不要按抖音链路重试**：平台侧不下发视频流，按上节降级处理即可。
- 原文有缺陷时保留原样，问题写在正文外的编者注里。
- 合规：仅用于自己创作或已获授权的内容，下载内容版权归原作者。
- 用户要求「与之前提取的几期对比 / 有什么进阶点」时，按
  `docs/troubleshooting.md` 的「系列内容的跨期对比」做表格与脉络图，只依据已提取内容。
- 深入阅读：`docs/agent-compatibility.md`（各框架接入与加载陷阱）、`docs/configuration.md`（依赖与配置）、
  `docs/architecture.md`（流水线）、`docs/troubleshooting.md`（风控、故障表、内容质量）。
