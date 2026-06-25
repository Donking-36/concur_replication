# CONCUR Qwen Single-GPU Reproduction Report

## 1. Scope

- Qwen only, no DeepSeek.
- Single RTX PRO 6000 GPU.
- Tensor parallel size target: TP=1.
- This report separates real Qwen runs from mock engineering-validation runs.

## 2. Hardware and Software

Environment snapshot is recorded in `outputs/reports/env_report.txt`.

```text
# Environment Report

timestamp: 2026-06-23T22:12:09+08:00
pwd: /data/3.8T-1/yue
CONCUR_ROOT: /data/3.8T-1/yue
CONCUR_REPRO_ROOT: /data/3.8T-1/yue/concur_qwen_repro
python: /data/3.8T-1/yue/envs/sglang/bin/python
Python 3.12.13

## Boundary Check
HOME /data/3.8T-1/yue OK
TMPDIR /data/3.8T-1/yue/.tmp OK
XDG_CACHE_HOME /data/3.8T-1/yue/.cache OK
HF_HOME /data/3.8T-1/yue/.cache/huggingface OK
HUGGINGFACE_HUB_CACHE /data/3.8T-1/yue/.cache/huggingface/hub OK
TRANSFORMERS_CACHE /data/3.8T-1/yue/.cache/huggingface/transformers OK
TORCH_HOME /data/3.8T-1/yue/.cache/torch OK
PIP_CACHE_DIR /data/3.8T-1/yue/.cache/pip OK
UV_CACHE_DIR /data/3.8T-1/yue/.cache/uv OK
CONDA_PKGS_DIRS /data/3.8T-1/yue/.cache/conda_pkgs OK

## Python Packages
torch: 2.11.0+cu130
sglang: 0.5.13.post1
transformers: 5.8.1
yaml: 6.0.1
httpx: 0.28.1
aiohttp: 3.14.1
pandas: 3.0.3
matplotlib: 3.11.0

## Model Paths
62G	/data/3.8T-1/yue/models/Qwen3-32B
/data/3.8T-1/yue/models/Qwen3-32B/config.json
/data/3.8T-1/yue/models/Qwen3-32B/tokenizer.json

## NVIDIA SMI
Tue Jun 23 22:12:16 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.126.20             Driver Version: 580.126.20     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA RTX PRO 6000 Blac...    On  |   00000000:21:00.0 Off |                    0 |
| N/A   31C    P0             90W /  600W |   84283MiB /  97887MiB |      0%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+
|   1  NVIDIA RTX PRO 6000 Blac...    On  |   00000000:41:00.0 Off |                    0 |
| N/A   34C    P0            135W /  600W |   36291MiB /  97887MiB |     91%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+
|   2  NVIDIA RTX PRO 6000 Blac...    On  |   00000000:A1:00.0 Off |                    0 |
| N/A   34C    P0            136W /  600W |   19674MiB /  97887MiB |     62%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+
|   3  NVIDIA RTX PRO 6000 Blac...    On  |   00000000:C1:00.0 Off |                    0 |
| N/A   34C    P0            139W /  600W |   24430MiB /  97887MiB |     92%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A          895004      G   /usr/lib/xorg/Xorg                        4MiB |
|    0   N/A  N/A         3055949      C   sglang::scheduler                     84260MiB |
|    1   N/A  N/A          895004      G   /usr/lib/xorg/Xorg                        4MiB |
|    1   N/A  N/A         3057454      C   .venv/bin/python                     
```

## 3. Model

- Primary candidate: `/data/3.8T-1/yue/models/Qwen3-32B`.
- Precision used for real runs: BF16.
- Qwen3-32B BF16 served successfully on one visible GPU with SGLang TP=1; no quantized or smaller-Qwen fallback was needed for the completed real runs.

## 4. Workload

Synthetic agentic workload:

- Each agent alternates LLM generation, synthetic tool wait, and synthetic observation append.
- Context length proxy grows monotonically by step.
- Agent observations and tool wait durations differ by agent and step.

