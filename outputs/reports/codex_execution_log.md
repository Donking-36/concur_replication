# Codex 执行日志

## 2026-06-26 02:05 Asia/Shanghai

- 阶段：P0 恢复现场和长期状态审计。
- 已阅读用户指定的 `COMPLETED_WORK.md`、`progress.md`、`next_steps.md`、`decisions.md`、`experiment_queue.yaml`、`outputs/reports/latest_status.md`、`outputs/reports/qwen_single_gpu_report.md`、`outputs/tables/end_to_end_latency_table.csv`、`outputs/tables/sglang_scheduler_summary_by_run.csv`、`outputs/tables/sglang_request_summary_by_run.csv`。
- 当前结论：旧 b8 sweep 已完成；Qwen3-32B BF16 在单张 RTX PRO 6000 上通过 SGLang TP=1 跑通；旧 v1 workload 的 exact cached token ratio 很低；旧 `concur_dynamic` 只在 agent admission 附近写 controller event，不能证明周期反馈控制。
- 状态审计：仓库中缺少 `heartbeat.json`、`run_lock.json`、`active_run.json`；`experiment_queue.yaml` 仍是旧可选重复实验队列，需要升级为 v2 阶段队列。
- 运行中进程审计：当前 sandbox 可见范围内未发现本用户的 `sglang` 或 `concur_repro.run_experiment` 实验进程。
- 下一步：补建状态文件、实现队列/heartbeat 原子更新工具、实现 `prefix_stable_v2` workload、实现 `concur_dynamic_v2` 周期反馈控制。
- 2026-06-26T02:35:00+08:00 阶段=P1：已新增 `outputs/reports/current_results_audit.md`，明确旧 v1 结果、可信度缺口和 v2 验收口径。
- 2026-06-26T02:35:00+08:00 阶段=P1：已升级 `experiment_queue.yaml` 为 schema v2，加入 P2/P5/P6 队列项和单 GPU、TP=1、原子更新策略说明。
- 2026-06-26T02:35:00+08:00 阶段=P2/P4：已修改 `src/concur_repro/workload.py`、`controllers.py`、`run_experiment.py`、`metadata.py`、`sglang_logs.py`、`analyze.py`，新增 `prefix_stable_v2`、`concur_dynamic_v2`、request-to-agent/step 映射列和状态文件维护。
- 2026-06-26T02:35:00+08:00 阶段=P0/P5：已新增 `src/concur_repro/state.py`、`live_metrics.py`、`queue_runner.py`、`scripts/08_run_queue.sh`，支持 heartbeat、run lock、active run 和队列原子更新；已新增 b2 smoke、b8 seed0/1/2 和 b8-long/b12/b16 的 v2 配置。
- 2026-06-26T02:40:00+08:00 阶段=P2：准备启动新的单卡 SGLang TP=1 server，然后先跑 `prefix_stable_v2` b2 smoke，验证 exact cached token ratio 是否高于旧 v1。
- 2026-06-26T02:31:12+08:00 阶段=P2：新 server 启动失败，`sglang::scheduler` 在 GPU0 上 OOM；当前 `nvidia-smi` 显示 GPU0/1/2/3 均有 PID `3597212/3597209/3597074/3597473`，用户为 `zhy`，不可终止。
- 2026-06-26T02:31:12+08:00 阶段=P2：未检测到可用的本仓库健康 SGLang server，端口复用路径暂不可用；下一步转为等待 GPU 或恢复时复用已有服务后再跑 `prefix_stable_v2` b2 smoke。
- 2026-06-26T02:45:00+08:00 阶段=P2：已把 `latest_sglang_server_run_dir.txt` 恢复为上一次成功 server run，失败尝试单独记录到 `latest_sglang_server_attempt_run_dir.txt`，避免恢复逻辑误用失败 run。
- 2026-06-26T02:45:00+08:00 阶段=P2：离线验证完成：`py_compile` 通过，`concur_repro.analyze` 已重新生成表格，v2 配置可读取；P2 实机 smoke 保持 pending，等待 GPU 或健康单 GPU TP=1 server。
- 2026-06-26T12:54:33+08:00 阶段=P0/P2：用户提示可能已有空闲 GPU 后执行恢复审计；`heartbeat.json`、`run_lock.json`、`active_run.json` 均显示当前没有本仓库实验运行，队列仍停在 `p2_prefix_v2_b2_smoke`。
- 2026-06-26T12:54:33+08:00 阶段=P2：重新运行 `nvidia-smi`，GPU0/1/2/3 仍各有约 88906MiB 被 `sglang::scheduler` 占用，暂不能新启动 Qwen3-32B BF16 单卡 TP=1 server；下一步只读检查端口和进程，确认是否存在本仓库可复用健康服务。
- 2026-06-26T12:55:00+08:00 阶段=P0/P2：端口审计显示 `127.0.0.1:30000` 当前未监听，旧 `latest_sglang_server_run_dir.txt` 指向的是历史成功 server run；PID 已不存在，不能复用。
- 2026-06-26T12:55:00+08:00 阶段=P0/P2：提权只读 `ps` 确认当前占用四张 GPU 的 `sglang::scheduler` 进程用户为 `zhy`，本次不会终止其他用户进程。
- 2026-06-26T12:58:00+08:00 阶段=P0/P2：代码审计发现 `queue_runner.py` 在 GPU 空闲但没有健康 server 时不会自动启动 SGLang；准备修复为“先复用健康本仓库 server，否则等待 GPU 后启动单卡 TP=1 server，再运行队列项”。
- 2026-06-26T12:58:00+08:00 阶段=P0：代码审计发现实验结束时 `active_run.json` 的 `started_at` 会被重写为结束时间；准备修正为结束状态不再伪造开始时间。
- 2026-06-26T13:05:00+08:00 阶段=P0/P2：已修改 `src/concur_repro/queue_runner.py` 和 `scripts/08_run_queue.sh`，支持 `GPU_ID=auto` 选择第一张低显存 GPU、等待空闲后自动调用 `scripts/01_launch_sglang.sh` 启动单卡 TP=1 server，并把实验进程绑定到同一张 GPU。
- 2026-06-26T13:05:00+08:00 阶段=P0：已修改 `src/concur_repro/run_experiment.py`，实验结束时 `active_run.json` 不再把 `started_at` 重写为结束时间。
- 2026-06-26T13:05:00+08:00 阶段=P0：已运行 `python -m py_compile queue_runner.py run_experiment.py`、`python -m concur_repro.queue_runner --help`、`bash -n scripts/08_run_queue.sh`，均通过。
- 2026-06-26T13:06:00+08:00 阶段=P2：再次只读检查 GPU，GPU0/1/2/3 仍各约 88929MiB 已用、8322MiB 空闲；P2 smoke 仍不能启动。未运行短超时队列入口，避免把 `p2_prefix_v2_b2_smoke` 错误标记为 failed。
- 2026-06-29T21:05:27+08:00 阶段=P0/P2：恢复现场：当前时间 2026-06-29 21:04 Asia/Shanghai；已读取 Git 状态、GPU 状态、experiment_queue.yaml、progress.md、next_steps.md、decisions.md、latest_status.md、heartbeat/run_lock/active_run；GPU0/1/2/3 当前空闲，准备审计状态路径和队列执行器，然后按队列运行 prefix_stable_v2 b2 smoke。
- 2026-06-29T21:06:37+08:00 阶段=P0：准备修改：文件 /data/3.8T-1/yue/concur_qwen_repro/src/concur_repro/state.py；目的：将 heartbeat/run_lock/active_run 主路径调整为 outputs/reports，并保留仓库根目录旧副本兼容恢复；备份策略：使用 git diff 和精确补丁，不覆盖旧 run 目录。
- 2026-06-29T21:08:16+08:00 阶段=P0：修改完成：state.py 现在以 outputs/reports/heartbeat.json、run_lock.json、active_run.json 为主状态文件，并同步写仓库根目录旧副本；已通过 py_compile。
- 2026-06-29T21:08:32+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:08:41+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:08:42+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:08:51+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:08:52+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:01+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:02+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:11+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:12+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:21+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:22+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:31+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:32+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:42+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:43+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:52+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:09:53+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:10:02+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:10:03+08:00 阶段=GPU_WAIT：GPU 等待检查失败：CalledProcessError: Command '['nvidia-smi', '--query-gpu=index,memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits']' returned non-zero exit status 9.
- 2026-06-29T21:10:46+08:00 阶段=P2：队列中断：运行 p2_prefix_v2_b2_smoke 时 GPU 查询命令多次返回 exit 9；普通 nvidia-smi 随后显示四张 GPU 均被 sglang::scheduler 占用，且本仓库未创建 20260629 server run 目录。已手动中断等待，准备恢复队列项为 pending，避免错误标记 failed。
- 2026-06-29T21:11:55+08:00 阶段=P2：队列恢复：已将 p2_prefix_v2_b2_smoke 从 running 放回 pending 队首；本次中断没有生成 20260629 实验 run，后续等待 GPU 真正可用后重试。
- 2026-06-29T21:13:50+08:00 阶段=P0/P2：准备修改：文件 src/concur_repro/queue_runner.py 和 scripts/08_run_queue.sh；目的：GPU 等待逻辑同时检查 memory.used 与 utilization.gpu，并要求连续两次空闲，且在 nvidia-smi query 失败时记录 stderr；备份策略：精确补丁，不修改 run 目录。
- 2026-06-29T21:18:28+08:00 阶段=P0/P2：修改完成：state.py 已更新队列 updated_at 与 outputs/reports 状态镜像；queue_runner.py 和 scripts/08_run_queue.sh 已增加 memory/util 双阈值与连续两次空闲确认；已通过 py_compile、queue_runner --help、bash -n。
- 2026-06-29T21:19:25+08:00 阶段=P2：GPU 审计：宿主 ps 确认当前四张 GPU 的 sglang::scheduler PID 144531/144811/145307/145701 均属用户 zhy，不属于本仓库；遵守约束，不终止其他用户进程。P2 smoke 保持 pending，等待 GPU 释放。
- 2026-06-29T21:21:49+08:00 阶段=P0/P2：准备修改：文件 src/concur_repro/queue_runner.py；目的：recorded_server_is_healthy 不再因沙箱 /proc 看不到宿主 PID 就否定 HTTP 健康 server，避免恢复复用路径误判；备份策略：精确补丁。
- 2026-06-29T21:24:08+08:00 阶段=P0/P2：安全修正：保留 recorded_server_is_healthy 的 PID 可见 + HTTP 健康双条件，避免在共享机器上误复用其他用户监听同端口的服务。
- 2026-06-29T21:24:58+08:00 阶段=P0/P2：准备修改：progress.md、next_steps.md、decisions.md、outputs/reports/latest_status.md；目的：记录 2026-06-29 恢复审计、状态路径修复、GPU 等待逻辑修复、P2 smoke 因其他用户 GPU 占用保持 pending；备份策略：精确补丁。
- 2026-06-29T21:26:36+08:00 阶段=P0/P2：修改完成：已更新 progress.md、next_steps.md、decisions.md、latest_status.md，记录 2026-06-29 恢复审计、离线验证和 GPU 阻塞状态。
- 2026-06-29T21:27:20+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:29+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:30+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:39+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:40+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:49+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:50+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:27:59+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:28:00+08:00 阶段=GPU_WAIT：GPU 等待检查失败：nvidia-smi exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:28:30+08:00 阶段=P2：队列恢复：第二次等待因 nvidia-smi --query-gpu 间歇性 exit 9 被手动中断；已将 p2 smoke 恢复为 pending，准备增加普通 nvidia-smi fallback。
- 2026-06-29T21:28:44+08:00 阶段=P0/P2：准备修改：src/concur_repro/queue_runner.py；目的：当 nvidia-smi --query-gpu 间歇性 exit 9 时，退回解析普通 nvidia-smi 表格以判断 memory/util，避免空闲 GPU 被错误等待。
- 2026-06-29T21:29:41+08:00 阶段=GPU_WAIT：结构化 GPU 查询失败，尝试普通 nvidia-smi fallback：exit=9 detail=NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.
- 2026-06-29T21:35:00+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260629-213236-sglang_server-Qwen3-32B-gpu0，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 prefix_stable_v2 b2 smoke。
- 2026-06-29T21:35:36+08:00 阶段=P2 run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2：开始实验 run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/smoke_qwen3_32b_bf16_prefix_v2_b2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-06-29T21:35:45+08:00 阶段=P2 run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2：实验结束 run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2 latency_s=8.333290606002265 status=success
- 2026-06-29T21:37:53+08:00 阶段=P2 run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2：P2 smoke 验收完成：run=20260629-213536-no-control-Qwen3-32B-BF16-prefix-v2-b2，latency=8.333s，exact cached_token_ratio=0.5066，后续 step 命中率约 0.51/0.67；已将队列项标记 done。
- 2026-06-29T21:38:48+08:00 阶段=P5 run=20260629-213848-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed0-b8：开始实验 run=20260629-213848-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/concur_dynamic_v2_b8_seed0_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2
- 2026-06-29T21:42:33+08:00 阶段=P5 run=20260629-213848-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed0-b8：实验结束 run=20260629-213848-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed0-b8 latency_s=225.03608802399685 status=success
- 2026-06-29T21:44:22+08:00 阶段=P5 run=20260629-213848-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed0-b8：P5 dynamic v2 b8 seed0 完成：latency=225.036s，controller_events=122，其中 exact feedback=114，window_min=1，window_max=8，max_token_usage=0.97，max_queue_req=218；已标记队列 done。
- 2026-06-29T21:47:41+08:00 阶段=SGLANG_STOP：准备停止 SGLang server：PID=175007，已通过宿主 ps 确认为本仓库启动的 Qwen3-32B TP=1 server；原因：dynamic_v2 b8 已结束但 server 仍有大量残留请求，需重启干净 server 避免污染 no_control 对照。
- 2026-06-29T21:49:55+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=175007 已退出，GPU0 显存释放；停止前 server 清空 remaining requests 到 0。下一步重启干净 server 后运行 no_control b8 seed0。
- 2026-06-29T22:00:00+08:00 阶段=P5：干净 SGLang server 已在宿主侧确认健康：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260629-215010-sglang_server-Qwen3-32B-gpu0，PID=193971，GPU0，TP=1；开始运行队列项 p5_no_control_b8_seed0_prefix_v2。
- 2026-06-29T22:01:19+08:00 阶段=P5：第一次直接启动 p5_no_control_b8_seed0_prefix_v2 未进入实验代码：宿主命令缺少 PYTHONPATH，报 ModuleNotFoundError；未创建 run 目录，队列项保持 running，立即用完整环境重跑。
- 2026-06-29T22:01:52+08:00 阶段=P5 run=20260629-220152-no-control-Qwen3-32B-prefix-v2-seed0-b8：开始实验 run=20260629-220152-no-control-Qwen3-32B-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/baseline_no_control_b8_seed0_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-06-29T22:07:21+08:00 阶段=P5 run=20260629-220152-no-control-Qwen3-32B-prefix-v2-seed0-b8：实验结束 run=20260629-220152-no-control-Qwen3-32B-prefix-v2-seed0-b8 latency_s=328.3031702530061 status=success
- 2026-06-29T22:13:28+08:00 阶段=P5 run=20260629-220152-no-control-Qwen3-32B-prefix-v2-seed0-b8：P5 no_control b8 seed0 完成：latency=328.303s，serving_metrics=64/64，scheduler max_token_usage=0.97，max_queue_req=336，max_pending_token=159879；SGLang request metrics 文件包含额外服务端记录，后续对比以 serving_metrics 请求数和 scheduler 压力为主，mapped harness cached ratio≈0.0208。已标记队列 done。
- 2026-06-29T22:14:09+08:00 阶段=SGLANG_STOP：准备停止 SGLang server：PID=193971，已通过宿主 ps 确认为本仓库启动的 Qwen3-32B TP=1 server；原因：no_control b8 seed0 完成后重启干净 server，避免 request_cap_4 对照受到 KV/radix cache 污染。
- 2026-06-29T22:15:02+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=193971 已退出，GPU0 显存释放；准备在 GPU0 重启干净 SGLang server 运行 p5_request_cap_4_b8_seed0_prefix_v2。
- 2026-06-29T22:17:53+08:00 阶段=P5：干净 SGLang server 已确认健康：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260629-221518-sglang_server-Qwen3-32B-gpu0，PID=236362，GPU0，TP=1；开始运行队列项 p5_request_cap_4_b8_seed0_prefix_v2。
- 2026-06-29T22:18:25+08:00 阶段=P5 run=20260629-221825-request-cap-4-Qwen3-32B-prefix-v2-seed0-b8：开始实验 run=20260629-221825-request-cap-4-Qwen3-32B-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/request_cap_4_b8_seed0_prefix_v2.yaml strategy=request_cap workload=prefix_stable_v2
- 2026-06-29T22:21:33+08:00 阶段=P5 run=20260629-221825-request-cap-4-Qwen3-32B-prefix-v2-seed0-b8：实验结束 run=20260629-221825-request-cap-4-Qwen3-32B-prefix-v2-seed0-b8 latency_s=186.7921785810031 status=success
- 2026-06-29T22:23:08+08:00 阶段=P5 run=20260629-221825-request-cap-4-Qwen3-32B-prefix-v2-seed0-b8：P5 request_cap_4 b8 seed0 完成：latency=186.792s，serving_metrics=64/64，exact request cached_token_ratio=0.1366，scheduler max_token_usage=0.92，max_queue_req=3，max_pending_token=65056；已标记队列 done。
- 2026-06-29T22:24:15+08:00 阶段=SGLANG_STOP：准备停止 SGLang server：PID=236362，已通过宿主 ps 确认为本仓库启动的 Qwen3-32B TP=1 server；原因：request_cap_4 完成后重启干净 server，避免 fixed_window_4 对照受到 KV/radix cache 污染。
- 2026-06-29T22:25:13+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=236362 已退出，GPU0 显存释放；准备在 GPU0 重启干净 SGLang server 运行 p5_fixed_window_4_b8_seed0_prefix_v2。
- 2026-06-29T22:28:05+08:00 阶段=P5：干净 SGLang server 已确认健康：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260629-222525-sglang_server-Qwen3-32B-gpu0，PID=251194，GPU0，TP=1；开始运行队列项 p5_fixed_window_4_b8_seed0_prefix_v2。
- 2026-06-29T22:28:35+08:00 阶段=P5 run=20260629-222835-fixed-window-4-Qwen3-32B-prefix-v2-seed0-b8：开始实验 run=20260629-222835-fixed-window-4-Qwen3-32B-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_4_b8_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-06-29T22:30:31+08:00 阶段=P5 run=20260629-222835-fixed-window-4-Qwen3-32B-prefix-v2-seed0-b8：实验结束 run=20260629-222835-fixed-window-4-Qwen3-32B-prefix-v2-seed0-b8 latency_s=115.47178020900174 status=success
- 2026-06-29T22:31:38+08:00 阶段=P5 run=20260629-222835-fixed-window-4-Qwen3-32B-prefix-v2-seed0-b8：P5 fixed_window_4 b8 seed0 完成：latency=115.472s，serving_metrics=64/64，exact request cached_token_ratio=0.6795，scheduler max_token_usage=0.96，max_queue_req=1，max_pending_token=20368；已标记队列 done。
- 2026-06-29T22:32:22+08:00 阶段=SGLANG_STOP：准备停止 SGLang server：PID=251194，已通过宿主 ps 确认为本仓库启动的 Qwen3-32B TP=1 server；原因：fixed_window_4 完成后重启干净 server，避免 fixed_window_8 对照受到 KV/radix cache 污染。
- 2026-07-03T12:58:18+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T12:58:18+08:00 阶段=P5：队列开始运行：p5_fixed_window_8_b8_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed0_prefix_v2.yaml
- 2026-07-03T12:58:18+08:00 阶段=P5 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8：开始实验 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T13:01:04+08:00 阶段=P5 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8：实验结束 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8 latency_s=165.42414223001106 status=success
- 2026-07-03T13:01:06+08:00 阶段=P5 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8：队列项完成：p5_fixed_window_8_b8_seed0_prefix_v2 run_id=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8
- 2026-07-03T13:03:25+08:00 阶段=P5 run=20260703-125818-fixed-window-8-Qwen3-32B-prefix-v2-seed0-b8：P5 fixed_window_8 b8 seed0 完成：latency=165.424s，serving_metrics=64/64，exact request cached_token_ratio=0.1895，scheduler max_token_usage=0.97，max_queue_req=6，max_pending_token=115568；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:03:25+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=429170 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-125444-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:05:58+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:05:58+08:00 阶段=P5：队列开始运行：p5_no_control_b8_seed1_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/baseline_no_control_b8_seed1_prefix_v2.yaml
- 2026-07-03T13:05:58+08:00 阶段=P5 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8：开始实验 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/baseline_no_control_b8_seed1_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T13:08:41+08:00 阶段=P5 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8：实验结束 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8 latency_s=162.9477029700065 status=success
- 2026-07-03T13:08:46+08:00 阶段=P5 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8：队列项完成：p5_no_control_b8_seed1_prefix_v2 run_id=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8
- 2026-07-03T13:09:38+08:00 阶段=P5 run=20260703-130558-no-control-Qwen3-32B-prefix-v2-seed1-b8：P5 no_control b8 seed1 完成：latency=162.948s，serving_metrics=64/64，exact request cached_token_ratio=0.2075，scheduler max_token_usage=0.97，max_queue_req=6，max_pending_token=135500；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:12:24+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=459311 已退出，scheduler PID=459807 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-130347-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:14:46+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-131243-sglang_server-Qwen3-32B-gpu0，PID=490232，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_request_cap_4_b8_seed1_prefix_v2。
- 2026-07-03T13:15:22+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:15:22+08:00 阶段=P5：队列开始运行：p5_request_cap_4_b8_seed1_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/request_cap_4_b8_seed1_prefix_v2.yaml
- 2026-07-03T13:15:22+08:00 阶段=P5 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8：开始实验 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/request_cap_4_b8_seed1_prefix_v2.yaml strategy=request_cap workload=prefix_stable_v2
- 2026-07-03T13:18:24+08:00 阶段=P5 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8：实验结束 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8 latency_s=181.56718123197788 status=success
- 2026-07-03T13:18:28+08:00 阶段=P5 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8：队列项完成：p5_request_cap_4_b8_seed1_prefix_v2 run_id=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8
- 2026-07-03T13:19:01+08:00 阶段=P5 run=20260703-131522-request-cap-4-Qwen3-32B-prefix-v2-seed1-b8：P5 request_cap_4 b8 seed1 完成：latency=181.567s，serving_metrics=64/64，exact request cached_token_ratio=0.1716，scheduler max_token_usage=0.92，max_queue_req=2，max_pending_token=56928；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:20:42+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=490232 已退出，scheduler PID=490739 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-131243-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:24:34+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-132236-sglang_server-Qwen3-32B-gpu0，PID=523871，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_fixed_window_4_b8_seed1_prefix_v2。
- 2026-07-03T13:28:00+08:00 阶段=P5 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8：P5 fixed_window_4 b8 seed1 完成：latency=120.300s，serving_metrics=64/64，exact request cached_token_ratio=0.6575，scheduler max_token_usage=0.97，max_queue_req=2，max_pending_token=44177；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:29:40+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=523871 已退出，scheduler PID=524388 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-132236-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:25:10+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:25:10+08:00 阶段=P5：队列开始运行：p5_fixed_window_4_b8_seed1_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_4_b8_seed1_prefix_v2.yaml
- 2026-07-03T13:25:10+08:00 阶段=P5 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8：开始实验 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_4_b8_seed1_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T13:27:11+08:00 阶段=P5 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8：实验结束 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8 latency_s=120.2997464860091 status=success
- 2026-07-03T13:27:16+08:00 阶段=P5 run=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8：队列项完成：p5_fixed_window_4_b8_seed1_prefix_v2 run_id=20260703-132510-fixed-window-4-Qwen3-32B-prefix-v2-seed1-b8
- 2026-07-03T13:32:39+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-133040-sglang_server-Qwen3-32B-gpu0，PID=551440，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_fixed_window_8_b8_seed1_prefix_v2。
- 2026-07-03T13:34:28+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:34:28+08:00 阶段=P5：队列开始运行：p5_fixed_window_8_b8_seed1_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed1_prefix_v2.yaml
- 2026-07-03T13:34:28+08:00 阶段=P5 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8：开始实验 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed1_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T13:37:12+08:00 阶段=P5 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8：实验结束 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8 latency_s=162.84753050800646 status=success
- 2026-07-03T13:37:16+08:00 阶段=P5 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8：队列项完成：p5_fixed_window_8_b8_seed1_prefix_v2 run_id=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8
- 2026-07-03T13:37:58+08:00 阶段=P5 run=20260703-133428-fixed-window-8-Qwen3-32B-prefix-v2-seed1-b8：P5 fixed_window_8 b8 seed1 完成：latency=162.848s，serving_metrics=64/64，exact request cached_token_ratio=0.2075，scheduler max_token_usage=0.97，max_queue_req=6，max_pending_token=135500；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:39:07+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=551440 已退出，scheduler PID=551935 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-133040-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:42:23+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-134024-sglang_server-Qwen3-32B-gpu0，PID=586227，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_concur_dynamic_v2_b8_seed1_prefix_v2。
- 2026-07-03T13:42:55+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:42:55+08:00 阶段=P5：队列开始运行：p5_concur_dynamic_v2_b8_seed1_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/concur_dynamic_v2_b8_seed1_prefix_v2.yaml
- 2026-07-03T13:42:55+08:00 阶段=P5 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8：开始实验 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/concur_dynamic_v2_b8_seed1_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2
- 2026-07-03T13:45:50+08:00 阶段=P5 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8：实验结束 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8 latency_s=173.86986810300732 status=success
- 2026-07-03T13:45:55+08:00 阶段=P5 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8：队列项完成：p5_concur_dynamic_v2_b8_seed1_prefix_v2 run_id=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8
- 2026-07-03T13:46:32+08:00 阶段=P5 run=20260703-134255-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed1-b8：P5 concur_dynamic_v2 b8 seed1 完成：latency=173.870s，serving_metrics=64/64，exact request cached_token_ratio=0.1497，scheduler max_token_usage=0.97，max_queue_req=5，max_pending_token=115118；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:47:31+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=586227 已退出，scheduler PID=586705 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-134024-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:50:17+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-134820-sglang_server-Qwen3-32B-gpu0，PID=613684，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_no_control_b8_seed2_prefix_v2。
- 2026-07-03T13:50:58+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:50:58+08:00 阶段=P5：队列开始运行：p5_no_control_b8_seed2_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/baseline_no_control_b8_seed2_prefix_v2.yaml
- 2026-07-03T13:50:58+08:00 阶段=P5 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8：开始实验 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/baseline_no_control_b8_seed2_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T13:53:44+08:00 阶段=P5 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8：实验结束 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8 latency_s=165.8982959339628 status=success
- 2026-07-03T13:53:46+08:00 阶段=P5 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8：队列项完成：p5_no_control_b8_seed2_prefix_v2 run_id=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8
- 2026-07-03T13:54:25+08:00 阶段=P5 run=20260703-135058-no-control-Qwen3-32B-prefix-v2-seed2-b8：P5 no_control b8 seed2 完成：latency=165.898s，serving_metrics=64/64，exact request cached_token_ratio=0.1854，scheduler max_token_usage=0.93，max_queue_req=6，max_pending_token=126811；已刷新分析表/图并更新队列 done。
- 2026-07-03T13:55:23+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=613684 已退出，scheduler PID=614185 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-134820-sglang_server-Qwen3-32B-gpu0。
- 2026-07-03T13:58:22+08:00 阶段=SGLANG_START：SGLang server 启动成功：run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-135606-sglang_server-Qwen3-32B-gpu0，PID=641668，GPU0，TP=1，base_url=http://127.0.0.1:30000；下一步运行 p5_request_cap_4_b8_seed2_prefix_v2。
- 2026-07-03T13:58:57+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T13:58:57+08:00 阶段=P5：队列开始运行：p5_request_cap_4_b8_seed2_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/request_cap_4_b8_seed2_prefix_v2.yaml
- 2026-07-03T13:58:57+08:00 阶段=P5 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8：开始实验 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/request_cap_4_b8_seed2_prefix_v2.yaml strategy=request_cap workload=prefix_stable_v2
- 2026-07-03T14:02:00+08:00 阶段=P5 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8：实验结束 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8 latency_s=182.12014083797112 status=success
- 2026-07-03T14:02:03+08:00 阶段=P5 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8：队列项完成：p5_request_cap_4_b8_seed2_prefix_v2 run_id=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8
- 2026-07-03T14:04:29+08:00 阶段=P5 run=20260703-135857-request-cap-4-Qwen3-32B-prefix-v2-seed2-b8：P5 request_cap_4 b8 seed2 完成：latency=182.120s，serving_metrics=64/64，exact request cached_token_ratio=0.1720，scheduler max_token_usage=0.92，max_queue_req=2，max_pending_token=56914；已刷新分析表/图并更新队列 done。
- 2026-07-03T14:05:57+08:00 阶段=SGLANG_STOP：SGLang server 停止完成：PID=641668 已退出，scheduler PID=642148 已退出，GPU0 显存释放；server_run_dir=/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-135606-sglang_server-Qwen3-32B-gpu0。

