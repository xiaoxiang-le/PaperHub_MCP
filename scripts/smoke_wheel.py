"""Install a wheel offline into a temporary venv and check its entry point.

Use the development interpreter to reuse its installed dependencies.
No network or model requests occur.
"""

import argparse
import json
import os
import subprocess
import sys
import sysconfig
import tempfile
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="paperhub-wheel-smoke-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
        binaries = environment / ("Scripts" if sys.platform == "win32" else "bin")
        python = binaries / ("python.exe" if sys.platform == "win32" else "python")
        # venv's system_site_packages refers to the base interpreter, not a
        # parent development venv. Explicitly share its dependency directory.
        location = subprocess.run(
            [str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (Path(location) / "paperhub-smoke-dependencies.pth").write_text(
            "import site; site.addsitedir(" + repr(sysconfig.get_path("purelib")) + ")\n",
            encoding="utf-8",
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
            cwd=root,
            check=True,
            capture_output=True,
        )
        code = "import json,paperhub; print(json.dumps({'version':paperhub.__version__,'file':paperhub.__file__}))"
        result = subprocess.run(
            [str(python), "-I", "-c", code],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        installed = json.loads(result.stdout)
        assert Path(installed["file"]).is_relative_to(environment), (
            "Imported editable source instead of wheel"
        )
        env = {
            **os.environ,
            "PAPERHUB_DATA_DIR": str(root / "state"),
            "PAPERHUB_OUTPUT_DIR": str(root / "output"),
        }
        launched = subprocess.run(
            [
                str(binaries / ("paperhub-mcp.exe" if sys.platform == "win32" else "paperhub-mcp")),
                "--doctor",
            ],
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
        )
        if launched.returncode:
            raise RuntimeError(launched.stderr.decode("utf-8", errors="replace"))
        print(
            json.dumps(
                {"wheel": wheel.name, "version": installed["version"], "installed_cli": "passed"}
            )
        )


if __name__ == "__main__":
    main()
