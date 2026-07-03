from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import asyncio
import contextlib
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
    DynamicWindowV2Controller,
    FixedWindowController,
    NoControlController,
    RequestCap,
)
from .live_metrics import SGLangLiveMetrics
from .gpu import GpuSampler
from .metadata import controller_metadata, safe_slug
from .state import (
    append_execution_log,
    now_iso,
    read_queue,
    update_queue_running_fields,
    update_active_run,
    update_heartbeat,
    update_run_lock,
)
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


def build_controller(config: dict[str, Any], events_path: Path, total_agents: int, metrics_reader=None):
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
    if strategy == "concur_dynamic_v2":
        if metrics_reader is None:
            raise ValueError("concur_dynamic_v2 requires metrics_reader")
        return DynamicWindowV2Controller(
            total_agents=total_agents,
            events_path=events_path,
            metrics_reader=metrics_reader,
            alpha=int(config.get("alpha", 2)),
            beta=float(config.get("beta", 0.5)),
            u_low=float(config.get("U_low", 0.35)),
            u_high=float(config.get("U_high", 0.8)),
            h_thresh=float(config.get("H_thresh", 0.05)),
            w0=int(config.get("W_0", 4)),
            w_min=int(config.get("W_min", 1)),
            w_max=int(config.get("W_max", total_agents)),
            update_interval_s=float(config.get("update_interval_s", 2.0)),
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
    workload_version = str(config.get("workload_version") or "legacy_v1")
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
            prompt = agent.build_prompt(step, workload_version=workload_version)
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
                    "workload_version": workload_version,
                },
            )
            async with request_cap:
                request_started_ts = time.time()
                result = await client.generate(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                )
            request_finished_ts = time.time()
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
                    "request_started_ts": request_started_ts,
                    "request_finished_ts": request_finished_ts,
                    "request_latency_s": request_finished_ts - request_started_ts,
                    "recompute_prefill_tokens_proxy": recompute_prefill_tokens_proxy,
                    "backend": config.get("backend", "openai"),
                    "agent_id": agent.agent_id,
                    "step": step,
                    "workload_version": workload_version,
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
                    "workload_version": workload_version,
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
            resident_context_tokens = input_tokens_proxy + result.output_tokens + obs_tokens
            context_rows.append(
                {
                    "agent_id": agent.agent_id,
                    "step": step,
                    "context_tokens_proxy": input_tokens_proxy,
                    "observation_tokens_proxy": obs_tokens,
                    "tool_wait_s": wait_s,
                    "workload_version": workload_version,
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
                    "workload_version": workload_version,
                },
            )
            agent.record_step_result(step, prompt, result.text, observation, workload_version=workload_version)
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
        "workload_version",
    ]
    with path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(columns) + "\n")
        for row in sorted(rows, key=lambda r: (r["agent_id"], r["step"])):
            fh.write(",".join(str(row[c]) for c in columns) + "\n")


