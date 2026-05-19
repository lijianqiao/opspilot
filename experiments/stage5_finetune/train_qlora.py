from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_dataset(path: Path) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        messages = row.get("messages", [])
        if [msg.get("role") for msg in messages] != ["system", "user", "assistant"]:
            raise ValueError(f"Invalid chat row: {row}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 5 QLoRA SFT experiment")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--dataset", default="experiments/stage5_finetune/data/opspilot_sft.jsonl")
    parser.add_argument("--output-dir", default="experiments/stage5_finetune/output")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    row_count = validate_dataset(dataset_path)
    if args.dry_run:
        print(f"Dataset OK: {row_count} rows")
        print(f"Model: {args.model}")
        print(f"Output: {args.output_dir}")
        return

    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=1,
        save_steps=args.max_steps,
        report_to="none",
        fp16=True,
    )
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        peft_config=peft_config,
        args=training_args,
        dataset_text_field="messages",
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
