from __future__ import annotations

from typing import Any


def safe_slug(value: str, max_len: int = 80) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in value).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[-max_len:] or "unknown"


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _clamp_window(value: int, total_agents: int, lower: int = 1, upper: int | None = None) -> int:
    max_window = total_agents if upper is None else min(upper, total_agents)
    return max(lower, min(value, max_window))


def controller_metadata(config: dict[str, Any], total_agents: int | None = None) -> dict[str, Any]:
    strategy = str(config.get("strategy", "unknown"))
    agents = int(total_agents if total_agents is not None else config.get("num_agents", 0) or 0)
    agents_for_clamp = max(1, agents)
    request_cap = None
    agent_window = None
    effective_agent_window = agents if agents else None
    w0 = None
    w_min = None
    w_max = None
    effective_w_max = None

    if strategy == "no_control":
        label = "no_control"
    elif strategy == "request_cap":
        request_cap = int(config.get("request_cap", 0) or 0)
        label = f"request_cap_{request_cap}" if request_cap > 0 else "request_cap_unlimited"
    elif strategy == "fixed_window":
        agent_window = int(config.get("agent_window", agents_for_clamp) or agents_for_clamp)
        effective_agent_window = _clamp_window(agent_window, agents_for_clamp)
        label = f"fixed_window_{agent_window}"
        if effective_agent_window != agent_window:
            label = f"{label}_effective_{effective_agent_window}"
    elif strategy == "concur_dynamic":
        w0 = int(config.get("W_0", 4) or 4)
        w_min = int(config.get("W_min", 1) or 1)
        configured_w_max = _int_or_none(config.get("W_max"))
        w_max = configured_w_max if configured_w_max is not None else agents_for_clamp
        effective_w_max = min(w_max, agents_for_clamp)
        effective_agent_window = _clamp_window(w0, agents_for_clamp, lower=w_min, upper=w_max)
        label = "concur_dynamic"
    elif strategy in {"concur_dynamic_v2", "concur_cache_aware_v1"}:
        w0 = int(config.get("W_0", 4) or 4)
        w_min = int(config.get("W_min", 1) or 1)
        configured_w_max = _int_or_none(config.get("W_max"))
        w_max = configured_w_max if configured_w_max is not None else agents_for_clamp
        effective_w_max = min(w_max, agents_for_clamp)
        effective_agent_window = _clamp_window(w0, agents_for_clamp, lower=w_min, upper=w_max)
        label = strategy
    elif strategy == "phase_window_v1":
        agent_window = int(config.get("W_warmup", 4) or 4)
        effective_agent_window = _clamp_window(agent_window, agents_for_clamp)
        configured_w_max = _int_or_none(config.get("W_after"))
        w_max = configured_w_max if configured_w_max is not None else agents_for_clamp
        effective_w_max = min(w_max, agents_for_clamp)
        w0 = agent_window
        w_min = agent_window
        label = "phase_window_v1"
    else:
        label = safe_slug(strategy)

    return {
        "controller_label": label,
        "request_cap": request_cap,
        "agent_window": agent_window,
        "effective_agent_window": effective_agent_window,
        "W_0": w0,
        "W_min": w_min,
        "W_max": w_max,
        "effective_W_max": effective_w_max,
    }
