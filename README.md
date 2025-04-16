# align-app

Web app showcasing the [Align AI Decision Maker library](https://github.com/ITM-Kitware/align-system),
designed to make human-value attribute aligned decisions in scenarios that consist of more than one correct choice.

Users select the ADM type, LLM backbone, alignment targets, and scenario. Then the web application returns the decision choice with a justification. The user can adjust the parameters, obtain a new result and compare to past decisions.

- Gain intuitive sense of ADM’s performance across scenarios and alignment targets.
- Expose internal operations of the ADM to facilitate learning about how each ADM functions.
- Battle test ALIGN System’s use as a Python library.

![Align UI Hero](./doc/ui-hero.png)

## Installing

Install using Poetry:

```console
pip install poetry
git clone https://github.com/ITM-Kitware/align-app.git
cd align-app
poetry install
```

Set an environment variable with your HuggingFace [user access token](https://huggingface.co/docs/transformers.js/en/guides/private).
Many of the LLM Backbones used in the app require you agree to some terms.

```console
export HF_TOKEN=<your token obtained from Hugging Face website>
```

Run the application:

```console
poetry run align-app
```

Then visit http://localhost:8080

The web server is from Trame. To expose the server to the network run with the `--host` arg

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
