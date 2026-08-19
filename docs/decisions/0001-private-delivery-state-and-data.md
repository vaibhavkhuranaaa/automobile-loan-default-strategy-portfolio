# 0001: Keep delivery state and data private

## Decision

Keep Project Delivery records in the private sibling operations folder. Keep the source CSV and derived SQLite database outside Git while allowing an authorized local database to enter the deployment image at build time.

## Why

The public repository should contain the product, reproducible aggregate evidence, and publication assets without shipping delivery tooling or a third-party dataset whose published licence is unclear.

## Alternatives rejected

- Continue tracking the legacy delivery folder, which exposes private operational state and fails the current publication contract.
- Continue tracking `loans.db`, which republishes derived record-level data and fails repository purity.
- Replace the real dataset with synthetic data, which would weaken the approved evidence boundary.

## Not done

Git history was not rewritten. The live container was not redeployed, and the portfolio registry was not changed.

## Changed

The tracked delivery files and database are removed from the public tree, their paths are ignored, and the README now explains the private local build input.
