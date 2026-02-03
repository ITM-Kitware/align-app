import os

import modal
from pathlib import Path

MINUTES = 60
PORT = 8080

REPO_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_ZIP = os.environ.get("ALIGN_EXPERIMENTS_ZIP")

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

if EXPERIMENTS_ZIP:
    image = (
        base_image.add_local_file(EXPERIMENTS_ZIP, "/app/experiments.zip", copy=True)
        .run_commands(
            "poetry config virtualenvs.create false && poetry install --only main",
            "unzip experiments.zip -d /app && rm experiments.zip",
        )
        .run_function(
            download_models,
            secrets=[modal.Secret.from_name("huggingface")],
        )
    )
else:
    image = base_image.run_commands(
        "poetry config virtualenvs.create false && poetry install --only main"
    ).run_function(
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
