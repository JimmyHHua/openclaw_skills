# Design

## Goals

- 把 OpenClaw 工作空间视为一个可版本化的“记忆系统”
- 在私有 GitHub 仓库里安全保存原始文件
- 同时生成脱敏快照、可读 diff 和恢复所需的结构化状态
- 支持 persona branch，把人格管理从“文案约定”提升为“可切换分支”

## Default operating model

1. 工作区文件是事实源
2. snapshot.json 是结构化状态视图
3. git commit 是历史记录
4. git branch 是人格分叉
5. heartbeat 是保底同步器

## Safety defaults

- 即便仓库私有，也执行脱敏扫描
- 默认保留本地 secrets，不在 restore 时盲目覆盖
- 默认输出 redaction report，便于人工复核
- diff 优先做人类可读摘要，而不是堆大段 unified diff

## Suggested private-repo policy

- 原始文件进入私有仓库
- 脱敏副本进入 artifacts
- commit message 使用低泄漏摘要
- 恢复时优先保守，不覆盖本机凭证

