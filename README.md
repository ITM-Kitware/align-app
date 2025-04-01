# align-app

Web app showcasing the [Align AI Decision Maker library](https://github.com/ITM-Kitware/align-system),
designed to make decisions in scenarios where no single right answer exists.

![Align UI Hero](./doc/ui-hero.png)

## Installing

```console
git clone https://github.com/ITM-Kitware/align-app.git
cd align-app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the application

```console
source .venv/bin/activate
align-app
```

Then visit http://localhost:8080

## Development

```console
pip install -e ".[dev]"
pre-commit install
```

### Release

Merge a PR to `main` with semantic commit messages.
