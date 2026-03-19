"""
FlowPilot Benchmark — measure workflow generation quality across
intelligence layers and LLM models.

Usage:
    # Default: all vs none layers, default model
    python -m scripts.benchmark

    # Compare models
    python -m scripts.benchmark --models ollama:qwen3.5:397b ollama:deepseek-v3.2

    # Compare layers with specific model
    python -m scripts.benchmark --layers all none rag-only --models ollama:qwen3.5:397b

    # Dry run (no LLM calls)
    python -m scripts.benchmark --dry-run

    # Single prompt
    python -m scripts.benchmark --only slack-webhook --verbose
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.context_manager import estimate_tokens
from app.core.conversation_engine import ConversationEngine
from app.workflow.generator import WorkflowGenerator, WorkflowGenerationError
from app.workflow.validator import WorkflowValidator


# ── Data Structures ────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    prompt_id: str
    model: str
    layer_config: str
    validation_errors: int = 0
    fix_count: int = 0
    expected_nodes_found: float = 0.0
    param_accuracy: float = 0.0
    node_count_in_range: bool = False
    has_trigger: bool = False
    all_connected: bool = False
    generation_time_ms: int = 0
    retry_count: int = 1
    success: bool = False
    error: str | None = None
    workflow_json: dict | None = None
    context_tokens: int = 0


@dataclass
class ModelScore:
    model: str
    valid_rate: float = 0.0
    avg_fixes: float = 0.0
    node_accuracy: float = 0.0
    param_accuracy: float = 0.0
    avg_time_ms: float = 0.0
    avg_retries: float = 0.0
    overall_score: float = 0.0


# ── Layer Configurations ──────────────────────────────────────

LAYER_CONFIGS = {
    "all": {"rag": True, "knowledge": True, "learning": True, "templates": True},
    "none": {"rag": False, "knowledge": False, "learning": False, "templates": False},
    "rag-only": {"rag": True, "knowledge": False, "learning": False, "templates": False},
    "templates-only": {"rag": False, "knowledge": False, "learning": False, "templates": True},
    "no-templates": {"rag": True, "knowledge": True, "learning": True, "templates": False},
}


# ── Context Assembly ──────────────────────────────────────────


async def assemble_context(
    engine: ConversationEngine,
    message: str,
    config: dict[str, bool],
    session=None,
) -> str:
    """Assemble context based on layer configuration."""
    keywords = engine._extract_keywords(message)
    parts: list[str] = []

    if config.get("rag"):
        rag = engine._get_rag_context(message)
        if rag:
            parts.append(rag)

    if config.get("knowledge") and session:
        knowledge = await engine._get_knowledge_context(session, keywords)
        if knowledge:
            parts.append(knowledge)

    if config.get("learning") and session:
        learning = await engine._get_learning_context(session, keywords)
        if learning:
            parts.append(learning)

    if config.get("templates"):
        templates = engine._get_template_context(message, keywords)
        if templates:
            parts.append(templates)

    return "\n".join(parts)


# ── Quality Scoring ───────────────────────────────────────────


def score_workflow(
    workflow_json: dict,
    prompt_spec: dict,
    fixes: list[dict],
) -> dict:
    """Score a generated workflow against expected outcomes."""
    nodes = workflow_json.get("nodes", [])
    node_types = {n.get("type", "") for n in nodes}
    connections = workflow_json.get("connections", {})

    # Expected nodes found
    expected = set(prompt_spec.get("expected_nodes", []))
    found = expected & node_types
    node_accuracy = len(found) / len(expected) if expected else 1.0

    # Parameter accuracy
    expected_params = prompt_spec.get("expected_params", {})
    param_correct = 0
    param_total = 0
    for node_type, params in expected_params.items():
        matching_nodes = [n for n in nodes if n.get("type") == node_type]
        if matching_nodes:
            node = matching_nodes[0]
            node_params = node.get("parameters", {})
            for key, value in params.items():
                param_total += 1
                if node_params.get(key) == value:
                    param_correct += 1
        else:
            param_total += len(params)
    param_accuracy = param_correct / param_total if param_total else 1.0

    # Node count in range
    min_n = prompt_spec.get("min_nodes", 1)
    max_n = prompt_spec.get("max_nodes", 20)
    in_range = min_n <= len(nodes) <= max_n

    # Has trigger
    trigger_types = {"trigger", "Trigger", "webhook", "Webhook"}
    has_trigger = any(
        any(t in n.get("type", "") for t in trigger_types)
        for n in nodes
    )

    # All connected (simple: every node name appears in connections as source or target)
    node_names = {n.get("name", "") for n in nodes}
    connected_names = set()
    for source, targets in connections.items():
        connected_names.add(source)
        if isinstance(targets, dict):
            for output_type, output_list in targets.items():
                if isinstance(output_list, list):
                    for conn_group in output_list:
                        if isinstance(conn_group, list):
                            for conn in conn_group:
                                if isinstance(conn, dict):
                                    connected_names.add(conn.get("node", ""))
    # Trigger nodes may not be targets; allow 1 unconnected node (the trigger)
    unconnected = node_names - connected_names
    all_connected = len(unconnected) <= 1

    # Validation
    validator = WorkflowValidator()
    errors = validator.validate(workflow_json)

    return {
        "validation_errors": len(errors),
        "fix_count": len(fixes),
        "expected_nodes_found": node_accuracy,
        "param_accuracy": param_accuracy,
        "node_count_in_range": in_range,
        "has_trigger": has_trigger,
        "all_connected": all_connected,
    }


# ── Model Parsing ─────────────────────────────────────────────


def parse_model_spec(spec: str) -> tuple[str, str]:
    """Parse 'provider:model_name' into (provider, model).

    Handles model names that contain colons (e.g., 'ollama:qwen3.5:397b').
    """
    parts = spec.split(":", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid model spec '{spec}'. Format: provider:model (e.g., ollama:qwen3.5:397b)"
        )
    return parts[0], parts[1]


# ── Benchmark Runner ──────────────────────────────────────────


async def run_single(
    prompt_spec: dict,
    layer_config_name: str,
    provider: str,
    model: str,
    engine: ConversationEngine,
    generator: WorkflowGenerator,
    session=None,
) -> BenchmarkResult:
    """Run a single benchmark: one prompt × one layer config × one model."""
    config = LAYER_CONFIGS[layer_config_name]
    model_label = f"{provider}:{model}"

    # Assemble context
    context = await assemble_context(engine, prompt_spec["prompt"], config, session)
    context_tokens = estimate_tokens(context)

    # Generate
    start = time.perf_counter()
    try:
        workflow_json, fixes = await generator.generate(
            user_description=prompt_spec["prompt"],
            rag_context=context,
            provider=provider,
            model=model,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Score
        scores = score_workflow(workflow_json, prompt_spec, fixes)

        return BenchmarkResult(
            prompt_id=prompt_spec["id"],
            model=model_label,
            layer_config=layer_config_name,
            success=True,
            generation_time_ms=elapsed_ms,
            context_tokens=context_tokens,
            workflow_json=workflow_json,
            **scores,
        )

    except (WorkflowGenerationError, Exception) as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return BenchmarkResult(
            prompt_id=prompt_spec["id"],
            model=model_label,
            layer_config=layer_config_name,
            success=False,
            error=str(e),
            generation_time_ms=elapsed_ms,
            context_tokens=context_tokens,
        )


# ── Output Formatting ─────────────────────────────────────────


def compute_model_scores(
    results: list[BenchmarkResult],
    model: str,
    layer_config: str,
) -> ModelScore:
    """Compute aggregate scores for a model + layer combination."""
    filtered = [
        r for r in results
        if r.model == model and r.layer_config == layer_config
    ]
    if not filtered:
        return ModelScore(model=model)

    total = len(filtered)
    successful = [r for r in filtered if r.success]
    valid_count = sum(1 for r in successful if r.validation_errors == 0)

    valid_rate = valid_count / total if total else 0
    avg_fixes = sum(r.fix_count for r in successful) / len(successful) if successful else 0
    node_acc = sum(r.expected_nodes_found for r in successful) / len(successful) if successful else 0
    param_acc = sum(r.param_accuracy for r in successful) / len(successful) if successful else 0
    avg_time = sum(r.generation_time_ms for r in filtered) / total if total else 0
    avg_retries = sum(r.retry_count for r in successful) / len(successful) if successful else 0

    # Normalize fix_rate: assume max 10 fixes
    fix_rate = min(1.0, avg_fixes / 10.0)

    overall = (
        valid_rate * 25 +
        (1 - fix_rate) * 25 +
        node_acc * 25 +
        param_acc * 25
    )

    return ModelScore(
        model=model,
        valid_rate=valid_rate,
        avg_fixes=avg_fixes,
        node_accuracy=node_acc,
        param_accuracy=param_acc,
        avg_time_ms=avg_time,
        avg_retries=avg_retries,
        overall_score=round(overall, 1),
    )


def print_layer_comparison(results: list[BenchmarkResult], model: str, layers: list[str]):
    """Print layer comparison table for a single model."""
    print(f"\n{'=' * 72}")
    print(f"  FlowPilot Benchmark — {model}")
    print(f"{'=' * 72}")

    scores = {layer: compute_model_scores(results, model, layer) for layer in layers}

    # Header
    header = f"  {'Metric':<24}"
    for layer in layers:
        header += f" | {layer:>12}"
    if len(layers) == 2:
        header += f" | {'Delta':>10}"
    print(header)
    print(f"  {'-' * 24}" + (" | " + "-" * 12) * len(layers) + (" | " + "-" * 10 if len(layers) == 2 else ""))

    # Rows
    metrics = [
        ("Valid workflows", lambda s: f"{s.valid_rate:.0%}"),
        ("Avg fixes", lambda s: f"{s.avg_fixes:.1f}"),
        ("Node accuracy", lambda s: f"{s.node_accuracy:.0%}"),
        ("Param accuracy", lambda s: f"{s.param_accuracy:.0%}"),
        ("Avg time", lambda s: f"{s.avg_time_ms / 1000:.1f}s"),
        ("Overall score", lambda s: f"{s.overall_score}/100"),
    ]

    for name, fmt in metrics:
        row = f"  {name:<24}"
        for layer in layers:
            row += f" | {fmt(scores[layer]):>12}"
        if len(layers) == 2:
            s1, s2 = scores[layers[0]], scores[layers[1]]
            if name == "Avg fixes":
                delta = s2.avg_fixes - s1.avg_fixes if s1.avg_fixes else 0
                row += f" | {delta:>+9.1f}"
            elif name == "Overall score":
                delta = s1.overall_score - s2.overall_score
                row += f" | {delta:>+9.1f}"
        print(row)

    print(f"{'=' * 72}\n")


def print_model_comparison(results: list[BenchmarkResult], models: list[str], layer: str):
    """Print model comparison table for a single layer config."""
    print(f"\n{'=' * 80}")
    print(f"  FlowPilot Model Comparison — layers: {layer}")
    print(f"{'=' * 80}")

    scores = {model: compute_model_scores(results, model, layer) for model in models}

    # Short model labels
    short_labels = {}
    for m in models:
        _, model_name = parse_model_spec(m)
        short = model_name.split(":")[0][:12]
        short_labels[m] = short

    # Header
    header = f"  {'Metric':<24}"
    for m in models:
        header += f" | {short_labels[m]:>12}"
    print(header)
    print(f"  {'-' * 24}" + (" | " + "-" * 12) * len(models))

    metrics = [
        ("Valid workflows", lambda s: f"{s.valid_rate:.0%}"),
        ("Avg fixes", lambda s: f"{s.avg_fixes:.1f}"),
        ("Node accuracy", lambda s: f"{s.node_accuracy:.0%}"),
        ("Param accuracy", lambda s: f"{s.param_accuracy:.0%}"),
        ("Avg time", lambda s: f"{s.avg_time_ms / 1000:.1f}s"),
        ("Avg retries", lambda s: f"{s.avg_retries:.1f}"),
        ("OVERALL SCORE", lambda s: f"{s.overall_score}/100"),
    ]

    for name, fmt in metrics:
        row = f"  {name:<24}"
        for m in models:
            row += f" | {fmt(scores[m]):>12}"
        print(row)

    # Winner
    best = max(models, key=lambda m: scores[m].overall_score)
    print(f"\n  Winner: {best} (score: {scores[best].overall_score}/100)")
    print(f"{'=' * 80}\n")


def print_verbose_table(results: list[BenchmarkResult]):
    """Print per-prompt detail table."""
    print(f"\n{'=' * 90}")
    print(f"  Per-Prompt Details")
    print(f"{'=' * 90}")
    print(
        f"  {'Prompt':<20} | {'Model':<14} | {'Layers':<12} | "
        f"{'Valid':>5} | {'Fixes':>5} | {'Nodes':>8} | {'Time':>7}"
    )
    print(f"  {'-' * 20}-+-{'-' * 14}-+-{'-' * 12}-+-{'-' * 5}-+-{'-' * 5}-+-{'-' * 8}-+-{'-' * 7}")

    for r in results:
        _, model_name = parse_model_spec(r.model) if ":" in r.model else ("", r.model)
        short_model = model_name.split(":")[0][:12]
        valid = "OK" if r.success and r.validation_errors == 0 else "FAIL"
        nodes = f"{r.expected_nodes_found:.0%}" if r.success else "N/A"
        time_s = f"{r.generation_time_ms / 1000:.1f}s"

        print(
            f"  {r.prompt_id:<20} | {short_model:<14} | {r.layer_config:<12} | "
            f"{valid:>5} | {r.fix_count:>5} | {nodes:>8} | {time_s:>7}"
        )

    print(f"{'=' * 90}\n")


def print_dry_run(prompts: list[dict], engine: ConversationEngine, layers: list[str]):
    """Print what would be tested without making LLM calls."""
    print(f"\n{'=' * 60}")
    print(f"  DRY RUN — No LLM calls will be made")
    print(f"{'=' * 60}")
    print(f"\n  Prompts: {len(prompts)}")
    print(f"  Layer configs: {', '.join(layers)}")
    print()

    for prompt in prompts:
        print(f"  [{prompt['id']}]")
        print(f"    Prompt: {prompt['prompt'][:70]}...")
        print(f"    Expected nodes: {', '.join(prompt.get('expected_nodes', []))}")

        for layer_name in layers:
            config = LAYER_CONFIGS[layer_name]
            keywords = engine._extract_keywords(prompt["prompt"])
            context = engine._get_rag_context(prompt["prompt"]) if config.get("rag") else ""
            template_ctx = engine._get_template_context(prompt["prompt"], keywords) if config.get("templates") else ""
            total = context + template_ctx
            tokens = estimate_tokens(total)
            print(f"    [{layer_name}] context: {tokens} tokens")
        print()


# ── Main ──────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="FlowPilot Benchmark")
    parser.add_argument(
        "--models", nargs="+", default=None,
        help="Models to test (format: provider:model, e.g., ollama:qwen3.5:397b)",
    )
    parser.add_argument(
        "--layers", nargs="+", default=["all", "none"],
        choices=list(LAYER_CONFIGS.keys()),
        help="Layer configurations to test",
    )
    parser.add_argument(
        "--prompts", type=str, default=None,
        help="Path to custom prompts JSON file",
    )
    parser.add_argument("--only", type=str, default=None, help="Run only this prompt ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be tested")
    parser.add_argument("--verbose", action="store_true", help="Show per-prompt details")
    parser.add_argument(
        "--output", type=str, default="scripts/benchmark_results.json",
        help="Output file for results JSON",
    )
    args = parser.parse_args()

    # Load prompts
    prompts_path = args.prompts or str(Path(__file__).parent / "benchmark_prompts.json")
    with open(prompts_path) as f:
        prompts = json.load(f)

    if args.only:
        prompts = [p for p in prompts if p["id"] == args.only]
        if not prompts:
            print(f"Error: prompt '{args.only}' not found")
            sys.exit(1)

    # Resolve models
    if args.models:
        model_specs = [parse_model_spec(m) for m in args.models]
    else:
        from app.config import settings
        model_specs = [(settings.llm_provider, {
            "ollama": settings.ollama_model,
            "anthropic": settings.anthropic_model,
            "openai": settings.openai_model,
        }.get(settings.llm_provider, settings.ollama_model))]

    model_labels = [f"{p}:{m}" for p, m in model_specs]

    engine = ConversationEngine()

    # Dry run
    if args.dry_run:
        print_dry_run(prompts, engine, args.layers)
        print(f"  Models: {', '.join(model_labels)}")
        total_runs = len(prompts) * len(args.layers) * len(model_specs)
        print(f"\n  Total LLM calls if run: {total_runs}")
        print(f"  ({len(prompts)} prompts x {len(args.layers)} configs x {len(model_specs)} models)")
        return

    # DB session for knowledge/learning context
    session = None
    try:
        from app.db.session import async_session_factory
        session = async_session_factory()
    except Exception:
        print("  Warning: DB not available, knowledge/learning layers will be empty")

    generator = WorkflowGenerator()
    results: list[BenchmarkResult] = []

    total_runs = len(prompts) * len(args.layers) * len(model_specs)
    current = 0

    print(f"\n  FlowPilot Benchmark")
    print(f"  {len(prompts)} prompts x {len(args.layers)} configs x {len(model_specs)} models = {total_runs} runs\n")

    for provider, model in model_specs:
        for layer_name in args.layers:
            for prompt in prompts:
                current += 1
                model_short = model.split(":")[0][:12]
                print(
                    f"  [{current}/{total_runs}] {prompt['id']} | "
                    f"{model_short} | {layer_name}...",
                    end="",
                    flush=True,
                )

                result = await run_single(
                    prompt_spec=prompt,
                    layer_config_name=layer_name,
                    provider=provider,
                    model=model,
                    engine=engine,
                    generator=generator,
                    session=session,
                )
                results.append(result)

                status = "OK" if result.success else "FAIL"
                print(f" {status} ({result.generation_time_ms}ms, {result.fix_count} fixes)")

    if session:
        await session.close()

    # Output
    print("\n" + "=" * 72)

    # Layer comparison (per model)
    if len(args.layers) > 1:
        for label in model_labels:
            print_layer_comparison(results, label, args.layers)

    # Model comparison (per layer)
    if len(model_labels) > 1:
        for layer in args.layers:
            print_model_comparison(results, model_labels, layer)

    # Verbose
    if args.verbose:
        print_verbose_table(results)

    # Save results
    output_data = {
        "models": model_labels,
        "layers": args.layers,
        "prompts": [p["id"] for p in prompts],
        "results": [
            {k: v for k, v in asdict(r).items() if k != "workflow_json"}
            for r in results
        ],
        "scores": {
            f"{label}|{layer}": asdict(compute_model_scores(results, label, layer))
            for label in model_labels
            for layer in args.layers
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"  Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
