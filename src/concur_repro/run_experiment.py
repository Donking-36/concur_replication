from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import asyncio
import json
import os
import platform
import statistics
import subprocess
import sys
import time

from .clients import MockClient, OpenAICompatClient
from .config import REPRO_ROOT, append_jsonl, assert_under_root, read_config, write_config
from .controllers import (
    DynamicWindowController,
    FixedWindowController,
    NoControlController,
    RequestCap,
)
from .gpu import GpuSampler
from .metadata import controller_metadata, safe_slug
from .workload import make_agents, make_observation, synthetic_tool_wait


def run_id(controller_label: str, model_label: str, num_agents: int) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_model = safe_slug(model_label, max_len=40)
    safe_controller = safe_slug(controller_label, max_len=80)
    return f"{stamp}-{safe_controller}-{safe_model}-b{num_agents}"


def shell_capture(cmd: list[str], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as fh:
        try:
            subprocess.run(
                cmd,
                cwd="/data/3.8T-1/yue",
                env=os.environ.copy(),
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:
            fh.write(f"COMMAND_FAILED {cmd}: {type(exc).__name__}: {exc}\n")


def make_client(config: dict[str, Any]):
    backend = config.get("backend", "openai")
    if backend == "mock":
        return MockClient(delay_ms=int(config.get("mock_delay_ms", 25)))
    if backend == "openai":
        return OpenAICompatClient(
            base_url=str(config.get("base_url", "http://127.0.0.1:30000")),
            model=str(config.get("served_model_name") or config.get("model") or "qwen"),
            timeout_s=int(config.get("timeout_s", 600)),
        )
    raise ValueError(f"unsupported backend: {backend}")


def build_controller(config: dict[str, Any], events_path: Path, total_agents: int):
    strategy = config["strategy"]
    if strategy == "no_control" or strategy == "request_cap":
        return NoControlController(total_agents=total_agents, events_path=events_path)
    if strategy == "fixed_window":
        return FixedWindowController(
            total_agents=total_agents,
            events_path=events_path,
            window=int(config.get("agent_window", 4)),
        )
    if strategy == "concur_dynamic":
        return DynamicWindowController(
            total_agents=total_agents,
            events_path=events_path,
            alpha=int(config.get("alpha", 2)),
            beta=float(config.get("beta", 0.5)),
            u_low=float(config.get("U_low", 0.2)),
            u_high=float(config.get("U_high", 0.5)),
            h_thresh=float(config.get("H_thresh", 0.2)),
            w0=int(config.get("W_0", 4)),
            w_min=int(config.get("W_min", 1)),
            w_max=int(config.get("W_max", total_agents)),
            update_interval_s=float(config.get("update_interval_s", 1.0)),
        )
    raise ValueError(f"unsupported strategy: {strategy}")


async def run_agent(
    agent,
    *,
    config: dict[str, Any],
    client,
    controller,
    request_cap: RequestCap,
    agent_events_path: Path,
    serving_metrics_path: Path,
    context_rows: list[dict[str, Any]],
    agent_latencies: list[float],
) -> None:
    seed = int(config.get("seed", 0))
    num_steps = int(config["num_steps"])
    max_new_tokens = int(config["max_new_tokens"])
    obs_tokens = int(config["observation_tokens_per_step"])
    wait_min = int(config.get("tool_wait_min_ms", 100))
    wait_max = int(config.get("tool_wait_max_ms", 1000))
    temperature = float(config.get("temperature", 0))
    kv_budget_tokens = int(config.get("kv_proxy_budget_tokens", max(1, obs_tokens * num_steps * max(1, config["num_agents"] // 2))))
    agent.started_at = time.time()
    await controller.acquire_agent()
    try:
        resident_context_tokens = 0
        for step in range(num_steps):
            prompt = agent.build_prompt(step)
            input_tokens_proxy = max(1, (len(prompt) + 3) // 4)
            append_jsonl(
                agent_events_path,
                {
                    "timestamp": time.time(),
                    "agent_id": agent.agent_id,
                    "step": step,
                    "event": "generation_start",
                    "context_tokens_proxy": input_tokens_proxy,
                    "strategy": config["strategy"],
                },
            )
            async with request_cap:
                result = await client.generate(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                )
            cache_hit_proxy = 1.0 if step > 0 and resident_context_tokens > 0 else 0.0
            recompute_prefill_tokens_proxy = 0 if cache_hit_proxy else result.input_tokens
            kv_usage_proxy = min(1.0, input_tokens_proxy / max(1, kv_budget_tokens))
            if hasattr(controller, "update_metrics"):
                controller.update_metrics(kv_usage_proxy, cache_hit_proxy)
            append_jsonl(
                serving_metrics_path,
                {
                    "timestamp": time.time(),
                    "agent_id": agent.agent_id,
                    "step": step,
                    "metric_type": "proxy",
                    "kv_cache_usage_proxy": kv_usage_proxy,
                    "kv_cache_hit_rate_proxy": cache_hit_proxy,
                    "prefill_tokens": result.input_tokens,
                    "decode_tokens": result.output_tokens,
                    "generation_latency_s": result.latency_s,
                    "recompute_prefill_tokens_proxy": recompute_prefill_tokens_proxy,
                    "backend": config.get("backend", "openai"),
                },
            )
            append_jsonl(
                agent_events_path,
                {
                    "timestamp": time.time(),
                    "agent_id": agent.agent_id,
                    "step": step,
                    "event": "generation_end",
                    "context_tokens_proxy": input_tokens_proxy,
                    "output_tokens": result.output_tokens,
                    "generation_latency_s": result.latency_s,
                    "strategy": config["strategy"],
                },
            )
            wait_s = await synthetic_tool_wait(
                agent.agent_id,
                step,
                wait_min,
                wait_max,
                seed,
            )
            observation = make_observation(agent.agent_id, step, obs_tokens, seed)
            agent.observations.append(observation)
            resident_context_tokens = input_tokens_proxy + result.output_tokens + obs_tokens
            context_rows.append(
                {
                    "agent_id": agent.agent_id,
                    "step": step,
                    "context_tokens_proxy": input_tokens_proxy,
                    "observation_tokens_proxy": obs_tokens,
                    "tool_wait_s": wait_s,
                }
            )
            append_jsonl(
                agent_events_path,
                {
                    "timestamp": time.time(),
                    "agent_id": agent.agent_id,
                    "step": step,
                    "event": "tool_observation_appended",
                    "tool_wait_s": wait_s,
                    "observation_tokens_proxy": obs_tokens,
                    "context_tokens_after_append_proxy": resident_context_tokens,
                    "strategy": config["strategy"],
                },
            )
    finally:
        agent.finished_at = time.time()
        agent_latencies.append(agent.finished_at - agent.started_at)
        controller.release_agent()


def write_context_growth(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "agent_id",
        "step",
        "context_tokens_proxy",
        "observation_tokens_proxy",
        "tool_wait_s",
    ]
    with path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(columns) + "\n")
        for row in sorted(rows, key=lambda r: (r["agent_id"], r["step"])):
            fh.write(",".join(str(row[c]) for c in columns) + "\n")


async def run_async(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    client = make_client(config)
    num_agents = int(config["num_agents"])
    agents = make_agents(num_agents, int(config.get("seed", 0)))
    agent_events_path = run_dir / "agent_events.jsonl"
    controller_events_path = run_dir / "controller_events.jsonl"
    serving_metrics_path = run_dir / "serving_metrics.jsonl"
    controller = build_controller(config, controller_events_path, num_agents)
    request_cap_value = int(config.get("request_cap", 0)) if config["strategy"] == "request_cap" else 0
    request_cap = RequestCap(request_cap_value)
    context_rows: list[dict[str, Any]] = []
    agent_latencies: list[float] = []
    start = time.perf_counter()
    await asyncio.gather(
        *[
            run_agent(
                agent,
                config=config,
                client=client,
                controller=controller,
                request_cap=request_cap,
                agent_events_path=agent_events_path,
                serving_metrics_path=serving_metrics_path,
                context_rows=context_rows,
                agent_latencies=agent_latencies,
            )
            for agent in agents
        ]
    )
    batch_latency = time.perf_counter() - start
    write_context_growth(run_dir / "context_growth.csv", context_rows)
    completed = len(agent_latencies)
    metadata = controller_metadata(config, num_agents)
    summary = {
        "run_id": run_dir.name,
        "status": "success",
        "backend": config.get("backend", "openai"),
        "model": config.get("model"),
        "model_label": config.get("model_label"),
        "served_model_name": config.get("served_model_name"),
        "strategy": config["strategy"],
        **metadata,
        "num_agents": num_agents,
        "num_steps": int(config["num_steps"]),
        "observation_tokens_per_step": int(config["observation_tokens_per_step"]),
        "max_new_tokens": int(config["max_new_tokens"]),
        "end_to_end_batch_latency_s": batch_latency,
        "completed_agents_per_second": completed / batch_latency if batch_latency else 0.0,
        "mean_agent_latency_s": statistics.mean(agent_latencies) if agent_latencies else 0.0,
        "p95_agent_latency_s": statistics.quantiles(agent_latencies, n=20)[18] if len(agent_latencies) >= 20 else max(agent_latencies or [0.0]),
        "mock_result_excluded_from_qwen_claims": config.get("backend") == "mock",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def prepare_run(config: dict[str, Any], config_path: Path) -> Path:
    label = config.get("model_label") or str(config.get("model", "model")).split("/")[-1]
    metadata = controller_metadata(config, int(config["num_agents"]))
    out = REPRO_ROOT / "outputs" / "runs" / run_id(metadata["controller_label"], label, int(config["num_agents"]))
    out = assert_under_root(out)
    out.mkdir(parents=True, exist_ok=False)
    write_config(out / "config.yaml", config)
    (out / "command.txt").write_text(
        " ".join(sys.argv) + f"\nconfig_path: {config_path}\n",
        encoding="utf-8",
    )
    env_rows = [f"{k}={v}" for k, v in sorted(os.environ.items()) if k.startswith(("CONCUR", "CUDA", "HOME", "TMP", "XDG", "HF_", "HUGGINGFACE", "TRANSFORMERS", "TORCH", "PIP", "UV", "CONDA", "PYTHON"))]
    (out / "env.txt").write_text("\n".join(env_rows) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config_path = assert_under_root(Path(args.config))
    config = read_config(config_path)
    run_dir = prepare_run(config, config_path)
    shell_capture(["nvidia-smi"], run_dir / "nvidia_smi_start.txt")
    shell_capture(["nvidia-smi", "pmon", "-c", "1"], run_dir / "nvidia_smi_pmon_start.txt")
    sampler = GpuSampler(
        run_dir / "gpu_metrics.csv",
        gpu_index=os.environ.get("CUDA_VISIBLE_DEVICES") if os.environ.get("CUDA_VISIBLE_DEVICES", "").isdigit() else None,
    )
    if bool(config.get("sample_gpu", True)):
        try:
            sampler.start()
        except Exception as exc:
            (run_dir / "gpu_metrics.csv").write_text(f"gpu_sampler_failed,{type(exc).__name__},{exc}\n", encoding="utf-8")
    try:
        summary = asyncio.run(run_async(config, run_dir))
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        metadata = controller_metadata(config, int(config.get("num_agents", 0) or 0))
        failure = {
            "run_id": run_dir.name,
            "status": "failed",
            "backend": config.get("backend", "openai"),
            "model": config.get("model"),
            "model_label": config.get("model_label"),
            "served_model_name": config.get("served_model_name"),
            "strategy": config.get("strategy"),
            **metadata,
            "num_agents": config.get("num_agents"),
            "num_steps": config.get("num_steps"),
            "observation_tokens_per_step": config.get("observation_tokens_per_step"),
            "max_new_tokens": config.get("max_new_tokens"),
            "mock_result_excluded_from_qwen_claims": config.get("backend") == "mock",
            "type": type(exc).__name__,
            "message": str(exc),
            "python": sys.version,
            "platform": platform.platform(),
        }
        (run_dir / "failure_reason.md").write_text(
            "# Failure Reason\n\n"
            f"- type: {failure['type']}\n"
            f"- message: {failure['message']}\n",
            encoding="utf-8",
        )
        (run_dir / "summary.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        sampler.stop()
        shell_capture(["nvidia-smi"], run_dir / "nvidia_smi_end.txt")


if __name__ == "__main__":
    raise SystemExit(main())
