from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import random
import time


@dataclass
class AgentState:
    agent_id: int
    prompt: str
    observations: list[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    def build_prompt(self, step: int) -> str:
        obs = "\n".join(self.observations)
        return (
            f"You are synthetic agent {self.agent_id} in a CONCUR cache experiment.\n"
            f"Step: {step}.\n"
            f"Previous observations:\n{obs}\n"
            "Produce a concise action and reasoning trace."
        )


def make_agents(num_agents: int, seed: int) -> list[AgentState]:
    return [
        AgentState(agent_id=i, prompt=f"agent-{i}-seed-{seed}")
        for i in range(num_agents)
    ]


def make_observation(agent_id: int, step: int, tokens: int, seed: int) -> str:
    rng = random.Random(seed * 1_000_003 + agent_id * 10_007 + step)
    words = [f"obs{agent_id}_{step}_{rng.randrange(1_000_000)}" for _ in range(tokens)]
    return " ".join(words)


async def synthetic_tool_wait(agent_id: int, step: int, min_ms: int, max_ms: int, seed: int) -> float:
    rng = random.Random(seed * 100_003 + agent_id * 991 + step * 17)
    delay = rng.uniform(min_ms / 1000.0, max_ms / 1000.0)
    await asyncio.sleep(delay)
    return delay

