"""API client with retries, a response cache, call logging, and cost tracking.

Every model call goes through `LLM.call`, which does four things:

1. **Cache.** The key is a SHA-256 hash of every request field plus a `sample` index.
   A hit returns the stored response with no API call and no cost, so resuming a run
   never pays twice. The models have no seed and don't accept a temperature, so
   repeated samples (such as the judge's three votes) are told apart by `sample`.
2. **Budget.** Paid calls stop once real spend reaches the cap. Cache hits always go
   through. Calls are sequential, so the cap can be exceeded by at most one call.
3. **Log.** Each call, including cache hits, appends one JSONL line with the model ID,
   prompt hash, token counts, cost, stop reason, and the run's config and seed.
4. **Refusals.** A `stop_reason` of "refusal" is stored and logged as data, never
   retried. Server-side refusal fallbacks stay off, since they would swap the model.

Retries for rate limits, server errors, and dropped connections come from the SDK.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "llm"
CACHE_VERSION = 1  # Bump if the stored format changes, so old entries aren't misread.
MAX_RETRIES = 5


@dataclass(frozen=True)
class Price:
    """Standard (non-batch) USD per million tokens."""

    input: float
    output: float
    long_threshold: int | None = None  # Prompt size above which `long_*` rates apply
    long_input: float | None = None
    long_output: float | None = None


# From the Claude API pricing table, checked November 5, 2026.
PRICES = {
    "claude-sonnet-5-5": Price(input=2.00, output=10.00),
    "claude-haiku-5-5": Price(input=0.10, output=0.50, long_threshold=100_000, long_input=0.50, long_output=2.50),
}
CACHE_WRITE_MULTIPLIER = 1.25  # Prompt-cache writes cost 1.25x the input rate.
CACHE_READ_MULTIPLIER = 0.10  # Prompt-cache reads cost 0.1x the input rate.


def cost_usd(model: str, usage: dict) -> float:
    """Price one call from its usage. Output tokens already include thinking tokens."""
    price = PRICES[model]
    uncached = usage.get("input_tokens", 0)
    written = usage.get("cache_creation_input_tokens") or 0
    read = usage.get("cache_read_input_tokens") or 0
    output = usage.get("output_tokens", 0)
    rate_in, rate_out = price.input, price.output
    if price.long_threshold and uncached + written + read > price.long_threshold:
        rate_in, rate_out = price.long_input, price.long_output
    total = (
        uncached * rate_in
        + written * rate_in * CACHE_WRITE_MULTIPLIER
        + read * rate_in * CACHE_READ_MULTIPLIER
        + output * rate_out
    )
    return total / 1_000_000


def _sha256(obj) -> str:
    """Hash JSON with sorted keys, so equal requests always hash the same."""
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def prompt_hash(system: str, messages: list[dict]) -> str:
    return _sha256({"system": system, "messages": messages})


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Track real spend and block new paid calls once it reaches the cap."""

    def __init__(self, cap_usd: float, spent_usd: float = 0.0):
        self.cap_usd = cap_usd
        self.spent_usd = spent_usd

    @classmethod
    def from_log(cls, cap_usd: float, log_path: Path) -> "Budget":
        """Resume a run's spend from its log, so a restart can't reset the cap."""
        spent = 0.0
        if log_path.exists():
            with log_path.open() as f:
                spent = sum(json.loads(line)["cost_usd"] for line in f if line.strip())
        return cls(cap_usd, spent)

    def check(self) -> None:
        if self.spent_usd >= self.cap_usd:
            raise BudgetExceeded(f"Spent ${self.spent_usd:.2f} of ${self.cap_usd:.2f} cap")

    def add(self, amount: float) -> None:
        self.spent_usd += amount


@dataclass(frozen=True)
class Response:
    text: str
    stop_reason: str
    refusal_category: str | None
    usage: dict
    model: str
    request_id: str | None
    cost_usd: float  # What the original API call cost
    cached: bool
    cache_key: str


class LLM:
    def __init__(
        self,
        budget: Budget,
        log_path: Path,
        run_info: dict | None = None,
        cache_dir: Path = CACHE_DIR,
        client=None,
    ):
        """`run_info` (config and seed) is copied into every log line."""
        self.budget = budget
        self.log_path = Path(log_path)
        self.run_info = run_info or {}
        self.cache_dir = Path(cache_dir)
        self._client = client

    @property
    def client(self):
        # Created on first paid call, so cache-only replays need no API key.
        if self._client is None:
            load_dotenv()
            self._client = anthropic.Anthropic(max_retries=MAX_RETRIES)
        return self._client

    def call(
        self,
        model: str,
        system: str,
        messages: list[dict],
        *,
        max_tokens: int,
        effort: str,
        sample: int = 0,
        tag: str = "",
    ) -> Response:
        request = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "output_config": {"effort": effort},
        }
        key = _sha256({"version": CACHE_VERSION, "request": request, "sample": sample})
        path = self.cache_dir / key[:2] / f"{key}.json"

        if path.exists():
            stored = json.loads(path.read_text())
            response = Response(**stored, cached=True, cache_key=key)
            charged = 0.0
        else:
            self.budget.check()
            message = self.client.messages.create(**request)
            usage = message.usage.to_dict()
            stored = {
                "text": "".join(b.text for b in message.content if b.type == "text"),
                "stop_reason": message.stop_reason,
                "refusal_category": message.stop_details.category if message.stop_details else None,
                "usage": usage,
                "model": message.model,
                "request_id": message._request_id,
                "cost_usd": cost_usd(model, usage),
            }
            _write_atomic(path, stored)
            response = Response(**stored, cached=False, cache_key=key)
            charged = response.cost_usd
            self.budget.add(charged)

        self._log(response, request, sample, tag, charged)
        return response

    def _log(self, response: Response, request: dict, sample: int, tag: str, charged: float) -> None:
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "tag": tag,
            "requested_model": request["model"],
            "model": response.model,
            "prompt_hash": prompt_hash(request["system"], request["messages"]),
            "cache_key": response.cache_key,
            "sample": sample,
            "effort": request["output_config"]["effort"],
            "max_tokens": request["max_tokens"],
            "usage": response.usage,
            "stop_reason": response.stop_reason,
            "refusal_category": response.refusal_category,
            "request_id": response.request_id,
            "cached": response.cached,
            "cost_usd": charged,  # Spend from this call; 0 for cache hits
            "spent_usd": self.budget.spent_usd,
            **self.run_info,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")


def _write_atomic(path: Path, data: dict) -> None:
    """Write to a temp file, then rename, so a crash never leaves a partial entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)

