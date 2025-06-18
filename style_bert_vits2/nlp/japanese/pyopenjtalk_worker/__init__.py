"""
Run the pyopenjtalk worker in a separate process
to avoid user dictionary access error
"""

import atexit
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Optional

from style_bert_vits2.logging import logger
from style_bert_vits2.nlp.japanese.pyopenjtalk_worker.worker_client import WorkerClient
from style_bert_vits2.nlp.japanese.pyopenjtalk_worker.worker_common import ConnectionClosedException, WORKER_PORT

# Declare global variables at module level
WORKER_CLIENT: Optional[WorkerClient] = None
WORKER_CLIENT_LOCK = threading.Lock()
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

def initialize_worker(port: int = WORKER_PORT) -> None:
    """Initialize the PyOpenJTalk worker client with retry logic."""
    global WORKER_CLIENT
    with WORKER_CLIENT_LOCK:
        if WORKER_CLIENT:
            return
        for attempt in range(MAX_RETRIES):
            try:
                client = WorkerClient(port)
                WORKER_CLIENT = client
                logger.info("Successfully initialized PyOpenJTalk worker client on port %d", port)
                atexit.register(terminate_worker)
                # Register signal handler for graceful termination
                def signal_handler(signum: int, frame: Any):
                    terminate_worker()
                try:
                    signal.signal(signal.SIGTERM, signal_handler)
                except ValueError:
                    # Signal only works in main thread
                    pass
                break
            except (OSError, socket.timeout) as e:
                logger.debug("Attempt %d/%d: Failed to connect to worker server: %s", attempt + 1, MAX_RETRIES, e)
                if attempt < MAX_RETRIES - 1:
                    # Try starting the worker server
                    try:
                        start_worker_server(port)
                        time.sleep(RETRY_DELAY)
                    except Exception as start_e:
                        logger.error("Failed to start worker server: %s", start_e)
                        time.sleep(RETRY_DELAY)
                else:
                    logger.error("Max retries reached, failed to initialize worker")
                    raise TimeoutError("サーバーに接続できませんでした")

def start_worker_server(port: int) -> None:
    """Start the pyopenjtalk worker server in a separate process."""
    logger.debug("Starting pyopenjtalk worker server on port %d", port)
    import os
    worker_pkg_path = os.path.relpath(
        os.path.dirname(__file__), os.getcwd()
    ).replace(os.sep, ".")
    args = [sys.executable, "-m", worker_pkg_path, "--port", str(port)]
    if sys.platform.startswith("win"):
        cf = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen(args, creationflags=cf, startupinfo=si)
    else:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

def dispatch_with_retry(method: str, *args: Any) -> Any:
    """Dispatch a request to the worker with retry logic."""
    global WORKER_CLIENT
    with WORKER_CLIENT_LOCK:
        if WORKER_CLIENT is None:
            initialize_worker()
        assert WORKER_CLIENT is not None
        for attempt in range(MAX_RETRIES):
            try:
                response = WORKER_CLIENT.dispatch_pyopenjtalk(method, *args)
                logger.debug("Dispatch successful for method %s", method)
                return response
            except (ConnectionClosedException, ValueError, socket.timeout) as e:
                logger.error("Dispatch failed for method %s (attempt %d/%d): %s", method, attempt + 1, MAX_RETRIES, e)
                if attempt < MAX_RETRIES - 1:
                    WORKER_CLIENT = None
                    time.sleep(RETRY_DELAY)
                    initialize_worker()
                else:
                    logger.error("Max retries reached for method %s", method)
                    raise

def run_frontend(text: str) -> list[dict[str, Any]]:
    """Run the frontend processing with retry logic."""
    if WORKER_CLIENT is not None:
        ret = dispatch_with_retry("run_frontend", text)
        assert isinstance(ret, list)
        return ret
    else:
        import pyopenjtalk
        return pyopenjtalk.run_frontend(text)

def make_label(njd_features: Any) -> list[str]:
    """Make labels from NJD features with retry logic."""
    if WORKER_CLIENT is not None:
        ret = dispatch_with_retry("make_label", njd_features)
        assert isinstance(ret, list)
        return ret
    else:
        import pyopenjtalk
        return pyopenjtalk.make_label(njd_features)

def mecab_dict_index(path: str, out_path: str, dn_mecab: Optional[str] = None) -> None:
    """Run mecab dictionary index operation."""
    if WORKER_CLIENT is not None:
        dispatch_with_retry("mecab_dict_index", path, out_path, dn_mecab)
    else:
        import pyopenjtalk
        pyopenjtalk.mecab_dict_index(path, out_path, dn_mecab)

def update_global_jtalk_with_user_dict(path: str) -> None:
    """Update global jtalk with user dictionary."""
    if WORKER_CLIENT is not None:
        dispatch_with_retry("update_global_jtalk_with_user_dict", path)
    else:
        import pyopenjtalk
        pyopenjtalk.update_global_jtalk_with_user_dict(path)

def unset_user_dict() -> None:
    """Unset user dictionary."""
    if WORKER_CLIENT is not None:
        dispatch_with_retry("unset_user_dict")
    else:
        import pyopenjtalk
        pyopenjtalk.unset_user_dict()

def terminate_worker() -> None:
    """Terminate the pyopenjtalk worker server."""
    global WORKER_CLIENT
    logger.debug("Terminating pyopenjtalk worker server")
    with WORKER_CLIENT_LOCK:
        if not WORKER_CLIENT:
            return
        try:
            if WORKER_CLIENT.status() == 1:
                WORKER_CLIENT.quit_server()
        except Exception as e:
            logger.error("Error quitting worker server: %s", e)
        try:
            WORKER_CLIENT.close()
        except Exception as e:
            logger.error("Error closing worker client: %s", e)
        WORKER_CLIENT = None