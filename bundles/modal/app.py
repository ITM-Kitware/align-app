import modal
from pathlib import Path

MINUTES = 60
PORT = 8080

REPO_ROOT = Path(__file__).parent.parent.parent

app = modal.App("align-app")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("poetry")
    .add_local_file(str(REPO_ROOT / "pyproject.toml"), "/app/pyproject.toml", copy=True)
    .add_local_file(str(REPO_ROOT / "poetry.lock"), "/app/poetry.lock", copy=True)
    .add_local_file(str(REPO_ROOT / "README.md"), "/app/README.md", copy=True)
    .add_local_dir(str(REPO_ROOT / "align_app"), "/app/align_app", copy=True)
    .workdir("/app")
    .run_commands(
        "poetry config virtualenvs.create false && poetry install --only main"
    )
)


@app.function(
    image=image,
    gpu="T4",
    secrets=[modal.Secret.from_name("huggingface")],
    timeout=30 * MINUTES,
    scaledown_window=5 * MINUTES,
)
@modal.web_server(port=PORT, startup_timeout=5 * MINUTES)
def serve():
    import subprocess

    subprocess.Popen(
        [
            "poetry",
            "run",
            "align-app",
            "--server",
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
        ],
        cwd="/app",
    )
