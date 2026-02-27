"""Entry point for running benchmarks.

Usage (from benchmarks/ directory):
    python -m run_benchmark
"""

from src.runner import run_benchmark


def main():
    run_benchmark()


if __name__ == "__main__":
    main()