## 2026-07-03 21:36:17 Asia/Shanghai - 恢复现场审计

- 当前动作：根据用户要求读取《CONCUR Qwen 单卡复现服务器端下一步计划书》，审计当前仓库状态、实验队列、长期状态文件和 GPU 遗留进程。
- 已读取文件：/data/3.8T-1/yue/CONCUR - Qwen单卡复现服务器端下一步计划书.md、progress.md、experiment_queue.yaml、outputs/reports/latest_status.md、outputs/reports/codex_execution_log.md。
- 初步发现：仓库位于 /data/3.8T-1/yue/concur_qwen_repro；P2 prefix_stable_v2 smoke 已完成，P5 b8 重复实验仍有 seed2 的 fixed_window_4、fixed_window_8、concur_dynamic_v2 等队列项 pending，P6 高压力扩展也仍 pending。
- 安全检查：沙箱内 nvidia-smi 无法访问 NVIDIA driver，/dev/nvidia* 不可见；下一步需要使用宿主侧 GPU/进程查询，只检查并处理明确属于当前用户且命令匹配本仓库 SGLang 的遗留进程，禁止影响其他用户进程。
- 结果：恢复审计进行中，尚未判定实验要求已完成，暂不 commit/push。

## 2026-07-03 21:37:03 Asia/Shanghai - GPU 遗留进程检查

