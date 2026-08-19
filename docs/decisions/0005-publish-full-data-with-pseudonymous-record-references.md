# Decision 0005: Publish the full-data product with pseudonymous record references

Date: 2026-08-18

Status: accepted; approved for publication on 2026-08-18

## Context

The public product must demonstrate the complete analytical workflow, not an aggregate-only mockup. The deployed database contains 233,154 authorized records and already powers portfolio, policy, risk, monitoring, and bounded record-review views. The record API previously serialized the source `UNIQUEID` as `loanId`, which contradicted the stated boundary that source identifiers are not public. A first replacement based on the sorted position of that identifier was also rejected because it was reversible against the named public source.

## Decision

Publish every analytical view and bounded record inspection backed by the complete authorized dataset. Replace source identifiers in public responses with opaque, release-specific random references in the form `VL-XXXXXXXXXXXX`. Store the mapping only in the private SQLite release asset and resolve references to internal keys only inside the API.

Limit public record discovery to four fixed, decision-relevant 20-row shortlists from the held-out month. Do not accept arbitrary filters, offsets, page sizes, split selection, or source-ID ordering. Omit exact disbursal dates, operational codes, and source identifiers from record responses.

Keep raw CSV and SQLite files, direct identifiers, prohibited applicant fields, private delivery state, and generated data artifacts outside the public repository and public API.

## Why

The complete decision product needs enough depth for an experienced analyst to inspect the portfolio, test policy, trace risk, review monitoring evidence, and open individual records. That does not require redistributing source files or exposing source identifiers.

## Alternatives rejected

- Publish aggregate views only, because that removes the bounded record-review workflow and understates the product.
- Publish the raw database, an enumerable transformed-row API, or source rows, because each would expose data beyond the public analytical contract.
- Continue returning source `UNIQUEID` values, because they are unnecessary for public review and contradict the documented identifier boundary.
- Derive references from source-ID ordering, because someone with the named source could reverse the mapping.
- Generate random record aliases per request, because unstable references would make review within a release harder.

## Not done

No raw dataset, SQLite database, direct source identifier, date of birth, pincode, workforce field, contact field, or identity-document field was added to Git. No applicant approval, decline, pricing, or fraud determination was enabled.

## Changed

The API now returns opaque `VL-XXXXXXXXXXXX` references and resolves record detail requests through a mapping held only in the private database. Record discovery is limited to four fixed 20-row shortlists with no pagination. The workbench and public documentation now describe full-data portfolio analysis with bounded pseudonymous record review. Release tests assert that public records contain `recordRef`, do not contain `loanId`, and do not expose an offset or source-ID sort contract.

## Consequences

The public product can demonstrate all intended analyst workflows without becoming a dataset distribution channel. The owner's 2026-08-18 directive approved publication of the complete product. Graph-backend data transmission and public-history rewriting remain separate approval gates, followed by exact deployed-source verification.
