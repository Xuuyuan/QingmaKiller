"""发行包构建脚本: PyInstaller 打包主程序, 组装发布 zip 并生成 Release 说明

需在 Python 3.11+ 环境运行(仅对构建环境的要求, 与程序本身的运行环境无关):

    pip install . pyinstaller
    python scripts/package_release.py

产物位于 dist/: QingmaKiller_v{版本号}.zip 与 release_notes.md
"""
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit('package_release.py 需要 Python 3.11+ 运行(tomllib), 请勿使用程序运行环境的旧版本 Python 执行本脚本')

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'


def run(cmd, **kwargs):  # 执行命令, 非零退出码时终止构建
    print(f'+ {subprocess.list2cmdline([str(c) for c in cmd])}')
    subprocess.run(cmd, check=True, **kwargs)


def read_version():  # 版本号单一来源: pyproject.toml
    with open(ROOT / 'pyproject.toml', 'rb') as fp:
        return tomllib.load(fp)['project']['version']


def build_exe():  # PyInstaller onefile 打包主程序(不用 UPX, 降低杀软误报概率)
    run([sys.executable, '-m', 'PyInstaller', '--onefile', '--clean', '--noconfirm', '--name', 'QingmaKiller', 'main.py'], cwd=ROOT)


def previous_tag():  # 当前提交的上一枚发行 tag, 用于生成变更日志(无 tag 时返回None)
    proc = subprocess.run(['git', 'describe', '--tags', '--abbrev=0', 'HEAD^'], capture_output=True, text=True, cwd=ROOT)
    return proc.stdout.strip() if proc.returncode == 0 else None


def write_release_notes(version):  # 生成 Release 说明: 静态模板 + 自上一 tag 以来的提交记录
    tag = previous_tag()
    changelog = ''
    if tag:
        proc = subprocess.run(['git', 'log', '--no-decorate', f'{tag}..HEAD'], capture_output=True, text=True, cwd=ROOT)
        changelog = '\n'.join(f'- {line.strip()}' for line in proc.stdout.splitlines() if line.strip())
    body = f'''## 青马易战自动答题工具 QingmaKiller v{version}

**本工具仅供学习交流使用。**

### 更新内容

{changelog or '- (无变更记录)'}

### 使用方法

1. 下载下方的 `QingmaKiller_v{version}.zip` 压缩包。
2. 解压到任意文件夹, 双击运行 `QingmaKiller.exe`, 按提示输入参数即可(搜题服务 tikuAdapter 会随主程序自动启动/关闭, 无需手动运行)。

### 注意事项

- 程序未做代码签名, 首次运行如遇 Windows SmartScreen 提示, 点击【更多信息】→【仍要运行】; 若被杀毒软件误报, 请添加信任后使用。
- 本地题库 `tiku.json` 位于程序同目录, 答题过程中会自动补充, 也可手动编辑。
- 程序运行日志见同目录 `qingmakiller.log`, 遇到异常时可通过该文件定位问题。
'''
    notes_path = DIST / 'release_notes.md'
    notes_path.write_text(body, encoding='utf-8')
    print(f'已生成 Release 说明: {notes_path}')


def make_zip(version):  # 组装发布 zip: 主程序 + tikuAdapter + 题库 + 许可证
    bundle_files = [
        (DIST / 'QingmaKiller.exe', 'QingmaKiller.exe'),
        (ROOT / 'tikuAdapter.exe', 'tikuAdapter.exe'),
        (ROOT / 'tiku.json', 'tiku.json'),
        (ROOT / 'LICENSE', 'LICENSE'),
    ]
    missing = [str(src) for src, _ in bundle_files if not src.is_file()]
    if missing:
        sys.exit(f'缺少发行文件: {", ".join(missing)}')
    zip_path = DIST / f'QingmaKiller_v{version}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, arcname in bundle_files:
            zf.write(src, arcname)
    print(f'已生成发行包: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f}MB)')


if __name__ == '__main__':
    version = read_version()
    build_exe()
    make_zip(version)
    write_release_notes(version)
