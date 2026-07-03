from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
import asyncio
import math
import time

from .config import append_jsonl
from .live_metrics import LiveMetricSnapshot


@dataclass
class ControllerSnapshot:
    window: int
    next_window: int
    active_agents: int
    pending_agents: int
    finished_agents: int
    kv_usage_proxy: float
    hit_rate_proxy: float
    action: str
    reason: str


class BaseController:
    def __init__(self, total_agents: int, events_path: Path) -> None:
        self.total_agents = total_agents
        self.events_path = events_path
        self.active_agents = 0
        self.finished_agents = 0

    async def acquire_agent(self) -> None:
        self.active_agents += 1

    def release_agent(self) -> None:
        self.active_agents -= 1
        self.finished_agents += 1

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def record_step_progress(self, agent_id: int, completed_steps: int) -> None:
        return None

    def record(self, snapshot: ControllerSnapshot) -> None:
        append_jsonl(
            self.events_path,
            {
                "timestamp": time.time(),
                "W_t": snapshot.window,
                "W_next": snapshot.next_window,
                "U_t": snapshot.kv_usage_proxy,
                "H_t": snapshot.hit_rate_proxy,
                "active_agents": snapshot.active_agents,
                "pending_agents": snapshot.pending_agents,
                "finished_agents": snapshot.finished_agents,
                "action": snapshot.action,
                "reason": snapshot.reason,
                "metric_type": "proxy",
            },
        )


class NoControlController(BaseController):
    async def acquire_agent(self) -> None:
        await super().acquire_agent()
        pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
        self.record(
            ControllerSnapshot(
                window=self.total_agents,
                next_window=self.total_agents,
                active_agents=self.active_agents,
                pending_agents=pending,
                finished_agents=self.finished_agents,
                kv_usage_proxy=0.0,
                hit_rate_proxy=0.0,
                action="admit",
                reason="no_control",
            )
        )


class FixedWindowController(BaseController):
    def __init__(self, total_agents: int, events_path: Path, window: int) -> None:
        super().__init__(total_agents, events_path)
        self.window = max(1, min(window, total_agents))
        self.sem = asyncio.Semaphore(self.window)

    async def acquire_agent(self) -> None:
        await self.sem.acquire()
        await super().acquire_agent()
        pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
        self.record(
            ControllerSnapshot(
                window=self.window,
                next_window=self.window,
                active_agents=self.active_agents,
                pending_agents=pending,
                finished_agents=self.finished_agents,
                kv_usage_proxy=self.active_agents / max(1, self.total_agents),
                hit_rate_proxy=0.0,
                action="admit",
                reason="fixed_agent_window",
            )
        )

    def release_agent(self) -> None:
        super().release_agent()
        self.sem.release()


class DynamicWindowController(BaseController):
    def __init__(
        self,
        total_agents: int,
        events_path: Path,
        alpha: int = 2,
        beta: float = 0.5,
        u_low: float = 0.2,
        u_high: float = 0.5,
        h_thresh: float = 0.2,
        w0: int = 4,
        w_min: int = 1,
        w_max: int | None = None,
        update_interval_s: float = 1.0,
    ) -> None:
        super().__init__(total_agents, events_path)
        self.alpha = alpha
        self.beta = beta
        self.u_low = u_low
        self.u_high = u_high
        self.h_thresh = h_thresh
        self.w_min = w_min
        self.w_max = min(w_max or total_agents, total_agents)
        self.window = max(self.w_min, min(w0, self.w_max))
        self.update_interval_s = update_interval_s
        self._cond = asyncio.Condition()
        self._last_update = 0.0
        self.kv_usage_proxy = 0.0
        self.hit_rate_proxy = 0.0

    def update_metrics(self, kv_usage_proxy: float, hit_rate_proxy: float) -> None:
        self.kv_usage_proxy = kv_usage_proxy
        self.hit_rate_proxy = hit_rate_proxy

    def _maybe_update_window(self) -> tuple[int, str, str]:
        now = time.monotonic()
        if now - self._last_update < self.update_interval_s:
            return self.window, "hold", "update_interval"
        self._last_update = now
        current = self.window
        if self.kv_usage_proxy < self.u_low:
            next_window = current + self.alpha
            action = "increase"
            reason = "U_t < U_low"
        elif self.kv_usage_proxy > self.u_high and self.hit_rate_proxy < self.h_thresh:
            next_window = math.floor(self.beta * current)
            action = "decrease"
            reason = "U_t > U_high and H_t < H_thresh"
        else:
            next_window = current
            action = "hold"
            reason = "within_band"
        self.window = max(self.w_min, min(next_window, self.w_max))
        return self.window, action, reason

    async def acquire_agent(self) -> None:
        async with self._cond:
            while self.active_agents >= self.window:
                await self._cond.wait()
            old_window = self.window
            next_window, action, reason = self._maybe_update_window()
            self.active_agents += 1
            pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
            self.record(
                ControllerSnapshot(
                    window=old_window,
                    next_window=next_window,
                    active_agents=self.active_agents,
                    pending_agents=pending,
                    finished_agents=self.finished_agents,
                    kv_usage_proxy=self.kv_usage_proxy,
                    hit_rate_proxy=self.hit_rate_proxy,
                    action=action if action != "hold" else "admit",
                    reason=reason,
                )
            )

    def release_agent(self) -> None:
        self.active_agents -= 1
        self.finished_agents += 1
        async def notify() -> None:
            async with self._cond:
                self._cond.notify_all()
        asyncio.create_task(notify())


