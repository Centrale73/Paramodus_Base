"""
scripts/get_llama_server.py
===========================
Downloads a pre-built llama-server binary for the current platform.

Usage
-----
    python scripts/get_llama_server.py              # installs to <app_data>/bin/ (PrismML fork)
    python scripts/get_llama_server.py --local      # installs to ./bin/ (for PyInstaller bundling)
    python scripts/get_llama_server.py --standard   # use standard llama.cpp instead of PrismML fork
    python scripts/get_llama_server.py --prismml    # build PrismML fork from source (needs cmake)

Default behaviour (no flags):
    Downloads a pre-built PrismML llama.cpp release binary — the only binary
    that supports the native Bonsai 8B Q1_0_g128 1-bit kernel.  No compiler
    or cmake required.

For the bartowski Q4_K_M variant only, the standard llama.cpp binary works fine
(use --standard in that case).

After running this script, the binary is automatically detected by
local_model/manager.py via <app_data>/bin/ (or PATH).
"""

import argparse
import os
import platform
import shutil
import sys
import zipfile

import requests

# Make repo root importable so we can share the path resolver.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
from paths import get_app_data_dir

GITHUB_RELEASES_URL        = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
PRISMML_RELEASES_URL       = "https://api.github.com/repos/PrismML-Eng/llama.cpp/releases/latest"
PRISMML_REPO_URL           = "https://github.com/PrismML-Eng/llama.cpp.git"

APP_DATA_BIN = os.path.join(get_app_data_dir(), "bin")
LOCAL_BIN    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


# ---------------------------------------------------------------------------
# GPU detection helpers (used at asset-selection time)
# ---------------------------------------------------------------------------

def _has_nvidia() -> bool:
    """
    Detect NVIDIA GPU using nvidia-smi (present on any machine with a driver,
    not just developer machines that have the CUDA toolkit / nvcc).
    """
    if shutil.which("nvidia-smi"):
        try:
            import subprocess
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                timeout=5, stderr=subprocess.DEVNULL,
            ).decode().strip()
            if out:
                print(f"[get_llama_server] NVIDIA GPU detected: {out.splitlines()[0]}")
                return True
        except Exception:
            pass
    return False


def _has_vulkan() -> bool:
    """
    Detect any Vulkan-capable GPU (covers AMD, Intel Arc, older NVIDIA without
    CUDA drivers, and Apple via MoltenVK).
    Uses vulkaninfo if present; falls back to checking for AMD driver files
    on Windows where vulkaninfo is often absent.
    """
    # vulkaninfo is shipped with Vulkan SDK and most Linux GPU drivers
    if shutil.which("vulkaninfo"):
        try:
            import subprocess
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True, text=True, timeout=8,
            )
            if result.returncode == 0 and "GPU" in result.stdout:
                print("[get_llama_server] Vulkan GPU detected via vulkaninfo")
                return True
        except Exception:
            pass

    # Windows fallback: check for AMD/Intel Vulkan ICD registry files
    if sys.platform == "win32":
        import winreg
        vulkan_reg_paths = [
            r"SOFTWARE\Khronos\Vulkan\Drivers",
            r"SOFTWARE\WOW6432Node\Khronos\Vulkan\Drivers",
        ]
        for reg_path in vulkan_reg_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                winreg.CloseKey(key)
                print("[get_llama_server] Vulkan ICD registry entry found — Vulkan GPU present")
                return True
            except OSError:
                pass

    # Linux fallback: check for AMD/Intel ICD files
    if sys.platform == "linux":
        icd_dirs = [
            "/usr/share/vulkan/icd.d",
            "/etc/vulkan/icd.d",
            os.path.expanduser("~/.local/share/vulkan/icd.d"),
        ]
        for d in icd_dirs:
            if os.path.isdir(d) and os.listdir(d):
                print(f"[get_llama_server] Vulkan ICD found in {d}")
                return True

    return False


# ---------------------------------------------------------------------------
# Standard llama.cpp release
# ---------------------------------------------------------------------------

