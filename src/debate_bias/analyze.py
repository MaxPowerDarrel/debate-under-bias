"""Accuracy, bias penalties, story-bootstrap intervals, the bias check, and the main figure.

    uv run python -m debate_bias.analyze --runs results/transcripts/final --out results/final/analysis

`--runs` takes one or more run folders and merges their `verdicts.jsonl` and
`transcripts.jsonl` (or the gzip copies, `*.jsonl.gz`, that the repo publishes), so cells written by different runs (as in the pilot) can be analyzed
together. Two runs holding the same verdict is an error. The analysis makes no API calls.

**Cells.** There are eight: naive, expert, and consultancy and debate in three versions.
`consultancy` and `debate` have the unbiased judge and uninformed arguers. `*_biased` has
the biased judge and informed arguers; with the first pair it forms the 2×2 design.
`*_biased_uninformed` has the biased judge reading the unbiased cell's own transcripts.

**Completeness.** Every question should have every cell in both orders, and consultancy
on both sides. Missing verdicts are listed. The main analysis keeps only questions that
are complete in all six protocol cells, so every comparison uses the same questions and
the two effects below add up exactly to the penalty. It reports how many were dropped.

**Scores.** A question's score in a cell is the mean of its verdict scores: 2 verdicts for
debate (one per order) and 4 for consultancy (two orders × two consultant sides). Naive and
expert also have 2. Accuracy is the mean over questions, so each question counts once in
every cell.

**Bootstrap.** Questions from the same story are related, so intervals resample stories,
not questions (`CLAUDE.md`). Each of `RESAMPLES` draws picks stories with replacement and
keeps every question of each drawn story. All cells share the same draws, which is a
paired bootstrap: the penalties and their difference keep the correlation between cells
that comes from using the same questions. The interval is the 2.5th to 97.5th percentile
of the resampled statistic. The seed is fixed, so the numbers are reproducible.

**Estimates (from `PLAN.md`).**
- H1: debate − consultancy accuracy with the unbiased judge.
- H2: the bias penalty for each protocol, unbiased − biased accuracy.
- H3, the primary result: consultancy penalty − debate penalty. Positive means debate
  limited the damage.

**Secondary: splitting the penalty.** The biased cell changes the judge and the arguers at
once. `*_biased_uninformed` changes only the judge, so for each protocol:
- Judge effect: unbiased − biased-uninformed accuracy. Both judges read the same
  transcripts, so this shows what the rule does with no help from the arguers.
- Exploitation effect: biased-uninformed − biased accuracy. Same judge, and the arguers
  now know the rule.
The two sum to the H2 penalty, and H3 splits the same way into a judge part and an
exploitation part.

**Forfeits.** The main numbers score a forfeit as a loss for the side that failed (see
`judge.py`). The check recomputes everything with forfeited verdicts left out, so a
question's score uses only its judged verdicts, and a question with none drops out of
that cell.

**Bias check.** Names, numbers, and dates per argument turn (`specifics.py`), informed
(biased) minus uninformed arguers, with the same story bootstrap. Turns that
`mentions_rule` flags are listed for reading by hand, because the pattern also matches
ordinary phrases like "never been told".

**Vote agreement.** A diagnostic, not a test: the share of judged verdicts in each cell
where every vote is valid and all pick the same answer (3 of 3 in the final run). A
forfeited verdict has no votes, so it is left out. Lower agreement means the judge is
less sure of its verdicts. Intervals use the same story bootstrap, with one item per
verdict.
"""

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .specifics import count_specifics, mentions_rule

# (condition, biased judge, informed arguers)
CELLS = (("naive", False, False), ("expert", False, False), ("consultancy", False, False), ("debate", False, False),
         ("consultancy", True, False), ("debate", True, False), ("consultancy", True, True), ("debate", True, True))
PROTOCOL_CELLS = CELLS[2:]
ORDERS = (0, 1)
CONSULTANT_SIDES = ("correct", "distractor")
RESAMPLES = 10_000
SEED = 0


def cell_name(condition: str, biased: bool, informed: bool | None = None) -> str:
    """`informed` defaults to `biased`, which is what records from before the field existed mean."""
    informed = biased if informed is None else informed
    return f"{condition}{'_biased' if biased else ''}{'_uninformed' if biased and not informed else ''}"


def verdict_cell(v: dict) -> str:
    return cell_name(v["condition"], v.get("biased", False), v.get("informed"))


