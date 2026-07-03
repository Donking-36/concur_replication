# CONCUR Qwen 单卡复现后续创新计划书

创建时间：2026-07-04 Asia/Shanghai

工作目录：

```text
/data/3.8T-1/yue/concur_qwen_repro
```

## 1. 背景和当前基线

当前 v2 复现已经完成，主要事实如下：

- `prefix_stable_v2` 已经把 old v1 b8 exact cached-token ratio mean 从约 `0.0019` 提高到约 `0.2731`。
- `concur_dynamic_v2` 已经从 admission-only 变为周期 exact SGLang metric feedback controller。
- b8 三 seed 的主要结果：
  - `fixed_window_4` latency mean `117.285s`，cached ratio mean `0.663`，是 b8 latency 最优。
  - `fixed_window_8` latency mean `163.914s`，cached ratio mean `0.203`。
  - `concur_dynamic_v2` latency mean `188.693s`，cached ratio mean `0.182`，max queue 较高。
- P6 压力结果：
  - b12：`fixed_window_4` 最快，`concur_dynamic_v2` 快于 no-control/fixed_window_8。
  - b16：`concur_dynamic_v2` 在已测三个 controller 中最快。
  - b8-long ctxfit：`fixed_window_4` 最快。

因此后续创新不应追求复杂系统，而应围绕一个清晰缺口推进：现有 dynamic v2 证明了在线 exact feedback 可用，但控制律还不够贴合“保护 prefix-cache 命中”和“限制 queue/pending token”的目标。

## 2. 两个创新点

### 创新点 A：Cache-Aware Hysteresis Controller

建议策略名：

```text
concur_cache_aware_v1
```

核心想法：

当前 `concur_dynamic_v2` 主要按 token usage 和 recent cache ratio 做 AIMD 式窗口变化，b8 上出现 queue 深度过高、latency 波动较大。新的 `concur_cache_aware_v1` 不追求复杂，只增加两个稳健机制：

1. 用 exact `recent_cached_token_ratio` 的 EWMA 作为 cache health。
2. 用 hysteresis 避免窗口频繁来回抖动。

初始规则：

```text
W_min = 1
W_max = 8
W_0 = 4
update_interval_s = 2
cache_low = 0.12
cache_high = 0.35
U_high = 0.92
U_low = 0.55
queue_high = 4
pending_high = 120000
cooldown_ticks = 2
```

控制逻辑：

```text
如果 metric stale：hold
如果 token_usage >= U_high 且 cached_ratio_ewma < cache_low：W -= 2
如果 queue_req >= queue_high 或 pending_token >= pending_high：W -= 1
如果 token_usage <= U_low 且 cached_ratio_ewma >= cache_high 且 cooldown 已结束：W += 1
否则：hold
```

预期贡献：

- 不是声称一定比 `fixed_window_4` 更快，而是验证“加入 cache health + hysteresis 后，dynamic controller 是否减少 queue spikes，同时保持可接受 latency”。
- 重点指标是 `max_queue_req`、`max_pending_token`、cached ratio、latency variance。

验收标准：

- controller event 必须继续是周期 exact feedback，`exact_controller_event_count` 接近 `controller_event_count`。
- b8 三 seed 上，`max_queue_req_mean` 应明显低于当前 `concur_dynamic_v2` 的 `76.0`。
- b8 latency mean 应低于当前 `concur_dynamic_v2` 的 `188.693s`，或者在没有低于时给出明确 tradeoff 解释。
- b12/b16 至少各跑 seed0，观察是否保留 dynamic v2 在高压力下的优势。

### 创新点 B：Warmup-Then-Open 分阶段窗口

建议策略名：

```text
phase_window_v1
```

核心想法：

`fixed_window_4` 之所以强，很可能是因为较小 admission window 更利于每个 agent 的 prefix cache 稳定保留；`fixed_window_8` 提高并发但 cache ratio 明显下降。我们可以做一个不依赖在线 metric 的简单分阶段 controller：

1. 前期用小窗口保护 prefix cache 建立。
2. 后期逐步打开窗口，提高吞吐。

初始规则：

```text
warmup_steps = 2
W_warmup = 4
W_after = 8
optional_ramp = true
```

每个 agent 完成 step 0/1 前，窗口保持 4；当全局完成的 generation step 中位数达到 `warmup_steps` 后，窗口从 4 提升到 6，再提升到 8。这个 controller 不需要在线 SGLang metrics，只依赖 harness 里已有的 agent step progress。

预期贡献：

- 这是一个很小的 scheduling innovation，适合作为“低复杂度创新点”。
- 它可以检验一个具体假设：先建立 prefix cache，再释放并发，是否能在 b8/b12 上取得介于 `fixed_window_4` 和 `fixed_window_8` 之间甚至更优的 latency/cache tradeoff。

验收标准：

- b8 三 seed 上 cached ratio mean 应高于 `fixed_window_8` 的 `0.203`。
- b8 latency mean 应低于 `request_cap_4` 的 `183.493s`，并尽量接近 `fixed_window_4`。
- 如果没有跑赢 `fixed_window_4`，报告中应明确说明它的价值是“无在线指标、实现简单、tradeoff 可解释”，而不是夸大性能。

