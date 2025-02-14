from .core import AlignApp


def main(server=None, **kwargs):
    app = AlignApp(server)
    app.server.start(**kwargs)


if __name__ == "__main__":
    main()