class DynamicWindowV2Controller(BaseController):
    def __init__(
        self,
        total_agents: int,
        events_path: Path,
        metrics_reader: Callable[[], LiveMetricSnapshot],
        alpha: int = 2,
        beta: float = 0.5,
        u_low: float = 0.35,
        u_high: float = 0.80,
        h_thresh: float = 0.05,
        w0: int = 4,
        w_min: int = 1,
        w_max: int | None = None,
        update_interval_s: float = 2.0,
    ) -> None:
        super().__init__(total_agents, events_path)
        self.alpha = alpha
        self.beta = beta
        self.u_low = u_low
        self.u_high = u_high
        self.h_thresh = h_thresh
        self.w_min = w_min
        self.w_max = min(w_max or total_agents, total_agents)
        self.window = max(self.w_min, min(w0, self.w_max))
        self.update_interval_s = update_interval_s
        self.metrics_reader = metrics_reader
        self._cond = asyncio.Condition()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_snapshot: LiveMetricSnapshot | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._feedback_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def acquire_agent(self) -> None:
        async with self._cond:
            while self.active_agents >= self.window:
                await self._cond.wait()
            self.active_agents += 1
            pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
            self._record_event(
                action="admit",
                reason="agent_admitted_under_current_window",
                window=self.window,
                next_window=self.window,
                pending_agents=pending,
                metric_type="exact_or_pending",
                extra={},
            )

    def release_agent(self) -> None:
        self.active_agents -= 1
        self.finished_agents += 1

        async def notify() -> None:
            async with self._cond:
                self._cond.notify_all()

        asyncio.create_task(notify())

    async def _feedback_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._sample_and_update()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.update_interval_s)
            except asyncio.TimeoutError:
                continue
        await self._sample_and_update(final=True)

    async def _sample_and_update(self, final: bool = False) -> None:
        snapshot = await asyncio.to_thread(self.metrics_reader)
        self._last_snapshot = snapshot
        token_usage = snapshot.token_usage
        cached_ratio = snapshot.recent_cached_token_ratio
        if cached_ratio is None:
            cached_ratio = snapshot.cached_token_ratio
        old_window = self.window
        next_window = old_window
        action = "hold"
        reason = "missing_exact_scheduler_metric"
        if token_usage is not None:
            if token_usage > self.u_high and (cached_ratio is None or cached_ratio < self.h_thresh):
                next_window = math.floor(self.beta * old_window)
                action = "decrease"
                reason = "exact_token_usage_high_and_cached_ratio_low"
            elif token_usage < self.u_low:
                next_window = old_window + self.alpha
                action = "increase"
                reason = "exact_token_usage_low"
            else:
                reason = "exact_metrics_within_band"
        next_window = max(self.w_min, min(next_window, self.w_max))
        self.window = next_window
        async with self._cond:
            self._cond.notify_all()
        pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
        self._record_event(
            action="final_sample" if final else action,
            reason=f"{reason}{'_final' if final else ''}",
            window=old_window,
            next_window=next_window,
            pending_agents=pending,
            metric_type="exact_sglang_log",
            extra={
                "scheduler_points": snapshot.scheduler_points,
                "request_count": snapshot.request_count,
                "token_usage": snapshot.token_usage,
                "running_req": snapshot.running_req,
                "queue_req": snapshot.queue_req,
                "pending_token": snapshot.pending_token,
                "cached_token_ratio": snapshot.cached_token_ratio,
                "recent_cached_token_ratio": snapshot.recent_cached_token_ratio,
                "metrics_source": snapshot.source,
            },
        )

    def _record_event(
        self,
        *,
        action: str,
        reason: str,
        window: int,
        next_window: int,
        pending_agents: int,
        metric_type: str,
        extra: dict[str, Any],
    ) -> None:
        row = {
            "timestamp": time.time(),
            "W_t": window,
            "W_next": next_window,
            "U_t": extra.get("token_usage"),
            "H_t": extra.get("recent_cached_token_ratio", extra.get("cached_token_ratio")),
            "active_agents": self.active_agents,
            "pending_agents": pending_agents,
            "finished_agents": self.finished_agents,
            "action": action,
            "reason": reason,
            "metric_type": metric_type,
        }
        row.update(extra)
        append_jsonl(self.events_path, row)


