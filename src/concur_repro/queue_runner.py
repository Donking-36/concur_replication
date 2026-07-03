from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import re
import select
import subprocess
import time
import urllib.request

from .config import REPRO_ROOT, assert_under_root
from .live_metrics import latest_server_run_dir
from .state import (
    append_execution_log,
    now_iso,
    queue_finish_running,
    queue_start_next,
    update_queue_running_fields,
    update_active_run,
    update_heartbeat,
    update_run_lock,
)


RUN_ID_RE = re.compile(r'"run_id":\s*"([^"]+)"')


def _env(gpu_id: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "CONCUR_ROOT": "/data/3.8T-1/yue",
            "CONCUR_REPRO_ROOT": str(REPRO_ROOT),
            "HOME": "/data/3.8T-1/yue",
            "TMPDIR": "/data/3.8T-1/yue/.tmp",
            "XDG_CACHE_HOME": "/data/3.8T-1/yue/.cache",
            "HF_HOME": "/data/3.8T-1/yue/.cache/huggingface",
            "HUGGINGFACE_HUB_CACHE": "/data/3.8T-1/yue/.cache/huggingface/hub",
            "TRANSFORMERS_CACHE": "/data/3.8T-1/yue/.cache/huggingface/transformers",
            "TORCH_HOME": "/data/3.8T-1/yue/.cache/torch",
            "PIP_CACHE_DIR": "/data/3.8T-1/yue/.cache/pip",
            "UV_CACHE_DIR": "/data/3.8T-1/yue/.cache/uv",
            "CONDA_PKGS_DIRS": "/data/3.8T-1/yue/.cache/conda_pkgs",
            "PYTHONPYCACHEPREFIX": "/data/3.8T-1/yue/.cache/pycache",
            "PYTHONPATH": f"{REPRO_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep),
            "PYTHONUNBUFFERED": "1",
        }
    )
    env["PATH"] = f"/data/3.8T-1/yue/envs/sglang/bin{os.pathsep}{env.get('PATH', '')}"
    if gpu_id not in (None, "", "auto"):
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return env


def _query_gpus_structured() -> list[dict[str, int]]:
    out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.used,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        cwd="/data/3.8T-1/yue",
        env=_env(),
        text=True,
        timeout=30,
        stderr=subprocess.STDOUT,
    )
    rows: list[dict[str, int]] = []
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        rows.append(
            {
                "index": int(parts[0]),
                "memory_used_mib": int(parts[1]),
                "memory_free_mib": int(parts[2]),
                "utilization_gpu": int(parts[3]),
            }
        )
    return rows


def _query_gpus_from_table() -> list[dict[str, int]]:
    out = subprocess.check_output(
        ["nvidia-smi"],
        cwd="/data/3.8T-1/yue",
        env=_env(),
        text=True,
        timeout=30,
        stderr=subprocess.STDOUT,
    )
    rows: list[dict[str, int]] = []
    current_index: int | None = None
    gpu_line_re = re.compile(r"^\|\s*(?P<index>\d+)\s+")
    mem_line_re = re.compile(
        r"^\|.*?(?P<used>\d+)MiB\s*/\s*(?P<total>\d+)MiB\s*\|\s*(?P<util>\d+)%"
    )
    for line in out.splitlines():
        gpu_match = gpu_line_re.match(line)
        if gpu_match:
            current_index = int(gpu_match.group("index"))
            continue
        mem_match = mem_line_re.match(line)
        if mem_match and current_index is not None:
            used = int(mem_match.group("used"))
            total = int(mem_match.group("total"))
            rows.append(
                {
                    "index": current_index,
                    "memory_used_mib": used,
                    "memory_free_mib": max(0, total - used),
                    "utilization_gpu": int(mem_match.group("util")),
                }
            )
            current_index = None
    if not rows:
        raise RuntimeError("failed to parse nvidia-smi table output")
    return rows


def _query_gpus() -> list[dict[str, int]]:
    try:
        return _query_gpus_structured()
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip() or str(exc)
        append_execution_log(
            f"结构化 GPU 查询失败，尝试普通 nvidia-smi fallback：exit={exc.returncode} detail={detail}",
            phase="GPU_WAIT",
        )
        return _query_gpus_from_table()


