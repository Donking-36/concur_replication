from __future__ import annotations

from pathlib import Path
import os
import signal
import subprocess
import time


class GpuSampler:
    def __init__(self, output_csv: Path, gpu_index: str | None = None, interval_s: int = 1) -> None:
        self.output_csv = output_csv
        self.gpu_index = gpu_index
        self.interval_s = interval_s
        self.proc: subprocess.Popen[str] | None = None

    def start(self) -> None:
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        query = (
            "timestamp,index,name,memory.used,memory.total,utilization.gpu,"
            "power.draw,temperature.gpu"
        )
        cmd = [
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv",
            "-l",
            str(self.interval_s),
        ]
        if self.gpu_index is not None:
            cmd.insert(1, f"--id={self.gpu_index}")
        fh = self.output_csv.open("w", encoding="utf-8")
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ.copy(),
                cwd="/data/3.8T-1/yue",
            )
        except Exception:
            fh.close()
            raise
        # Let nvidia-smi write the header before the workload starts.
        time.sleep(0.25)

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.proc = None