## 5. Strategies

- `no_control`
- `request_cap`
- `fixed_window`
- `concur_dynamic`

## 6. Metrics

The local SGLang/Torch environment is repaired and real Qwen requests are served. Current structured harness outputs record:

- End-to-end batch latency.
- Mean and p95 agent latency.
- GPU metrics from `nvidia-smi` where available.
- Proxy KV cache usage, hit rate, prefill tokens, and recompute prefill tokens.

SGLang log parsing now additionally records exact server-emitted request and scheduler signals:

- Per-request prompt tokens, completion tokens, cached tokens, queue time, and request latency.
- Scheduler token usage, running request count, queued request count, pending tokens, prefill batches, and decode batches.
- Exact SGLang token usage and queue-depth figures generated from scheduler logs.

The remaining gap is block-level cache allocation, eviction, and HiCache internals; generated KV/hit-rate figures still include proxy fields where the harness does not receive exact block-level values.

See `outputs/reports/metrics_definition.md` and `outputs/reports/proxy_metric_explanation.md`.

## 7. Results

| run_id | status | backend | controller | agents | steps | latency_s | mock_excluded |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 20260623-184136-no_control-mock-pipeline-b2 | success | mock | no_control | 2 | 2 | 0.462 | True |
| 20260623-220318-no_control-Qwen3-32B-BF16-b2 | failed | openai | no_control | 2 | 2 |  |  |
| 20260623-221042-no_control-Qwen3-32B-BF16-b2 | success | openai | no_control | 2 | 2 | 3.993 | False |
| 20260623-221314-no_control-Qwen3-32B-b8 | success | openai | no_control | 8 | 8 | 181.513 | False |
| 20260623-221617-request_cap-Qwen3-32B-b8 | success | openai | request_cap_2 | 8 | 8 | 238.073 | False |
| 20260623-222107-fixed_window-Qwen3-32B-b8 | success | openai | fixed_window_4 | 8 | 8 | 200.244 | False |
| 20260623-222503-concur_dynamic-Qwen3-32B-b8 | success | openai | concur_dynamic | 8 | 8 | 200.295 | False |
| 20260623-224424-request-cap-1-Qwen3-32B-b8 | success | openai | request_cap_1 | 8 | 8 | 335.316 | False |
| 20260623-225031-request-cap-4-Qwen3-32B-b8 | success | openai | request_cap_4 | 8 | 8 | 195.781 | False |
| 20260623-225415-request-cap-8-Qwen3-32B-b8 | success | openai | request_cap_8 | 8 | 8 | 181.931 | False |
| 20260623-225754-fixed-window-2-Qwen3-32B-b8 | success | openai | fixed_window_2 | 8 | 8 | 251.800 | False |
| 20260623-230240-fixed-window-8-Qwen3-32B-b8 | success | openai | fixed_window_8 | 8 | 8 | 182.340 | False |
| 20260623-230625-fixed-window-16-effective-8-Qwen3-32B-b8 | success | openai | fixed_window_16_effective_8 | 8 | 8 | 181.918 | False |

## 7.1 Exact SGLang Log Metrics

| controller | requests | max_token_usage | max_queue_req | max_pending_token | cached_token_ratio | p95_request_latency_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_control | 4 | 0.04 | 0 | 0 | 0.0150 | 1.988 |
| no_control | 64 | 0.97 | 6 | 115056 | 0.0059 | 46.316 |
| request_cap_2 | 64 | 0.59 | 1 | 17134 | 0.0014 | 12.527 |
| fixed_window_4 | 64 | 0.93 | 2 | 50811 | 0.0017 | 24.945 |
| concur_dynamic | 64 | 0.93 | 4 | 87107 | 0.0017 | 31.831 |
| request_cap_1 | 64 | 0.29 | 0 | 11364 | 0.0013 | 7.775 |
| request_cap_4 | 64 | 0.88 | 2 | 53592 | 0.0014 | 30.211 |
| request_cap_8 | 64 | 0.97 | 6 | 115056 | 0.0014 | 46.216 |
| fixed_window_2 | 64 | 0.59 | 0 | 14487 | 0.0018 | 12.466 |
| fixed_window_8 | 64 | 0.97 | 6 | 115056 | 0.0014 | 46.384 |
| fixed_window_16_effective_8 | 64 | 0.97 | 6 | 115056 | 0.0014 | 46.241 |

