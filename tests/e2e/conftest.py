import multiprocessing
import socket
import time
from typing import Generator

import pytest
import urllib.request
import urllib.error

SERVER_STARTUP_TIMEOUT = 30
SERVER_HEALTH_CHECK_INTERVAL = 0.5
DECISION_TIMEOUT = 10000
DEFAULT_WAIT_TIMEOUT = 10000
SPINNER_APPEAR_TIMEOUT = 5000


def _run_server(port: int):
    from align_app.app import main

    main(port=port, open_browser=False)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_server(url: str, timeout: int = SERVER_STARTUP_TIMEOUT) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(SERVER_HEALTH_CHECK_INTERVAL)
    return False


@pytest.fixture(scope="session")
def align_app_server() -> Generator[str, None, None]:
    port = get_free_port()
    server_url = f"http://localhost:{port}"

    process = multiprocessing.Process(target=_run_server, args=(port,))
    process.start()

    if not wait_for_server(server_url):
        process.terminate()
        raise RuntimeError(
            f"Failed to start align-app server at {server_url} - timeout waiting for HTTP response"
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
