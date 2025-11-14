import logging

from .core import AlignApp

logging.getLogger().setLevel(logging.WARNING)


def main(server=None, **kwargs):
    app = AlignApp(server)
    app.server.start(**kwargs)


if __name__ == "__main__":
    main()