class CacheAwareHysteresisController(BaseController):
    def __init__(
        self,
        total_agents: int,
        events_path: Path,
        metrics_reader: Callable[[], LiveMetricSnapshot],
        cache_low: float = 0.12,
        cache_high: float = 0.35,
        ewma_alpha: float = 0.35,
        u_low: float = 0.55,
        u_high: float = 0.92,
        queue_high: int = 4,
        pending_high: int = 120000,
        cooldown_ticks: int = 2,
        w0: int = 4,
        w_min: int = 1,
        w_max: int | None = None,
        update_interval_s: float = 2.0,
    ) -> None:
        super().__init__(total_agents, events_path)
        self.metrics_reader = metrics_reader
        self.cache_low = cache_low
        self.cache_high = cache_high
        self.ewma_alpha = ewma_alpha
        self.u_low = u_low
        self.u_high = u_high
        self.queue_high = queue_high
        self.pending_high = pending_high
        self.cooldown_ticks = cooldown_ticks
        self.cooldown_remaining = 0
        self.w_min = w_min
        self.w_max = min(w_max or total_agents, total_agents)
        self.window = max(self.w_min, min(w0, self.w_max))
        self.update_interval_s = update_interval_s
        self.cached_ratio_ewma: float | None = None
        self._cond = asyncio.Condition()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._feedback_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def acquire_agent(self) -> None:
        async with self._cond:
            while self.active_agents >= self.window:
                await self._cond.wait()
            self.active_agents += 1
            pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
            self._record_event(
                action="admit",
                reason="agent_admitted_under_cache_aware_window",
                window=self.window,
                next_window=self.window,
                pending_agents=pending,
                metric_type="exact_or_pending",
                extra={},
            )

    def release_agent(self) -> None:
        self.active_agents -= 1
        self.finished_agents += 1

        async def notify() -> None:
            async with self._cond:
                self._cond.notify_all()

        asyncio.create_task(notify())

    async def _feedback_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._sample_and_update()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.update_interval_s)
            except asyncio.TimeoutError:
                continue
        await self._sample_and_update(final=True)

    async def _sample_and_update(self, final: bool = False) -> None:
        snapshot = await asyncio.to_thread(self.metrics_reader)
        old_window = self.window
        recent_ratio = snapshot.recent_cached_token_ratio
        if recent_ratio is None:
            recent_ratio = snapshot.cached_token_ratio
        if recent_ratio is not None:
            if self.cached_ratio_ewma is None:
                self.cached_ratio_ewma = recent_ratio
            else:
                self.cached_ratio_ewma = (
                    self.ewma_alpha * recent_ratio
                    + (1.0 - self.ewma_alpha) * self.cached_ratio_ewma
                )

        token_usage = snapshot.token_usage
        queue_req = snapshot.queue_req or 0
        pending_token = snapshot.pending_token or 0
        next_window = old_window
        action = "hold"
        reason = "missing_exact_scheduler_metric"
        if token_usage is not None:
            reason = "within_hysteresis_band"
            if token_usage >= self.u_high and (
                self.cached_ratio_ewma is None or self.cached_ratio_ewma < self.cache_low
            ):
                next_window = old_window - 2
                action = "decrease"
                reason = "token_usage_high_and_cache_ewma_low"
                self.cooldown_remaining = self.cooldown_ticks
            elif queue_req >= self.queue_high or pending_token >= self.pending_high:
                next_window = old_window - 1
                action = "decrease"
                reason = "queue_or_pending_token_high"
                self.cooldown_remaining = self.cooldown_ticks
            elif self.cooldown_remaining > 0:
                self.cooldown_remaining -= 1
                reason = "cooldown_hold"
            elif token_usage <= self.u_low and (
                self.cached_ratio_ewma is not None and self.cached_ratio_ewma >= self.cache_high
            ):
                next_window = old_window + 1
                action = "increase"
                reason = "token_usage_low_and_cache_ewma_healthy"
        next_window = max(self.w_min, min(next_window, self.w_max))
        self.window = next_window
        async with self._cond:
            self._cond.notify_all()
        pending_agents = max(0, self.total_agents - self.active_agents - self.finished_agents)
        self._record_event(
            action="final_sample" if final else action,
            reason=f"{reason}{'_final' if final else ''}",
            window=old_window,
            next_window=next_window,
            pending_agents=pending_agents,
            metric_type="exact_sglang_log",
            extra={
                "scheduler_points": snapshot.scheduler_points,
                "request_count": snapshot.request_count,
                "token_usage": snapshot.token_usage,
                "running_req": snapshot.running_req,
                "queue_req": snapshot.queue_req,
                "pending_token": snapshot.pending_token,
                "cached_token_ratio": snapshot.cached_token_ratio,
                "recent_cached_token_ratio": snapshot.recent_cached_token_ratio,
                "cached_ratio_ewma": self.cached_ratio_ewma,
                "cooldown_remaining": self.cooldown_remaining,
                "metrics_source": snapshot.source,
            },
        )

    def _record_event(
        self,
        *,
        action: str,
        reason: str,
        window: int,
        next_window: int,
        pending_agents: int,
        metric_type: str,
        extra: dict[str, Any],
    ) -> None:
        row = {
            "timestamp": time.time(),
            "W_t": window,
            "W_next": next_window,
            "U_t": extra.get("token_usage"),
            "H_t": extra.get("cached_ratio_ewma", extra.get("recent_cached_token_ratio", extra.get("cached_token_ratio"))),
            "active_agents": self.active_agents,
            "pending_agents": pending_agents,
            "finished_agents": self.finished_agents,
            "action": action,
            "reason": reason,
            "metric_type": metric_type,
        }
        row.update(extra)
        append_jsonl(self.events_path, row)


