# 0002: Require exact deployed-source identity

## Decision

Embed the Git commit in the container as `SOURCE_SHA`, return it from `/health` as `source_sha`, and require the portfolio registry to compare that field with the GitHub default branch.

## Why

Operational status alone proves only that some container is running. It cannot prove which source produced the public behavior or evidence.

## Alternatives rejected

- Verify only `status: ok`, which admits stale or unrelated builds.
- Query GitHub from the application at runtime, which adds network failure and still does not identify the image itself.
- Ship `.git` inside the image, which adds unnecessary history and expands the release artifact.

## Not done

No deployment, push, portfolio sync, or GitHub metadata mutation was performed. Those actions remain behind the human release gate.

## Changed

The build, health endpoint, deployment script, CI regression test, and release manifest now share one exact source-identity contract.
