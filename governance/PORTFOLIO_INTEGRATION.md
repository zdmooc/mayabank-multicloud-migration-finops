# Governance integration — 2026-10-09

Master portfolio: `zdmooc/cadrage_202682030`. This repository is L0/L1 **cross-cloud architecture assessment and migration FinOps program**, not an independently deployed technical platform.

Canonical upstream documents in the master portfolio:

- `portfolio/REPOSITORY_CLASSIFICATION.md`
- `portfolio/REPOSITORY_MAP.md`
- `portfolio/PRODUCT_PLATFORM_DEPENDENCIES.md`
- `portfolio/RUNTIME_DEPLOYMENT_MATRIX.md`
- `portfolio/PLATFORM_RATIONALIZATION_ROADMAP.md`
- `program/MASTER_ROADMAP.md`
- `BACKLOG.md`

The D-091 / D-100 principles remain valid: reuse existing platform owners and avoid duplicating stateful shared platforms; actual cloud runtime evidence is absent. The new repository exists specifically for the **real, cross-provider migration assessment and cost governance** consumer, so it does not contradict 'no new generic platform repository'.

### Owners and expected reuse

- Azure: `mayabank-azure-cloud-ai-platform`
- Infrastructure and cluster factory: `k8s-openshift-cluster-factory`
- Migration runtime patterns: `openshift-migration-framework`
- Shared Platform: `shared-platform-services-openshift`
- Pilot product owner: `mayabank-instant-payments-resilience-platform`

**Next change:** add master references and mark I0 baseline only, I1 not complete. No migration closure or production readiness claim.