def _format_gpu_rows(rows: list[dict[str, int]]) -> str:
    if not rows:
        return "未读到 GPU 行"
    return "; ".join(
        f"gpu{row['index']} used={row['memory_used_mib']}MiB free={row['memory_free_mib']}MiB util={row['utilization_gpu']}%"
        for row in rows
    )


def _gpu_is_idle(row: dict[str, int], max_used_mib: int, max_util_pct: int) -> bool:
    return row["memory_used_mib"] <= max_used_mib and row["utilization_gpu"] <= max_util_pct


def _choose_gpu(rows: list[dict[str, int]], requested_gpu: str, max_used_mib: int, max_util_pct: int) -> str | None:
    if requested_gpu != "auto":
        for row in rows:
            if str(row["index"]) == requested_gpu and _gpu_is_idle(row, max_used_mib, max_util_pct):
                return requested_gpu
        return None
    candidates = [row for row in rows if _gpu_is_idle(row, max_used_mib, max_util_pct)]
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row["memory_used_mib"], row["utilization_gpu"], row["index"]))
    return str(candidates[0]["index"])


def wait_for_gpu(
    requested_gpu: str,
    max_used_mib: int,
    max_util_pct: int,
    idle_confirmations: int,
    poll_s: int,
    timeout_s: int,
) -> str | None:
    deadline = time.time() + timeout_s
    last_selected: str | None = None
    consecutive_idle = 0
    while time.time() < deadline:
        try:
            rows = _query_gpus()
            selected = _choose_gpu(
                rows,
                requested_gpu=requested_gpu,
                max_used_mib=max_used_mib,
                max_util_pct=max_util_pct,
            )
            if selected is not None:
                if selected == last_selected:
                    consecutive_idle += 1
                else:
                    last_selected = selected
                    consecutive_idle = 1
                if consecutive_idle >= max(1, idle_confirmations):
                    append_execution_log(
                        f"GPU 等待完成：选择 GPU{selected}，阈值 memory<={max_used_mib} MiB 且 util<={max_util_pct}%，连续确认={consecutive_idle}；当前 {_format_gpu_rows(rows)}。",
                        phase="GPU_WAIT",
                    )
                    return selected
                append_execution_log(
                    f"GPU 空闲候选确认中：候选 GPU{selected}，第 {consecutive_idle}/{max(1, idle_confirmations)} 次；当前 {_format_gpu_rows(rows)}。",
                    phase="GPU_WAIT",
                )
            else:
                last_selected = None
                consecutive_idle = 0
            update_heartbeat(
                active=True,
                phase="GPU_WAIT",
                message=f"等待 GPU 空闲，目标={requested_gpu}，阈值 memory<={max_used_mib} MiB 且 util<={max_util_pct}%；当前 {_format_gpu_rows(rows)}。",
            )
            append_execution_log(
                f"GPU 等待：目标={requested_gpu}，阈值 memory<={max_used_mib} MiB 且 util<={max_util_pct}%；当前 {_format_gpu_rows(rows)}。",
                phase="GPU_WAIT",
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or str(exc)
            append_execution_log(f"GPU 等待检查失败：nvidia-smi exit={exc.returncode} detail={detail}", phase="GPU_WAIT")
        except Exception as exc:
            append_execution_log(f"GPU 等待检查失败：{type(exc).__name__}: {exc}", phase="GPU_WAIT")
        time.sleep(min(poll_s, max(1, int(deadline - time.time()))))
    return None


def recorded_server_is_healthy(port: int = 30000) -> bool:
    server_dir = latest_server_run_dir()
    if server_dir is None:
        return False
    pid_file = server_dir / "sglang_server.pid"
    if not pid_file.exists():
        return False
    pid = pid_file.read_text(encoding="utf-8").strip()
    if not pid.isdigit() or not Path(f"/proc/{pid}").exists():
        return False
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps(
                {
                    "model": "qwen3-32b",
                    "messages": [{"role": "user", "content": "Reply OK."}],
                    "temperature": 0,
                    "max_tokens": 2,
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception:
        return False


def _server_gpu_id() -> str | None:
    server_dir = latest_server_run_dir()
    if server_dir is None:
        return None
    match = re.search(r"-gpu([0-9]+)$", server_dir.name)
    return match.group(1) if match else None


def launch_sglang_server(gpu_id: str, port: int, model_path: str, timeout_s: int) -> bool:
    cmd = [
        "bash",
        str(REPRO_ROOT / "scripts" / "01_launch_sglang.sh"),
        str(gpu_id),
        str(port),
        model_path,
    ]
    append_execution_log(
        f"启动 SGLang server：GPU{gpu_id} port={port} model_path={model_path}，TP=1 由启动脚本强制设置。",
        phase="SGLANG_START",
    )
    update_heartbeat(
        active=True,
        phase="SGLANG_START",
        message=f"正在 GPU{gpu_id} 启动 SGLang TP=1 server，port={port}。",
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd="/data/3.8T-1/yue",
            env=_env(gpu_id),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        detail_path = REPRO_ROOT / "outputs" / "reports" / f"sglang_launch_timeout_{int(time.time())}.log"
        detail_path.write_text(exc.stdout or "", encoding="utf-8")
        append_execution_log(f"SGLang server 启动超时：log={detail_path}", phase="SGLANG_START")
        return False
    detail_path = REPRO_ROOT / "outputs" / "reports" / f"sglang_launch_{int(time.time())}.log"
    detail_path.write_text(proc.stdout or "", encoding="utf-8")
    if proc.returncode != 0:
        append_execution_log(
            f"SGLang server 启动失败：exit_code={proc.returncode} log={detail_path}",
            phase="SGLANG_START",
        )
        return False
    append_execution_log(f"SGLang server 启动成功：log={detail_path}", phase="SGLANG_START")
    return True


def ensure_server_ready(
    *,
    requested_gpu: str,
    max_used_mib: int,
    max_util_pct: int,
    idle_confirmations: int,
    poll_s: int,
    timeout_s: int,
    port: int,
    model_path: str,
    launch_timeout_s: int,
) -> tuple[bool, str | None]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if recorded_server_is_healthy(port=port):
            gpu_id = _server_gpu_id()
            append_execution_log(
                f"检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu={gpu_id or 'unknown'}。",
                phase="GPU_WAIT",
            )
            return True, gpu_id
        remaining = int(max(1, deadline - time.time()))
        selected_gpu = wait_for_gpu(
            requested_gpu=requested_gpu,
            max_used_mib=max_used_mib,
            max_util_pct=max_util_pct,
            idle_confirmations=idle_confirmations,
            poll_s=min(poll_s, remaining),
            timeout_s=min(poll_s, remaining),
        )
        if selected_gpu is None:
            continue
        if recorded_server_is_healthy(port=port):
            return True, _server_gpu_id() or selected_gpu
        if launch_sglang_server(
            gpu_id=selected_gpu,
            port=port,
            model_path=model_path,
            timeout_s=launch_timeout_s,
        ):
            if recorded_server_is_healthy(port=port):
                return True, selected_gpu
            append_execution_log("SGLang 启动脚本成功返回，但健康检查随后失败；继续等待或重试。", phase="SGLANG_START")
        time.sleep(min(poll_s, max(1, int(deadline - time.time()))))
    return False, None


def newest_run_id_from_output(text: str) -> str | None:
    matches = RUN_ID_RE.findall(text)
    return matches[-1] if matches else None


def run_item(item: dict, watchdog_timeout_s: int, gpu_id: str | None) -> tuple[int, str | None, str]:
    config_path = assert_under_root(Path(str(item["config_path"])))
    cmd = [
        "/data/3.8T-1/yue/envs/sglang/bin/python",
        "-m",
        "concur_repro.run_experiment",
        "--config",
        str(config_path),
    ]
    append_execution_log(f"队列开始运行：{item.get('name')} config={config_path}", phase=str(item.get("phase") or "QUEUE"))
    proc = subprocess.Popen(
        cmd,
        cwd="/data/3.8T-1/yue",
        env=_env(gpu_id),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    start = time.time()
    output_parts: list[str] = []
    while proc.poll() is None:
        if time.time() - start > watchdog_timeout_s:
            proc.terminate()
            append_execution_log(f"watchdog 超时，终止当前队列项：{item.get('name')}", phase=str(item.get("phase") or "QUEUE"))
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=60)
            return 124, None, "".join(output_parts)
        if proc.stdout is not None:
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            if ready:
                line = proc.stdout.readline()
                if line:
                    output_parts.append(line)
        update_heartbeat(
            active=True,
            phase=str(item.get("phase") or "QUEUE"),
            message=f"队列项 {item.get('name')} 正在运行，已运行 {time.time() - start:.0f}s。",
            run_id=item.get("run_id"),
        )
        time.sleep(5)
    if proc.stdout is not None:
        output_parts.append(proc.stdout.read())
    output = "".join(output_parts)
    return proc.returncode or 0, newest_run_id_from_output(output), output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=0, help="0 means drain all pending items")
    parser.add_argument("--gpu-max-used-mib", type=int, default=2000)
    parser.add_argument("--gpu-max-util-pct", type=int, default=5)
    parser.add_argument("--gpu-idle-confirmations", type=int, default=2)
    parser.add_argument("--gpu-id", default=os.environ.get("GPU_ID", "auto"), help="GPU index or auto")
    parser.add_argument("--gpu-wait-timeout-s", type=int, default=21600)
    parser.add_argument("--gpu-poll-s", type=int, default=300)
    parser.add_argument("--watchdog-timeout-s", type=int, default=7200)
    parser.add_argument("--server-port", type=int, default=30000)
    parser.add_argument("--model-path", default="/data/3.8T-1/yue/models/Qwen3-32B")
    parser.add_argument("--server-launch-timeout-s", type=int, default=1800)
    args = parser.parse_args()

    count = 0
    while args.max_items <= 0 or count < args.max_items:
        item = queue_start_next()
        if item is None:
            append_execution_log("队列为空，runner 退出。", phase="QUEUE")
            update_heartbeat(active=False, phase="QUEUE", message="队列为空，runner 已退出。")
            update_run_lock(locked=False, phase="QUEUE", reason="queue_empty")
            update_active_run(active=False, phase="QUEUE")
            return 0
        phase = str(item.get("phase") or "QUEUE")
        update_run_lock(locked=True, phase=phase, reason="queue_item_running", run_id=item.get("run_id"))
        update_active_run(
            active=True,
            phase=phase,
            config_path=str(item.get("config_path") or ""),
        )
        update_queue_running_fields(
            {
                "status_note": "waiting_for_gpu_or_server",
                "runner_updated_at": now_iso(),
                "requested_gpu": str(args.gpu_id),
            }
        )
        server_ready, gpu_id = ensure_server_ready(
            requested_gpu=str(args.gpu_id),
            max_used_mib=args.gpu_max_used_mib,
            max_util_pct=args.gpu_max_util_pct,
            idle_confirmations=args.gpu_idle_confirmations,
            poll_s=args.gpu_poll_s,
            timeout_s=args.gpu_wait_timeout_s,
            port=args.server_port,
            model_path=args.model_path,
            launch_timeout_s=args.server_launch_timeout_s,
        )
        if not server_ready:
            queue_finish_running("failed", "GPU wait timeout")
            append_execution_log(f"GPU 等待超时，队列项失败：{item.get('name')}", phase=phase)
            update_heartbeat(active=False, phase=phase, message=f"队列项 {item.get('name')} GPU 等待超时。")
            update_run_lock(locked=False, phase=phase, reason="gpu_wait_timeout")
            update_active_run(active=False, phase=phase)
            return 2
        update_queue_running_fields(
            {
                "status_note": "server_ready_running_experiment",
                "runner_updated_at": now_iso(),
                "selected_gpu": gpu_id,
            }
        )
        code, run_id, output = run_item(item, args.watchdog_timeout_s, gpu_id=gpu_id)
        if code == 0:
            queue_finish_running("done", "success", run_id=run_id)
            append_execution_log(f"队列项完成：{item.get('name')} run_id={run_id}", phase=phase, run_id=run_id)
        else:
            detail_path = REPRO_ROOT / "outputs" / "reports" / f"queue_failure_{int(time.time())}.log"
            detail_path.write_text(output, encoding="utf-8")
            queue_finish_running("failed", f"exit_code={code}; log={detail_path}", run_id=run_id)
            append_execution_log(f"队列项失败：{item.get('name')} exit_code={code} log={detail_path}", phase=phase, run_id=run_id)
            update_heartbeat(active=False, phase=phase, message=f"队列项 {item.get('name')} 失败，exit_code={code}。", run_id=run_id)
            update_run_lock(locked=False, phase=phase, reason="queue_item_failed", run_id=run_id)
            update_active_run(active=False, phase=phase, run_id=run_id)
            return code
        count += 1
    update_run_lock(locked=False, phase="QUEUE", reason="max_items_reached")
    update_heartbeat(active=False, phase="QUEUE", message="runner 达到 max-items 后退出。")
    update_active_run(active=False, phase="QUEUE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
