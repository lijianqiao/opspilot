"""One-command eval score table:  uv run python scripts/run_eval.py"""

import anyio

from opspilot.eval.harness import format_table, run_all


def main() -> None:
    results = anyio.run(run_all)
    print(format_table(results))
    if not all(r.passed for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