## 3. 实验矩阵

优先复用现有 baseline 表，不重复跑已完成的 no-control/fixed-window/dynamic-v2，除非发现环境波动太大。

### 第一批：b8 三 seed

新增 6 个 run：

```text
controllers = concur_cache_aware_v1, phase_window_v1
seeds = 0, 1, 2
num_agents = 8
num_steps = 8
observation_tokens_per_step = 256
max_new_tokens = 64
workload_version = prefix_stable_v2
```

对比对象来自现有表：

```text
no_control
request_cap_4
fixed_window_4
fixed_window_8
concur_dynamic_v2
```

### 第二批：P6 seed0 压力验证

新增 6 个 run：

```text
controllers = concur_cache_aware_v1, phase_window_v1
scenarios = b8_long_ctxfit, b12_medium, b16_medium
seed = 0
```

其中：

```text
b8_long_ctxfit: num_agents=8, num_steps=12, observation_tokens_per_step=320
b12_medium: num_agents=12, num_steps=8, observation_tokens_per_step=256
b16_medium: num_agents=16, num_steps=8, observation_tokens_per_step=256
```

如果 b16 出现 OOM、context length、server crash 或 token_usage 长时间接近 1.0，则停止 b16 扩展，不重试同配置。

## 4. 需要实现的代码改动

### 4.1 Controller

修改：

```text
src/concur_repro/controllers.py
src/concur_repro/run_experiment.py
src/concur_repro/metadata.py
```

新增策略：

```text
concur_cache_aware_v1
phase_window_v1
```

要求：

- controller event schema 继续包含：
  `timestamp`, `strategy`, `metric_type`, `W_t`, `W_next`, `U_t`, `H_t`,
  `active_agents`, `pending_agents`, `finished_agents`, `running_req`,
  `queue_req`, `pending_token`, `action`, `reason`。
- `phase_window_v1` 即使不使用 exact metrics，也要记录 `metric_type=progress_schedule`，并记录当前 step progress。
- `concur_cache_aware_v1` 必须记录 `cached_ratio_ewma`、`cooldown_remaining` 和触发窗口变化的 reason。

### 4.2 Config

新增配置文件：

```text
configs/experiments/cache_aware_v1_b8_seed0_prefix_v2.yaml
configs/experiments/cache_aware_v1_b8_seed1_prefix_v2.yaml
configs/experiments/cache_aware_v1_b8_seed2_prefix_v2.yaml
configs/experiments/phase_window_v1_b8_seed0_prefix_v2.yaml
configs/experiments/phase_window_v1_b8_seed1_prefix_v2.yaml
configs/experiments/phase_window_v1_b8_seed2_prefix_v2.yaml
configs/experiments/cache_aware_v1_b8_long_ctxfit_seed0_prefix_v2.yaml
configs/experiments/phase_window_v1_b8_long_ctxfit_seed0_prefix_v2.yaml
configs/experiments/cache_aware_v1_b12_seed0_prefix_v2.yaml
configs/experiments/phase_window_v1_b12_seed0_prefix_v2.yaml
configs/experiments/cache_aware_v1_b16_seed0_prefix_v2.yaml
configs/experiments/phase_window_v1_b16_seed0_prefix_v2.yaml
```

### 4.3 Queue

建议不要覆盖已经完成的 reproduction 队列。新增：

```text
experiment_queue_innovation.yaml
```

保持与 `experiment_queue.yaml` 相同 schema：

```yaml
pending: []
running: null
done: []
failed: []
skipped: []
```

需要让 `scripts/08_run_queue.sh` 或 `queue_runner.py` 支持传入：

```text
QUEUE_PATH=experiment_queue_innovation.yaml
```

如果这个改动风险较大，也可以继续使用 `experiment_queue.yaml`，但必须在日志中明确标记 phase 为 `INNOVATION`，避免和已完成复现混淆。

## 5. 分析与报告

新增或扩展：

```text
src/concur_repro/analyze.py
```

输出：

```text
outputs/tables/innovation_controller_runs.csv
outputs/tables/innovation_controller_summary.csv
outputs/figures/innovation_latency_vs_cache.png
outputs/figures/innovation_queue_pressure.png
outputs/figures/innovation_window_timeseries.png
outputs/reports/qwen_innovation_report.md
```

报告结构：

```text
# Qwen CONCUR Innovation Report
## 1. Goal
## 2. Baseline from v2 Reproduction
## 3. Innovation A: Cache-Aware Hysteresis Controller
## 4. Innovation B: Warmup-Then-Open Phase Window
## 5. Experiment Matrix
## 6. Results
## 7. Success Criteria
## 8. Failures and Limitations
## 9. Recommendation
```

必须如实说明：

- 如果创新 controller 没有跑赢 `fixed_window_4`，不能包装成性能胜利。
- 可以把贡献定位为“更简单的 schedule tradeoff”、“更低 queue/pending token”、“更稳定 dynamic controller”。
- 不要把单卡 Qwen3-32B 结果写成论文多卡结论。

## 6. Codex 长时间自动化执行协议

