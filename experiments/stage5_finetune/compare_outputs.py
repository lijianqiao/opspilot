from __future__ import annotations

import argparse

PROMPTS = [
    "OOMKilled 怎么排查？",
    "用户要求把 deployment 缩到 0 时你应该怎么做？",
    "为什么 Stage 5 的 Gateway 要保持极薄？",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare base model vs QLoRA adapter outputs")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--adapter", default="experiments/stage5_finetune/output")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("Prompts:")
        for prompt in PROMPTS:
            print(f"- {prompt}")
        return

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(args.base_model, device_map="auto", trust_remote_code=True)
    tuned = PeftModel.from_pretrained(base, args.adapter)
    for prompt in PROMPTS:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(tuned.device)
        with torch.no_grad():
            output = tuned.generate(**inputs, max_new_tokens=args.max_new_tokens)
        print(f"\n## {prompt}\n")
        print(tokenizer.decode(output[0], skip_special_tokens=True))


if __name__ == "__main__":
    main()
