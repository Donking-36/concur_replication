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

    def build_prompt(self, step: int, workload_version: str = "legacy_v1") -> str:
        if workload_version == "prefix_stable_v2":
            return (
                f"{self.prompt}"
                f"\n<current_request>\n"
                f"Step: {step}\n"
                "Produce a concise action and reasoning trace.\n"
                "</current_request>"
            )
        obs = "\n".join(self.observations)
        return (
            f"You are synthetic agent {self.agent_id} in a CONCUR cache experiment.\n"
            f"Step: {step}.\n"
            f"Previous observations:\n{obs}\n"
            "Produce a concise action and reasoning trace."
        )

    def record_step_result(self, step: int, prompt: str, generation: str, observation: str, workload_version: str = "legacy_v1") -> None:
        self.observations.append(observation)
        if workload_version != "prefix_stable_v2":
            return
        self.prompt = (
            f"{prompt}\n"
            f"<assistant_output step=\"{step}\">\n"
            f"{generation}\n"
            "</assistant_output>\n"
            f"<tool_observation step=\"{step}\">\n"
            f"{observation}\n"
            "</tool_observation>\n"
        )


def make_agents(num_agents: int, seed: int, workload_version: str = "legacy_v1") -> list[AgentState]:
    agents = []
    for i in range(num_agents):
        if workload_version == "prefix_stable_v2":
            prompt = (
                f"You are synthetic agent {i} in a CONCUR cache experiment.\n"
                f"Stable agent identity: agent-{i}-seed-{seed}.\n"
                "The following transcript is append-only. Later requests must keep every earlier byte as a prefix.\n"
                "<transcript>\n"
            )
        else:
            prompt = f"agent-{i}-seed-{seed}"
        agents.append(AgentState(agent_id=i, prompt=prompt))
    return agents


def make_observation(agent_id: int, step: int, tokens: int, seed: int) -> str:
    rng = random.Random(seed * 1_000_003 + agent_id * 10_007 + step)
    words = [f"obs{agent_id}_{step}_{rng.randrange(1_000_000)}" for _ in range(tokens)]
    return " ".join(words)


async def synthetic_tool_wait(agent_id: int, step: int, min_ms: int, max_ms: int, seed: int) -> float:
    rng = random.Random(seed * 100_003 + agent_id * 991 + step * 17)
    delay = rng.uniform(min_ms / 1000.0, max_ms / 1000.0)
    await asyncio.sleep(delay)
    return delay
