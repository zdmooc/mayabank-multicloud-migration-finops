# TradeOps — Architecture hybride CRC / station IA ou GPU Cloud (HLD d'étude)

**Date :** 2026-10-09. **Statut :** OPTION, aucune exécution cloud / GPU nouvellement prouvée.

## Choix d'architecture à instruire

**Séparer calcul métier et inférence** : le HP ZBook continue d'héberger OpenShift Local CRC et TradeOps. La station Linux NVIDIA (LAN privé) ou la VM GPU Azure/AWS/GCP héberge uniquement Ollama/vLLM et les poids des modèles. La gouvernance d'accès reste dans TradeOps/Kong/AI Access/LiteLLM.

### Chemin nominal

TradeOps genai-api -> Keycloak -> Kong -> AI Access -> LiteLLM -> réseau privé authentifié/TLS -> Ollama/vLLM sur station IA ou VM GCP L4 -> réponse et métriques.

Les contrôles risque et HITL restent en amont de toute action métier. Une indisponibilité du GPU externe doit provoquer un état **degraded/unavailable explicite**, jamais un fallback mock silencieux si l'exécution d'un modèle réel est requise.

### Variantes évaluées

| Variante | Infrastructure | Exploitation | Point de vigilance |
| --- | --- | --- | --- |
| A — Station fixe | Ubuntu + GPU RTX 3090/4090/5090 ou GB10 | Locale, achat et électricité | CAPEX/VRAM, thermique, sauvegarde |
| B — GCP | Compute Engine g2-standard-8, NVIDIA L4 24Go, PD, schedule | 4 h/jour ; stockage persistant | quota/capacité au start, coût réseau/fixe |
| C — AWS | EC2 G6 L4 + volume EBS, planning via mécanisme dédié | 4 h/jour | quotas/coûts/endpoint privé |
| D — Azure | VM GPU T4 16Go ou 24Go à sélectionner | 4 h/jour | SKU/région/VRAM/frais fixes |

### Déploiement proposé GCP

Terraform : VPC/subnet sans ingress public GPU, IAM, VM Standard, Persistent Disk, Instance Schedule Europe/Paris, budget/labels. Image Linux GPU et installation reproductible Docker + pilotes ; poids du modèle sur PD sauvegardé ; tests d'inférence et d'arrêt/reprise. VPN/IAP/proxy TLS correctement routable **depuis les pods CRC** (Windows seul ne suffit pas).

### Garde-fous

- Interdire exposition du port Ollama 11434 au monde, vérifier filtrage réseau et identité de bout en bout.
- Pas de secrets/tokens/terraform.tfstate en Git public.
- Pas de Local SSD sur une instance démarrée/stoppée par Instance Schedule (restriction Google).
- Pas d'hypothèse de garantie de redémarrage GPU ; prévoir l'indisponibilité.
- Mesures : SLO de latence, p95, débit tokens/s, temps de cold-start, consommation CPU/RAM/VRAM, $/1000 appels et réseau.
- Réutiliser le D-090 existant (G1/G2 prouvés sur l'ancien chemin local), **requalification requise** pour GPU distant.

## Référence canonique (ne pas dupliquer les tableaux de prix)

**[Étude TCO complet : station/portable versus Azure, AWS, GCP](../finops/AI_INFERENCE_TCO_LOCAL_STATIONS_AZURE_AWS_GCP_2026-10-09.md)**.

Dépôts : [TradeOps](https://github.com/zdmooc/TradeOps-GenAI-Integration) pour les contrats applicatifs, [cadrage global](https://github.com/zdmooc/cadrage_202682030) pour les décisions, [ce dépôt FinOps](https://github.com/zdmooc/mayabank-multicloud-migration-finops) pour le chiffrage.

Aucune infrastructure payante n'a été créée à partir de cette étude.
