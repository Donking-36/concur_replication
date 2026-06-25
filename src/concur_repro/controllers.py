from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import asyncio
import math
import time

from .config import append_jsonl


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


class RequestCap:
    def __init__(self, cap: int | None) -> None:
        self.sem = asyncio.Semaphore(cap) if cap and cap > 0 else None

    async def __aenter__(self) -> None:
        if self.sem is not None:
            await self.sem.acquire()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.sem is not None:
            self.sem.release()