def _find_release_asset(assets: list[dict]) -> tuple[str, str]:
    """
    Pick the best release asset for the current platform.

    Asset naming convention (as of llama.cpp b3xxx+):
      llama-b<N>-bin-win-avx2-x64.zip
      llama-b<N>-bin-ubuntu-x64.zip
      llama-b<N>-bin-macos-arm64.zip
    """
    system  = platform.system()
    machine = platform.machine().lower()

    is_arm = "arm" in machine or "aarch64" in machine

    def _score(name: str) -> int:
        n = name.lower()
        score = 0

        if n.startswith("cudart"):
            return -100

        if system == "Windows":
            if not (n.startswith("llama-") and "bin" in n and "win" in n and n.endswith(".zip")):
                return 0
            score += 10

            if is_arm:
                if "arm64" in n:  score += 8
                else:             score -= 20
            else:
                if "x64" in n:   score += 8
                if "arm64" in n: score -= 20

            if "cpu" in n:                          score += 4
            elif "cuda" in n or "vulkan" in n or "hip" in n or "sycl" in n:
                score -= 2

            if "avx2" in n:   score += 2
            elif "avx" in n:  score += 1

        elif system == "Linux":
            if not (n.startswith("llama-") and "bin" in n and n.endswith((".zip", ".tar.gz"))):
                return 0
            score += 10
            if is_arm:
                if "arm64" in n or "aarch64" in n: score += 5
            else:
                if "x64" in n or "amd64" in n:    score += 5
            if "cpu" in n:  score += 3

        elif system == "Darwin":
            if not (n.startswith("llama-") and "macos" in n and n.endswith((".zip", ".tar.gz"))):
                return 0
            score += 10
            if is_arm and "arm64" in n:      score += 5
            elif not is_arm and "x64" in n:  score += 5

        return score

    ranked = sorted(assets, key=lambda a: _score(a["name"]), reverse=True)
    if not ranked or _score(ranked[0]["name"]) <= 0:
        raise RuntimeError(
            f"No compatible llama.cpp binary found for {system}/{machine}.\n"
            "Please download manually from https://github.com/ggerganov/llama.cpp/releases"
        )
    best = ranked[0]
    return best["browser_download_url"], best["name"]


