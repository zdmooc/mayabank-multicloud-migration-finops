# Working rules

- Canonical technical owners remain in `architecture/ADR-001-ownership-boundaries.md`.
- Any new source quote must give provider, region, SKU, number of instances, billing mode, date and official URL.
- Preserve historical `UNVERIFIED_ESTIMATE` and create a versioned, individually verified price record instead of silently promoting it.
- Never copy unpublished client information or private inventory from the private master into this public repository.
- Every evidence record has status, commit SHA, date, results and explicit limitations.
- Before any cloud apply: authorization, max spend, budget alerts, least privilege, clean destroy criteria and human go/no-go.
- This repository contains no cloud apply automation. Keep live scripts in their appropriate qualified owner repository.
