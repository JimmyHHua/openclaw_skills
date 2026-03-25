# Usage Examples

## 自然语言触发

- 备份当前 memory 到 GitHub
- 给我看这次记忆更新的可读 diff
- 切到 research 人格分支
- 跑一次 heartbeat 备份
- 只恢复 MEMORY.md 和 memory/profile.md

## 命令式触发

```bash
python scripts/sync.py snapshot
python scripts/sync.py diff
python scripts/sync.py backup
python scripts/sync.py restore --only MEMORY.md memory/profile.md
python scripts/sync.py branch create --name research
python scripts/sync.py branch switch --name research
python scripts/sync.py heartbeat
python scripts/sync.py status
```