class PhaseWindowController(BaseController):
    def __init__(
        self,
        total_agents: int,
        events_path: Path,
        warmup_steps: int = 2,
        w_warmup: int = 4,
        w_mid: int | None = 6,
        w_after: int = 8,
        ramp: bool = True,
    ) -> None:
        super().__init__(total_agents, events_path)
        self.warmup_steps = max(1, warmup_steps)
        self.w_warmup = max(1, min(w_warmup, total_agents))
        self.w_mid = max(1, min(w_mid or w_after, total_agents))
        self.w_after = max(1, min(w_after, total_agents))
        self.ramp = ramp
        self.window = self.w_warmup
        self.agent_progress: dict[int, int] = {}
        self._cond = asyncio.Condition()

    def _warm_agents(self) -> int:
        return sum(1 for steps in self.agent_progress.values() if steps >= self.warmup_steps)

    def _target_window(self) -> tuple[int, str]:
        warm_agents = self._warm_agents()
        if warm_agents < self.w_warmup:
            return self.w_warmup, "warmup_window"
        if self.ramp and warm_agents < self.w_mid:
            return self.w_mid, "ramp_mid_window"
        return self.w_after, "open_window_after_warmup"

    async def acquire_agent(self) -> None:
        async with self._cond:
            target, reason = self._target_window()
            self.window = target
            while self.active_agents >= self.window:
                await self._cond.wait()
                target, reason = self._target_window()
                self.window = target
            self.active_agents += 1
            pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
            self._record_event(
                action="admit",
                reason=reason,
                window=target,
                next_window=target,
                pending_agents=pending,
            )

    def release_agent(self) -> None:
        self.active_agents -= 1
        self.finished_agents += 1

        async def notify() -> None:
            async with self._cond:
                self._cond.notify_all()

        asyncio.create_task(notify())

    def record_step_progress(self, agent_id: int, completed_steps: int) -> None:
        self.agent_progress[agent_id] = max(self.agent_progress.get(agent_id, 0), completed_steps)
        old_window = self.window
        next_window, reason = self._target_window()
        self.window = next_window
        pending = max(0, self.total_agents - self.active_agents - self.finished_agents)
        self._record_event(
            action="progress",
            reason=reason,
            window=old_window,
            next_window=next_window,
            pending_agents=pending,
            extra={
                "agent_id": agent_id,
                "completed_steps": completed_steps,
                "warmup_steps": self.warmup_steps,
                "warm_agents": self._warm_agents(),
            },
        )

        async def notify() -> None:
            async with self._cond:
                self._cond.notify_all()

        asyncio.create_task(notify())

    def _record_event(
        self,
        *,
        action: str,
        reason: str,
        window: int,
        next_window: int,
        pending_agents: int,
        extra: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "timestamp": time.time(),
            "W_t": window,
            "W_next": next_window,
            "U_t": None,
            "H_t": None,
            "active_agents": self.active_agents,
            "pending_agents": pending_agents,
            "finished_agents": self.finished_agents,
            "action": action,
            "reason": reason,
            "metric_type": "progress_schedule",
            "warmup_steps": self.warmup_steps,
            "warm_agents": self._warm_agents(),
        }
        if extra:
            row.update(extra)
        append_jsonl(self.events_path, row)


class RequestCap:
    def __init__(self, cap: int | None) -> None:
        self.sem = asyncio.Semaphore(cap) if cap and cap > 0 else None

    async def __aenter__(self) -> None:
        if self.sem is not None:
            await self.sem.acquire()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.sem is not None:
            self.sem.release()