## 7.2 Findings Against Success Criteria

- Context growth: every successful real run includes `context_growth.csv`, and the b8 workload uses 8 agents x 8 steps with 256 observation tokens appended per step.
- Baseline KV pressure: no-control b8 reached max SGLang scheduler token usage `0.97`, max queue depth `6`, and max pending tokens `115056`.
- Request-level cap is not a stable solution: `request_cap_1` and `request_cap_2` reduced scheduler pressure but worsened end-to-end latency to `335.316s` and `238.073s`; `request_cap_8` returned to no-control-like pressure with max token usage `0.97`.
- Fixed agent windows show both modes: conservative `fixed_window_2` reduced max token usage to `0.59` but slowed completion to `251.800s`; aggressive `fixed_window_8` matched no-control-like max token usage `0.97` and queue depth `6`.
- CONCUR dynamic completed the b8 run at `200.295s`, close to `fixed_window_4` (`200.244s`) and better than conservative fixed/request-cap settings, but it did not beat the no-control/aggressive-window latency in this single-run b8 measurement.
- CONCUR dynamic changed scheduler cache/token pressure under load: max token usage was `0.93` versus no-control `0.97`, while allowing max running requests `6` and max queue depth `4`.
- The ideal paper trend `CONCUR latency < no_control` was not reproduced on this single RTX PRO 6000 b8 run. The report should therefore be read as a single-GPU scaled Qwen reproduction with mixed latency outcome, not a numeric replication of the paper.

Artifacts:

- `outputs/tables/end_to_end_latency_table.csv`
- `outputs/tables/sglang_request_metrics_by_run.csv`
- `outputs/tables/sglang_request_summary_by_run.csv`
- `outputs/tables/sglang_scheduler_pressure_by_run.csv`
- `outputs/tables/sglang_scheduler_summary_by_run.csv`
- `outputs/figures/kv_usage_timeseries.png`
- `outputs/figures/cache_hit_rate_timeseries.png`
- `outputs/figures/sglang_token_usage_timeseries.png`
- `outputs/figures/sglang_queue_req_timeseries.png`
- `outputs/figures/window_timeseries.png`
- `outputs/figures/fixed_vs_dynamic_latency.png`
- `outputs/figures/prefill_recompute_overhead.png`

## 8. Difference from Paper

- Hardware is RTX PRO 6000 single-GPU instead of H100 multi-GPU.
- TP is fixed to 1 instead of paper-scale multi-GPU TP settings.
- Any mock run is pipeline validation only and not a Qwen or paper-scale result.
- Quantized or smaller-Qwen fallback was not needed for the completed real Qwen3-32B BF16 runs.

## 9. Failures and Limitations

- The initial local `/data/3.8T-1/yue/envs/sglang` environment lacked required packages; it has since been repaired for the reported runs.
- An earlier Qwen smoke run failed with connection refused before the final server lifecycle fix; the failed run is retained in `outputs/runs`.
- Exact SGLang request and scheduler log metrics are normalized into CSVs. Block-level cache allocation, eviction, and HiCache internals are not yet captured.
- Results are single-run measurements on a shared machine, not a statistical paper-scale reproduction.

## 10. Next Steps

- Add repeated trials for the best fixed-window and dynamic settings if GPU time permits.
- Add block-level cache allocation or eviction metrics if SGLang exposes them in a stable endpoint or log format.
- Keep mock runs excluded from Qwen performance claims.
