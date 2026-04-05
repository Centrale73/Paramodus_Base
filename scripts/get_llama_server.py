"""
scripts/get_llama_server.py
===========================
Downloads a pre-built llama-server binary for the current platform from the
official llama.cpp GitHub releases.

Usage
-----
    python scripts/get_llama_server.py              # installs to ~/.myapp/bin/
    python scripts/get_llama_server.py --local      # installs to ./bin/ (for PyInstaller bundling)
    python scripts/get_llama_server.py --prismml    # build PrismML fork instead (needs cmake)

For the Bonsai 8B native Q1_0_g128 format you need PrismML's fork:
    https://github.com/PrismML-Eng/llama.cpp
The --prismml flag will clone and build it locally (requires cmake + compiler).

For the bartowski Q4_K_M variant, the standard llama.cpp binary works fine.

After running this script, the binary is automatically detected by
local_model/manager.py via ~/.myapp/bin/ (or PATH).
"""

import argparse
import os
import platform
import shutil
import sys
import zipfile

import requests

GITHUB_RELEASES_URL = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
PRISMML_REPO_URL    = "https://github.com/PrismML-Eng/llama.cpp.git"

APP_DATA_BIN = os.path.join(os.path.expanduser("~"), ".myapp", "bin")
LOCAL_BIN    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


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

    def _score(name: str) -> int:
        name = name.lower()
        score = 0
        if system == "Windows":
            if "win" in name and name.endswith(".zip"):
                score += 10
                if "avx2" in name:   score += 3
                elif "avx" in name:  score += 1
                if "cuda" not in name and "vulkan" not in name:
                    score += 1  # prefer CPU-only for broadest compatibility
        elif system == "Linux":
            if "ubuntu" in name or "linux" in name:
                if name.endswith(".zip") or name.endswith(".tar.gz"):
                    score += 10
                if "x64" in name or "amd64" in name:
                    score += 2
        elif system == "Darwin":
            if "macos" in name and (name.endswith(".zip") or name.endswith(".tar.gz")):
                score += 10
                if "arm64" in name and ("arm" in machine or "aarch64" in machine):
                    score += 3
        return score

    ranked = sorted(assets, key=lambda a: _score(a["name"]), reverse=True)
    if not ranked or _score(ranked[0]["name"]) == 0:
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
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as z:
            for member in z.namelist():
                base = os.path.basename(member)
                if base == exe_name or base.rstrip(".exe") == "llama-server":
                    dest_path = os.path.join(dest_dir, exe_name)
                    with z.open(member) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if sys.platform != "win32":
                        os.chmod(dest_path, 0o755)
                    return dest_path
    else:
        import tarfile
        with tarfile.open(archive_path) as t:
            for member in t.getmembers():
                base = os.path.basename(member.name)
                if base == exe_name:
                    dest_path = os.path.join(dest_dir, exe_name)
                    f = t.extractfile(member)
                    with open(dest_path, "wb") as dst:
                        shutil.copyfileobj(f, dst)
                    if sys.platform != "win32":
                        os.chmod(dest_path, 0o755)
                    return dest_path

    raise RuntimeError(f"Could not find {exe_name} inside {archive_path}")


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

    # Detect CUDA
    has_cuda = shutil.which("nvcc") is not None
    cmake_args = ["-B", "build"]
    if has_cuda:
        cmake_args += ["-DGGML_CUDA=ON"]
        print("CUDA detected — building with GPU support.")
    else:
        print("No CUDA detected — building CPU-only binary.")

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

    # Locate the binary in common build output locations
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
        help="Install to ./bin/ (for PyInstaller bundling) instead of ~/.myapp/bin/",
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
        else:
            path = download_standard_binary(dest_dir)

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
