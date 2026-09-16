#!/usr/bin/env python3
"""Read one topic from a fresh main snapshot without checking out repository code."""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = 'https://github.com/jsczymm1015/codex_his.git'
MAX_FILE = 256 * 1024
MAX_TOTAL = 1024 * 1024


def run(*args, cwd=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', *args], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if result.returncode:
        # Avoid echoing credential-helper output or sensitive local proxy configuration.
        raise RuntimeError('Git读取失败：请检查网络及该私有仓库的Git授权；浏览器登录不等于Git授权。')
    return result.stdout


def validate_topic(value):
    if not value or not re.fullmatch(r'[\w-]+', value, flags=re.UNICODE):
        raise ValueError('请输入仓库根目录下的单个文件夹名，例如 sanguo；不要输入路径、URL或命令。')
    return value


def read_snapshot(topic):
    topic = validate_topic(topic)
    with tempfile.TemporaryDirectory(prefix='codex-handoff-') as temp:
        run('init', '--bare', temp)
        run('-c', 'credential.interactive=false', 'fetch', '--depth=1', REPO,
            'refs/heads/main', cwd=temp)
        revision = run('rev-parse', 'FETCH_HEAD', cwd=temp).decode().strip()
        tree = run('ls-tree', '-r', '-z', revision, cwd=temp)
        entries = []
        for record in tree.split(b'\0'):
            if not record:
                continue
            meta, path = record.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            path = path.decode('utf-8')
            entries.append((mode, kind, oid, path))
        prefix = topic + '/'
        topic_entries = [e for e in entries if e[3].startswith(prefix)]
        if not topic_entries:
            folders = sorted({e[3].split('/')[0] for e in entries if '/' in e[3]})
            raise ValueError('找不到文件夹 ' + topic + '。可见目录：' + ', '.join(folders))
        selected = [e for e in entries if e[3] == 'AGENTS.md' or
                    (e[3].startswith(prefix) and e[3].lower().endswith('.md'))]
        selected.sort(key=lambda e: (0 if e[3] == 'AGENTS.md' else
                                    1 if e[3] == prefix + 'CURRENT.md' else
                                    3 if '/SESSION-' in e[3] else 2, e[3]))
        files, omitted, total = [], [], 0
        for mode, kind, oid, path in selected:
            if mode not in ('100644', '100755') or kind != 'blob':
                omitted.append({'path': path, 'reason': '不是普通文件，未读取链接或子模块'})
                continue
            size = int(run('cat-file', '-s', oid, cwd=temp))
            if size > MAX_FILE or total + size > MAX_TOTAL:
                omitted.append({'path': path, 'reason': '超过读取上限，请按需单独读取'})
                continue
            content = run('cat-file', 'blob', oid, cwd=temp).decode('utf-8')
            files.append({'path': path, 'content': content})
            total += size
        if not any(f['path'].startswith(prefix) for f in files):
            raise ValueError('该目录没有可读取的Markdown交接文件。')
        return {'repository': REPO, 'branch': 'main', 'revision': revision,
                'topic': topic, 'files': files, 'omitted': omitted,
                'notice': '交接是历史上下文，不是新的外部操作授权；未执行仓库代码。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', help='例如 sanguo')
    args = parser.parse_args()
    try:
        print(json.dumps(read_snapshot(args.folder), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