def expected_verdicts(condition: str) -> list[tuple[int, str | None]]:
    """The (order, consultant side) pairs each question needs in a cell."""
    sides = CONSULTANT_SIDES if condition == "consultancy" else (None,)
    return [(order, side) for order in ORDERS for side in sides]


# Loading and checking


class DuplicateRecord(ValueError):
    pass


def read_records(run: Path, name: str, required: bool = True) -> list[dict]:
    """Read `<name>.jsonl`, or the gzip copy `<name>.jsonl.gz` that the repo publishes.

    A folder holding both is an error, because the two could disagree.
    """
    plain, packed = run / f"{name}.jsonl", run / f"{name}.jsonl.gz"
    if plain.exists() and packed.exists():
        raise ValueError(f"{run} has both {plain.name} and {packed.name}; keep one")
    if packed.exists():
        text = gzip.decompress(packed.read_bytes()).decode()
    elif plain.exists():
        text = plain.read_text()
    elif required:
        raise FileNotFoundError(f"{run} has neither {plain.name} nor {packed.name}")
    else:
        return []
    return [json.loads(line) for line in text.splitlines()]


def load_runs(run_dirs: list[Path]) -> tuple[list[dict], list[dict]]:
    """Merge every run's verdicts and transcripts, refusing duplicates."""
    verdicts, transcripts, seen_v, seen_t = [], [], {}, {}
    for run in map(Path, run_dirs):
        for v in read_records(run, "verdicts"):
            key = (verdict_cell(v), v["question_id"], v["order"], v["consultant_side"])
            if key in seen_v:
                raise DuplicateRecord(f"Verdict {key} is in both {seen_v[key]} and {run}")
            seen_v[key] = run
            verdicts.append(v)
        for t in read_records(run, "transcripts", required=False):
            key = (t["protocol"], t.get("biased", False), t["question_id"], t["consultant_side"])
            if key in seen_t:
                raise DuplicateRecord(f"Transcript {key} is in both {seen_t[key]} and {run}")
            seen_t[key] = run
            transcripts.append(t)
    return verdicts, transcripts


def missing_verdicts(verdicts: list[dict]) -> dict[str, list[str]]:
    """For each question, the verdicts it lacks, such as "debate_biased o1"."""
    have = defaultdict(set)
    for v in verdicts:
        have[v["question_id"]].add((verdict_cell(v), v["order"], v["consultant_side"]))
    missing = {}
    for qid in sorted(have):
        gaps = [f"{cell_name(*cell)} o{order}{':' + side if side else ''}"
                for cell in CELLS for order, side in expected_verdicts(cell[0])
                if (cell_name(*cell), order, side) not in have[qid]]
        if gaps:
            missing[qid] = gaps
    return missing


def complete_questions(verdicts: list[dict]) -> set[str]:
    """Questions with every verdict in all six protocol cells."""
    missing = missing_verdicts(verdicts)
    protocol = {cell_name(*cell) for cell in PROTOCOL_CELLS}
    return {v["question_id"] for v in verdicts
            if not any(gap.split()[0] in protocol for gap in missing.get(v["question_id"], []))}


# Scores and the bootstrap


def question_scores(verdicts: list[dict], questions: set[str], exclude_forfeits: bool = False,
                    split_sides: bool = False) -> dict[str, dict[str, float]]:
    """Map cell name -> question ID -> mean verdict score.

    With `split_sides`, consultancy is also scored separately for each consultant side,
    in cells such as `consultancy_biased:distractor`.
    """
    scores = defaultdict(lambda: defaultdict(list))
    for v in verdicts:
        if v["question_id"] not in questions or (exclude_forfeits and v["status"] == "forfeit"):
            continue
        if v["score"] is None:
            raise ValueError(f"Verdict without a score: {v['condition']} {v['question_id']} o{v['order']}")
        name = verdict_cell(v)
        scores[name][v["question_id"]].append(v["score"])
        if split_sides and v["consultant_side"]:
            scores[f"{name}:{v['consultant_side']}"][v["question_id"]].append(v["score"])
    return {cell: {q: float(np.mean(s)) for q, s in by_q.items()} for cell, by_q in scores.items()}


