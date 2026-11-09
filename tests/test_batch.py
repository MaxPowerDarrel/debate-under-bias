import json
from types import SimpleNamespace

import pytest

from debate_bias.batch import BatchRequestInvalid, BatchRunner, estimate_usd
from debate_bias.data import Question
from debate_bias.judge import JudgeSettings
from debate_bias.llm import LLM, Budget, BudgetExceeded, Pending, cost_usd
from debate_bias.protocols import ArguerSettings, run_debate, system_blocks
from debate_bias.run import run_question

STORY = "The captain kept the map in a locked drawer. Nobody else had the key to the drawer."
QUESTION = Question("q1", "a1", "Title", STORY, "Where was the map?", "In a locked drawer", "On the deck")
ARGUER = ArguerSettings("claude-sonnet-5-5", "high", 16000, rounds=3, debate_words=150, consultancy_words=300,
                        debate_target_words=100, consultancy_target_words=200,
                        debater_prompts="debater_v2", consultant_prompts="consultant_v2",
                        debater_informed_prompts="debater_informed_v1",
                        consultant_informed_prompts="consultant_informed_v1", prompt_cache_ttl="1h")
JUDGE = JudgeSettings("claude-haiku-5-5", "medium", 8000, votes=3, prompts="judge_v2",
                      biased_prompts="judge_biased_v1")
USAGE = {"input_tokens": 1_000, "output_tokens": 100}


class FakeUsage(dict):
    def to_dict(self):
        return dict(self)


def message(params):
    """The same request always gets the same reply, so sync and batch runs can be compared."""
    if params["model"] == "claude-haiku-5-5":
        text = "Reasons.\nAnswer: A"
    else:
        text = "<argument>My case. <quote>the map</quote></argument>"
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn",
                           stop_details=None, usage=FakeUsage(USAGE), model=params["model"], _request_id="req")


class FakeAPI:
    """Stands in for anthropic.Anthropic, with both `messages.create` and `messages.batches`."""

    def __init__(self, outcome=lambda key, attempt: "succeeded"):
        self.messages = self
        self.batches = self
        self.sync_calls = 0
        self.batch_requests: list[list[str]] = []  # custom_ids of each submitted batch
        self.params: dict[str, dict] = {}
        self.attempts: dict[str, int] = {}
        self.outcome = outcome  # (custom_id, attempt) -> "succeeded", "errored", "invalid", or "expired"

    def create(self, **request):
        if "requests" in request:
            ids = [r["custom_id"] for r in request["requests"]]
            for r in request["requests"]:
                self.params[r["custom_id"]] = r["params"]
            self.batch_requests.append(ids)
            return SimpleNamespace(id=f"batch_{len(self.batch_requests)}")
        self.sync_calls += 1
        return message(request)

    def retrieve(self, batch_id):
        return SimpleNamespace(processing_status="ended", request_counts=None)

    def results(self, batch_id):
        for key in self.batch_requests[int(batch_id.split("_")[1]) - 1]:
            attempt = self.attempts[key] = self.attempts.get(key, 0) + 1
            kind = self.outcome(key, attempt)
            if kind == "succeeded":
                result = SimpleNamespace(type="succeeded", message=message(self.params[key]))
            elif kind in ("errored", "invalid"):
                error = "invalid_request" if kind == "invalid" else "api_error"
                result = SimpleNamespace(type="errored", error=SimpleNamespace(type=error))
            else:
                result = SimpleNamespace(type=kind)
            yield SimpleNamespace(custom_id=key, result=result)


def make_llm(tmp_path, api, name="run", cap=10.0):
    return LLM(Budget(cap), tmp_path / name / "calls.jsonl", cache_dir=tmp_path / "cache", client=api)


def run_batched(llm, runner, conditions="all"):
    out = {}

    def run_pass(final):
        try:
            out["result"] = run_question(llm, ARGUER, JUDGE, QUESTION, conditions)
        except Pending:
            assert not final

    runner.run(run_pass)
    return out["result"]


def log(llm):
    return [json.loads(line) for line in llm.log_path.read_text().splitlines()]


# Collect mode


def test_collect_mode_records_a_miss_without_calling_the_api(tmp_path):
    api = FakeAPI()
    llm = make_llm(tmp_path, api)
    llm.collect = True
    with pytest.raises(Pending):
        llm.call("claude-haiku-5-5", "sys", [{"role": "user", "content": "x"}], max_tokens=10, effort="low", tag="t")
    assert api.sync_calls == 0 and len(llm.pending) == 1
    assert not llm.log_path.exists()


def test_debate_collects_both_sides_before_pausing(tmp_path):
    llm = make_llm(tmp_path, FakeAPI())
    llm.collect = True
    with pytest.raises(Pending):
        run_debate(llm, ARGUER, QUESTION)
    assert sorted(item["meta"]["tag"] for item in llm.pending.values()) == [
        "debate:q1:correct:r1", "debate:q1:distractor:r1"]


# Whole runs