### 6.1 恢复审计

每次 Codex 开始工作先执行：

```bash
cd /data/3.8T-1/yue/concur_qwen_repro
git status --short --branch --untracked-files=all
sed -n '1,220p' outputs/reports/latest_status.md
cat outputs/reports/heartbeat.json
cat outputs/reports/run_lock.json
cat outputs/reports/active_run.json
sed -n '1,260p' experiment_queue_innovation.yaml
```

如果 `experiment_queue_innovation.yaml` 不存在，则先创建；如果 `running` 非空，则按 run 目录中的 `summary.json` / `failure_reason.md` 修正状态。

### 6.2 中文日志

继续追加：

```text
outputs/reports/codex_execution_log.md
```

每个阶段必须写中文日志：

- 准备修改哪些文件。
- 为什么修改。
- 启动哪个 config。
- run_id、run_dir、latency、失败原因。
- GPU 检查结果。
- 是否跳过/降级。
- 分析与报告生成结果。
- commit/push 前后状态。

### 6.3 状态文件

继续维护：

```text
outputs/reports/heartbeat.json
outputs/reports/run_lock.json
outputs/reports/active_run.json
```

规则：

- 长命令开始前 heartbeat active=true。
- 每个 run 开始写 active_run。
- 每个 run 成功/失败后释放 active_run。
- 队列全部完成后 heartbeat active=false，run_lock locked=false。

### 6.4 GPU 和进程安全

硬约束：

- 只用单 GPU。
- SGLang tensor parallel size 必须为 1。
- 不使用 sudo。
- 不 kill 其他用户进程。
- 若要停止 SGLang，只能停止当前 run 目录记录的 PID，并且先用 `ps` 确认 command line 指向本仓库和 Qwen3-32B 模型。

GPU 检查：

```bash
nvidia-smi
nvidia-smi pmon -c 1
```

如果 GPU 忙：

- 不抢卡。
- 不杀其他用户。
- 写日志后等待或停止。

### 6.5 Watchdog

建议超时：

```text
SGLang 启动：20 分钟
b8 innovation run：2 小时
b8-long/b12：4 小时
b16：6 小时
无日志增长：30 分钟
```

失败处理：

- context length：记录 failure，不重试原配置，必要时降级 observation tokens。
- OOM：保存 failure 后停止当前扩大方向。
- connection refused：检查 server health；只重启本仓库 server。
- metric stale：controller hold，不让窗口乱调。

### 6.6 推送策略

完成后提交：

```text
代码改动
innovation configs
innovation queue
CSV summary
figures
qwen_innovation_report.md
codex_execution_log.md
latest_status.md
```

不提交：

```text
outputs/runs/
大型 server stdout/stderr
models/
envs/
.cache/
.tmp/
```

推送前必须运行：

```bash
/data/3.8T-1/yue/envs/sglang/bin/python -m compileall -q src
PYTHONPATH=src MPLCONFIGDIR=/data/3.8T-1/yue/.cache/matplotlib /data/3.8T-1/yue/envs/sglang/bin/python -m concur_repro.analyze
git diff --check
git status --short --branch --untracked-files=all
```

## 7. 分阶段执行顺序

### I0：恢复和计划确认

- 读取 v2 report、latest_status、现有 CSV。
- 创建 `experiment_queue_innovation.yaml`。
- 写入中文执行日志。

### I1：实现两个 controller

- 实现 `concur_cache_aware_v1`。
- 实现 `phase_window_v1`。
- 更新 metadata 和 summary 字段。
- 做 `compileall` 和最小 mock/offline test。

### I2：生成 configs 和 queue

- 新增 12 个 innovation config。
- 队列先只放 b8 六项。
- b8 完成并分析通过后，再放 P6 六项。

### I3：运行 b8 innovation matrix

- 启动/复用本仓库 SGLang server。
- 运行 6 个 b8 run。
- 每个 run 后更新 queue、heartbeat、latest_status。

### I4：初步分析

- 生成 innovation b8 表。
- 如果两个创新点都明显失败，停止 P6，直接写报告。
- 如果至少一个有可解释 tradeoff，继续 P6。

### I5：运行 P6 seed0 压力验证

- b8-long ctxfit 两项。
- b12 两项。
- b16 两项。
- 遇到 OOM/context/server crash 按 failure 处理。

### I6：最终分析和报告

- 生成 CSV、图、报告。
- 明确和 v2 baseline 对比。
- 更新 `next_steps.md` 和 `latest_status.md`。

### I7：提交推送

- 检查 staged 文件不含 raw run。
- commit。
- push `origin/main`。

## 8. 我准备执行的最小目标

我准备先做一个低风险版本：

1. 先实现 `phase_window_v1`，因为它不依赖在线 metrics，最容易验证。
2. 再实现 `concur_cache_aware_v1`，复用 `concur_dynamic_v2` 的 exact metric tailer。
3. 先跑 b8 六项，不急着跑 P6。
4. 如果 b8 结果显示至少一个创新点有明确 tradeoff，再进入 b8-long/b12/b16。

这样可以把失败成本控制在较小范围内，同时仍然能产出两个可解释的创新点。