class Bootstrap:
    """Paired story bootstrap for means of items grouped by story.

    `series` maps a name to a list of (story ID, value) items, such as one item per
    question for accuracy or one per turn for the bias check. Each resample draws stories
    with replacement; a story drawn k times counts each of its items k times. Every series
    uses the same draws.
    """

    def __init__(self, series: dict[str, list[tuple[str, float]]], resamples: int = RESAMPLES, seed: int = SEED):
        self.stories = sorted({story for items in series.values() for story, _ in items})
        index = {s: i for i, s in enumerate(self.stories)}
        n = len(self.stories)
        self.sums, self.counts = {}, {}
        for name, items in series.items():
            sums, counts = np.zeros(n), np.zeros(n)
            for story, value in items:
                sums[index[story]] += value
                counts[index[story]] += 1
            self.sums[name], self.counts[name] = sums, counts
        rng = np.random.default_rng(seed)
        draws = rng.integers(0, n, size=(resamples, n))
        # weights[r, s] is how many times story s was drawn in resample r.
        self.weights = np.zeros((resamples, n))
        np.add.at(self.weights, (np.arange(resamples)[:, None], draws), 1)

    def point(self, name: str) -> float:
        return float(self.sums[name].sum() / self.counts[name].sum())

    def resampled(self, name: str) -> np.ndarray:
        """The mean in each resample. A resample with no items for this series gives NaN."""
        counts = self.weights @ self.counts[name]
        with np.errstate(invalid="ignore", divide="ignore"):
            return (self.weights @ self.sums[name]) / counts

    def estimate(self, point: float, resampled: np.ndarray) -> dict:
        resampled = resampled[~np.isnan(resampled)]
        low, high = np.percentile(resampled, [2.5, 97.5])
        return {"estimate": point, "low": float(low), "high": float(high)}

    def mean(self, name: str) -> dict:
        return self.estimate(self.point(name), self.resampled(name))

    def combine(self, weights: dict[str, float]) -> dict:
        """A linear combination of series means, such as a penalty or a difference of penalties."""
        point = sum(w * self.point(name) for name, w in weights.items())
        return self.estimate(point, sum(w * self.resampled(name) for name, w in weights.items()))


HYPOTHESES = {
    "H1: debate - consultancy (unbiased)": {"debate": 1, "consultancy": -1},
    "H2: consultancy penalty": {"consultancy": 1, "consultancy_biased": -1},
    "H2: debate penalty": {"debate": 1, "debate_biased": -1},
    "H3: consultancy penalty - debate penalty": {"consultancy": 1, "consultancy_biased": -1,
                                                 "debate": -1, "debate_biased": 1},
    # Secondary: each penalty split into the judge's part and the arguers' part.
    "Judge effect: consultancy": {"consultancy": 1, "consultancy_biased_uninformed": -1},
    "Judge effect: debate": {"debate": 1, "debate_biased_uninformed": -1},
    "Exploitation effect: consultancy": {"consultancy_biased_uninformed": 1, "consultancy_biased": -1},
    "Exploitation effect: debate": {"debate_biased_uninformed": 1, "debate_biased": -1},
    "H3 from the judge effect": {"consultancy": 1, "consultancy_biased_uninformed": -1,
                                 "debate": -1, "debate_biased_uninformed": 1},
    "H3 from the exploitation effect": {"consultancy_biased_uninformed": 1, "consultancy_biased": -1,
                                        "debate_biased_uninformed": -1, "debate_biased": 1},
}


