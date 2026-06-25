# 已完成工作说明

本文档记录本次 CONCUR Qwen 单卡复现实验中已经完成的工作，便于在 GitHub 仓库中直接查看当前进度和产物。

## 1. 任务范围

- 只做 Qwen，不做 DeepSeek-V3。
- 只用单张 NVIDIA RTX PRO 6000 Blackwell GPU，Tensor Parallel 固定为 1。
- 目标是单卡缩放复现 CONCUR 的趋势，而不是论文 H100 多卡数值复刻。

## 2. 已完成的工程修复

### 2.1 本地环境修复

- 修复了 `/data/3.8T-1/yue/envs/sglang` 中的运行环境。
- 确认可用版本包括 `torch 2.11.0+cu130`、`sglang 0.5.13.post1`、`transformers 5.8.1`、`pandas 3.0.3`、`matplotlib 3.11.0`。
- 修复了 `scripts/env.sh`，把本地 venv 的 `bin` 目录加入 `PATH`，使 FlashInfer 可以找到 `ninja`。

### 2.2 SGLang 启动与生命周期

- 修复了 `scripts/01_launch_sglang.sh`。
- 启动时记录了 `nvidia-smi`、`nvidia-smi pmon`、`torch_visible_devices.txt`、`command.txt`、`env.txt`。
- 启动失败时写入 `failure_reason.md`。
- 以脱离终端的方式拉起 SGLang，并保留 PID 文件、stdout、stderr、health check 和日志输出。
- 最终可稳定服务 Qwen3-32B BF16，TP=1。

## 3. 已完成的实机实验

### 3.1 模型与 smoke

- 成功在 GPU 0 上服务 Qwen3-32B BF16。
- 真实 smoke 运行成功：
  - `20260623-221042-no_control-Qwen3-32B-BF16-b2`
  - 2 agents x 2 steps
  - 延迟约 `3.993s`
- 早期失败 smoke 保留用于诊断：
  - `20260623-220318-no_control-Qwen3-32B-BF16-b2`

### 3.2 b8 sweep

完成了 8 agents x 8 steps 的真实 Qwen BF16 sweep：

- `no_control`
- `request_cap_1`
- `request_cap_2`
- `request_cap_4`
- `request_cap_8`
- `fixed_window_2`
- `fixed_window_4`
- `fixed_window_8`
- `fixed_window_16_effective_8`
- `concur_dynamic`

结果上：

- no-control b8 的 SGLang token usage 最高到 `0.97`，queue depth 最高到 `6`。
- request cap 不是稳定解法，cap 越小越慢。
- fixed window 同时展示了保守和激进两种行为。
- CONCUR dynamic 在本次单卡单次 b8 测量里降低了一部分 scheduler 压力，但没有达到 `CONCUR latency < no_control` 的理想趋势。

## 4. 已完成的代码与数据产物

### 4.1 代码修改

- 增加了运行元数据标识，记录 `controller_label`、`request_cap`、`agent_window`、`effective_agent_window`、`W_0`、`W_min`、`W_max` 等字段。
- 新增 SGLang 日志解析逻辑，生成结构化的 request 和 scheduler 统计。
- 更新了分析脚本，让结果表和图表可以同时保留 proxy 指标和 exact SGLang log 指标。
- 更新了报告生成脚本，使结论部分明确写出本次实验的实际发现。

### 4.2 主要输出

已生成并保留：

- `outputs/tables/end_to_end_latency_table.csv`
- `outputs/tables/sglang_request_metrics_by_run.csv`
- `outputs/tables/sglang_request_summary_by_run.csv`
- `outputs/tables/sglang_scheduler_pressure_by_run.csv`
- `outputs/tables/sglang_scheduler_summary_by_run.csv`
- `outputs/figures/kv_usage_timeseries.png`
- `outputs/figures/cache_hit_rate_timeseries.png`
- `outputs/figures/window_timeseries.png`
- `outputs/figures/fixed_vs_dynamic_latency.png`
- `outputs/figures/prefill_recompute_overhead.png`
- `outputs/figures/sglang_token_usage_timeseries.png`
- `outputs/figures/sglang_queue_req_timeseries.png`
- `outputs/reports/qwen_single_gpu_report.md`

## 5. 已完成的报告与记录

- `progress.md`
- `next_steps.md`
- `decisions.md`
- `experiment_queue.yaml`
- `outputs/reports/latest_status.md`
- `outputs/reports/metrics_definition.md`
- `outputs/reports/proxy_metric_explanation.md`

这些文件记录了本次复现的当前状态、剩余工作和已知限制。

## 6. 已知限制

- 本次结果是单卡缩放复现，不是论文原始多卡 H100 结果。
- 本次结果是单次测量，不是统计意义上的多次重复实验。
- exact SGLang request/scheduler 日志已经结构化，但 block-level cache allocation、eviction、HiCache 内部状态仍未纳入最终分析。

## 7. 不包含的内容

- 不包含模型权重。
- 不包含 `/data/3.8T-1/yue/models`、`/data/3.8T-1/yue/envs`、`/data/3.8T-1/yue/.cache` 等大体积环境或缓存目录。
- 仓库只保留复现进度相关的代码、配置、日志、图表、表格和报告。

