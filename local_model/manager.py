"""
BonsaiManager — lifecycle manager for the Bonsai 8B local model server.

Architecture
------------
Bonsai 8B is a 1-bit LLM from PrismML (Apache 2.0).  It ships in two GGUF
variants relevant to Paramodus:

  bonsai-8b-native  (Q1_0_g128, ~1 GB)
    Native 1-bit format.  Requires PrismML's llama.cpp fork for the custom
    CUDA / CPU kernels.  Fastest on GPU; smallest download.

  bonsai-8b-q4  (Q4_K_M, ~4.6 GB)
    Unpacked re-quantization by bartowski.  Runs on any standard llama.cpp
    binary (CPU or GPU).  Best for users without a dedicated GPU.

The manager downloads the chosen GGUF to ~/.myapp/models/ on first use, then
starts llama-server as a subprocess on localhost:8080 exposing an
OpenAI-compatible /v1 endpoint.  Paramodus connects to it via OpenAIChat with
a custom base_url — no API key required.

Binary resolution order (for llama-server):
  1. PyInstaller bundle (sys._MEIPASS / sibling exe dir)
  2. ~/.myapp/bin/llama-server[.exe]   ← placed by scripts/get_llama_server.py
  3. System PATH

For the .exe distribution, bundle llama-server.exe via paramodus.spec:
  binaries=[('bin/llama-server.exe', '.')]
"""

import os
import sys
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

APP_DATA   = os.path.join(os.path.expanduser("~"), ".myapp")
MODELS_DIR = os.path.join(APP_DATA, "models")
BIN_DIR    = os.path.join(APP_DATA, "bin")

