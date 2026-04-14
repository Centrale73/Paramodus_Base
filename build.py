"""
build.py — One-command Paramodus .exe builder.

Usage:
    python build.py

What it does:
    1. Downloads the PrismML llama-server binary into ./bin/  (skipped if present)
    2. Downloads the Bonsai 8B GGUF model into ./models/      (skipped if present)
    3. Runs PyInstaller with paramodus.spec
    4. Prints the path to the final dist/ folder

End users receive the dist/Paramodus/ folder.  They open Paramodus.exe and
chat immediately — no internet connection, no API keys, no extra steps.

The model (~1.15 GB) is bundled inside the exe distribution so the binary +
model ship together as a single distributable.
"""

import subprocess
import sys
import os
import shutil


def main():
    root = os.path.dirname(os.path.abspath(__file__))

    # ── Step 1: PrismML llama-server binary ───────────────────────────────────
    # The PrismML fork is required for native Q1_0_g128 1-bit kernel support.
    # A pre-built binary is downloaded from GitHub releases — no cmake needed.
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    bin_path  = os.path.join(root, "bin", exe_name)

    if os.path.isfile(bin_path):
        print(f"[build] llama-server already in bin/ — skipping download.")
    else:
        print("[build] Downloading PrismML llama-server binary (1-bit kernel support)…")
        # No --standard flag = downloads PrismML pre-built release by default
        result = subprocess.run(
            [sys.executable, os.path.join(root, "scripts", "get_llama_server.py"), "--local"],
            check=False,
        )
        if result.returncode != 0:
            print("[build] ERROR: Failed to download llama-server. Check your internet connection.")
            sys.exit(1)
        if not os.path.isfile(bin_path):
            print(f"[build] ERROR: Expected binary not found at {bin_path}")
            sys.exit(1)
        print(f"[build] llama-server ready at {bin_path}")

    # ── Step 2: Bonsai 8B model ───────────────────────────────────────────────
    # Download the native 1-bit Bonsai GGUF (~1.15 GB) into ./models/ so that
    # paramodus.spec can bundle it.  End users never download it themselves.
    model_path = os.path.join(root, "models", "Bonsai-8B.gguf")

    if os.path.isfile(model_path):
        size_gb = os.path.getsize(model_path) / (1024 ** 3)
        print(f"[build] Bonsai-8B.gguf already in models/ ({size_gb:.2f} GB) — skipping download.")
    else:
        print("[build] Downloading Bonsai 8B model (~1.15 GB) into ./models/ for bundling…")
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(root, "scripts", "download_model_for_bundle.py"),
                "--model", "bonsai-8b-native",
            ],
            check=False,
        )
        if result.returncode != 0:
            print("[build] ERROR: Failed to download Bonsai model. Check your internet connection.")
            sys.exit(1)
        if not os.path.isfile(model_path):
            print(f"[build] ERROR: Expected model not found at {model_path}")
            sys.exit(1)
        print(f"[build] Bonsai-8B.gguf ready at {model_path}")

    # ── Step 3: PyInstaller ───────────────────────────────────────────────────
    if shutil.which("pyinstaller") is None:
        print("[build] PyInstaller not found — installing…")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    spec = os.path.join(root, "paramodus.spec")
    print("[build] Running PyInstaller…")
    result = subprocess.run(
        ["pyinstaller", spec, "--clean", "--noconfirm"],
        check=False,
    )
    if result.returncode != 0:
        print("[build] ERROR: PyInstaller failed.")
        sys.exit(1)

    # ── Done ──────────────────────────────────────────────────────────────────
    dist_dir = os.path.join(root, "dist", "Paramodus")
    exe_out  = os.path.join(dist_dir, "Paramodus.exe" if sys.platform == "win32" else "Paramodus")
    if os.path.isfile(exe_out):
        dist_size_mb = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, dn, fn in os.walk(dist_dir) for f in fn
        ) / (1024 ** 2)
        print(f"\n[build] ✓ Done — {dist_dir}/ ({dist_size_mb:.0f} MB total)")
        print("[build]   Distribute the dist/Paramodus/ folder.")
        print("[build]   End users open Paramodus.exe and chat immediately — no setup.")
    else:
        print(f"\n[build] Build finished. Check the dist/ folder.")


if __name__ == "__main__":
    main()
