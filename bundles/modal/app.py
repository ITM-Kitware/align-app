import os

import modal
from pathlib import Path

MINUTES = 60
PORT = 8080

REPO_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS = os.environ.get("EXPERIMENTS")
EXPERIMENTS_PATH = Path(EXPERIMENTS) if EXPERIMENTS else None

app = modal.App("align-app")

MODELS_TO_PREBAKE = [
    "mistralai/Mistral-7B-Instruct-v0.3",
]


def download_models():
    from huggingface_hub import snapshot_download

    for model_id in MODELS_TO_PREBAKE:
        print(f"Downloading {model_id}...")
        snapshot_download(model_id, token=os.environ.get("HF_TOKEN"))
        print(f"Completed {model_id}")


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

image = base_image

if EXPERIMENTS_PATH and EXPERIMENTS_PATH.exists():
    if EXPERIMENTS_PATH.is_dir():
        image = image.add_local_dir(
            str(EXPERIMENTS_PATH), "/app/experiments", copy=True
        )
    elif EXPERIMENTS_PATH.suffix.lower() == ".zip":
        image = image.add_local_file(
            str(EXPERIMENTS_PATH), "/app/experiments.zip", copy=True
        )

install_commands = [
    "poetry config virtualenvs.create false && poetry install --only main",
]

if EXPERIMENTS_PATH and EXPERIMENTS_PATH.exists():
    if EXPERIMENTS_PATH.is_file() and EXPERIMENTS_PATH.suffix.lower() == ".zip":
        install_commands.append("unzip experiments.zip -d /app && rm experiments.zip")

image = image.run_commands(*install_commands).run_function(
    download_models,
    secrets=[modal.Secret.from_name("huggingface")],
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
        "--llm-backbones",
        *MODELS_TO_PREBAKE,
    ]
    if Path("/app/experiments").exists():
        cmd.extend(["--experiments", "/app/experiments"])

    subprocess.Popen(cmd, cwd="/app")