- 当前动作：在宿主侧执行 nvidia-smi 与 nvidia-smi pmon -c 1，检查是否存在上次会话遗留的 GPU 进程。
- 检查结果：GPU0 存在 PID 680122，进程名 sglang::scheduler，占用约 84168 MiB；GPU3 存在 PID 1320119，进程名为保留 GPU 的进程，用户从进程列表看为 howarli，不属于本仓库。
- 安全判断：GPU3 进程明确不是本仓库进程，不处理；GPU0 PID 680122 需要继续用 ps 精确确认用户、父进程和 command line。
- 下一步：只在确认 PID 680122 属于当前用户 yue、且命令匹配本仓库 Qwen3-32B SGLang server 后停止该遗留服务。

## 2026-07-03 21:38:00 Asia/Shanghai - 准备停止遗留 SGLang

- 当前动作：准备停止本仓库遗留的 SGLang server。
- 涉及 run 目录：/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-140646-sglang_server-Qwen3-32B-gpu0。
- PID 文件检查：sglang_server.pid 记录 PID 679547；宿主 ps 显示其子进程 PID 680122 为 sglang::scheduler，占用 GPU0。
- 安全检查：进程用户为 yue；command line 为 /data/3.8T-1/yue/envs/sglang/bin/python -m sglang.launch_server，模型路径和日志路径均指向本仓库与 /data/3.8T-1/yue/models/Qwen3-32B；确认不是其他用户进程。
- 下一步：向 PID 679547 发送 TERM，随后复查 ps 和 nvidia-smi。

