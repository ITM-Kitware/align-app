# align-app

Web app showcasing the [Align AI Decision Maker library](https://github.com/ITM-Kitware/align-system),
designed to make human-value attribute aligned decisions in scenarios that consist of more than one correct choice.

Users select the ADM type, LLM backbone, alignment targets, and scenario. Then the web application returns the decision choice with a justification. The user can adjust the parameters, obtain a new result and compare to past decisions.

- Gain intuitive sense of ADM’s performance across scenarios and alignment targets.
- Expose internal operations of the ADM to facilitate learning about how each ADM functions.
- Battle test ALIGN System’s use as a Python library.

### [Watch the demo](https://drive.google.com/file/d/1d7rykoFe7UB6SyoV_GtJy499F5zqBTea/view?usp=sharing)

![Align UI Hero](./doc/ui-hero.png)

## Install

### Use Poetry Package Manager

```console
pip install poetry
git clone https://github.com/ITM-Kitware/align-app.git
cd align-app
poetry install
```

### Setup HuggingFace User Access Token

Many of the LLM Backbones used in the app require you agree to some terms.
Example [Mistral-AI's](https://huggingface.co/mistralai/Mistral-7B-v0.3)

1. Agree to the terms on the HuggingFace website for the models you use.
2. Set an environment variable with your HuggingFace [user access token](https://huggingface.co/docs/transformers.js/en/guides/private).

```console
export HF_TOKEN=<your token obtained from Hugging Face website>
```

### Run the Application

```console
poetry run align-app
```

Then visit http://localhost:8080

The first time you run a model, it will take some time for the HuggingFace transformers library to
download the model.

### Run with Custom ADM Configs

You can load custom ADM configurations from align-system using the `--decider` flag. This supports both:

- **Composable ADM configs** (e.g., `adm/outlines_regression_aligned.yaml`)
- **Full experiment configs** with `@package _global_` directive (e.g., `phase2_july_collab/pipeline_baseline.yaml`)

```console
# Load a composable ADM config
poetry run align-app --decider adm/phase2_pipeline_zeroshot_comparative_regression.yaml

# Load a full experiment config
poetry run align-app --decider phase2_july_collab/pipeline_fewshot_comparative_regression_20icl_live_eval_test.yaml

# Load multiple configs
poetry run align-app --decider adm/phase2_pipeline_zeroshot_comparative_regression.yaml phase2_july_collab/pipeline_baseline.yaml

# Load configs using absolute paths
poetry run align-app --decider /path/to/align-system/configs/adm/phase2_pipeline_zeroshot_comparative_regression.yaml
```

### Optionally Configure Network Port or Host

The web server is from Trame. To configure the port, use the `--port` arg

```console
poetry run align-app --port 8081
```

To expose the server to the network run with the `--host` arg

```console
poetry run align-app --host 0.0.0.0
```

## Development

```console
pip install poetry
git clone https://github.com/ITM-Kitware/align-app.git
cd align-app
poetry install --with dev
pre-commit install
```

### Release

Merge a PR to `main` with semantic commit messages.
