from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

SYSTEM_PROMPT = "你是 OpsPilot 运维助手。"


def convert_rows(rows: Iterable[dict[str, str]]) -> Iterator[dict[str, object]]:
    for row in rows:
        instruction = row["instruction"].strip()
        answer = row["answer"].strip()
        if not instruction or not answer:
            continue
        yield {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": answer},
            ]
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Stage 5 SFT JSONL dataset")
    parser.add_argument("--input", default="fixtures/finetune_seed_prompts.jsonl")
    parser.add_argument("--output", default="experiments/stage5_finetune/data/opspilot_sft.jsonl")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for item in convert_rows(rows):
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
