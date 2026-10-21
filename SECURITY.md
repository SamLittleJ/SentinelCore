# Security policy

SentinelCore is a personal portfolio and dissertation project, not a hosted
service. Reports of security flaws are still welcome.

## Reporting a vulnerability

Please report privately, through GitHub's
[private vulnerability reporting](https://github.com/SamLittleJ/SentinelCore/security/advisories/new)
(the **Security** tab, then **Report a vulnerability**). Do not open a
public issue for a flaw that is not yet fixed.

A useful report says which version or commit is affected, how to reproduce
the flaw and what an attacker could gain. You should get an answer within
seven days.

## Supported versions

Only the latest commit of `main` is supported. There are no releases with
separate fixes.

## How the project handles its own risks

The threat model is in [docs/04-threat-model.md](docs/04-threat-model.md):
each threat, its mitigation and the test that checks it. The supply-chain
checks (pinned actions, tools and images, Dependabot, CodeQL, dependency and
configuration scans) are described in [README.md](README.md#continuous-integration).
