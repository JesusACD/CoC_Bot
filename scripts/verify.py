"""Run project verification checks (syntax/lint + pytest)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(title, cmd):
    print(f"\n=== {title} ===")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"[FAIL] {title} exited with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[OK] {title}")


def main():
    python = sys.executable
    run_step("Ruff syntax & undefined-name check", [python, "-m", "ruff", "check", "src", "tests"])
    run_step("Pytest suite", [python, "-m", "pytest"])
    print("\nAll verification checks passed.")


if __name__ == "__main__":
    main()
