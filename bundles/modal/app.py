import os

import modal
from pathlib import Path

MINUTES = 60
PORT = 8080

REPO_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_ZIP = os.environ.get("ALIGN_EXPERIMENTS_ZIP")

app = modal.App("align-app")

base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "unzip")
    .pip_install("poetry")
    .add_local_file(str(REPO_ROOT / "pyproject.toml"), "/app/pyproject.toml", copy=True)
    .add_local_file(str(REPO_ROOT / "poetry.lock"), "/app/poetry.lock", copy=True)
    .add_local_file(str(REPO_ROOT / "README.md"), "/app/README.md", copy=True)
    .add_local_dir(str(REPO_ROOT / "align_app"), "/app/align_app", copy=True)
    .workdir("/app")
)

if EXPERIMENTS_ZIP:
    image = base_image.add_local_file(
        EXPERIMENTS_ZIP, "/app/experiments.zip", copy=True
    ).run_commands(
        "poetry config virtualenvs.create false && poetry install --only main",
        "unzip experiments.zip -d /app && rm experiments.zip",
    )
else:
    image = base_image.run_commands(
        "poetry config virtualenvs.create false && poetry install --only main"
    )


@app.function(
    image=image,
    gpu="L4",
    secrets=[modal.Secret.from_name("huggingface")],
    timeout=30 * MINUTES,
    scaledown_window=5 * MINUTES,
)
@modal.web_server(port=PORT, startup_timeout=5 * MINUTES)
def serve():
    import subprocess
    from pathlib import Path

    cmd = [
        "poetry",
        "run",
        "align-app",
        "--server",
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
    ]
    if Path("/app/experiments").exists():
        cmd.extend(["--experiments", "/app/experiments"])

    subprocess.Popen(cmd, cwd="/app")
