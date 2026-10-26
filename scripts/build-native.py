"""Build a self-contained engine for the current platform."""
import platform
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
os_name = {'Darwin': 'darwin', 'Linux': 'linux', 'Windows': 'win32'}.get(platform.system())
cpu = {'arm64': 'arm64', 'aarch64': 'arm64', 'AMD64': 'x64', 'x86_64': 'x64'}.get(platform.machine())
if f'{os_name}-{cpu}' not in {'darwin-arm64', 'darwin-x64', 'linux-x64', 'win32-x64'}:
    raise SystemExit(f'Unsupported platform: {platform.system()} {platform.machine()}')
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
    '--name', 'websmith', '--paths', str(root / 'src'), '--collect-all', 'websmith',
    '--collect-all', 'jsonschema_specifications', '--copy-metadata', 'jsonschema',
    '--distpath', str(root / 'dist/native'), '--workpath', str(root / 'build/native'),
    '--specpath', str(root / 'build'), str(root / 'src/websmith_native.py'),
], check=True, cwd=root)
binary = 'websmith.exe' if os_name == 'win32' else 'websmith'
subprocess.run([str(root / 'dist/native' / binary), '--version'], check=True)
