# Build from repository root using the project's Python environment.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

root = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(root / "server"))
analysis = Analysis(
    [str(root / "server" / "desktop_entry.py")],
    pathex=[str(root / "server")],
    datas=[(str(root / "web" / "dist"), "frontend"), (str(root / "docs" / "欢乐斗地主经典玩法规则.md"), "docs")] + collect_data_files("app"),
    hiddenimports=collect_submodules("app") + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"],
    excludes=["torch", "transformers", "peft", "datasets", "accelerate", "pytest"],
    hookspath=[],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="cardlab-backend", console=True)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="backend")
