import json
from pathlib import Path

from scripts.prepare_sft_dataset import convert_rows


def test_convert_rows_outputs_chat_messages() -> None:
    rows = [{"instruction": "hello", "answer": "world"}]
    converted = list(convert_rows(rows))
    assert converted == [
        {
            "messages": [
                {"role": "system", "content": "你是 OpsPilot 运维助手。"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ]
        }
    ]


def test_seed_dataset_has_required_fields() -> None:
    path = Path("fixtures/finetune_seed_prompts.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 10
    assert all(row["instruction"] and row["answer"] for row in rows)
