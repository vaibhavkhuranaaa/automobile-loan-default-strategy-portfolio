# Architecture

The product is a single-container, read-only analytics application. Private source data is validated, split by time, and used to produce a SQLite star schema plus aggregate evaluation evidence. Parameterized SQL feeds a FastAPI API. A React client, report artifacts, and the API are served from the same process.

The repository does not track the source CSV or derived SQLite database. An authorized local database is copied into the deployment image at build time.

Release identity is part of the runtime contract. The build receives the exact Git commit through `SOURCE_SHA`; the anonymous `/health` response exposes it as `source_sha`; the portfolio registry compares that value with the GitHub default branch before admitting a release.

See [the canonical Mermaid source](../architecture/system.mmd) and [decision 0002](decisions/0002-exact-deployed-source-contract.md).
