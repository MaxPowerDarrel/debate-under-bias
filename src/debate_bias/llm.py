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

**Batch mode.** With `collect=True`, a call that isn't cached is recorded in `pending`
and raises `Pending` instead of calling the API. `batch.py` sends the pending calls as a
Message Batch and stores each result with `store_result`, which writes the same cache
entry and log line a synchronous call would, priced at batch rates. The next replay of
the run then finds the result in the cache. `log_hits=False` silences cache-hit log lines
during those intermediate replays, so each call is logged once when paid and once in the
final pass.
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
CACHE_WRITE_MULTIPLIER = 1.25  # 5-minute prompt-cache writes cost 1.25x the input rate.
CACHE_WRITE_1H_MULTIPLIER = 2.0  # 1-hour prompt-cache writes cost 2x the input rate.
CACHE_READ_MULTIPLIER = 0.10  # Prompt-cache reads cost 0.1x the input rate.
BATCH_MULTIPLIER = 0.5  # The Batch API halves the price of every token.


def cost_usd(model: str, usage: dict, batch: bool = False) -> float:
    """Price one call from its usage. Output tokens already include thinking tokens."""
    price = PRICES[model]
    uncached = usage.get("input_tokens", 0)
    written = usage.get("cache_creation_input_tokens") or 0
    by_ttl = usage.get("cache_creation") or {}
    written_1h = by_ttl.get("ephemeral_1h_input_tokens") or 0
    read = usage.get("cache_read_input_tokens") or 0
    output = usage.get("output_tokens", 0)
    rate_in, rate_out = price.input, price.output
    if price.long_threshold and uncached + written + read > price.long_threshold:
        rate_in, rate_out = price.long_input, price.long_output
    total = (
        uncached * rate_in
        + (written - written_1h) * rate_in * CACHE_WRITE_MULTIPLIER
        + written_1h * rate_in * CACHE_WRITE_1H_MULTIPLIER
        + read * rate_in * CACHE_READ_MULTIPLIER
        + output * rate_out
    )
    return total / 1_000_000 * (BATCH_MULTIPLIER if batch else 1.0)


def _sha256(obj) -> str:
    """Hash JSON with sorted keys, so equal requests always hash the same."""
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def prompt_hash(system: str, messages: list[dict]) -> str:
    return _sha256({"system": system, "messages": messages})


def logged_spend(log_path: Path) -> float:
    """Total paid spend recorded in one call log. A missing log has spent nothing."""
    if not log_path.exists():
        return 0.0
    with log_path.open() as f:
        return sum(json.loads(line)["cost_usd"] for line in f if line.strip())


class BudgetExceeded(RuntimeError):
    pass


class Pending(Exception):
    """Raised in collect mode when a call isn't cached yet; the call is now in `LLM.pending`."""


class Budget:
    """Track real spend and block new paid calls once it reaches the cap."""

    def __init__(self, cap_usd: float, spent_usd: float = 0.0):
        self.cap_usd = cap_usd
        self.spent_usd = spent_usd

    @classmethod
    def from_log(cls, cap_usd: float, log_path: Path) -> "Budget":
        """Resume a run's spend from its log, so a restart can't reset the cap."""
        return cls(cap_usd, logged_spend(log_path))

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
        collect: bool = False,
    ):
        """`run_info` (config and seed) is copied into every log line."""
        self.budget = budget
        self.log_path = Path(log_path)
        self.run_info = run_info or {}
        self.cache_dir = Path(cache_dir)
        self._client = client
        self.collect = collect
        self.log_hits = True
        self.pending: dict[str, dict] = {}  # Cache key -> {"request", "meta"} for calls to batch

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
        system: str | list[dict],
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
        meta = {
            "tag": tag,
            "requested_model": model,
            "prompt_hash": prompt_hash(system, messages),
            "sample": sample,
            "effort": effort,
            "max_tokens": max_tokens,
        }
        path = self._path(key)

        if path.exists():
            stored = json.loads(path.read_text())
            response = Response(**stored, cached=True, cache_key=key)
            if self.log_hits:
                self._log(response, meta, 0.0)
            return response
        if self.collect:
            self.pending[key] = {"request": request, "meta": meta}
            raise Pending(key)
        self.budget.check()
        message = self.client.messages.create(**request)
        return self.store_result(key, meta, message, message._request_id)

    def store_result(self, key: str, meta: dict, message, request_id: str | None = None,
                     batch_id: str | None = None) -> Response:
        """Cache, charge, and log one API result, from a synchronous call or a batch."""
        usage = message.usage.to_dict()
        stored = {
            "text": "".join(b.text for b in message.content if b.type == "text"),
            "stop_reason": message.stop_reason,
            "refusal_category": message.stop_details.category if message.stop_details else None,
            "usage": usage,
            "model": message.model,
            "request_id": request_id,
            "cost_usd": cost_usd(meta["requested_model"], usage, batch=batch_id is not None),
        }
        _write_atomic(self._path(key), stored)
        response = Response(**stored, cached=False, cache_key=key)
        self.budget.add(response.cost_usd)
        self._log(response, meta, response.cost_usd, batch_id)
        return response

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def _log(self, response: Response, meta: dict, charged: float, batch_id: str | None = None) -> None:
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "tag": meta["tag"],
            "requested_model": meta["requested_model"],
            "model": response.model,
            "prompt_hash": meta["prompt_hash"],
            "cache_key": response.cache_key,
            "sample": meta["sample"],
            "effort": meta["effort"],
            "max_tokens": meta["max_tokens"],
            "usage": response.usage,
            "stop_reason": response.stop_reason,
            "refusal_category": response.refusal_category,
            "request_id": response.request_id,
            "cached": response.cached,
            "batch_id": batch_id,  # Set when the call went through the Batch API
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

