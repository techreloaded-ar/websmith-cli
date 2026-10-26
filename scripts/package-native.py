"""Package the tested native executable and a SHA-256 digest for GitHub Releases."""
import hashlib
import platform
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
os_name = {'Darwin': 'darwin', 'Linux': 'linux', 'Windows': 'win32'}[platform.system()]
cpu = {'arm64': 'arm64', 'aarch64': 'arm64', 'AMD64': 'x64', 'x86_64': 'x64'}[platform.machine()]
binary = 'websmith.exe' if os_name == 'win32' else 'websmith'
source = root / 'dist/native' / binary
out = root / 'dist/release'
out.mkdir(parents=True, exist_ok=True)
archive = out / f'websmith-{os_name}-{cpu}.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    bundle.write(source, binary)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix('.sha256')).write_text(f'{digest}  {archive.name}\n')
print(archive)
