---
name: openclaw-memory-orchestrator
description: orchestrate openclaw memory backup, restore, snapshot, diff, redaction, persona branches, and heartbeat sync for private github repositories. use when user wants to backup or restore workspace files, summarize memory automatically, generate human-readable diffs, redact sensitive data, manage multiple persona branches, create snapshot.json state, or configure sync strategy for openclaw.
---

# OpenClaw Memory Orchestrator

统一管理 OpenClaw 工作空间的备份、恢复、快照、diff、脱敏、人格分支和定时同步。

## Core workflow

按下面顺序执行，除非用户只要求某一个子能力：

1. 识别意图：`backup` / `restore` / `snapshot` / `diff` / `redact` / `branch` / `heartbeat` / `status`
2. 读取配置：优先读取 `OPENCLAW_SYNC_CONFIG`，否则读取 `sync.config.json`，最后回退到环境变量
3. 生成快照：在任何 push、restore 前，先生成 `snapshot.json`
4. 脱敏：默认启用规则脱敏，哪怕仓库是私有的也要做一次检查
5. 生成 diff：输出机器可读 diff 和人类可读摘要
6. 执行 git 操作：commit / push / pull / branch
7. 回报结果：说明变更文件、脱敏命中、branch、是否推送成功、后续建议

## Default assumptions

- 默认仓库是 **private**
- 默认允许把原始工作空间文件同步到私有仓库
- 默认仍生成 **脱敏后的 snapshot** 与 **diff 摘要**，避免误把敏感内容扩散到别的环境
- 默认把 **git branch** 当作 persona branch，例如 `main`, `research`, `coder`, `friend`
- 默认先 `pull --rebase` 再 `push`，降低冲突概率

## Sync scope

优先同步这些文件与目录：

- `SOUL.md`
- `IDENTITY.md`
- `USER.md`
- `MEMORY.md`
- `TOOLS.md`
- `HEARTBEAT.md`
- `AGENTS.md`
- `BOOTSTRAP.md`
- `memory/**/*.md`
- `skills/**`
- `avatars/**`

默认排除：

- `.git/**`
- `node_modules/**`
- `sessions/**`
- `*.log`
- `*.tmp`
- `*.bak`
- 二进制大文件和显然的缓存目录

## Config precedence

按以下优先级解析配置：

1. `OPENCLAW_SYNC_CONFIG` 指向的 JSON 文件
2. 工作空间内的 `sync.config.json`
3. 环境变量

关键配置项：

- `workspace_dir`
- `repo_dir`
- `remote`
- `branch`
- `persona_branch_prefix`
- `sync_strategy`
- `heartbeat_minutes`
- `include_patterns`
- `exclude_patterns`
- `redaction`
- `snapshot_dir`
- `artifacts_dir`

## Intent handling

### 1. Backup / push

执行：

1. 运行 `python scripts/sync.py snapshot`
2. 运行 `python scripts/sync.py diff`
3. 运行 `python scripts/sync.py backup`

输出至少包含：

- snapshot 路径
- 变更文件列表
- 人类可读 diff 摘要
- 脱敏命中结果
- commit message
- push 结果

### 2. Restore / pull

执行：

1. 说明将从远端恢复到本地
2. 运行 `python scripts/sync.py restore`
3. 如果用户要求只恢复某些文件，使用 `--only`
4. 恢复后重新生成一个本地 snapshot 以确认状态

默认不要覆盖本机的额外凭证文件。若发现潜在 secrets 配置文件，优先保留本地版本并提示用户。

### 3. Snapshot

执行 `python scripts/sync.py snapshot`。

生成物包括：

- `snapshot.json`：完整结构化状态
- `snapshot.redacted.json`：脱敏版本
- `summary.txt`：自动总结

## Snapshot contract

`snapshot.json` 至少包含这些顶级字段：

- `schema_version`
- `created_at`
- `workspace_dir`
- `repo_dir`
- `git`
- `persona`
- `sync_strategy`
- `files`
- `memory_summary`
- `diff_from_previous`
- `redaction_report`
- `heartbeat`

`files[]` 每项至少包含：