## 2026-07-03 21:38:19 Asia/Shanghai - 遗留 SGLang 停止完成

- 当前动作：复查刚才停止的本仓库 SGLang server。
- 结果：PID 679547、680121、680122、680123 均已退出；GPU0 显存从约 84191 MiB 降至 14 MiB。
- 安全结果：未处理 GPU3 上 howarli 的保留进程，未影响其他用户进程。
- 下一步：继续审计队列、状态文件、报告和 git 变更，判断是否达到计划书的实验完成与可推送条件。

## 2026-07-03 21:39:22 Asia/Shanghai - 准备修改状态文件

- 当前动作：准备更新恢复审计状态，修正过期的 latest_status，并刷新 heartbeat/run_lock/active_run 的空闲状态说明。
- 涉及文件：outputs/reports/latest_status.md、outputs/reports/heartbeat.json、outputs/reports/run_lock.json、outputs/reports/active_run.json、heartbeat.json、run_lock.json、active_run.json。
- 修改目的：记录 P2 已完成、P5/P6/P7/P8 尚未完成、GPU0 遗留 SGLang 已释放，避免误判为已完成并推送。
- 是否备份：不单独备份；本次为小型文本状态更新，git diff 可追踪。

## 2026-07-03 21:39:22 Asia/Shanghai - 状态文件修改完成

