# ADR-002 — Compare managed Kubernetes separately from managed OpenShift

**Date:** 2026-10-09 | **Status:** PROVISIONAL / NOT DEPLOYMENT_APPROVED

The first cost/portability lane uses **AKS (Azure), EKS (AWS), GKE (Google Cloud)**. Managed OpenShift is a **distinct alternative**: Azure Red Hat OpenShift (ARO), Red Hat OpenShift Service on AWS (ROSA), and OpenShift Dedicated on Google Cloud where product availability permits. Licenses/support, minimum size and architecture differ.

**First depth target:** Azure AKS, because an existing Azure architecture/Terraform owner exists. Follow with AWS EKS, then GCP GKE, only after explicit budget approval.

**Portability gaps:** OpenShift `Route`, SCC, BuildConfig/ImageStream, OLM Operators, storage classes, PVC topology and some networking semantics are not automatically supported on vanilla Kubernetes. Qualify per application. Stateful MQ/Kafka/PostgreSQL and Keycloak issuers need separate architecture decisions.

Decision only after comparable BOM by region, security, data residency, cost, RTO/RPO and demonstrated workload behavior.
