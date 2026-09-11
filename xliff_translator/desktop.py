from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import uvicorn


HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _find_free_port(start_port: int = DEFAULT_PORT) -> int:
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            try:
                sock.bind((HOST, port))
                return port

            except OSError:
                continue

    raise RuntimeError(
        "Could not find an available local port."
    )


def _wait_for_server(
    port: int,
    timeout: float = 30.0,
) -> bool:

    deadline = time.time() + timeout

    while time.time() < deadline:

        try:
            with socket.create_connection(
                (HOST, port),
                timeout=0.5,
            ):
                return True

        except OSError:
            time.sleep(0.2)

    return False


def _find_browser() -> str | None:
    """
    Find a Chromium-based browser that supports
    application-window mode.

    Preference:
        Microsoft Edge
        Google Chrome
    """

    candidates: list[Path] = []

    local_app_data = os.environ.get(
        "LOCALAPPDATA"
    )

    program_files = os.environ.get(
        "PROGRAMFILES"
    )

    program_files_x86 = os.environ.get(
        "PROGRAMFILES(X86)"
    )

    if local_app_data:

        candidates.extend(
            [
                Path(local_app_data)
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe",

                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
            ]
        )

    if program_files:

        candidates.extend(
            [
                Path(program_files)
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe",

                Path(program_files)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
            ]
        )

    if program_files_x86:

        candidates.extend(
            [
                Path(program_files_x86)
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe",

                Path(program_files_x86)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
            ]
        )

    for candidate in candidates:

        if candidate.is_file():

            return str(candidate)

    for executable in (
        "msedge.exe",
        "chrome.exe",
    ):

        found = shutil.which(executable)

        if found:

            return found

    return None


def _launch_application_window(
    port: int,
) -> subprocess.Popen | None:

    url = f"http://{HOST}:{port}"

    browser = _find_browser()

    if browser is None:

        return None

    executable_name = Path(
        browser
    ).name.lower()

    profile_dir = (
        Path.home()
        / "AppData"
        / "Local"
        / "XLIFF Translator"
        / "BrowserProfile"
    )

    profile_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    arguments = [
        browser,
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if executable_name == "msedge.exe":

        arguments.append(
            "--disable-features=msEdgeSidebarV2"
        )

    return subprocess.Popen(
        arguments,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _launch_fallback_browser(
    port: int,
) -> None:

    import webbrowser

    webbrowser.open(
        f"http://{HOST}:{port}"
    )


def main() -> None:

    # --------------------------------------------------------
    # Customer build marker.
    # --------------------------------------------------------

    os.environ[
        "XLIFF_CUSTOMER_BUILD"
    ] = "1"

    # --------------------------------------------------------
    # Find an available local port.
    # --------------------------------------------------------

    port = _find_free_port()

    # --------------------------------------------------------
    # Start Uvicorn without its console logging system.
    #
    # This is required for the windowed PyInstaller build,
    # because console=False means stdout/stderr do not exist.
    # --------------------------------------------------------

    server_config = uvicorn.Config(
        "xliff_translator.web.app:app",
        host=HOST,
        port=port,
        reload=False,
        log_config=None,
        access_log=False,
    )

    server = uvicorn.Server(
        server_config
    )

    # --------------------------------------------------------
    # Start server in the background.
    # --------------------------------------------------------

    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )

    server_thread.start()

    # --------------------------------------------------------
    # Wait until FastAPI is actually available.
    # --------------------------------------------------------

    if not _wait_for_server(port):

        server.should_exit = True

        server_thread.join(
            timeout=5
        )

        raise RuntimeError(
            "XLIFF Translator could not start."
        )

    # --------------------------------------------------------
    # Open customer application window.
    # --------------------------------------------------------

    browser_process = (
        _launch_application_window(port)
    )

    if browser_process is None:

        _launch_fallback_browser(port)

        # No browser process is available to monitor.
        # Keep the local application alive.
        #
        # This is only a fallback for unusual Windows
        # installations without Edge or Chrome.

        try:

            while True:

                time.sleep(1)

        except KeyboardInterrupt:

            server.should_exit = True

        return

    # --------------------------------------------------------
    # Keep application alive while its window is open.
    # --------------------------------------------------------

    try:

        browser_process.wait()

    finally:

        # Closing the application window shuts down the
        # local FastAPI server as well.
        server.should_exit = True

        server_thread.join(
            timeout=10
        )


if __name__ == "__main__":

    main()