- 实际改动：更新 outputs/reports/latest_status.md，记录 P2 smoke 已完成、P5/P6/P7/P8 仍未完成、GPU0 遗留 SGLang 已释放、当前不满足推送条件。
- 实际改动：刷新 outputs/reports/heartbeat.json、outputs/reports/run_lock.json、outputs/reports/active_run.json 及仓库根目录兼容副本，保持 active/locked 均为 false，并记录恢复审计完成。
- 结果：成功。
- 下一步：复查 GPU 和 git 状态；若仍未满足实验要求，则不执行 commit/push。

## 2026-07-03 21:40:00 Asia/Shanghai - 恢复审计结论

- GPU 复查：nvidia-smi pmon 显示 GPU0/1/2 仅有 Xorg，GPU3 仍有 howarli 的保留进程；本仓库遗留 SGLang 已释放。
- 队列结论：experiment_queue.yaml 仍有 P5 seed2 的 fixed_window_4、fixed_window_8、concur_dynamic_v2 pending，且 P6 高压力扩展仍 pending。
- 交付物结论：尚未发现计划书要求的 v2_b8_repeated_trials.csv、v2_b8_repeated_trials_summary.csv、P7 v2_* 正式图表和 qwen_single_gpu_report_v2.md。
- Git 结论：main 跟踪 origin/main，但工作区有 tracked modifications 和大量 untracked configs/run artifacts。
- 决策：实验要求未完成，不能按“已完成实验要求”执行 commit/push；本次只完成恢复审计、状态修正和安全 GPU 清理。

## 2026-07-03 22:00:00 Asia/Shanghai - 准备运行 P5 seed2 队列

- 当前动作：根据用户要求继续计划书实验，先运行剩余 P5 b8 seed2 队列项，再决定是否进入 P6。
- 目标队列项：p5_fixed_window_4_b8_seed2_prefix_v2、p5_fixed_window_8_b8_seed2_prefix_v2、p5_concur_dynamic_v2_b8_seed2_prefix_v2。
- 命令摘要：MAX_ITEMS=3 GPU_ID=0 GPU_POLL_S=30 GPU_WAIT_TIMEOUT_S=21600 WATCHDOG_TIMEOUT_S=7200 bash scripts/08_run_queue.sh。
- 预计输出：新的 outputs/runs/<timestamp>-*-Qwen3-32B-prefix-v2-seed2-b8/ run 目录、更新 experiment_queue.yaml、heartbeat/run_lock/active_run、分析表和中文执行日志。

## 2026-07-03 23:46:00 Asia/Shanghai - P6 完成后 GPU 清理

- 当前动作：恢复会话后检查正在运行的队列会话、experiment_queue.yaml、heartbeat 和 GPU 进程。
- 队列结果：pending 为空，running 为 null；最后一个 P6 b16 `concur_dynamic_v2` run 已生成 summary.json，latency=341.366s，status=success。
- GPU 检查：GPU0 上仍有本仓库本次实验启动的 SGLang server，父进程 PID 1327450，scheduler PID 1327637；命令行和日志路径均指向 `/data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-215102-sglang_server-Qwen3-32B-gpu0`。
- 安全判断：GPU3 上 PID 1320119 是其他用户保留进程，未处理；只停止 GPU0 上属主为 yue 且命令匹配本仓库的 SGLang 进程组。
- 结果：对 PID 1327450/1327636/1327637/1327638 发送 TERM 后，本仓库 SGLang 已退出；复查 `nvidia-smi pmon -c 1` 显示 GPU0 只剩 Xorg，GPU3 其他用户进程仍在。
- 下一步：进入 P7/P8 离线统计、正式图表和 v2 报告生成，不再需要占用 GPU。

## 2026-07-03 23:48:00 Asia/Shanghai - 准备修改分析与报告生成

- 当前动作：准备修改 `src/concur_repro/analyze.py`，补齐计划书要求的 v2 b8 重复实验表、P6 压力表、matplotlib 正式图和 `qwen_single_gpu_report_v2.md`。
- 涉及文件：`src/concur_repro/analyze.py`；输出文件将写入 `outputs/tables/`、`outputs/figures/` 和 `outputs/reports/`。
- 修改目的：让 v2 交付物可由分析脚本重建，表格直接从 run summary、exact SGLang request/scheduler CSV 和 controller_events 生成，避免手工统计。
- 是否备份：不创建额外备份，使用 git diff 和精确补丁追踪。

## 2026-07-03 23:56:46 Asia/Shanghai - P7/P8 分析与报告完成

- 当前动作：完成 `src/concur_repro/analyze.py` 修改并运行完整离线分析。
- 实际改动：新增 v2 结果聚合逻辑，生成 `v2_b8_repeated_trials.csv`、`v2_b8_repeated_trials_summary.csv`、`v2_pressure_runs.csv`、`v2_pressure_runs_summary.csv`。
- 实际改动：新增 matplotlib 图表输出，生成 `v2_latency_mean_std.png`、`v2_scheduler_token_usage_by_controller.png`、`v2_queue_depth_by_controller.png`、`v2_cached_token_ratio_by_controller.png`、`v2_dynamic_window_timeseries.png`、`v2_fixed_vs_dynamic_latency.png`。
- 实际改动：新增 `outputs/reports/v2_b8_repeated_trials.md` 和 `outputs/reports/qwen_single_gpu_report_v2.md`。
- 验证命令：`/data/3.8T-1/yue/envs/sglang/bin/python -m py_compile src/concur_repro/analyze.py` 通过。
- 验证命令：`PYTHONPATH=src MPLCONFIGDIR=/data/3.8T-1/yue/.cache/matplotlib /data/3.8T-1/yue/envs/sglang/bin/python -m concur_repro.analyze` 成功，已重建表格、图表和报告。
- 验证结果：b8 repeated CSV 共 15 条成功记录，覆盖 5 个 controller x 3 seeds；P6 pressure CSV 覆盖 b8-long ctxfit、b12、b16，并记录原始 b8-long context-length failed run。
- 关键结果：old v1 b8 exact cached-token ratio mean 约 0.0019；prefix_stable_v2 b8 mean 约 0.2731。dynamic_v2 controller_events 为周期 exact 反馈事件，b16 dynamic_v2 latency=341.366s，在已测 b16 controller 中最快。
- 局限说明：fixed_window_4 仍是 b8/b12 latency 最优；dynamic_v2 未稳定跑赢所有固定窗口，报告中已如实说明。

## 2026-07-03 23:57:00 Asia/Shanghai - 准备最终提交推送

- 当前动作：更新阶段性文档和长期状态文件，准备进入最终 git 审查。
- 实际改动：更新 `progress.md`、`next_steps.md`、`decisions.md` 和 `outputs/reports/latest_status.md`，记录 P5/P6/P7/P8 完成、GPU 清理、安全边界和后续建议。
- 实际改动：刷新 `outputs/reports/heartbeat.json`、`run_lock.json`、`active_run.json` 及仓库根目录兼容副本，状态为 inactive/unlocked，phase=`P9_FINAL_REVIEW`。
- 下一步：执行 `git status --short`、筛选相关文件、commit，并按用户要求推送远端。

## 2026-07-04 00:00:00 Asia/Shanghai - 最终 git 检查

