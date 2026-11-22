# 0012. Progressive delivery: a canary by pods with synthetic traffic, and previews whose isolation comes from main

- **Status:** Accepted
- **Date:** 2026-11-22

## Context and problem

A new version of the API should reach users gradually and stop on its own if it fails, and a pull request should be seen running before it is merged, without letting unreviewed code weaken the cluster.

## Considered options

- All-at-once rollouts, previews by hand: no automatic stop, no safe place to try a change.
- An ingress or the Gateway API for weighted traffic, and previews built only from the pull request's own manifests: exact splits, but a component for that alone; and a pull request could widen its own access.
- Argo Rollouts splitting by pods with its own synthetic traffic; ApplicationSet previews whose base is read from `main` (chosen).

## Decision

On the GitOps cluster the API is a `Rollout`: one pod of five, then three, each step after an analysis that sends side-effect-free traffic to the new pods and requires at least 100 requests and under 1% of 5xx. Pull requests labelled `preview` get images signed under their own workflow identity, which Kyverno accepts only in `preview-*` namespaces; each preview's namespace, network policies, Secrets Job and database come from `main`, and its Argo CD project forbids cluster resources, network policies and roles.

## Consequences

- Good: A failing version is stopped without anyone watching.
- Good: A pull request runs in isolation, and is deleted with its namespace when closed.
- Bad: Traffic splits by pods, not requests.
- Bad: A preview still runs the pull request's code, so only the owner labels pull requests.

## More information

Written in November 2026 from the decisions log: [The API's canary (D1b)](../02-decisions-log.md#the-apis-canary-d1b), [Previews of pull requests (D1c)](../02-decisions-log.md#previews-of-pull-requests-d1c).
