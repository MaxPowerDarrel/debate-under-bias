Versioned prompt files. Runs store each prompt's hash with their records.

Each folder is one prompt version. Never edit a version once it has been used in a run. Copy it to a new version instead.

- `system.md`: the story, then the role, the word limit, the quote system, and the judging criteria. The story comes first so later calls can share a cached prefix.
- `user.md`: the question, both answers, the transcript so far, and this round's request.
- `opening.md`, `second.md`, `later.md`: the request for round 1, round 2, and each round after. Consultants have no `second.md`, so they use `later.md` from round 2 on.

Placeholders use `$name` (`string.Template`), because stories can contain `{}`. The wording is adapted from Khan et al.'s `llm_debate` prompts (`core/config/experiment/debaters/v1.yaml` and `consultants/v1.yaml`, MIT license). The changes from their wording:
- There are no `<thinking>` tags, because Sonnet 5.5 thinks before every answer.
- The story moves into the system prompt, and Khan's "restate your position" exchange is dropped.
- Debaters refer to each other as "my opponent", so the judge's Debater A/B labels can be swapped freely.
- Consultants have no judge questions, so later rounds ask the consultant to develop its case further.
- The prompt states the hard word limit. Khan's prompt asks for fewer words than the hard limit.