- `path`
- `kind`
- `size`
- `mtime`
- `sha256`
- `line_count`
- `sensitive_hits`
- `frontmatter`
- `preview`

## Human-readable diff rules

执行 `python scripts/sync.py diff`。

输出格式优先：

- `changed`: 新增 / 修改 / 删除 文件计数
- `sections`: 哪些主题变化最大
- `highlights`: 3 到 8 条人类可读变化说明
- `risk`: 是否触发敏感信息或身份配置变更

当 diff 很长时，不要逐行铺开；优先总结：

- 记忆增长了什么
- 用户画像改变了什么
- 人格设定改变了什么
- 工具配置改变了什么
- 哪些变化需要人工复核

## Redaction rules

执行 `python scripts/sync.py redact` 或任何默认带脱敏检查的命令。

默认检测并替换：

- GitHub token：`ghp_`, `github_pat_`
- OpenAI key：`sk-`
- 通用密钥字段：`api_key`, `access_token`, `secret`, `password`
- 邮箱
- IPv4
- Bearer token
- 明显的私钥片段

默认替换形式：

- `<redacted:github_token>`
- `<redacted:openai_key>`
- `<redacted:secret_field>`
- `<redacted:email>`

如果用户明确要求保留原文用于私有备份，可保留原始文件进入私仓，但仍必须生成脱敏副本与命中报告。

## Persona branches

执行 `python scripts/sync.py branch create --name research` 等命令。

分支规则：

- 每个 persona 对应一个 git branch
- 默认从当前分支分叉
- 分支名优先 `persona/<name>`，除非配置关闭前缀
- `branch switch` 用于切换人格
- `branch list` 列出所有 persona branches
- `branch snapshot` 先生成快照再切分支

建议映射：

- `persona/research`：偏事实、长上下文
- `persona/coder`：偏执行、工具、脚本
- `persona/friend`：偏陪伴和口语化
- `persona/ops`：偏备份、迁移、运行维护

## Heartbeat

执行 `python scripts/sync.py heartbeat`。

heartbeat 不依赖常驻守护进程；它做两件事：

1. 根据配置判断是否到了备份窗口
2. 若到了，则执行 snapshot + backup

同时产出 `heartbeat_state.json`，记录：

- `last_run_at`
- `last_success_at`
- `next_due_at`
- `last_result`

如果用户要接入 crontab、systemd timer 或其他外部调度器，优先让外部调度器周期性调用这个 heartbeat 命令。

## Sync strategies

支持这些策略：

- `manual`: 仅用户显式要求时同步
- `on_change`: 检测到文件变化就允许同步
- `heartbeat`: 定期尝试同步
- `hybrid`: 手动优先，heartbeat 保底
- `snapshot_only`: 只做快照不推远端

默认策略：`hybrid`

推荐规则：

- 高频改动工作区：`on_change` 或 `hybrid`
- 高敏感环境：`snapshot_only` 或 `manual`
- 跨服务器迁移：先 `snapshot_only` 本地验证，再 `backup`

## Recommended commands

```bash
# 生成快照
python scripts/sync.py snapshot

# 查看可读 diff
python scripts/sync.py diff

# 脱敏检查
python scripts/sync.py redact

# 备份到 GitHub
python scripts/sync.py backup

# 从 GitHub 恢复
python scripts/sync.py restore

# 只恢复指定文件
python scripts/sync.py restore --only MEMORY.md memory/profile.md

# 创建人格分支
python scripts/sync.py branch create --name research

# 切换人格分支
python scripts/sync.py branch switch --name research

# heartbeat 执行一次
python scripts/sync.py heartbeat
```

## Response checklist

完成任务后，始终在回复中说明：

- 执行了哪个命令
- 处理了哪些文件
- 是否发现敏感信息
- 当前分支 / persona
- 是否成功生成 snapshot.json
- 是否成功推送或恢复
- 若失败，给出最可能原因和下一步

## Resources

- `references/design.md`: 架构和默认策略
- `references/snapshot-schema.md`: snapshot 结构
- `references/redaction-rules.md`: 脱敏规则
- `scripts/sync.py`: 可执行的本地同步脚本

