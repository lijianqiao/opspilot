"""Run RAGAS evaluation on the 30 QA pairs.

Requires Qdrant running with ingested runbook docs.
Requires a real LLM for faithfulness + context_precision metrics.

Usage:
    uv run python scripts/run_rag_eval.py
    uv run python scripts/run_rag_eval.py --qa fixtures/rag_eval_qa.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference

from opspilot.rag.embedding import EmbeddingService
from opspilot.rag.qdrant_store import QdrantStore
from opspilot.rag.retrieval import RetrievalService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation on runbook RAG")
    parser.add_argument("--qa", default="fixtures/rag_eval_qa.json", help="Path to QA dataset JSON")
    parser.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant server URL")
    parser.add_argument("--llm-base-url", default="http://localhost:8080/v1", help="LLM API base URL")
    parser.add_argument("--llm-model", default="qwen3.5-9b", help="LLM model name")
    parser.add_argument("--llm-api-key", default="sk-local", help="LLM API key")
    args = parser.parse_args()

    # 1. Load QA dataset
    qa_path = Path(args.qa)
    qa_data = json.loads(qa_path.read_text("utf-8"))
    logger.info("Loaded %d QA pairs from %s", len(qa_data), qa_path)

    # 2. Initialize RAG pipeline
    store = QdrantStore(url=args.qdrant_url)
    count = store.point_count()
    if count == 0:
        raise SystemExit("Qdrant collection is empty. Run ingest_runbooks.py first.")
    logger.info("Qdrant has %d chunks", count)

    emb_svc = EmbeddingService()
    retriever = RetrievalService(store=store, embedding_service=emb_svc)

    # 3. Build RAGAS evaluation dataset
    samples: list[SingleTurnSample] = []
    for item in qa_data:
        contexts = retriever.retrieve(item["question"], top_k=3)
        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                retrieved_contexts=contexts,
                reference=item["reference"],
            )
        )

    dataset = EvaluationDataset(samples=samples)
    logger.info("Built evaluation dataset with %d samples", len(samples))

    # 4. Initialize LLM for evaluation
    from langchain_openai import ChatOpenAI

    eval_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=args.llm_model,
            base_url=args.llm_base_url,
            api_key=args.llm_api_key,
            temperature=0,
        )
    )

    # 5. Run evaluation
    metrics = [
        LLMContextPrecisionWithReference(llm=eval_llm),
        Faithfulness(llm=eval_llm),
    ]

    logger.info("Running RAGAS evaluation...")
    result = evaluate(dataset=dataset, metrics=metrics)
    df = result.to_pandas()

    # 6. Print results
    print("\n===== RAGAS Evaluation Results =====\n")
    print(f"Samples: {len(dataset)}")
    for metric_name in df.columns:
        if metric_name in ("user_input", "retrieved_contexts", "reference"):
            continue
        values = df[metric_name].dropna()
        if len(values) > 0:
            avg = values.mean()
            print(f"{metric_name}: {avg:.4f} (avg over {len(values)} samples)")

    print("\n===== Per-Question Scores =====\n")
    cols = ["user_input", "context_precision_with_reference", "faithfulness"]
    print(df[cols].to_string(index=False))

    store.close()
    logger.info("Evaluation complete")


if __name__ == "__main__":
    main()