def test_a_full_question_takes_four_batches_and_matches_the_sync_run(tmp_path):
    sync_api = FakeAPI()
    sync_llm = LLM(Budget(10.0), tmp_path / "sync.jsonl", cache_dir=tmp_path / "sync_cache", client=sync_api)
    sync_transcripts, sync_verdicts = run_question(sync_llm, ARGUER, JUDGE, QUESTION)

    api = FakeAPI()
    llm = make_llm(tmp_path, api)
    runner = BatchRunner(llm, tmp_path / "run" / "batches.json", poll_seconds=0)
    transcripts, verdicts = run_batched(llm, runner)

    assert api.sync_calls == 0 and runner.submitted == 4  # round 1 + naive/expert, round 2, round 3, judging
    assert [t.to_dict() for t in transcripts] == [t.to_dict() for t in sync_transcripts]
    assert [v.to_dict() for v in verdicts] == [v.to_dict() for v in sync_verdicts]
    assert sum(map(len, api.batch_requests)) == sync_api.sync_calls  # Every call made exactly once


def test_each_paid_call_is_logged_once_at_half_price(tmp_path):
    api = FakeAPI()
    llm = make_llm(tmp_path, api)
    run_batched(llm, BatchRunner(llm, tmp_path / "run" / "batches.json", poll_seconds=0), "biased")
    lines = log(llm)
    paid = [line for line in lines if not line["cached"]]
    assert len(paid) == len({line["cache_key"] for line in paid}) == sum(map(len, api.batch_requests))
    assert all(line["batch_id"] for line in paid)
    sonnet = next(line for line in paid if line["model"] == "claude-sonnet-5-5")
    assert sonnet["cost_usd"] == pytest.approx(cost_usd("claude-sonnet-5-5", USAGE) / 2)
    hits = [line for line in lines if line["cached"]]
    assert len(hits) == len(paid)  # The final pass logs each call once more, as a free cache hit
    assert llm.budget.spent_usd == pytest.approx(sum(line["cost_usd"] for line in paid))


def test_a_restart_collects_a_saved_batch_instead_of_paying_again(tmp_path):
    api = FakeAPI()
    llm = make_llm(tmp_path, api)
    llm.collect = True
    with pytest.raises(Pending):
        run_question(llm, ARGUER, JUDGE, QUESTION, "biased")
    state = tmp_path / "run" / "batches.json"
    BatchRunner(llm, state, poll_seconds=0).submit(llm.pending)  # ...then the process dies
    first_batch = set(api.batch_requests[0])

    fresh = make_llm(tmp_path, api)
    run_batched(fresh, BatchRunner(fresh, state, poll_seconds=0), "biased")
    later = {key for batch in api.batch_requests[1:] for key in batch}
    assert not first_batch & later
    assert all(entry["collected"] for entry in json.loads(state.read_text()))


def test_failed_requests_are_resubmitted_on_the_next_pass(tmp_path):
    failing = {}

    def outcome(key, attempt):
        if not failing:
            failing["key"] = key
        return "errored" if key == failing["key"] and attempt == 1 else "succeeded"

    api = FakeAPI(outcome)
    llm = make_llm(tmp_path, api)
    run_batched(llm, BatchRunner(llm, tmp_path / "run" / "batches.json", poll_seconds=0), "biased")
    assert api.attempts[failing["key"]] == 2


def test_an_invalid_request_stops_the_run(tmp_path):
    api = FakeAPI(lambda key, attempt: "invalid")
    llm = make_llm(tmp_path, api)
    with pytest.raises(BatchRequestInvalid):
        run_batched(llm, BatchRunner(llm, tmp_path / "run" / "batches.json", poll_seconds=0))


def test_a_batch_that_could_pass_the_cap_is_not_submitted(tmp_path):
    api = FakeAPI()
    llm = make_llm(tmp_path, api, cap=0.001)
    with pytest.raises(BudgetExceeded):
        run_batched(llm, BatchRunner(llm, tmp_path / "run" / "batches.json", poll_seconds=0))
    assert api.batch_requests == []


def test_estimate_is_at_batch_rates_and_above_the_typical_cost():
    request = {"model": "claude-sonnet-5-5", "system": "x" * 30_000, "messages": [], "max_tokens": 16000}
    estimate = estimate_usd({"k": {"request": request}})
    typical = cost_usd("claude-sonnet-5-5", {"input_tokens": 7_500, "output_tokens": 450}, batch=True)
    assert typical < estimate < 2 * cost_usd("claude-sonnet-5-5", {"input_tokens": 10_000, "output_tokens": 1_200})


# Pricing and prompt caching


def test_batch_halves_the_price_and_one_hour_writes_cost_double():
    usage = {"input_tokens": 1_000, "cache_creation_input_tokens": 2_000, "cache_read_input_tokens": 4_000,
             "cache_creation": {"ephemeral_1h_input_tokens": 2_000, "ephemeral_5m_input_tokens": 0},
             "output_tokens": 100}
    standard = (1_000 * 2 + 2_000 * 2 * 2.0 + 4_000 * 2 * 0.1 + 100 * 10) / 1e6
    assert cost_usd("claude-sonnet-5-5", usage) == pytest.approx(standard)
    assert cost_usd("claude-sonnet-5-5", usage, batch=True) == pytest.approx(standard / 2)


def test_story_split_keeps_the_text_and_marks_only_the_story():
    system = "<story>\nOnce upon a time.\n</story>\n\nYou will act as an expert debater."
    blocks = system_blocks(system, "1h")
    assert "".join(b["text"] for b in blocks) == system
    assert blocks[0]["text"].endswith("</story>") and blocks[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "cache_control" not in blocks[1]
    assert system_blocks(system, "5m")[0]["cache_control"] == {"type": "ephemeral"}
    assert system_blocks(system, None) == system
