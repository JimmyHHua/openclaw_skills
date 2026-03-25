# Redaction Rules

## Built-in patterns

- GitHub token: `ghp_`, `github_pat_`
- OpenAI key: `sk-`
- Bearer token
- `password=`, `secret=`, `api_key=` 等键值形式
- 电子邮箱
- IPv4 地址
- 私钥头部标记

## Replacement policy

- 命中后替换为 `<redacted:type>`
- 在 `redaction_report` 中记录类型、文件、命中次数
- 保留行号上下文时，避免保留敏感原文

## Operational guidance

- 私有仓库 ≠ 不需要脱敏检查
- 默认生成两份工件：原始 snapshot 和 redacted snapshot
- 如果用户要求公开分享快照，只能使用 redacted 版本

