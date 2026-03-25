# Snapshot Schema

## Top-level fields

- `schema_version`: 当前 schema 版本
- `created_at`: ISO-8601 时间
- `workspace_dir`: 工作区根目录
- `repo_dir`: git 仓库目录
- `git`: 当前分支、remote、HEAD、dirty 状态
- `persona`: 从分支推导的人格信息
- `sync_strategy`: 当前同步策略及来源
- `files`: 纳入快照的文件数组
- `memory_summary`: 自动总结，按文件和主题归纳
- `diff_from_previous`: 与上一个 snapshot 的变化摘要
- `redaction_report`: 脱敏命中统计
- `heartbeat`: 上次运行和下一次建议运行

## File object

每个 file 对象包含：

- `path`
- `kind`
- `size`
- `mtime`
- `sha256`
- `line_count`
- `sensitive_hits`
- `frontmatter`
- `preview`

## Redacted snapshot

`snapshot.redacted.json` 与 `snapshot.json` 结构相同，但以下字段内容会被规则替换：

- `preview`
- `memory_summary`
- 任何命中 secrets 规则的文本

