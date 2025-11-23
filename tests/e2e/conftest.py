import socket
import time
import sys
import subprocess
import threading
from typing import Generator, List

import pytest
import urllib.request
import urllib.error

SERVER_STARTUP_TIMEOUT = 30
SERVER_HEALTH_CHECK_INTERVAL = 0.5
DECISION_TIMEOUT = 10000
DEFAULT_WAIT_TIMEOUT = 10000
SPINNER_APPEAR_TIMEOUT = 5000


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


_server_stderr_lines: List[str] = []
_server_stdout_lines: List[str] = []
_output_lock = threading.Lock()


def _capture_stream(pipe, output_list):
    for line in iter(pipe.readline, b''):
        decoded_line = line.decode('utf-8', errors='replace')
        with _output_lock:
            output_list.append(decoded_line)
    pipe.close()


@pytest.fixture(scope="session")
def align_app_server() -> Generator[str, None, None]:
    global _server_stderr_lines, _server_stdout_lines
    _server_stderr_lines = []
    _server_stdout_lines = []

    port = get_free_port()
    server_url = f"http://localhost:{port}"

    import os
    venv_bin = os.path.join(os.path.dirname(sys.executable), "align-app")

    process = subprocess.Popen(
        [venv_bin, "--port", str(port)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    stderr_thread = threading.Thread(target=_capture_stream, args=(process.stderr, _server_stderr_lines), daemon=True)
    stdout_thread = threading.Thread(target=_capture_stream, args=(process.stdout, _server_stdout_lines), daemon=True)
    stderr_thread.start()
    stdout_thread.start()

    if not wait_for_server(server_url):
        process.terminate()
        process.wait(timeout=2)
        with _output_lock:
            stderr_content = "".join(_server_stderr_lines)
        raise RuntimeError(f"Failed to start align-app server at {server_url}\n\nServer stderr:\n{stderr_content}")

    if process.poll() is not None:
        with _output_lock:
            stderr_content = "".join(_server_stderr_lines)
        raise RuntimeError(f"Failed to start align-app server - process died\n\nServer stderr:\n{stderr_content}")

    yield server_url

    process.terminate()
    process.wait(timeout=5)
    if process.poll() is None:
        process.kill()
        process.wait()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        with _output_lock:
            stderr_content = "".join(_server_stderr_lines)
            stdout_content = "".join(_server_stdout_lines)

            output_to_append = []
            if stderr_content:
                output_to_append.append(f"{'='*60}\nBACKEND SERVER STDERR:\n{'='*60}\n{stderr_content}")
            if stdout_content:
                output_to_append.append(f"{'='*60}\nBACKEND SERVER STDOUT:\n{'='*60}\n{stdout_content}")

            if output_to_append:
                if report.failed:
                    report.longrepr = str(report.longrepr) + "\n\n" + "\n\n".join(output_to_append)
                else:
                    import sys
                    print("\n" + "\n\n".join(output_to_append), file=sys.stderr)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "headless": True,
    }