def _download_file(url: str, dest_path: str) -> None:
    print(f"  → {url}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done  = 0
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done / total * 100
                    mb  = done / (1024 ** 2)
                    print(f"\r    {pct:5.1f}%  {mb:7.1f} MB", end="", flush=True)
    print()


def _extract_server_binary(archive_path: str, dest_dir: str) -> str:
    """
    Extract llama-server[.exe] AND all companion DLLs/SOs from the archive.
    llama-server.exe depends on llama.dll, ggml.dll, etc. — they must all
    live in the same directory or the exe will fail with a missing-DLL error.
    """
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    server_path: str | None = None

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as z:
            for member in z.namelist():
                base = os.path.basename(member)
                if not base:
                    continue
                is_server = (base == exe_name)
                is_dll    = base.lower().endswith(".dll")
                if is_server or is_dll:
                    dest_path = os.path.join(dest_dir, base)
                    with z.open(member) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if is_server:
                        if sys.platform != "win32":
                            os.chmod(dest_path, 0o755)
                        server_path = dest_path
    else:
        import tarfile
        with tarfile.open(archive_path) as t:
            for member in t.getmembers():
                base = os.path.basename(member.name)
                is_server = (base == exe_name)
                is_lib    = base.lower().endswith((".so", ".dylib"))
                if is_server or is_lib:
                    dest_path = os.path.join(dest_dir, base)
                    f = t.extractfile(member)
                    if f is None:
                        continue
                    with open(dest_path, "wb") as dst:
                        shutil.copyfileobj(f, dst)
                    os.chmod(dest_path, 0o755)
                    if is_server:
                        server_path = dest_path

    if server_path is None:
        raise RuntimeError(f"Could not find {exe_name} inside {archive_path}")
    return server_path


def download_standard_binary(dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)

    print("Fetching latest llama.cpp release info from GitHub…")
    resp = requests.get(GITHUB_RELEASES_URL, timeout=15)
    resp.raise_for_status()
    data   = resp.json()
    tag    = data["tag_name"]
    assets = data["assets"]

    print(f"Latest release: {tag}")
    url, filename = _find_release_asset(assets)
    print(f"Downloading {filename}…")

    archive_path = os.path.join(dest_dir, filename)
    _download_file(url, archive_path)

    print("Extracting llama-server…")
    binary_path = _extract_server_binary(archive_path, dest_dir)

    os.remove(archive_path)
    print(f"✓ llama-server installed at {binary_path}")
    return binary_path


# ---------------------------------------------------------------------------
# PrismML pre-built release download (no cmake needed)
# ---------------------------------------------------------------------------

def _find_prismml_release_asset(assets: list[dict]) -> tuple[str, str]:
    """
    Pick the best PrismML release asset for the current platform.

    PrismML release naming conventions:
      Windows CPU:  llama-bin-win-cpu-x64.zip / llama-bin-win-cpu-arm64.zip
      Windows CUDA: llama-prism-b1-*-bin-win-cuda-12.4-x64.zip
      macOS ARM64:  llama-prism-*-bin-macos-arm64.tar.gz
      macOS x64:    llama-prism-*-bin-macos-x64.tar.gz
      Linux x64:    llama-prism-*-bin-ubuntu-x64.tar.gz
      Linux ARM64:  llama-prism-*-bin-ubuntu-arm64.tar.gz

    GPU preference order:
      NVIDIA CUDA (detected via nvidia-smi) > Vulkan (AMD/Intel/other)
      > CPU-only fallback.
    """
    system  = platform.system()
    machine = platform.machine().lower()
    is_arm  = "arm" in machine or "aarch64" in machine

    # Detect available GPU acceleration once, before scoring
    has_nvidia = _has_nvidia()
    has_vulkan = _has_vulkan() if not has_nvidia else False  # no need to check both

    def _score(name: str) -> int:
        n = name.lower()
        score = 0

        if n.startswith("cudart"):
            return -100
        if "xcframework" in n or n.endswith(".tar.gz.sha256") or n.endswith(".zip.sha256"):
            return -100

        if system == "Windows":
            if not n.endswith(".zip"):
                return 0
            score += 10

            if is_arm:
                if "arm64" in n:  score += 8
                else:             score -= 20
            else:
                if "x64" in n:   score += 8
                if "arm64" in n: score -= 20

            # GPU preference: CUDA > Vulkan > CPU
            if has_nvidia and "cuda" in n:   score += 6
            elif has_vulkan and "vulkan" in n: score += 5
            elif "cpu" in n:                  score += 4

        elif system == "Linux":
            if not n.endswith(".tar.gz"):
                return 0
            if not ("ubuntu" in n or "linux" in n):
                return 0
            score += 10

            if is_arm:
                if "arm64" in n or "aarch64" in n: score += 5
            else:
                if "x64" in n or "amd64" in n:    score += 5

            # GPU preference: CUDA > Vulkan > CPU
            if has_nvidia and "cuda" in n:    score += 6
            elif has_vulkan and "vulkan" in n: score += 5
            elif not ("cuda" in n or "vulkan" in n or "rocm" in n): score += 2

        elif system == "Darwin":
            if not n.endswith(".tar.gz"):
                return 0
            if "macos" not in n:
                return 0
            score += 10
            if is_arm and "arm64" in n:      score += 5
            elif not is_arm and "x64" in n:  score += 5
            # Metal is always used on Apple Silicon — no explicit GPU flag needed

        return score

    ranked = sorted(assets, key=lambda a: _score(a["name"]), reverse=True)
    if not ranked or _score(ranked[0]["name"]) <= 0:
        raise RuntimeError(
            f"No compatible PrismML binary found for {system}/{machine}.\n"
            "Visit https://github.com/PrismML-Eng/llama.cpp/releases to download manually."
        )
    best = ranked[0]
    return best["browser_download_url"], best["name"]


def download_prismml_binary(dest_dir: str) -> str:
    """
    Download a pre-built PrismML llama.cpp binary from GitHub releases.
    This is the recommended path: no cmake, no compiler, no git-clone needed.
    Required for native Bonsai 8B Q1_0_g128 1-bit kernel support.
    """
    os.makedirs(dest_dir, exist_ok=True)

    print("Fetching latest PrismML llama.cpp release info from GitHub…")
    resp = requests.get(PRISMML_RELEASES_URL, timeout=15)
    resp.raise_for_status()
    data   = resp.json()
    tag    = data["tag_name"]
    assets = data["assets"]

    print(f"Latest PrismML release: {tag}")
    url, filename = _find_prismml_release_asset(assets)
    print(f"Downloading {filename}…")

    archive_path = os.path.join(dest_dir, filename)
    _download_file(url, archive_path)

    print("Extracting llama-server…")
    binary_path = _extract_server_binary(archive_path, dest_dir)

    os.remove(archive_path)
    print(f"✓ PrismML llama-server installed at {binary_path}")
    return binary_path


# ---------------------------------------------------------------------------
# PrismML fork (build from source)
# ---------------------------------------------------------------------------

def build_prismml_binary(dest_dir: str) -> str:
    """
    Clone PrismML's llama.cpp fork and build llama-server.
    Requires: git, cmake, a C++17 compiler.
    Optional: CUDA toolkit for GPU support.
    """
    import subprocess

    os.makedirs(dest_dir, exist_ok=True)
    build_dir = os.path.join(dest_dir, "_prismml_build")

    print("Cloning PrismML/llama.cpp fork…")
    subprocess.run(
        ["git", "clone", "--depth=1", PRISMML_REPO_URL, build_dir],
        check=True
    )

    has_nvidia = _has_nvidia()
    cmake_args = ["-B", "build"]
    if has_nvidia:
        cmake_args += ["-DGGML_CUDA=ON"]
        print("NVIDIA GPU detected — building with CUDA support.")
    else:
        print("No NVIDIA GPU detected — building CPU-only binary.")

    print("Running cmake configure…")
    subprocess.run(["cmake"] + cmake_args, check=True, cwd=build_dir)

    print("Building llama-server (this takes a few minutes)…")
    subprocess.run(
        ["cmake", "--build", "build", "--config", "Release", "-j", "--target", "llama-server"],
        check=True,
        cwd=build_dir
    )

    exe_name   = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    built_path = None

    for candidate_rel in [
        os.path.join("build", "bin", "Release", exe_name),
        os.path.join("build", "bin", exe_name),
        os.path.join("build", exe_name),
    ]:
        candidate = os.path.join(build_dir, candidate_rel)
        if os.path.isfile(candidate):
            built_path = candidate
            break

    if built_path is None:
        raise RuntimeError("Could not locate built llama-server binary.")

    dest_path = os.path.join(dest_dir, exe_name)
    shutil.copy2(built_path, dest_path)
    if sys.platform != "win32":
        os.chmod(dest_path, 0o755)

    shutil.rmtree(build_dir, ignore_errors=True)
    print(f"✓ PrismML llama-server built at {dest_path}")
    return dest_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download or build the llama-server binary for Paramodus."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Install to ./bin/ (for PyInstaller bundling) instead of <app_data>/bin/",
    )
    parser.add_argument(
        "--standard",
        action="store_true",
        help="Download standard llama.cpp binary instead of PrismML fork (only for Q4_K_M variant).",
    )
    parser.add_argument(
        "--prismml",
        action="store_true",
        help=(
            "Build PrismML's llama.cpp fork from source (enables native Q1_0_g128 "
            "1-bit kernels). Requires git, cmake, and a C++17 compiler."
        ),
    )
    args = parser.parse_args()

    dest_dir = LOCAL_BIN if args.local else APP_DATA_BIN

    try:
        if args.prismml:
            path = build_prismml_binary(dest_dir)
        elif args.standard:
            path = download_standard_binary(dest_dir)
        else:
            path = download_prismml_binary(dest_dir)

        print()
        print("Done.  Paramodus will automatically detect the binary at:")
        print(f"  {path}")
        print()
        if args.local:
            print("Include it in your PyInstaller build via paramodus.spec:")
            print("  binaries=[('bin/llama-server.exe', '.')]")
    except Exception as exc:
        print(f"\n✗ Error: {exc}", file=sys.stderr)
        sys.exit(1)