- 当前动作：检查 staged 文件范围并修正提交前问题。
- 结果：`.gitignore` 已新增 `outputs/runs/`、queue failure logs 和 transient SGLang launch logs 忽略规则；staged 清单不包含 raw run 目录或大型 server stdout/stderr。
- 修正：将 `analyze.py` 和 `sglang_logs.py` 的 CSV writer 统一设置为 `lineterminator="\n"`，避免 Python csv 默认 CRLF 被 `git diff --check` 识别为 trailing whitespace。
- 验证命令：`/data/3.8T-1/yue/envs/sglang/bin/python -m compileall -q src` 通过。
- 验证命令：`PYTHONPATH=src MPLCONFIGDIR=/data/3.8T-1/yue/.cache/matplotlib /data/3.8T-1/yue/envs/sglang/bin/python -m concur_repro.analyze` 通过。
- 验证命令：`git diff --cached --check` 通过。
- 下一步：创建 commit 并推送 `origin/main`。
- 安全检查：只使用 GPU0；不触碰 GPU3 上 howarli 的保留进程；SGLang TP=1；输出路径均在 /data/3.8T-1/yue/concur_qwen_repro 下。
- 2026-07-03T21:50:33+08:00 阶段=GPU_WAIT：GPU 空闲候选确认中：候选 GPU0，第 1/2 次；当前 gpu0 used=14MiB free=97237MiB util=0%; gpu1 used=14MiB free=97237MiB util=0%; gpu2 used=14MiB free=97237MiB util=0%; gpu3 used=572MiB free=96679MiB util=0%。
- 2026-07-03T21:50:33+08:00 阶段=GPU_WAIT：GPU 等待：目标=0，阈值 memory<=2000 MiB 且 util<=5%；当前 gpu0 used=14MiB free=97237MiB util=0%; gpu1 used=14MiB free=97237MiB util=0%; gpu2 used=14MiB free=97237MiB util=0%; gpu3 used=572MiB free=96679MiB util=0%。
- 2026-07-03T21:51:02+08:00 阶段=GPU_WAIT：GPU 等待完成：选择 GPU0，阈值 memory<=2000 MiB 且 util<=5%，连续确认=2；当前 gpu0 used=14MiB free=97237MiB util=0%; gpu1 used=14MiB free=97237MiB util=0%; gpu2 used=14MiB free=97237MiB util=0%; gpu3 used=572MiB free=96679MiB util=0%。
- 2026-07-03T21:51:02+08:00 阶段=SGLANG_START：启动 SGLang server：GPU0 port=30000 model_path=/data/3.8T-1/yue/models/Qwen3-32B，TP=1 由启动脚本强制设置。
- 2026-07-03T21:52:49+08:00 阶段=SGLANG_START：SGLang server 启动成功：log=/data/3.8T-1/yue/concur_qwen_repro/outputs/reports/sglang_launch_1783086769.log
- 2026-07-03T21:52:49+08:00 阶段=P5：队列开始运行：p5_fixed_window_4_b8_seed2_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_4_b8_seed2_prefix_v2.yaml
- 2026-07-03T21:52:49+08:00 阶段=P5 run=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8：开始实验 run=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_4_b8_seed2_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T21:54:46+08:00 阶段=P5 run=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8：实验结束 run=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8 latency_s=116.08204838697566 status=success
- 2026-07-03T21:54:49+08:00 阶段=P5 run=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8：队列项完成：p5_fixed_window_4_b8_seed2_prefix_v2 run_id=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8
- 2026-07-03T21:54:49+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T21:54:49+08:00 阶段=P5：队列开始运行：p5_fixed_window_8_b8_seed2_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed2_prefix_v2.yaml
- 2026-07-03T21:54:50+08:00 阶段=P5 run=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8：开始实验 run=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/fixed_window_8_b8_seed2_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T21:57:34+08:00 阶段=P5 run=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8：实验结束 run=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8 latency_s=163.46947550197365 status=success
- 2026-07-03T21:57:38+08:00 阶段=P5 run=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8：队列项完成：p5_fixed_window_8_b8_seed2_prefix_v2 run_id=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8
- 2026-07-03T21:57:38+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T21:57:38+08:00 阶段=P5：队列开始运行：p5_concur_dynamic_v2_b8_seed2_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/concur_dynamic_v2_b8_seed2_prefix_v2.yaml
- 2026-07-03T21:57:38+08:00 阶段=P5 run=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8：开始实验 run=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/concur_dynamic_v2_b8_seed2_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2

## 2026-07-03 22:01:00 Asia/Shanghai - P5 seed2 队列完成

- 当前动作：完成剩余 P5 b8 seed2 三个队列项。
- 结果：fixed_window_4 seed2 成功，run_id=20260703-215249-fixed-window-4-Qwen3-32B-prefix-v2-seed2-b8，latency_s=116.082。
- 结果：fixed_window_8 seed2 成功，run_id=20260703-215450-fixed-window-8-Qwen3-32B-prefix-v2-seed2-b8，latency_s=163.469。
- 结果：concur_dynamic_v2 seed2 成功，run_id=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8，latency_s=167.174，controller_events=93。
- 队列状态：P5 b8 repeated matrix 已补齐；experiment_queue.yaml 当前 pending 从 P6 b8-long 开始。
- 下一步：刷新分析表和图，审计 P5 exact metrics；通过后继续 P6。

## 2026-07-03 22:01:00 Asia/Shanghai - 准备刷新分析

