# Modal Deployment for Align App

Deploy align-app as a serverless GPU application on Modal with scale-to-zero.

## Prerequisites

1. Install Modal CLI:

   ```bash
   pip install modal
   modal setup  # authenticate with Modal
   ```

2. Create a HuggingFace secret in Modal:
   ```bash
   modal secret create huggingface HF_TOKEN=<your_huggingface_token>
   ```

## Deployment

```bash
modal deploy bundles/modal/app.py
```

This will output a URL like `https://<workspace>--align-app-serve.modal.run`

## Development / Testing

To test without deploying (ephemeral endpoint):

```bash
modal serve bundles/modal/app.py
```

The app will be available at the printed URL. Press Ctrl+C to stop.

## Configuration

Edit `app.py` to adjust:

- `gpu="T4"` - GPU type (options: T4, L4, A10G, A100, H100)
- `scaledown_window=5 * MINUTES` - How long to keep warm after last request
- `timeout=30 * MINUTES` - Max request duration
- `startup_timeout=5 * MINUTES` - Max time for container to start

Experiment data is baked into the image and passed to `align-app` at startup:

- `EXPERIMENTS` - Local path copied into the image at `/app/experiments`.
  If it is a directory, it is copied directly.
  If it is a `.zip`, it is unpacked into `/app` during the build.

## Costs

- **L4 GPU**: ~$0.76/hour (billed per second)
- **Scale-to-zero**: $0 when no requests
- **Free tier**: $30/month credits

## Architecture

```
User Request → Modal → Container spins up (if cold) → Trame app serves request
                                ↓
                    Container stays warm for scaledown_window
                                ↓
                    No requests → scales to zero ($0)
```
