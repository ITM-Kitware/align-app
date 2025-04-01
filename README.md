# align-app

Web app showcasing the [Align AI Decision Maker library](https://github.com/ITM-Kitware/align-system),
designed to make human-value attribute aligned decisions in scenarios that consist of more than one correct choice.

![Align UI Hero](./doc/ui-hero.png)

## Installing

```console
python3 -m venv .venv
source .venv/bin/activate
pip install https://github.com/ITM-Kitware/align-app.git
```

Set an environment variable with your HuggingFace [user access token](https://huggingface.co/docs/transformers.js/en/guides/private).
Many of the LLM Backbones used in the app require you agree to some terms.

```console
export HF_TOKEN=<your token obtained from Hugging Face website>
```

Run the application

```console
source .venv/bin/activate
align-app
```

Then visit http://localhost:8080

## Development

```console
git clone https://github.com/ITM-Kitware/align-app.git
cd align-app
pip install -e ".[dev]"
pre-commit install
```

### Release

Merge a PR to `main` with semantic commit messages.