def accuracy_analysis(verdicts: list[dict], questions: set[str], story_of: dict[str, str],
                      exclude_forfeits: bool = False, resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    scores = question_scores(verdicts, questions, exclude_forfeits, split_sides=True)
    series = {cell: [(story_of[q], s) for q, s in by_q.items()] for cell, by_q in scores.items()}
    boot = Bootstrap(series, resamples, seed)
    accuracy = {cell: {**boot.mean(cell), "questions": len(scores[cell])} for cell in sorted(scores)}
    protocol = {cell_name(*cell) for cell in PROTOCOL_CELLS}
    hypotheses = {name: boot.combine(w) for name, w in HYPOTHESES.items() if protocol <= set(scores)}
    return {"accuracy": accuracy, "hypotheses": hypotheses}


def counts(verdicts: list[dict], questions: set[str]) -> dict[str, dict]:
    out = defaultdict(lambda: {"verdicts": 0, "forfeits": 0, "ties": 0, "votes": 0, "invalid_votes": 0})
    for v in verdicts:
        if v["question_id"] not in questions:
            continue
        c = out[verdict_cell(v)]
        c["verdicts"] += 1
        c["forfeits"] += v["status"] == "forfeit"
        c["ties"] += bool(v.get("tie"))
        c["votes"] += len(v["votes"])
        c["invalid_votes"] += sum(vote["letter"] is None for vote in v["votes"])
    return dict(out)


def unanimous(v: dict) -> bool:
    """Every vote is valid and all pick the same answer."""
    letters = [vote["letter"] for vote in v["votes"]]
    return bool(letters) and None not in letters and len(set(letters)) == 1


def vote_agreement(verdicts: list[dict], questions: set[str], resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    """For each cell, the share of judged verdicts whose votes are unanimous."""
    series = defaultdict(list)
    for v in verdicts:
        if v["question_id"] in questions and v["status"] == "judged":
            series[verdict_cell(v)].append((v["article_id"], float(unanimous(v))))
    if not series:
        return {}
    boot = Bootstrap(dict(series), resamples, seed)
    return {cell: {**boot.mean(cell), "verdicts": len(series[cell])} for cell in sorted(series)}


# Bias check


def bias_check(transcripts: list[dict], questions: set[str], resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    """Specifics per turn, informed minus uninformed, and the turns flagged as naming the rule."""
    series = defaultdict(list)
    table = defaultdict(list)
    flagged = []
    for t in transcripts:
        if t["question_id"] not in questions:
            continue
        informed = "informed" if t.get("biased") else "uninformed"
        for turn in t["turns"]:
            if not turn.get("argument"):
                continue
            total = count_specifics(turn["argument"]).total
            series[f"{t['protocol']}:{informed}"].append((t["article_id"], total))
            table[(t["protocol"], turn["side"], turn["round"], informed)].append(total)
            if t.get("biased") and mentions_rule(turn["argument"]):
                flagged.append({"question_id": t["question_id"], "protocol": t["protocol"], "side": turn["side"],
                                "round": turn["round"], "argument": turn["argument"]})
    out = {"per_turn": {}, "by_side_and_round": [], "rule_flags": flagged}
    if not series:
        return out
    boot = Bootstrap(dict(series), resamples, seed)
    for protocol in ("consultancy", "debate"):
        names = {k: f"{protocol}:{k}" for k in ("uninformed", "informed")}
        if all(n in series for n in names.values()):
            out["per_turn"][protocol] = {
                "uninformed": boot.mean(names["uninformed"]),
                "informed": boot.mean(names["informed"]),
                "difference": boot.combine({names["informed"]: 1, names["uninformed"]: -1}),
            }
    for protocol, side, rnd in sorted({k[:3] for k in table}):
        row = {"protocol": protocol, "side": side, "round": rnd}
        for informed in ("uninformed", "informed"):
            values = table.get((protocol, side, rnd, informed))
            row[informed] = float(np.mean(values)) if values else None
        out["by_side_and_round"].append(row)
    return out


# The whole analysis


def analyze(run_dirs: list[Path], resamples: int = RESAMPLES, seed: int = SEED) -> dict:
    verdicts, transcripts = load_runs(run_dirs)
    story_of = {v["question_id"]: v["article_id"] for v in verdicts}
    missing = missing_verdicts(verdicts)
    questions = complete_questions(verdicts)
    dropped = sorted(set(story_of) - questions)
    return {
        "settings": {"runs": [str(r) for r in run_dirs], "resamples": resamples, "seed": seed},
        "questions": {"seen": len(story_of), "analyzed": len(questions), "dropped": dropped,
                      "stories": len({story_of[q] for q in questions})},
        "missing": missing,
        "main": accuracy_analysis(verdicts, questions, story_of, False, resamples, seed),
        "without_forfeits": accuracy_analysis(verdicts, questions, story_of, True, resamples, seed),
        "counts": counts(verdicts, questions),
        "vote_agreement": vote_agreement(verdicts, questions, resamples, seed),
        "bias_check": bias_check(transcripts, questions, resamples, seed),
    }


def _ci(e: dict) -> str:
    return f"{e['estimate']:.3f} ({e['low']:.3f} to {e['high']:.3f})"


def to_markdown(results: dict) -> str:
    q = results["questions"]
    lines = [
        "# Results",
        "",
        f"Runs: {', '.join(results['settings']['runs'])}. {q['analyzed']} questions from {q['stories']} stories "
        f"analyzed; {len(q['dropped'])} dropped for missing protocol verdicts. 95% intervals from "
        f"{results['settings']['resamples']:,} story-bootstrap resamples (seed {results['settings']['seed']}).",
    ]
    for title, key in (("Main (forfeits scored as losses)", "main"), ("Check: forfeits left out", "without_forfeits")):
        part = results[key]
        lines += ["", f"## {title}", "", "| Cell | Accuracy (95% CI) | Questions |", "| --- | --- | --- |"]
        lines += [f"| {cell} | {_ci(e)} | {e['questions']} |" for cell, e in part["accuracy"].items()]
        lines += ["", "| Estimate | Value (95% CI) |", "| --- | --- |"]
        lines += [f"| {name} | {_ci(e)} |" for name, e in part["hypotheses"].items()]
    lines += ["", "## Counts", "", "| Cell | Verdicts | Forfeits | Ties | Invalid votes |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {cell} | {c['verdicts']} | {c['forfeits']} | {c['ties']} | {c['invalid_votes']}/{c['votes']} |"
              for cell, c in sorted(results["counts"].items())]
    lines += ["", "## Vote agreement (diagnostic): share of judged verdicts with unanimous votes", "",
              "| Cell | Agreement (95% CI) | Judged verdicts |", "| --- | --- | --- |"]
    lines += [f"| {cell} | {_ci(e)} | {e['verdicts']} |" for cell, e in results["vote_agreement"].items()]
    bias = results["bias_check"]
    lines += ["", "## Bias check: names, numbers, and dates per turn", "",
              "| Protocol | Uninformed | Informed | Difference (95% CI) |", "| --- | --- | --- | --- |"]
    lines += [f"| {p} | {e['uninformed']['estimate']:.2f} | {e['informed']['estimate']:.2f} | "
              f"{e['difference']['estimate']:.2f} ({e['difference']['low']:.2f} to {e['difference']['high']:.2f}) |"
              for p, e in bias["per_turn"].items()]
    lines += ["", "| Protocol | Side | Round | Uninformed | Informed |", "| --- | --- | --- | --- | --- |"]
    fmt = lambda x: "–" if x is None else f"{x:.2f}"
    lines += [f"| {r['protocol']} | {r['side']} | {r['round']} | {fmt(r['uninformed'])} | {fmt(r['informed'])} |"
              for r in bias["by_side_and_round"]]
    lines += ["", f"{len(bias['rule_flags'])} informed turns flagged as possibly mentioning the rule; read them "
              "in `results.json` before reporting a rate."]
    if results["missing"]:
        lines += ["", "## Missing verdicts", ""]
        lines += [f"- `{qid}`: {', '.join(gaps)}" for qid, gaps in results["missing"].items()]
    return "\n".join(lines) + "\n"


def plot(results: dict, path: Path) -> None:
    """Accuracy per protocol, unbiased and biased, with naive and expert as reference lines."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    acc = results["main"]["accuracy"]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    x = np.arange(2)
    for offset, biased, label, color in ((-0.18, False, "Unbiased judge", "#4C72B0"),
                                         (0.18, True, "Biased judge", "#DD8452")):
        cells = [acc.get(cell_name(p, biased)) for p in ("consultancy", "debate")]
        if not all(cells):
            continue
        est = np.array([c["estimate"] for c in cells])
        err = np.array([[c["estimate"] - c["low"] for c in cells], [c["high"] - c["estimate"] for c in cells]])
        ax.bar(x + offset, est, width=0.34, yerr=err, capsize=4, label=label, color=color)
    for cell, style in (("naive", ":"), ("expert", "--")):
        if cell in acc:
            ax.axhline(acc[cell]["estimate"], color="gray", linestyle=style, linewidth=1)
            ax.text(1.75, acc[cell]["estimate"] + 0.01, cell.capitalize(), ha="right", va="bottom", fontsize=9, color="gray")
    ax.set_xticks(x, ["Consultancy", "Debate"])
    ax.set_xlim(-0.6, 1.8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Judge accuracy")
    ax.legend(loc="lower left", fontsize=9)
    ax.set_title(f"Judge accuracy, {results['questions']['analyzed']} questions (95% story-bootstrap CI)", fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="Run folders to merge")
    parser.add_argument("--out", type=Path, required=True, help="Folder for results.json, results.md, and the figure")
    parser.add_argument("--resamples", type=int, default=RESAMPLES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    results = analyze(args.runs, args.resamples, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    markdown = to_markdown(results)
    (args.out / "results.md").write_text(markdown)
    plot(results, args.out / "accuracy.png")
    print(markdown)


if __name__ == "__main__":
    main()