for _d in (APP_DATA, MODELS_DIR, BIN_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

MODELS: dict[str, dict] = {
    "bonsai-8b-native": {
        "repo_id":     "prism-ml/Bonsai-8B-gguf",
        "filename":    "Bonsai-8B.gguf",
        "hf_url":      "https://huggingface.co/prism-ml/Bonsai-8B-gguf/resolve/main/Bonsai-8B.gguf",
        "size_gb":     1.0,
        "quant":       "Q1_0_g128 (native 1-bit)",
        "description": "Native 1-bit (~1 GB) — requires PrismML llama.cpp fork, GPU recommended.",
        "requires_prismml_fork": True,
    },
    "bonsai-8b-q4": {
        "repo_id":     "bartowski/prism-ml_Bonsai-8B-unpacked-GGUF",
        "filename":    "prism-ml_Bonsai-8B-unpacked-Q4_K_M.gguf",
        "hf_url":      (
            "https://huggingface.co/bartowski/prism-ml_Bonsai-8B-unpacked-GGUF"
            "/resolve/main/prism-ml_Bonsai-8B-unpacked-Q4_K_M.gguf"
        ),
        "size_gb":     4.6,
        "quant":       "Q4_K_M (unpacked, standard llama.cpp)",
        "description": "Unpacked Q4_K_M (~4.6 GB) — works with standard llama-server, CPU friendly.",
        "requires_prismml_fork": False,
    },
}

DEFAULT_MODEL   = "bonsai-8b-q4"   # Works with standard llama.cpp on any hardware
SERVER_HOST     = "127.0.0.1"
SERVER_PORT     = 8080
HEALTH_URL      = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
CHUNK_SIZE      = 1024 * 256        # 256 KB download chunks


# ---------------------------------------------------------------------------
# BonsaiManager
# ---------------------------------------------------------------------------

class BonsaiManager:
    """
    Manages the download and server lifecycle for Bonsai 8B.

    Thread-safe: start/stop/download can be called from background threads.
    """

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._server_lock  = threading.Lock()
        self._download_lock = threading.Lock()
        self._active_model_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Binary resolution
    # ------------------------------------------------------------------

    def _get_llama_server_path(self) -> Optional[str]:
        """
        Locate the llama-server executable.  Checks three locations in order:

        1. Bundled inside the PyInstaller .exe directory (sys._MEIPASS or
           the folder that contains the frozen executable).
        2. ~/.myapp/bin/  — populated by scripts/get_llama_server.py.
        3. System PATH.
        """
        exe = "llama-server.exe" if sys.platform == "win32" else "llama-server"
        candidates: list[str] = []

        # 1. PyInstaller bundle
        if getattr(sys, "frozen", False):
            # _MEIPASS is the temp extraction dir; the binary is extracted there
            candidates.append(os.path.join(sys._MEIPASS, exe))
            # Also check the folder containing the .exe itself
            candidates.append(os.path.join(os.path.dirname(sys.executable), exe))

        # 2. App-data bin dir (populated by setup script)
        candidates.append(os.path.join(BIN_DIR, exe))

        # 3. System PATH
        path_result = shutil.which("llama-server")
        if path_result:
            candidates.append(path_result)

        for path in candidates:
            if path and os.path.isfile(path):
                return path

        return None

    # ------------------------------------------------------------------
    # Model info helpers
    # ------------------------------------------------------------------

    def get_model_path(self, model_key: str = DEFAULT_MODEL) -> str:
        return os.path.join(MODELS_DIR, MODELS[model_key]["filename"])

    def is_model_downloaded(self, model_key: str = DEFAULT_MODEL) -> bool:
        path = self.get_model_path(model_key)
        # A partial download leaves a .partial file — don't count it
        return os.path.isfile(path) and not os.path.isfile(path + ".partial")

    def get_models(self) -> list[dict]:
        """Return model catalog enriched with download status."""
        result = []
        for key, info in MODELS.items():
            result.append({
                "key":         key,
                "filename":    info["filename"],
                "size_gb":     info["size_gb"],
                "quant":       info["quant"],
                "description": info["description"],
                "requires_prismml_fork": info["requires_prismml_fork"],
                "downloaded":  self.is_model_downloaded(key),
                "model_path":  self.get_model_path(key),
            })
        return result

    # ------------------------------------------------------------------
    # Download (streaming, resume-capable)
    # ------------------------------------------------------------------

    def download_model(
        self,
        model_key: str = DEFAULT_MODEL,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """
        Download the specified model GGUF from HuggingFace.

        Uses huggingface_hub.hf_hub_download() which correctly handles
        HuggingFace Xet storage, CDN redirects, and automatic retries.
        Progress is reported by polling the in-progress file size from a
        background thread (hf_hub_download is synchronous).

        progress_cb(percent: float, message: str)
          percent: 0-100 on progress, -1.0 on error
        """
        with self._download_lock:
            if self.is_model_downloaded(model_key):
                if progress_cb:
                    progress_cb(100.0, "Already downloaded.")
                return True

            from huggingface_hub import hf_hub_download

            info       = MODELS[model_key]
            dest_path  = self.get_model_path(model_key)
            total_bytes = int(info["size_gb"] * 1024 ** 3)

            if progress_cb:
                progress_cb(0.0, f"Connecting to HuggingFace… ({info['size_gb']:.1f} GB)")

            # hf_hub_download is blocking; we poll the in-progress cache file
            # from a side thread to report live progress.
            _stop = threading.Event()

            def _poll_progress():
                """
                hf_hub_download writes to a .incomplete temp file inside
                the local_dir while downloading.  We find and stat it.
                """
                while not _stop.is_set():
                    try:
                        # Look for any partial file in MODELS_DIR
                        for fname in os.listdir(MODELS_DIR):
                            if fname.endswith(".incomplete") or fname.endswith(".part"):
                                fpath = os.path.join(MODELS_DIR, fname)
                                size  = os.path.getsize(fpath)
                                if size > 0 and total_bytes > 0 and progress_cb:
                                    pct      = min(size / total_bytes * 100, 99.0)
                                    done_gb  = size / (1024 ** 3)
                                    total_gb = total_bytes / (1024 ** 3)
                                    progress_cb(
                                        pct,
                                        f"Downloading… {done_gb:.2f} / {total_gb:.2f} GB"
                                    )
                                break
                    except OSError:
                        pass
                    _stop.wait(timeout=1.5)

            monitor = threading.Thread(target=_poll_progress, daemon=True)
            monitor.start()

            try:
                hf_hub_download(
                    repo_id=info["repo_id"],
                    filename=info["filename"],
                    local_dir=MODELS_DIR,
                    local_dir_use_symlinks=False,
                )
                _stop.set()

                if progress_cb:
                    progress_cb(100.0, "Download complete ✓")
                return True

            except Exception as exc:
                _stop.set()
                if progress_cb:
                    progress_cb(-1.0, f"Download failed: {exc}")
                return False

    def cancel_download(self, model_key: str = DEFAULT_MODEL) -> None:
        """Remove the .partial file to start fresh next time."""
        tmp_path = self.get_model_path(model_key) + ".partial"
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def is_server_running(self) -> bool:
        try:
            r = requests.get(HEALTH_URL, timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def start_server(
        self,
        model_key:      str = DEFAULT_MODEL,
        n_gpu_layers:   int = 0,
        context_length: int = 4096,
        timeout_s:      int = 360,
    ) -> bool:
        """
        Start llama-server as a background subprocess.

        Parameters
        ----------
        model_key      : Which model variant to load
        n_gpu_layers   : GPU layers to offload (0 = CPU only, 99 = full GPU)
        context_length : Context window in tokens
        timeout_s      : Max seconds to wait for the server to become ready

        Returns True when the /health endpoint responds 200.
        """
        with self._server_lock:
            if self.is_server_running():
                return True

            llama_bin = self._get_llama_server_path()
            if llama_bin is None:
                print(
                    "[BonsaiManager] llama-server not found.\n"
                    "  Run: python scripts/get_llama_server.py\n"
                    "  Or add llama-server to PATH."
                )
                return False

            model_path = self.get_model_path(model_key)
            if not os.path.isfile(model_path):
                print(f"[BonsaiManager] Model not found at {model_path} — download it first.")
                return False

            cmd = [
                llama_bin,
                "--model",    model_path,
                "--host",     SERVER_HOST,
                "--port",     str(SERVER_PORT),
                "--ctx-size", str(context_length),
                "-ngl",       str(n_gpu_layers),
                "--no-mmap",              # safer on Windows / spinning disks
                "--log-disable",          # silence stdout noise
            ]

            log_path = os.path.join(APP_DATA, "llama_server.log")
            log_fh   = open(log_path, "a", buffering=1)

            extra_kwargs = {}
            if sys.platform == "win32":
                extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
                **extra_kwargs,
            )
            self._active_model_key = model_key
            print(f"[BonsaiManager] Started llama-server (pid={self._process.pid})")

        # Poll outside the lock so other threads can query status
        for _ in range(timeout_s):
            time.sleep(1)
            if self._process.poll() is not None:
                print("[BonsaiManager] llama-server exited unexpectedly — check ~/.myapp/llama_server.log")
                return False
            if self.is_server_running():
                print(f"[BonsaiManager] Server ready at http://{SERVER_HOST}:{SERVER_PORT}/v1")
                return True

        print("[BonsaiManager] Timed out waiting for server to become ready.")
        return False

    def stop_server(self) -> None:
        with self._server_lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self._process = None
                self._active_model_key = None
                print("[BonsaiManager] llama-server stopped.")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self, model_key: str = DEFAULT_MODEL) -> dict:
        llama_bin = self._get_llama_server_path()
        return {
            "model_key":       model_key,
            "model_downloaded": self.is_model_downloaded(model_key),
            "partial_exists":  os.path.isfile(self.get_model_path(model_key) + ".partial"),
            "server_running":  self.is_server_running(),
            "active_model":    self._active_model_key,
            "model_path":      self.get_model_path(model_key),
            "server_url":      f"http://{SERVER_HOST}:{SERVER_PORT}/v1",
            "binary_found":    llama_bin is not None,
            "binary_path":     llama_bin,
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

bonsai = BonsaiManager()
