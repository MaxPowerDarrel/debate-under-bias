"""Run the experiment through the Message Batches API, which costs half as much.

The experiment code makes calls one at a time and waits for each answer, but a batch
answers many calls at once, minutes to hours later. Rather than rewrite the experiment,
`BatchRunner` replays it in passes:

1. **Collect.** Run every question with `LLM.collect` on. Cached calls return as usual.
   A call that isn't cached is recorded in `LLM.pending` and raises `Pending`, which
   pauses that unit (one debate, consultancy, or verdict) while the other units keep
   going. One pass therefore gathers every call that is ready to be made.
2. **Submit.** Check the estimated cost against the cap, send the pending calls as one
   batch (in chunks of `CHUNK` requests), and save each batch's ID to the state file.
3. **Collect results.** Poll until each batch ends, then store every successful result
   in the response cache with `LLM.store_result`.
4. Repeat until a pass has nothing pending. Then run one final pass with logging on,
   which writes the output files.

A full run takes about four batches: round 1 (with the naive and expert judges), round 2,
round 3, and judging. The batch `custom_id` is the cache key, so results land in the same
cache that synchronous calls use.

**Crashes:** the state file records every submitted batch as soon as it's created, and
`run` collects any batch it lists before submitting anything new. A restarted run
therefore never pays for the same call twice.

**Failed requests:** a server error, expired request, or canceled request isn't cached,
so the next pass submits it again. An `invalid_request` error means the request itself is
wrong, so the run stops.

**Spending cap:** a batch's real cost is known only after it ends. Before submitting,
`estimate_usd` prices each request with input as characters / 3 tokens and 1,200 output
tokens at batch rates. The Day 8 pilot averaged 450 output tokens for Sonnet and 680 for
Haiku, so this is deliberately high. A batch that would take spending past the cap is not
submitted.
"""

import json
import os
import tempfile
import time
from pathlib import Path

from .llm import BATCH_MULTIPLIER, LLM, PRICES, BudgetExceeded

CHUNK = 2_000  # Requests per batch, well under the API's 100,000-request and 256 MB limits
MAX_PASSES = 12
POLL_SECONDS = 30
CHARS_PER_TOKEN = 3  # English averages nearer 4, so this overestimates input tokens
OUTPUT_TOKENS_ESTIMATE = 1_200


class BatchRequestInvalid(RuntimeError):
    pass


def estimate_usd(pending: dict[str, dict]) -> float:
    """A deliberately high estimate of what a batch of pending calls will cost."""
    total = 0.0
    for item in pending.values():
        request = item["request"]
        price = PRICES[request["model"]]
        input_tokens = len(json.dumps([request["system"], request["messages"]])) / CHARS_PER_TOKEN
        total += input_tokens * price.input + OUTPUT_TOKENS_ESTIMATE * price.output
    return total / 1_000_000 * BATCH_MULTIPLIER


class BatchRunner:
    def __init__(self, llm: LLM, state_path: Path, poll_seconds: float = POLL_SECONDS, client=None):
        self.llm = llm
        self.state_path = Path(state_path)
        self.poll_seconds = poll_seconds
        self._client = client
        self.submitted = 0  # Batches submitted by this runner, for reporting and tests

    @property
    def client(self):
        return self._client or self.llm.client

    def run(self, run_pass):
        """Call `run_pass(final)` until nothing is pending, then once with `final=True`."""
        self.collect_saved()
        self.llm.collect = True
        for _ in range(MAX_PASSES):
            self.llm.pending = {}
            self.llm.log_hits = False
            run_pass(final=False)
            if not self.llm.pending:
                break
            self.submit(self.llm.pending)
            self.collect_saved()
        else:
            raise RuntimeError(f"Calls still pending after {MAX_PASSES} passes")
        self.llm.log_hits = True
        return run_pass(final=True)

    def submit(self, pending: dict[str, dict]) -> None:
        estimate = estimate_usd(pending)
        budget = self.llm.budget
        if budget.spent_usd + estimate > budget.cap_usd:
            raise BudgetExceeded(
                f"A batch of {len(pending)} calls is estimated at ${estimate:.2f}; with ${budget.spent_usd:.2f} "
                f"spent, that could pass the ${budget.cap_usd:.2f} cap, so it wasn't submitted"
            )
        keys = list(pending)
        for start in range(0, len(keys), CHUNK):
            chunk = keys[start:start + CHUNK]
            batch = self.client.messages.batches.create(
                requests=[{"custom_id": key, "params": pending[key]["request"]} for key in chunk]
            )
            state = self._load()
            state.append({"batch_id": batch.id, "collected": False,
                          "meta": {key: pending[key]["meta"] for key in chunk}})
            self._save(state)
            self.submitted += 1
            print(f"Submitted batch {batch.id} with {len(chunk)} calls, estimated ${estimate:.2f} in all", flush=True)

    def collect_saved(self) -> None:
        """Wait for every saved batch that hasn't been collected, and cache its results."""
        state = self._load()
        for entry in state:
            if entry["collected"]:
                continue
            batch_id = entry["batch_id"]
            while (batch := self.client.messages.batches.retrieve(batch_id)).processing_status != "ended":
                counts = batch.request_counts
                print(f"Batch {batch_id}: {counts.processing} processing, {counts.succeeded} done", flush=True)
                time.sleep(self.poll_seconds)
            invalid, retry = [], 0
            for result in self.client.messages.batches.results(batch_id):
                key = result.custom_id
                if result.result.type == "succeeded":
                    if not self.llm._path(key).exists():
                        self.llm.store_result(key, entry["meta"][key], result.result.message, batch_id=batch_id)
                elif result.result.type == "errored" and result.result.error.type == "invalid_request":
                    invalid.append(key)
                else:
                    retry += 1  # Not cached, so the next pass submits it again
            entry["collected"] = True
            self._save(state)
            print(f"Collected batch {batch_id}: {retry} to resubmit, {len(invalid)} invalid", flush=True)
            if invalid:
                raise BatchRequestInvalid(f"Batch {batch_id} rejected {len(invalid)} requests, such as {invalid[0]}")

    def _load(self) -> list[dict]:
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else []

    def _save(self, state: list[dict]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.state_path)
