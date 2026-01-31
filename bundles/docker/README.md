# Docker Bundle

Deploy align-app as a multi-user Docker container with GPU support.

## Building the Docker Image

```bash
cd /path/to/align-app
./bundles/docker/scripts/build_image.sh
```

This builds the `align-app` image from the project root using the Dockerfile.

## Running the Container

### Using the run script (defaults to port 9000)
```bash
./bundles/docker/scripts/run_image.sh        # runs on port 9000
./bundles/docker/scripts/run_image.sh 8080   # runs on port 8080
```

### Manual run without GPU
```bash
docker run -it --rm -p 9000:80 align-app
```

### Manual run with GPU (requires nvidia-container-toolkit)
```bash
docker run -it --rm --gpus all -p 9000:80 align-app
```

Open your browser to `http://localhost:9000`

## Environment Variables

- `HF_TOKEN` - HuggingFace token for downloading models
- `TRAME_USE_HOST` - Override session URL for reverse proxy setups

Example with HuggingFace token:
```bash
docker run -it --rm --gpus all -p 9000:80 -e HF_TOKEN=your_token align-app
```

## CapRover Deployment

For Heroku-like deployment using CapRover:

1. Create an app in CapRover web UI with **Websocket Support** enabled
2. Deploy:
```bash
cd /path/to/align-app
tar -cvf trame-app.tar \
    bundles/docker/captain-definition \
    bundles/docker/Dockerfile \
    bundles/docker/setup \
    align_app \
    pyproject.toml \
    README.md
caprover deploy -t trame-app.tar
```

## GPU Support on Host

For GPU access, install nvidia-container-toolkit:
```bash
# Ubuntu/Debian
sudo apt-get install nvidia-container-toolkit
sudo systemctl restart docker
```
