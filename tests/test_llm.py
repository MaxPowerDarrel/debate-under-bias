import json
from types import SimpleNamespace

import pytest

from debate_bias.llm import LLM, Budget, BudgetExceeded, cost_usd

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
MESSAGES = [{"role": "user", "content": "Which answer is correct?"}]


class FakeUsage(dict):
    def to_dict(self):
        return dict(self)


class FakeClient:
    """Stands in for anthropic.Anthropic and counts API calls."""

    def __init__(self, stop_reason="end_turn", text="Answer: A", usage=None):
        self.calls = 0
        self.stop_reason = stop_reason
        self.text = text
        self.usage = usage or {"input_tokens": 1_000, "output_tokens": 100}
        self.messages = self

    def create(self, **request):
        self.calls += 1
        refused = self.stop_reason == "refusal"
        return SimpleNamespace(
            content=[] if refused else [SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=self.text)],
            stop_reason=self.stop_reason,
            stop_details=SimpleNamespace(category="other") if refused else None,
            usage=FakeUsage(self.usage),
            model=request["model"],
            _request_id=f"req_{self.calls}",
        )


@pytest.fixture
def make_llm(tmp_path):
    def make(client=None, cap=10.0, run_info=None):
        client = client or FakeClient()
        llm = LLM(Budget(cap), tmp_path / "log.jsonl", run_info=run_info, cache_dir=tmp_path / "cache", client=client)
        return llm, client

    return make


def call(llm, sample=0, model=SONNET, effort="high"):
    return llm.call(model, "You are a judge.", MESSAGES, max_tokens=1000, effort=effort, sample=sample, tag="q1")


def log_lines(llm):
    return [json.loads(line) for line in llm.log_path.read_text().splitlines()]


def test_repeated_call_is_served_from_cache(make_llm):
    llm, client = make_llm()
    first = call(llm)
    second = call(llm)
    assert client.calls == 1
    assert not first.cached and second.cached
    assert second.text == first.text == "Answer: A"
    assert llm.budget.spent_usd == pytest.approx(first.cost_usd)


def test_cache_survives_a_new_client(make_llm, tmp_path):
    llm, _ = make_llm()
    call(llm)
    fresh = FakeClient()
    replay = LLM(Budget(10.0), tmp_path / "log2.jsonl", cache_dir=tmp_path / "cache", client=fresh)
    assert call(replay).cached
    assert fresh.calls == 0


@pytest.mark.parametrize("change", [{"sample": 1}, {"effort": "low"}, {"model": HAIKU}])
def test_any_request_change_gets_a_new_key(make_llm, change):
    llm, client = make_llm()
    call(llm)
    call(llm, **change)
    assert client.calls == 2


def test_sonnet_cost():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd(SONNET, usage) == pytest.approx(12.00)


def test_prompt_cache_tokens_are_priced():
    usage = {
        "input_tokens": 0,
        "cache_creation_input_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "output_tokens": 0,
    }
    assert cost_usd(SONNET, usage) == pytest.approx(2.00 * 1.25 + 2.00 * 0.10)


def test_haiku_long_prompt_rate():
    short = {"input_tokens": 100_000, "output_tokens": 0}
    long = {"input_tokens": 100_001, "output_tokens": 0}
    assert cost_usd(HAIKU, short) == pytest.approx(100_000 * 0.10 / 1e6)
    assert cost_usd(HAIKU, long) == pytest.approx(100_001 * 0.50 / 1e6)


def test_cap_blocks_paid_calls_but_allows_cache_hits(make_llm):
    llm, client = make_llm(cap=0.001)
    call(llm)  # Costs $0.003, crossing the cap
    with pytest.raises(BudgetExceeded):
        call(llm, sample=1)
    assert client.calls == 1
    assert call(llm).cached


def test_budget_resumes_from_log(make_llm, tmp_path):
    llm, _ = make_llm()
    paid = call(llm)
    call(llm)  # Cache hit adds nothing
    resumed = Budget.from_log(10.0, llm.log_path)
    assert resumed.spent_usd == pytest.approx(paid.cost_usd)


def test_refusal_is_recorded_and_not_retried(make_llm):
    llm, client = make_llm(client=FakeClient(stop_reason="refusal"))
    first = call(llm)
    second = call(llm)
    assert first.stop_reason == "refusal" and first.refusal_category == "other"
    assert first.text == ""
    assert second.cached and client.calls == 1
    assert log_lines(llm)[0]["stop_reason"] == "refusal"


def test_every_call_is_logged_with_run_info(make_llm):
    llm, _ = make_llm(run_info={"config": {"split": "train"}, "seed": 0})
    call(llm)
    call(llm)
    first, second = log_lines(llm)
    for line in (first, second):
        assert line["config"] == {"split": "train"} and line["seed"] == 0
        assert line["model"] == SONNET and line["prompt_hash"] and line["usage"]["output_tokens"] == 100
    assert not first["cached"] and first["cost_usd"] > 0
    assert second["cached"] and second["cost_usd"] == 0


def test_prompt_hash_tracks_prompt_only(make_llm):
    llm, _ = make_llm()
    call(llm)
    call(llm, sample=1)
    call(llm, effort="low")
    hashes = {line["prompt_hash"] for line in log_lines(llm)}
    assert len(hashes) == 1
