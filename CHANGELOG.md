# Changelog

## Unreleased（功能分支 `feat/weixin-channels-source`）

来源适配与一等降级契约。依据 2026-11-19 的微信视频号提取失败归因方案落地
（该诊断文档是运行时产物，位于被 `.gitignore` 排除的 `notes/`，不在仓库内）。

### 新增

- `douyin2md/sources.py`：**唯一来源判定源**（抖音 / 微信视频号 / 未知），含 5 个结果状态、
  统一 `meta_id()` 与分级提示；纯标准库、不联网、可离线单测。
- `scripts/wx_fetch.py`：视频号预览页只读适配器。桌面 UA 浏览器渲染 → 拦截
  `get_feed_info` 响应 → 压缩为统一 `meta.json` 契约（`extraction_status` / `playability` /
  `missing` / `evidence`）→ 下载去缩图参数的高清封面。**不尝试下载视频流**。
- `doctor --json` 增加 `supported_sources`；`url` 增加来源即时提示。
- 新增 4 个测试文件、共 50 个用例：来源判定、URL 归一化、适配器契约、空 `feedInfo`
  对抗式检查、模板降级与抖音产物回归、批量状态机。

### 变更

- `scripts/dy.py`：按来源分流；新增状态机与结束时的分级状态清单；用 `meta_id()`
  统一中间文件命名，避免非抖音条目出现 `None`。原有转写与清理逻辑**保持不变**。
- `scripts/dy_tomd.py`：`source` 驱动 `type` 与 ID 标签；`metadata_only` 时自动输出
  「摘要说明（请先读）」与缺失清单，且不伪造转写正文/时间戳；传入非空转写后自动升级为
  完整文稿。**旧抖音 meta 的产物逐字不变**（不新增任何 frontmatter 字段）。
- `scripts/dy_fetch.py`：`normalize_input()` 复用统一归一化，修复分享文案尾随中文标点
  （如 `）。`）被吞进 URL；非抖音链接独立调用时给出可解释提示而非 `Unsupported URL`。
- `SKILL.md` / `README.md` / `docs/architecture.md` / `docs/troubleshooting.md`：
  同步来源适配层、视频号踩坑（含裸 HTTP 直连接口返回 `permission verification failed`
  的实测证据）与降级话术。

### 已知边界

- 视频号预览页由平台限制，产物恒为 `metadata_only`；逐字稿需用户提供微信客户端保存的
  视频/录屏，再走 `transcribe` → `to-md`。
- 2.0.0 段落中「`scripts/*.py` 逐字节保持不变」描述的是该版本当时的状态，
  **不适用于本版**；本版对 3 个脚本做了增量修改，但保持参数与产物兼容。

## 2.0.0 (2026-11-15)

通用化改造与仓库整理。目标是「同一份文件，无需修改即可被主流 agent 框架识别调用」。

### 新增

- 统一入口 `bin/douyin2md`：9 个子命令（url / batch / transcribe / to-md / capture /
  model / cookie / doctor / config），用 `BASH_SOURCE` 自定位技能根，任意 cwd 可调用。
- 接口层包 `douyin2md/`：`cli.py`（参数归并 + 转发）、`config.py`（配置优先级 + 脱敏）、
  `__main__.py`（`python3 -m douyin2md`）。
- 统一依赖声明：`pyproject.toml`（core / local / browser / all / dev extras + console script）
  与 `requirements.txt`。
- 统一配置：`config.example.json`、`DOUYIN2MD_*` 环境变量、四级优先级、密钥只走环境变量。
- `doctor` 只读环境体检、`config` 脱敏配置打印。
- 文档：`docs/agent-compatibility.md`、`configuration.md`、`architecture.md`、`troubleshooting.md`。
- 示例：`examples/urls.txt`、`cli.sh`、`agent-prompts.md`；零依赖单测 `tests/`。
- `LICENSE`（MIT）与完善的 `.gitignore`（排除 cookie、模型、媒体、本地配置）。

### 变更

- `SKILL.md` 重写为通用版：移除本机绝对路径与解释器踩坑，统一为 `bin/douyin2md` 调用；
  环境相关记录迁至 `docs/troubleshooting.md`，知识不丢失。
- `README.md` 重写，补齐框架接入、依赖分层、命令速查与仓库结构。
- `install.sh` 新增 `workbuddy` 目标并在帮助中标注统一入口。

### 未变更

- `scripts/*.py` 全部 9 个原始脚本**逐字节保持不变**，继续可单独调用；新入口仅做转发，
  历史命令 `python3 scripts/dy.py ...` 仍然有效。
