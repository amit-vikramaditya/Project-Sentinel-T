"""
test_detection.py – entry-point shim
=====================================
Run the full pytest test suite from the repository root:

    pytest tests/ -v

Or run this file directly for a quick offline stress-test:

    python test_detection.py
"""
import subprocess
import sys


def main():
    print("Running Sentinel-T test suite via pytest …")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd="."
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
