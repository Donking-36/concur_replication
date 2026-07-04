# CONCUR Qwen 单卡复现第二轮轻量创新计划书

创建时间：2026-07-04 Asia/Shanghai

工作目录：

```text
/data/3.8T-1/yue/concur_qwen_repro
```

目标分支：

```text
feature/qwen-innovation-round2
```

## 1. 当前依据

第一轮创新实验已经完成并推送，核心结论如下：

- `concur_cache_aware_v1` 在 b8 三 seed 上最好：latency mean `111.392s`，优于 `fixed_window_4` 的 `117.285s`，并把 `concur_dynamic_v2` 的 max queue mean 从 `76.000` 降到 `3.333`。
- `phase_window_v1` 是可解释的低复杂度 baseline，b8 上 latency mean `143.415s`，优于 `request_cap_4`，但不及 `fixed_window_4` 和 `concur_cache_aware_v1`。
- b12 seed0 上第一轮创新未超过 `fixed_window_4`：最佳创新 `phase_window_v1` 为 `216.478s`，而 `fixed_window_4` 为 `174.931s`。
- b16 seed0 上 `concur_cache_aware_v1` 表现好：`289.608s`，优于 `concur_dynamic_v2` 的 `341.366s`。

第二轮不追求复杂控制系统，只验证两个直接来自第一轮结果的简单假设：

1. 固定窗口 4 的 early-cache 优势是否可以通过尾部打开窗口进一步降低尾延迟。
2. metric-aware controller 是否应该保留一个更高的安全地板，而不是在压力下过度降到 1。

## 2. 创新点 C：Tail-Open Fixed Window

策略名：

```text
tail_open_v1
```

核心想法：

`fixed_window_4` 是 b8 和 b12 的强 baseline，说明早期较小 admission window 对 prefix cache 友好。但当部分 agent 已经完成或进入后半程时，继续保持窗口 4 可能导致尾部串行。`tail_open_v1` 保留 early `W=4`，在进度达到阈值后打开到 `W=8`。

初始规则：

```text
W_base = 4
W_tail = 8
tail_finished_ratio = 0.50
tail_progress_steps = 5
```

窗口规则：

```text
如果 finished_agents / total_agents >= tail_finished_ratio：W = W_tail
否则如果 warm_agents(step >= tail_progress_steps) >= W_base：W = W_tail
否则：W = W_base
```

预期贡献：

- 仍然是 progress-only，不依赖 SGLang exact metrics，复杂度接近固定窗口。
- 验证“先保护 cache，再释放尾部并发”是否能在 b8/b12 接近或超过 `fixed_window_4`。

验收标准：

- b8 latency mean 应接近或低于 `fixed_window_4` 的 `117.285s`。
- b8 exact cached ratio 不应明显低于 `fixed_window_4` 的 `0.663`。
- b12 seed0 如果不能超过 `fixed_window_4`，需要报告 tail-open 的 tradeoff，而不是夸大。

## 3. 创新点 D：Cache-Gated Growth Controller

策略名：

```text
cache_gate_v1
```

核心想法：

`concur_cache_aware_v1` 在 b8/b16 表现好，但 b12 没有超过 `fixed_window_4`。一个可能原因是 queue/pending-token guard 在中段把窗口降得过低，牺牲吞吐。`cache_gate_v1` 保留 exact metric feedback，但把窗口地板设为 4：在压力下回到固定窗口强 baseline，而不是降到 1；只有 cache health 足够好且 queue 不高时才增长到 6/8。

初始规则：

```text
W_0 = 4
W_min = 4
W_max = 8
W_step = 1
cache_low = 0.28
cache_high = 0.55
queue_high = 4
pending_high = 120000
U_high = 0.94
cooldown_ticks = 1
```

控制逻辑：

```text
如果 token_usage >= U_high 且 cache_ewma < cache_low：W -= 1，但不低于 4
如果 queue_req >= queue_high 或 pending_token >= pending_high：W -= 1，但不低于 4
如果 cache_ewma >= cache_high 且 queue_req < queue_high 且 cooldown 结束：W += 1
否则：hold
```

预期贡献：

- 比 `concur_cache_aware_v1` 更保守，重点不是更激进地降负载，而是把 fixed-window-4 作为安全地板。
- 在 b12 上验证是否能避免过度收缩；在 b16 上验证是否仍能保持第一轮的高压优势。

验收标准：

- b8 latency mean 应低于 `concur_dynamic_v2` 的 `188.693s`，并尽量接近 `concur_cache_aware_v1`。
- b12 seed0 应优先对比 `fixed_window_4` 和 `concur_dynamic_v2`。
- b16 seed0 应不差于 `concur_dynamic_v2`，否则说明高地板破坏了压力控制。
- controller event 中必须记录 exact SGLang metrics、`cached_ratio_ewma`、`cooldown_remaining` 和窗口变化 reason。

## 4. 实验矩阵

第二轮新增 10 个 run，输出目录单独放在：

```text
outputs/innovation_round2/runs
```

### 4.1 b8 三 seed

```text
controllers = tail_open_v1, cache_gate_v1
seeds = 0, 1, 2
num_agents = 8
num_steps = 8
observation_tokens_per_step = 256
max_new_tokens = 64
workload_version = prefix_stable_v2
```

### 4.2 b12/b16 seed0 压力验证

```text
controllers = tail_open_v1, cache_gate_v1
scenarios = b12_medium, b16_medium
seed = 0
```

具体规模：

```text
b12_medium: num_agents=12, num_steps=8, observation_tokens_per_step=256
b16_medium: num_agents=16, num_steps=8, observation_tokens_per_step=256
```

## 5. 需要改动的文件

代码：

```text
src/concur_repro/controllers.py
src/concur_repro/run_experiment.py
src/concur_repro/metadata.py
src/concur_repro/analyze.py
```

配置：

```text
configs/experiments/tail_open_v1_b8_seed{0,1,2}_prefix_v2.yaml
configs/experiments/cache_gate_v1_b8_seed{0,1,2}_prefix_v2.yaml
configs/experiments/tail_open_v1_b12_seed0_prefix_v2.yaml
configs/experiments/cache_gate_v1_b12_seed0_prefix_v2.yaml
configs/experiments/tail_open_v1_b16_seed0_prefix_v2.yaml
configs/experiments/cache_gate_v1_b16_seed0_prefix_v2.yaml
```

队列：

```text
experiment_queue_innovation_round2.yaml
```

生成物：

```text
outputs/innovation_round2/tables
outputs/innovation_round2/figures
outputs/innovation_round2/reports
```

## 6. 执行流程

1. 实现 `tail_open_v1` 和 `cache_gate_v1`。
2. 新增 10 个配置文件和第二轮队列。
3. 用 `QUEUE_PATH=experiment_queue_innovation_round2.yaml bash scripts/08_run_queue.sh` 跑完队列。
4. 运行分析脚本，生成第二轮表格、图和报告。
5. 检查 GPU 上是否遗留本次 SGLang 进程；若有，只清理本次实验启动的进程。
6. 提交并推送 `feature/qwen-innovation-round2`，不合并到 `main`。