async def run_async(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    client = make_client(config)
    num_agents = int(config["num_agents"])
    workload_version = str(config.get("workload_version") or "legacy_v1")
    agents = make_agents(num_agents, int(config.get("seed", 0)), workload_version=workload_version)
    agent_events_path = run_dir / "agent_events.jsonl"
    controller_events_path = run_dir / "controller_events.jsonl"
    serving_metrics_path = run_dir / "serving_metrics.jsonl"
    run_start_ts = time.time()
    metrics_reader = None
    if config["strategy"] == "concur_dynamic_v2":
        from .live_metrics import latest_server_run_dir

        server_run_dir = latest_server_run_dir()
        metrics_reader = SGLangLiveMetrics(server_run_dir=server_run_dir, run_start_ts=run_start_ts).read
    controller = build_controller(config, controller_events_path, num_agents, metrics_reader=metrics_reader)
    request_cap_value = int(config.get("request_cap", 0)) if config["strategy"] == "request_cap" else 0
    request_cap = RequestCap(request_cap_value)
    context_rows: list[dict[str, Any]] = []
    agent_latencies: list[float] = []
    start = time.perf_counter()
    monitor_stop = asyncio.Event()

    async def heartbeat_loop() -> None:
        last_summary = time.time()
        while not monitor_stop.is_set():
            update_heartbeat(
                active=True,
                phase=str(config.get("phase", config["strategy"])),
                message=f"run={run_dir.name} 正在运行，策略={config['strategy']}，workload={workload_version}",
                run_id=run_dir.name,
            )
            now = time.time()
            if now - last_summary >= 1800:
                append_execution_log(
                    f"阶段小结：run {run_dir.name} 仍在执行，策略={config['strategy']}，workload={workload_version}，已运行 {now - run_start_ts:.0f}s。",
                    phase=str(config.get("phase", config["strategy"])),
                    run_id=run_dir.name,
                )
                last_summary = now
            try:
                await asyncio.wait_for(monitor_stop.wait(), timeout=300)
            except asyncio.TimeoutError:
                continue

    heartbeat_task = asyncio.create_task(heartbeat_loop())
    if hasattr(controller, "start"):
        await controller.start()
    try:
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
    finally:
        monitor_stop.set()
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        if hasattr(controller, "stop"):
            await controller.stop()
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
        "workload_version": workload_version,
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
    run_id_value = run_dir.name
    append_execution_log(
        f"开始实验 run={run_id_value} config={config_path} strategy={config.get('strategy')} workload={config.get('workload_version', 'legacy_v1')}",
        phase=str(config.get("phase", config.get("strategy", "run"))),
        run_id=run_id_value,
    )
    update_run_lock(locked=True, phase=str(config.get("phase", config.get("strategy", "run"))), reason="experiment_running", run_id=run_id_value)
    update_active_run(
        active=True,
        phase=str(config.get("phase", config.get("strategy", "run"))),
        run_id=run_id_value,
        run_dir=str(run_dir),
        config_path=str(config_path),
        started_at=now_iso(),
    )
    update_heartbeat(
        active=True,
        phase=str(config.get("phase", config.get("strategy", "run"))),
        message=f"实验 {run_id_value} 已启动，等待完成。",
        run_id=run_id_value,
    )
    running_update = {
        "config_path": str(config_path),
        "strategy": config.get("strategy"),
        "workload_version": config.get("workload_version", "legacy_v1"),
        "run_id": run_id_value,
        "run_dir": str(run_dir),
        "status_note": "running by run_experiment",
    }
    queue = read_queue()
    if queue.get("running") is not None:
        update_queue_running_fields(running_update)
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
        append_execution_log(
            f"实验结束 run={run_id_value} latency_s={summary.get('end_to_end_batch_latency_s')} status=success",
            phase=str(config.get("phase", config.get("strategy", "run"))),
            run_id=run_id_value,
        )
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
        append_execution_log(
            f"实验失败 run={run_id_value} type={type(exc).__name__} message={exc}",
            phase=str(config.get("phase", config.get("strategy", "run"))),
            run_id=run_id_value,
        )
        print(json.dumps(failure, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        sampler.stop()
        shell_capture(["nvidia-smi"], run_dir / "nvidia_smi_end.txt")
        update_heartbeat(
            active=False,
            phase=str(config.get("phase", config.get("strategy", "run"))),
            message=f"实验 {run_id_value} 已结束。",
            run_id=run_id_value,
        )
        update_active_run(
            active=False,
            phase=str(config.get("phase", config.get("strategy", "run"))),
            run_id=run_id_value,
            run_dir=str(run_dir),
            config_path=str(config_path),
        )
        update_run_lock(locked=False, phase=str(config.get("phase", config.get("strategy", "run"))), reason="experiment_finished", run_id=run_id_value)


if __name__ == "__main__":
    raise SystemExit(main())
