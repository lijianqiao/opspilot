# Stage 5 QLoRA Experiment

This is a principle experiment, not the OpsPilot runtime path.

## Setup

Use WSL2/Linux for `bitsandbytes` if native Windows fails.

```bash
python -m venv .venv-finetune
source .venv-finetune/bin/activate
pip install -r experiments/stage5_finetune/requirements.txt
```

## Prepare Dataset

```bash
uv run python scripts/prepare_sft_dataset.py
python experiments/stage5_finetune/train_qlora.py --dry-run
```

## Train

Default uses a 1.5B Qwen model for laptop feasibility. If you have a verified 2B-class GGUF/HF model path, pass it via `--model`.

```bash
python experiments/stage5_finetune/train_qlora.py \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --dataset experiments/stage5_finetune/data/opspilot_sft.jsonl \
  --output-dir experiments/stage5_finetune/output \
  --max-steps 20
```

## Compare

```bash
python experiments/stage5_finetune/compare_outputs.py \
  --base-model Qwen/Qwen2.5-1.5B-Instruct \
  --adapter experiments/stage5_finetune/output
```

Expected artifact: training logs with loss values and saved LoRA adapter files.
