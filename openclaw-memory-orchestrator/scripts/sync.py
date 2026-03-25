#!/usr/bin/env python3
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_INCLUDE = [
    'SOUL.md', 'IDENTITY.md', 'USER.md', 'MEMORY.md', 'TOOLS.md',
    'HEARTBEAT.md', 'AGENTS.md', 'BOOTSTRAP.md', 'memory/**/*.md',
    'skills/**', 'avatars/**'
]
DEFAULT_EXCLUDE = ['.git/**', '.openclaw-sync/**', 'node_modules/**', 'sessions/**', '*.log', '*.tmp', '*.bak']
TEXT_EXTS = {'.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'}

REDACTION_PATTERNS = [
    ('github_token', re.compile(r'(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})')),
    ('openai_key', re.compile(r'sk-[A-Za-z0-9]{20,}')),
    ('bearer_token', re.compile(r'Bearer\s+[A-Za-z0-9._\-]+')),
    ('secret_field', re.compile(r'(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*[^\s\n]+')),
    ('email', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    ('ipv4', re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
    ('private_key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run(cmd: List[str], cwd: Path = None, check: bool = False) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(f'command failed: {cmd}\n{p.stderr}')
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def count_lines(text: str) -> int:
    return 0 if not text else text.count('\n') + (0 if text.endswith('\n') else 1)


def extract_frontmatter(text: str):
    if not text.startswith('---\n'):
        return None
    parts = text.split('\n---\n', 1)
    if len(parts) != 2:
        return None
    raw = parts[0][4:]
    data = {}
    for line in raw.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            data[k.strip()] = v.strip()
    return data


def text_preview(text: str, limit: int = 240) -> str:
    flat = ' '.join(line.strip() for line in text.splitlines() if line.strip())
    return flat[:limit]


def redact_text(text: str) -> Tuple[str, List[Dict[str, object]]]:
    hits = []
    redacted = text
    for name, pattern in REDACTION_PATTERNS:
        matches = list(pattern.finditer(redacted))
        if matches:
            hits.append({'type': name, 'count': len(matches)})
            redacted = pattern.sub(f'<redacted:{name}>', redacted)
    return redacted, hits


def merge_hit_reports(reports: List[List[Dict[str, object]]]) -> List[Dict[str, object]]:
    merged: Dict[str, int] = {}
    for report in reports:
        for item in report:
            merged[item['type']] = merged.get(item['type'], 0) + int(item['count'])
    return [{'type': k, 'count': v} for k, v in sorted(merged.items())]


def load_config(cli_workspace: str = None) -> Dict[str, object]:
    env_cfg = os.environ.get('OPENCLAW_SYNC_CONFIG')
    if env_cfg and Path(env_cfg).exists():
        cfg = load_json(Path(env_cfg), {})
        cfg['_config_source'] = env_cfg
        return apply_defaults(cfg, cli_workspace)
    if cli_workspace:
        candidate = Path(cli_workspace) / 'sync.config.json'
        if candidate.exists():
            cfg = load_json(candidate, {})
            cfg['_config_source'] = str(candidate)
            return apply_defaults(cfg, cli_workspace)
    cwd_candidate = Path.cwd() / 'sync.config.json'
    if cwd_candidate.exists():
        cfg = load_json(cwd_candidate, {})
        cfg['_config_source'] = str(cwd_candidate)
        return apply_defaults(cfg, cli_workspace)
    return apply_defaults({}, cli_workspace)


def apply_defaults(cfg: Dict[str, object], cli_workspace: str = None) -> Dict[str, object]:
    workspace_dir = Path(cli_workspace or cfg.get('workspace_dir') or os.environ.get('WORKSPACE_DIR') or os.getcwd()).resolve()
    repo_dir = Path(cfg.get('repo_dir') or os.environ.get('REPO_DIR') or workspace_dir).resolve()
    snapshot_dir = Path(cfg.get('snapshot_dir') or (workspace_dir / '.openclaw-sync' / 'snapshots')).resolve()
    artifacts_dir = Path(cfg.get('artifacts_dir') or (workspace_dir / '.openclaw-sync' / 'artifacts')).resolve()
    return {
        'workspace_dir': str(workspace_dir),
        'repo_dir': str(repo_dir),
        'snapshot_dir': str(snapshot_dir),
        'artifacts_dir': str(artifacts_dir),
        'remote': cfg.get('remote') or os.environ.get('GITHUB_REMOTE', 'origin'),
        'branch': cfg.get('branch') or os.environ.get('GITHUB_BRANCH', ''),
        'persona_branch_prefix': cfg.get('persona_branch_prefix', 'persona/'),
        'sync_strategy': cfg.get('sync_strategy', 'hybrid'),
        'heartbeat_minutes': int(cfg.get('heartbeat_minutes', 60)),
        'include_patterns': cfg.get('include_patterns', DEFAULT_INCLUDE),
        'exclude_patterns': cfg.get('exclude_patterns', DEFAULT_EXCLUDE),
        'private_repo': bool(cfg.get('private_repo', True)),
        'allow_raw_push_to_private': bool(cfg.get('allow_raw_push_to_private', True)),
        'pull_before_push': bool(cfg.get('pull_before_push', True)),
        'redaction': cfg.get('redaction', {'enabled': True}),
        '_config_source': cfg.get('_config_source', 'defaults+env'),
    }


def path_matches(path: Path, patterns: List[str]) -> bool:
    s = path.as_posix()
    for pat in patterns:
        if path.match(pat) or s == pat:
            return True
    return False


def collect_files(workspace: Path, include_patterns: List[str], exclude_patterns: List[str]) -> List[Path]:
    candidates = []
    for path in workspace.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace)
        if path_matches(rel, exclude_patterns):
            continue
        if include_patterns and not any(rel.match(p) or rel.as_posix() == p for p in include_patterns):
            continue
        candidates.append(path)
    return sorted(set(candidates))


def summarize_text(text: str) -> Dict[str, object]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = [line.lstrip('#').strip() for line in lines if line.startswith('#')]
    bullets = [line[1:].strip() for line in lines if line.startswith(('-', '*'))]
    return {
        'headings': headings[:8],
        'key_points': bullets[:8],
        'preview': text_preview(text, 180)
    }


def get_git_state(repo_dir: Path) -> Dict[str, object]:
    if not (repo_dir / '.git').exists():
        return {'present': False}
    _, branch, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir)
    _, head, _ = run(['git', 'rev-parse', 'HEAD'], cwd=repo_dir)
    _, remote_url, _ = run(['git', 'remote', 'get-url', 'origin'], cwd=repo_dir)
    _, status, _ = run(['git', 'status', '--short'], cwd=repo_dir)
    return {
        'present': True,
        'branch': branch,
        'head': head,
        'remote_url': remote_url,
        'dirty': bool(status.strip()),
        'status_short': status.splitlines() if status else []
    }


def current_persona(git_state: Dict[str, object], prefix: str) -> Dict[str, object]:
    branch = git_state.get('branch', '') if git_state else ''
    name = branch[len(prefix):] if prefix and branch.startswith(prefix) else branch or 'unknown'
    return {'branch': branch, 'name': name}


def previous_snapshot(snapshot_dir: Path):
    if not snapshot_dir.exists():
        return None
    files = sorted(snapshot_dir.glob('*/snapshot.json'))
    return files[-1] if files else None


def build_snapshot(cfg: Dict[str, object]) -> Dict[str, object]:
    workspace = Path(cfg['workspace_dir'])
    repo_dir = Path(cfg['repo_dir'])
    include_patterns = cfg['include_patterns']
    exclude_patterns = cfg['exclude_patterns']
    file_paths = collect_files(workspace, include_patterns, exclude_patterns)
    file_entries = []
    summaries = []
    per_file_hits = []
    for path in file_paths:
        rel = path.relative_to(workspace).as_posix()
        kind = path.suffix.lower() or 'binary'
        size = path.stat().st_size
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()
        preview = ''
        frontmatter = None
        hits = []
        line_count = 0
        try:
            if path.suffix.lower() in TEXT_EXTS or size < 512 * 1024:
                text = path.read_text(encoding='utf-8', errors='replace')
                preview = text_preview(text)
                frontmatter = extract_frontmatter(text)
                _, hits = redact_text(text)
                line_count = count_lines(text)
                summaries.append({'path': rel, **summarize_text(text)})
            else:
                text = ''
        except Exception as e:
            text = ''
            preview = f'<unreadable:{e}>'
        per_file_hits.append(hits)
        file_entries.append({
            'path': rel,
            'kind': kind,
            'size': size,
            'mtime': mtime,
            'sha256': sha256_file(path),
            'line_count': line_count,
            'sensitive_hits': hits,
            'frontmatter': frontmatter,
            'preview': preview,
        })

    git_state = get_git_state(repo_dir)
    persona = current_persona(git_state, cfg['persona_branch_prefix'])
    prev_path = previous_snapshot(Path(cfg['snapshot_dir']))
    prev = load_json(prev_path, {}) if prev_path else {}
    diff_summary = diff_snapshots(prev, {'files': file_entries})
    report = merge_hit_reports(per_file_hits)
    snapshot = {
        'schema_version': '1.0.0',
        'created_at': now_iso(),
        'workspace_dir': str(workspace),
        'repo_dir': str(repo_dir),
        'git': git_state,
        'persona': persona,
        'sync_strategy': {
            'mode': cfg['sync_strategy'],
            'config_source': cfg['_config_source'],
            'pull_before_push': cfg['pull_before_push'],
            'allow_raw_push_to_private': cfg['allow_raw_push_to_private'],
            'private_repo': cfg['private_repo']
        },
        'files': file_entries,
        'memory_summary': summaries,
        'diff_from_previous': diff_summary,
        'redaction_report': report,
        'heartbeat': load_json(Path(cfg['artifacts_dir']) / 'heartbeat_state.json', {}),
    }
    return snapshot


def diff_snapshots(old: Dict[str, object], new: Dict[str, object]) -> Dict[str, object]:
    old_map = {f['path']: f for f in old.get('files', [])}
    new_map = {f['path']: f for f in new.get('files', [])}
    old_paths = set(old_map)
    new_paths = set(new_map)
    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    modified = sorted([p for p in old_paths & new_paths if old_map[p].get('sha256') != new_map[p].get('sha256')])
    highlights = []
    for p in added[:3]:
        highlights.append(f'新增文件: {p}')
    for p in modified[:4]:
        old_hits = sum(x['count'] for x in old_map[p].get('sensitive_hits', []))
        new_hits = sum(x['count'] for x in new_map[p].get('sensitive_hits', []))
        hint = '，敏感命中增加' if new_hits > old_hits else ''
        highlights.append(f'修改文件: {p}{hint}')
    for p in removed[:3]:
        highlights.append(f'删除文件: {p}')
    risk = 'review' if any('IDENTITY' in p or 'SOUL' in p or 'TOOLS' in p for p in modified + added + removed) else 'low'
    return {
        'changed': {'added': len(added), 'removed': len(removed), 'modified': len(modified)},
        'sections': section_change_counts(added + modified + removed),
        'highlights': highlights,
        'risk': risk,
        'paths': {'added': added, 'removed': removed, 'modified': modified},
    }


def section_change_counts(paths: List[str]) -> List[Dict[str, object]]:
    groups: Dict[str, int] = {}
    for p in paths:
        group = p.split('/', 1)[0]
        groups[group] = groups.get(group, 0) + 1
    return [{'section': k, 'changes': v} for k, v in sorted(groups.items(), key=lambda x: (-x[1], x[0]))]


def snapshot_command(cfg: Dict[str, object]) -> Dict[str, object]:
    snapshot = build_snapshot(cfg)
    ts = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = Path(cfg['snapshot_dir']) / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(out_dir / 'snapshot.json', snapshot)
    redacted_text, hits = redact_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    (out_dir / 'snapshot.redacted.json').write_text(redacted_text, encoding='utf-8')
    summary_lines = ['# memory summary', '']
    for item in snapshot['memory_summary'][:10]:
        summary_lines.append(f"- {item['path']}: {item['preview']}")
    (out_dir / 'summary.txt').write_text('\n'.join(summary_lines), encoding='utf-8')
    return {'snapshot_dir': str(out_dir), 'snapshot': snapshot, 'redaction_hits': hits}


def human_diff(snapshot: Dict[str, object]) -> str:
    diff = snapshot['diff_from_previous']
    lines = [
        '# human-readable diff',
        '',
        f"changed: +{diff['changed']['added']} / ~{diff['changed']['modified']} / -{diff['changed']['removed']}",
        f"risk: {diff['risk']}",
        ''
    ]
    if diff['sections']:
        lines.append('top sections:')
        for item in diff['sections'][:6]:
            lines.append(f"- {item['section']}: {item['changes']}")
        lines.append('')
    lines.append('highlights:')
    for item in diff['highlights'][:8] or ['- 无显著变化']:
        lines.append(f'- {item}')
    return '\n'.join(lines)


def diff_command(cfg: Dict[str, object]) -> Dict[str, object]:
    result = snapshot_command(cfg)
    text = human_diff(result['snapshot'])
    out = Path(result['snapshot_dir']) / 'human_diff.txt'
    out.write_text(text, encoding='utf-8')
    return {'snapshot_dir': result['snapshot_dir'], 'human_diff_path': str(out), 'text': text}


def redact_command(cfg: Dict[str, object]) -> Dict[str, object]:
    workspace = Path(cfg['workspace_dir'])
    files = collect_files(workspace, cfg['include_patterns'], cfg['exclude_patterns'])
    results = []
    for path in files:
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        redacted, hits = redact_text(text)
        if hits:
            rel = path.relative_to(workspace)
            out = Path(cfg['artifacts_dir']) / 'redacted' / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(redacted, encoding='utf-8')
            results.append({'path': rel.as_posix(), 'hits': hits, 'redacted_copy': str(out)})
    report = {'created_at': now_iso(), 'files': results}
    out_path = Path(cfg['artifacts_dir']) / 'redaction_report.json'
    save_json(out_path, report)
    return {'report_path': str(out_path), 'report': report}


def make_commit_message(snapshot: Dict[str, object]) -> str:
    diff = snapshot['diff_from_previous']['changed']
    persona = snapshot['persona']['name']
    return f"memory({persona}): +{diff['added']} ~{diff['modified']} -{diff['removed']}"


def ensure_git_repo(repo_dir: Path):
    if not (repo_dir / '.git').exists():
        raise RuntimeError(f'{repo_dir} is not a git repository')


def backup_command(cfg: Dict[str, object]) -> Dict[str, object]:
    repo_dir = Path(cfg['repo_dir'])
    ensure_git_repo(repo_dir)
    snap = snapshot_command(cfg)
    diff = diff_command(cfg)
    redact = redact_command(cfg)
    snapshot = snap['snapshot']
    msg = make_commit_message(snapshot)
    if cfg['pull_before_push']:
        run(['git', 'pull', '--rebase', cfg['remote']], cwd=repo_dir)
    run(['git', 'add', '.'], cwd=repo_dir)
    code, out, err = run(['git', 'commit', '-m', msg], cwd=repo_dir)
    if code != 0 and 'nothing to commit' not in (out + err):
        raise RuntimeError(err or out)
    push_code, push_out, push_err = run(['git', 'push', cfg['remote'], snapshot['git'].get('branch') or 'HEAD'], cwd=repo_dir)
    return {
        'snapshot_dir': snap['snapshot_dir'],
        'human_diff_path': diff['human_diff_path'],
        'redaction_report_path': redact['report_path'],
        'commit_message': msg,
        'push_code': push_code,
        'push_stdout': push_out,
        'push_stderr': push_err,
    }


def restore_command(cfg: Dict[str, object], only: List[str]) -> Dict[str, object]:
    repo_dir = Path(cfg['repo_dir'])
    ensure_git_repo(repo_dir)
    branch = current_branch(repo_dir)
    run(['git', 'fetch', cfg['remote']], cwd=repo_dir, check=False)
    run(['git', 'pull', cfg['remote'], branch], cwd=repo_dir, check=False)
    restored = []
    if only:
        for item in only:
            run(['git', 'checkout', 'HEAD', '--', item], cwd=repo_dir, check=False)
            restored.append(item)
    snap = snapshot_command(cfg)
    return {'restored': restored or ['all tracked changes'], 'snapshot_dir': snap['snapshot_dir']}


def current_branch(repo_dir: Path) -> str:
    _, branch, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir)
    return branch or 'main'


def list_branches(repo_dir: Path) -> List[str]:
    _, out, _ = run(['git', 'branch', '--list'], cwd=repo_dir)
    return [line.replace('*', '').strip() for line in out.splitlines() if line.strip()]


def branch_command(cfg: Dict[str, object], action: str, name: str = '') -> Dict[str, object]:
    repo_dir = Path(cfg['repo_dir'])
    ensure_git_repo(repo_dir)
    prefix = cfg['persona_branch_prefix']
    target = f'{prefix}{name}' if name and prefix and not name.startswith(prefix) else name
    if action == 'list':
        return {'branches': list_branches(repo_dir)}
    if action == 'create':
        run(['git', 'checkout', '-b', target], cwd=repo_dir, check=True)
        return {'created': target}
    if action == 'switch':
        run(['git', 'checkout', target], cwd=repo_dir, check=True)
        return {'switched': target}
    if action == 'snapshot':
        snap = snapshot_command(cfg)
        return {'snapshot_dir': snap['snapshot_dir'], 'branch': current_branch(repo_dir)}
    raise ValueError(f'unsupported branch action: {action}')


def heartbeat_command(cfg: Dict[str, object]) -> Dict[str, object]:
    state_path = Path(cfg['artifacts_dir']) / 'heartbeat_state.json'
    state = load_json(state_path, {}) or {}
    now = dt.datetime.now(dt.timezone.utc)
    mins = int(cfg['heartbeat_minutes'])
    due = True
    if state.get('last_success_at'):
        last = dt.datetime.fromisoformat(state['last_success_at'])
        due = (now - last) >= dt.timedelta(minutes=mins)
    result = {'triggered': due, 'strategy': cfg['sync_strategy']}
    if cfg['sync_strategy'] in ('heartbeat', 'hybrid') and due:
        try:
            backup = backup_command(cfg)
            result['last_result'] = 'success'
            result['backup'] = backup
            state['last_success_at'] = now_iso()
        except Exception as e:
            result['last_result'] = f'failed: {e}'
    else:
        result['last_result'] = 'skipped'
    state['last_run_at'] = now_iso()
    state['next_due_at'] = (now + dt.timedelta(minutes=mins)).isoformat()
    state['last_result'] = result['last_result']
    save_json(state_path, state)
    result['state_path'] = str(state_path)
    return result


def status_command(cfg: Dict[str, object]) -> Dict[str, object]:
    repo_dir = Path(cfg['repo_dir'])
    git = get_git_state(repo_dir)
    heartbeat = load_json(Path(cfg['artifacts_dir']) / 'heartbeat_state.json', {}) or {}
    return {
        'config_source': cfg['_config_source'],
        'workspace_dir': cfg['workspace_dir'],
        'repo_dir': cfg['repo_dir'],
        'git': git,
        'persona': current_persona(git, cfg['persona_branch_prefix']),
        'strategy': cfg['sync_strategy'],
        'heartbeat': heartbeat,
    }


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description='OpenClaw memory sync utility')
    p.add_argument('--workspace', default=None)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('snapshot')
    sub.add_parser('diff')
    sub.add_parser('redact')
    sub.add_parser('backup')
    restore = sub.add_parser('restore')
    restore.add_argument('--only', nargs='*', default=[])
    branch = sub.add_parser('branch')
    branch.add_argument('action', choices=['create', 'switch', 'list', 'snapshot'])
    branch.add_argument('--name', default='')
    sub.add_parser('heartbeat')
    sub.add_parser('status')
    return p


def main():
    args = build_parser().parse_args()
    cfg = load_config(args.workspace)
    cmd = args.command
    if cmd == 'snapshot':
        print_json(snapshot_command(cfg))
    elif cmd == 'diff':
        print_json(diff_command(cfg))
    elif cmd == 'redact':
        print_json(redact_command(cfg))
    elif cmd == 'backup':
        print_json(backup_command(cfg))
    elif cmd == 'restore':
        print_json(restore_command(cfg, args.only))
    elif cmd == 'branch':
        print_json(branch_command(cfg, args.action, args.name))
    elif cmd == 'heartbeat':
        print_json(heartbeat_command(cfg))
    elif cmd == 'status':
        print_json(status_command(cfg))
    else:
        raise ValueError(cmd)

if __name__ == '__main__':
    main()

