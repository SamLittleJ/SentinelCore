# Agent skills

Claude Code skills used while developing SentinelCore. Type `/grill-me` to start an interview about a plan; `grilling` and `tdd` are also picked up by the agent when a task fits.

| Skill | Purpose |
|---|---|
| `grill-me` | User-invoked entry point; calls `grilling`. |
| `grilling` | Interviews the user in numbered rounds, each question with a recommended answer, until no decision is left open. |
| `tdd` | Red → green loop at seams agreed with the user; `tests.md` and `mocking.md` are its references. |

## Source

Copied verbatim from [mattpocock/skills](https://github.com/mattpocock/skills) at commit
[`49dd158d1076134a641b33efb035946536778336`](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336),
under the MIT license kept in [`LICENSE-mattpocock-skills`](LICENSE-mattpocock-skills).
The `agents/openai.yaml` files (Codex metadata) were left out.

They are copied rather than installed as the self-updating plugin, so the instructions the agent follows change only through a reviewed pull request. To update, compare the upstream files at a newer commit with these, then change the commit above.
