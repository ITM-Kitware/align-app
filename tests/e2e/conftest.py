import multiprocessing
import socket
import time
from typing import Generator

import pytest


def _run_server(port: int):
    from align_app.app import main

    main(port=port, open_browser=False)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_port(port: int, host: str = "localhost", timeout: int = 30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def align_app_server() -> Generator[str, None, None]:
    port = get_free_port()
    server_url = f"http://localhost:{port}"

    process = multiprocessing.Process(target=_run_server, args=(port,))
    process.start()

    if not wait_for_port(port, timeout=30):
        process.terminate()
        raise RuntimeError(
            "Failed to start align-app server - timeout waiting for port"
        )

    if not process.is_alive():
        raise RuntimeError("Failed to start align-app server - process died")

    yield server_url

    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
    }