- 当前动作：准备运行 python -m concur_repro.analyze，重建 latency、SGLang request/scheduler 表和当前图。
- 涉及文件：outputs/tables/*.csv、outputs/figures/*.png。
- 修改目的：把刚完成的 P5 seed2 run 纳入结构化结果，用于决定是否进入 P6。
- 是否备份：不单独备份；表格和图由原始 run 目录可重建，git diff 可追踪。

## 2026-07-03 22:01:30 Asia/Shanghai - 分析刷新完成

- 当前动作：python -m concur_repro.analyze 已完成。
- 结果：重写 outputs/tables/end_to_end_latency_table.csv，更新 SGLang request/scheduler CSV，并刷新当前 PNG 图。
- 下一步：汇总 P5 b8 repeated matrix 的 latency、scheduler pressure 和 cached-token ratio，确认是否进入 P6。

## 2026-07-03 22:03:00 Asia/Shanghai - P5 审计与准备补齐 P6 队列

- 当前动作：审计 P5 b8 repeated matrix，并准备补齐 P6 配置。
- P5 审计摘要：seed2 no_control/request_cap_4/fixed_window_4/fixed_window_8/concur_dynamic_v2 均 success；fixed_window_4 latency=116.082s；fixed_window_8 latency=163.469s；concur_dynamic_v2 latency=167.174s，controller_events=93。
- exact metrics 摘要：seed2 fixed_window_8 cached_token_ratio_total=0.2117，concur_dynamic_v2 cached_token_ratio_total=0.2065，未观察到明显跨 run cache ratio 异常。
- 准备修改：新增 P6 缺失配置文件，补齐 b8-long fixed_window_4/fixed_window_8，b12 request_cap_4/request_cap_8/fixed_window_4/fixed_window_8，b16 fixed_window_8；同步更新 experiment_queue.yaml 的 pending 顺序。
- 修改目的：让 P6 与计划书要求一致，而不是只跑 no_control/concur_dynamic_v2 配对。
- 是否备份：不单独备份；新增配置和队列修改由 git diff 追踪。
- 2026-07-03T22:00:26+08:00 阶段=P5 run=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8：实验结束 run=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8 latency_s=167.17403246602044 status=success
- 2026-07-03T22:00:31+08:00 阶段=P5 run=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8：队列项完成：p5_concur_dynamic_v2_b8_seed2_prefix_v2 run_id=20260703-215738-concur-dynamic-v2-Qwen3-32B-prefix-v2-seed2-b8

## 2026-07-03 22:04:00 Asia/Shanghai - P6 队列补齐完成

- 实际改动：新增 7 个 P6 配置文件：b8_long_fixed_window_4、b8_long_fixed_window_8、b12_request_cap_4、b12_request_cap_8、b12_fixed_window_4、b12_fixed_window_8、b16_fixed_window_8。
- 实际改动：experiment_queue.yaml pending 已补齐为 13 项，顺序为 b8-long 四项、b12 六项、b16 三项。
- 验证结果：所有 *prefix_v2.yaml 可被 yaml.safe_load 读取；experiment_queue.yaml 显示 pending=13、running=None、failed=1，首项为 p6_b8_long_no_control_seed0_prefix_v2。
- 下一步：运行 P6 b8-long 四项；若安全，再进入 b12。

## 2026-07-03 22:05:00 Asia/Shanghai - 准备运行 P6 b8-long

- 当前动作：准备运行 P6 b8-long 四个 controller：no_control、fixed_window_4、fixed_window_8、concur_dynamic_v2。
- 命令摘要：MAX_ITEMS=4 GPU_ID=0 GPU_POLL_S=30 GPU_WAIT_TIMEOUT_S=21600 WATCHDOG_TIMEOUT_S=14400 bash scripts/08_run_queue.sh。
- 预计输出：4 个 b8-long run 目录、更新 experiment_queue.yaml、heartbeat/run_lock/active_run、中文执行日志。
- 安全检查：仅使用 GPU0；当前 server 为本仓库记录的 /data/3.8T-1/yue/concur_qwen_repro/outputs/runs/20260703-215102-sglang_server-Qwen3-32B-gpu0；SGLang TP=1。
- 2026-07-03T22:05:01+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:05:01+08:00 阶段=P6：队列开始运行：p6_b8_long_no_control_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_no_control_seed0_prefix_v2.yaml
- 2026-07-03T22:05:02+08:00 阶段=P6 run=20260703-220502-no-control-Qwen3-32B-b8-long-prefix-v2-seed0-b8：开始实验 run=20260703-220502-no-control-Qwen3-32B-b8-long-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_no_control_seed0_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T22:12:49+08:00 阶段=P6 run=20260703-220502-no-control-Qwen3-32B-b8-long-prefix-v2-seed0-b8：实验失败 run=20260703-220502-no-control-Qwen3-32B-b8-long-prefix-v2-seed0-b8 type=RuntimeError message=SGLang HTTP 400: {"object":"error","message":"The input (43028 tokens) is longer than the model's context length (40960 tokens).","type":"BadRequestError","param":null,"code":400}
- 2026-07-03T22:12:55+08:00 阶段=P6 run=20260703-220502-no-control-Qwen3-32B-b8-long-prefix-v2-seed0-b8：队列项失败：p6_b8_long_no_control_seed0_prefix_v2 exit_code=1 log=/data/3.8T-1/yue/concur_qwen_repro/outputs/reports/queue_failure_1783087975.log

## 2026-07-03 22:14:00 Asia/Shanghai - P6 b8-long 降级

- 当前动作：处理 b8-long no_control 失败。
- 失败原因：SGLang HTTP 400，input=43028 tokens 超过模型 context length=40960 tokens；不是 OOM，不是 GPU 被抢占。
- 决策：不重试原始 b8-long 配置；新增 context-fit 降级版本，保持 num_steps=12，把 observation_tokens_per_step 从 384 降到 320。
- 准备修改：新增 b8_long_ctxfit 的 no_control、fixed_window_4、fixed_window_8、concur_dynamic_v2 四个配置，并更新 experiment_queue.yaml，跳过原始 b8-long 剩余配置。
- 是否备份：不单独备份；新增配置和队列修改由 git diff 追踪。

## 2026-07-03 22:15:00 Asia/Shanghai - P6 b8-long 降级修改完成

- 实际改动：新增 b8_long_ctxfit_no_control、fixed_window_4、fixed_window_8、concur_dynamic_v2 四个配置，num_steps=12，observation_tokens_per_step=320。
- 实际改动：experiment_queue.yaml pending 前四项替换为 b8_long_ctxfit 四项；原始 b8_long fixed_window_4/fixed_window_8/concur_dynamic_v2 放入 skipped，避免重复同类 context-length 失败。
- 验证结果：YAML 解析成功；pending=13，running=None，failed=2，skipped=3。
- 下一步：运行 b8_long_ctxfit 四项。

## 2026-07-03 22:15:00 Asia/Shanghai - 准备运行 P6 b8-long ctxfit

- 当前动作：准备运行降级后的 b8-long ctxfit 四项。
- 命令摘要：MAX_ITEMS=4 GPU_ID=0 GPU_POLL_S=30 GPU_WAIT_TIMEOUT_S=21600 WATCHDOG_TIMEOUT_S=14400 bash scripts/08_run_queue.sh。
- 安全检查：仅使用 GPU0；复用本仓库记录的 SGLang server；若仍触发 context length 或 OOM，将记录失败并继续降级/停止扩大方向。
- 2026-07-03T22:16:53+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:16:54+08:00 阶段=P6：队列开始运行：p6_b8_long_ctxfit_no_control_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_no_control_seed0_prefix_v2.yaml
- 2026-07-03T22:16:54+08:00 阶段=P6 run=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：开始实验 run=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_no_control_seed0_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T22:27:10+08:00 阶段=P6 run=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：实验结束 run=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 latency_s=616.1151651630062 status=success
- 2026-07-03T22:27:12+08:00 阶段=P6 run=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：队列项完成：p6_b8_long_ctxfit_no_control_seed0_prefix_v2 run_id=20260703-221654-no-control-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8
- 2026-07-03T22:27:12+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:27:12+08:00 阶段=P6：队列开始运行：p6_b8_long_ctxfit_fixed_window_4_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_fixed_window_4_seed0_prefix_v2.yaml
- 2026-07-03T22:27:12+08:00 阶段=P6 run=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：开始实验 run=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_fixed_window_4_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T22:36:09+08:00 阶段=P6 run=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：实验结束 run=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 latency_s=536.6152037620195 status=success
- 2026-07-03T22:36:12+08:00 阶段=P6 run=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：队列项完成：p6_b8_long_ctxfit_fixed_window_4_seed0_prefix_v2 run_id=20260703-222712-fixed-window-4-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8
- 2026-07-03T22:36:12+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:36:12+08:00 阶段=P6：队列开始运行：p6_b8_long_ctxfit_fixed_window_8_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_fixed_window_8_seed0_prefix_v2.yaml
- 2026-07-03T22:36:13+08:00 阶段=P6 run=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：开始实验 run=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_fixed_window_8_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T22:46:28+08:00 阶段=P6 run=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：实验结束 run=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 latency_s=614.365340696997 status=success
- 2026-07-03T22:46:31+08:00 阶段=P6 run=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：队列项完成：p6_b8_long_ctxfit_fixed_window_8_seed0_prefix_v2 run_id=20260703-223613-fixed-window-8-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8
- 2026-07-03T22:46:31+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:46:31+08:00 阶段=P6：队列开始运行：p6_b8_long_ctxfit_concur_dynamic_v2_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_concur_dynamic_v2_seed0_prefix_v2.yaml
- 2026-07-03T22:46:31+08:00 阶段=P6 run=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：开始实验 run=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b8_long_ctxfit_concur_dynamic_v2_seed0_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2
- 2026-07-03T22:56:47+08:00 阶段=P6 run=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：实验结束 run=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8 latency_s=614.9532074869494 status=success
- 2026-07-03T22:56:49+08:00 阶段=P6 run=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8：队列项完成：p6_b8_long_ctxfit_concur_dynamic_v2_seed0_prefix_v2 run_id=20260703-224631-concur-dynamic-v2-Qwen3-32B-b8-long-ctxfit-prefix-v2-seed0-b8

## 2026-07-03 23:00:00 Asia/Shanghai - 准备运行 P6 b12

- 当前动作：b8-long ctxfit 四项已完成，准备继续运行 b12 六项。
- b8-long ctxfit 摘要：no_control latency=616.115s；fixed_window_4 latency=536.615s；fixed_window_8 latency=614.365s；concur_dynamic_v2 latency=614.953s。
- b12 配置审计：num_agents=12，num_steps=8，observation_tokens_per_step=256；比原始 b8-long 短，预期不会触发 40960 context length 限制。
- GPU 安全检查：nvidia-smi pmon 显示 GPU0 为本仓库 SGLang scheduler；GPU3 有其他用户进程，未触碰。
- 命令摘要：MAX_ITEMS=6 GPU_ID=0 GPU_POLL_S=30 GPU_WAIT_TIMEOUT_S=21600 WATCHDOG_TIMEOUT_S=14400 bash scripts/08_run_queue.sh。
- 2026-07-03T22:58:08+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T22:58:08+08:00 阶段=P6：队列开始运行：p6_b12_no_control_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_no_control_seed0_prefix_v2.yaml
- 2026-07-03T22:58:08+08:00 阶段=P6 run=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_no_control_seed0_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T23:02:42+08:00 阶段=P6 run=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=273.7267286760034 status=success
- 2026-07-03T23:02:44+08:00 阶段=P6 run=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_no_control_seed0_prefix_v2 run_id=20260703-225808-no-control-Qwen3-32B-b12-prefix-v2-seed0-b12
- 2026-07-03T23:02:44+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:02:44+08:00 阶段=P6：队列开始运行：p6_b12_request_cap_4_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_request_cap_4_seed0_prefix_v2.yaml
- 2026-07-03T23:02:44+08:00 阶段=P6 run=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_request_cap_4_seed0_prefix_v2.yaml strategy=request_cap workload=prefix_stable_v2
- 2026-07-03T23:07:43+08:00 阶段=P6 run=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=297.78504300501663 status=success
- 2026-07-03T23:07:44+08:00 阶段=P6 run=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_request_cap_4_seed0_prefix_v2 run_id=20260703-230244-request-cap-4-Qwen3-32B-b12-prefix-v2-seed0-b12
- 2026-07-03T23:07:45+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:07:45+08:00 阶段=P6：队列开始运行：p6_b12_request_cap_8_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_request_cap_8_seed0_prefix_v2.yaml
- 2026-07-03T23:07:45+08:00 阶段=P6 run=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_request_cap_8_seed0_prefix_v2.yaml strategy=request_cap workload=prefix_stable_v2
- 2026-07-03T23:12:26+08:00 阶段=P6 run=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=280.767155790003 status=success
- 2026-07-03T23:12:27+08:00 阶段=P6 run=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_request_cap_8_seed0_prefix_v2 run_id=20260703-230745-request-cap-8-Qwen3-32B-b12-prefix-v2-seed0-b12
- 2026-07-03T23:12:27+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:12:27+08:00 阶段=P6：队列开始运行：p6_b12_fixed_window_4_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_fixed_window_4_seed0_prefix_v2.yaml
- 2026-07-03T23:12:27+08:00 阶段=P6 run=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_fixed_window_4_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T23:15:23+08:00 阶段=P6 run=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=174.93097077601124 status=success
- 2026-07-03T23:15:27+08:00 阶段=P6 run=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_fixed_window_4_seed0_prefix_v2 run_id=20260703-231227-fixed-window-4-Qwen3-32B-b12-prefix-v2-seed0-b12
- 2026-07-03T23:15:27+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:15:27+08:00 阶段=P6：队列开始运行：p6_b12_fixed_window_8_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_fixed_window_8_seed0_prefix_v2.yaml
- 2026-07-03T23:15:27+08:00 阶段=P6 run=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_fixed_window_8_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T23:19:12+08:00 阶段=P6 run=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=224.32833229197422 status=success
- 2026-07-03T23:19:15+08:00 阶段=P6 run=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_fixed_window_8_seed0_prefix_v2 run_id=20260703-231527-fixed-window-8-Qwen3-32B-b12-prefix-v2-seed0-b12
- 2026-07-03T23:19:16+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:19:16+08:00 阶段=P6：队列开始运行：p6_b12_concur_dynamic_v2_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_concur_dynamic_v2_seed0_prefix_v2.yaml
- 2026-07-03T23:19:16+08:00 阶段=P6 run=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12：开始实验 run=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b12_concur_dynamic_v2_seed0_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2
- 2026-07-03T23:22:49+08:00 阶段=P6 run=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12：实验结束 run=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12 latency_s=212.75632365996717 status=success
- 2026-07-03T23:22:52+08:00 阶段=P6 run=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12：队列项完成：p6_b12_concur_dynamic_v2_seed0_prefix_v2 run_id=20260703-231916-concur-dynamic-v2-Qwen3-32B-b12-prefix-v2-seed0-b12

## 2026-07-03 23:24:00 Asia/Shanghai - 准备运行 P6 b16

- 当前动作：b12 六项已完成，准备运行 b16 三项。
- b12 摘要：no_control=273.727s；request_cap_4=297.785s；request_cap_8=280.767s；fixed_window_4=174.931s；fixed_window_8=224.328s；concur_dynamic_v2=212.756s。
- b16 配置审计：num_agents=16，num_steps=8，observation_tokens_per_step=256；若 no_control 失败，则按队列注释停止扩展方向。
- GPU 安全检查：nvidia-smi pmon 显示 GPU0 仍为本仓库 SGLang scheduler；GPU3 仍有其他用户进程，未触碰。
- 命令摘要：MAX_ITEMS=3 GPU_ID=0 GPU_POLL_S=30 GPU_WAIT_TIMEOUT_S=21600 WATCHDOG_TIMEOUT_S=14400 bash scripts/08_run_queue.sh。
- 2026-07-03T23:24:06+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:24:06+08:00 阶段=P6：队列开始运行：p6_b16_no_control_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_no_control_seed0_prefix_v2.yaml
- 2026-07-03T23:24:06+08:00 阶段=P6 run=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16：开始实验 run=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_no_control_seed0_prefix_v2.yaml strategy=no_control workload=prefix_stable_v2
- 2026-07-03T23:30:22+08:00 阶段=P6 run=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16：实验结束 run=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16 latency_s=376.1821273720125 status=success
- 2026-07-03T23:30:24+08:00 阶段=P6 run=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16：队列项完成：p6_b16_no_control_seed0_prefix_v2 run_id=20260703-232406-no-control-Qwen3-32B-b16-prefix-v2-seed0-b16
- 2026-07-03T23:30:24+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:30:24+08:00 阶段=P6：队列开始运行：p6_b16_fixed_window_8_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_fixed_window_8_seed0_prefix_v2.yaml
- 2026-07-03T23:30:24+08:00 阶段=P6 run=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16：开始实验 run=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_fixed_window_8_seed0_prefix_v2.yaml strategy=fixed_window workload=prefix_stable_v2
- 2026-07-03T23:36:14+08:00 阶段=P6 run=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16：实验结束 run=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16 latency_s=349.6993705299683 status=success
- 2026-07-03T23:36:18+08:00 阶段=P6 run=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16：队列项完成：p6_b16_fixed_window_8_seed0_prefix_v2 run_id=20260703-233024-fixed-window-8-Qwen3-32B-b16-prefix-v2-seed0-b16
- 2026-07-03T23:36:18+08:00 阶段=GPU_WAIT：检测到本仓库记录的 SGLang server 健康，跳过启动；server_gpu=0。
- 2026-07-03T23:36:18+08:00 阶段=P6：队列开始运行：p6_b16_concur_dynamic_v2_seed0_prefix_v2 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_concur_dynamic_v2_seed0_prefix_v2.yaml
- 2026-07-03T23:36:18+08:00 阶段=P6 run=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16：开始实验 run=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16 config=/data/3.8T-1/yue/concur_qwen_repro/configs/experiments/b16_concur_dynamic_v2_seed0_prefix_v2.yaml strategy=concur_dynamic_v2 workload=prefix_stable_v2
- 2026-07-03T23:42:00+08:00 阶段=P6 run=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16：实验结束 run=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16 latency_s=341.3661269340082 status=success
- 2026-07-03T23:42:06+08:00 阶段=P6 run=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16：队列项完成：p6_b16_concur_dynamic_v2_seed0_prefix_v2 run_id=20260703-233618-concur-dynamic-v2-Qwen3-32B-b16-prefix-v2-seed0-b16

## 2026-07-04 02:08:34 Asia/Shanghai - innovation feature branch setup

- 当前分支：feature/qwen-innovation；不合并到 main。
- GPU 检查：GPU0/1/2 只有 Xorg 轻量占用；GPU3 的唯一计算进程 PID 1320119 属于 howarli，命令为保留 GPU 提示，未触碰。
- 已分离创新结果路径：raw runs 写入 outputs/innovation/runs，汇总表/图/报告写入 outputs/innovation/{tables,figures,reports}。
- 已准备首轮创新队列：cache-aware hysteresis 与 phase-window 两个 controller，各跑 b8 seed0/1/2；b8-long、b12、b16 作为 planned 扩展项等待首轮分析。
