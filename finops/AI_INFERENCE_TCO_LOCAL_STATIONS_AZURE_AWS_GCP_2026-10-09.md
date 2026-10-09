# TradeOps IA : TCO matériel local versus Azure, AWS, GCP — dossier de référence

**Date de consolidation : 2026-10-09.** **Responsable de l'étude :** mayabank-multicloud-migration-finops. **Statut :** COMPARATIVE_ASSESSMENT / NON_DEPLOYED / PRICES_PENDING_DIRECT_VENDOR_QUOTES. **Décision achat/location :** OPEN.

## 1. Objet et périmètre de cette conversation

Conserver dans **un seul dossier maître** les options évaluées pour alimenter l'IA de MayaBank TradeOps, en conservant le HP ZBook 17 G3 pour **Windows 11 + OpenShift Local (CRC 4.22.7)** :

1. remplacement initial envisagé par un portable haut de gamme (hypothèse **écartée au profit de deux machines**) ;
2. achat d'une **station de travail fixe dédiée IA**, Linux + NVIDIA GPU ;
3. location GPU sur **Microsoft Azure, AWS et GCP**, avec essais de **4 h/jour** ;
4. architecture réseau/intégration **TradeOps / Keycloak / Kong / AI Access / LiteLLM / Ollama** ;
5. approches GitHub publiques Terraform, planification automatique et sécurité ;
6. coût complet, contraintes, hypothèses, preuves attendues et conditions de décision.

**Ne pas confondre** cette étude GPU (inférence externalisée, cluster CRC restant local) avec le projet distinct de migration complète des workloads vers **AKS/EKS/GKE** et ses tarifs de control plane.

## 2. État existant et besoin technique

- Machine conservée : HP ZBook 17 G3, Windows 11, OpenShift CRC. CRC a déjà servi à des preuves TradeOps ; l'IA externe doit **libérer des ressources sur la machine locale**, pas déplacer OpenShift.
- Dépôt applicatif : https://github.com/zdmooc/TradeOps-GenAI-Integration .
- Chemin G1 déjà documenté dans TradeOps : genai-api -> Shared Keycloak -> Kong -> AI Access -> LiteLLM -> Ollama/qwen2.5:3b ; alias gouverné tradeops-default, politiques model/consumer, quota, budget, traces et tests négatifs.
- Travaux à prévoir : remplacer l'endpoint Ollama actuellement accessible via l'hôte CRC par un endpoint **privé** dédié ; conserver la frontière de sécurité et rejouer les preuves D-090 G1/G2. G3/G4 multi-consommateurs et A2A nécessitent leurs propres validations.
- Objectifs modèles : 7B / 14B quantifiés en première étape, 32B quantifiés selon VRAM/contexte ; 70B généralement hors GPU unique 24/32 Go sans offload ou matériel à mémoire plus importante. Taille du contexte, KV cache, débit et simultanéité doivent être benchmarkés.

## 3. Matériel local — comparaison des options évoquées

**Prix ci-dessous = enveloppes indicatives communiquées dans l'échange, PAS devis d'achat ou prix garantis au 09/10/2026.** Configurations exactes, garantie, pièces et stock restent à vérifier.

| Solution | GPU / mémoire utile IA | RAM système cible | Coût d'acquisition évoqué | Positionnement / limites |
| --- | --- | --- | --- | --- |
| Garder ZBook actuel | Pas de nouvel achat | Ressources CRC existantes | 0 € CAPEX additionnel | CRC côté applicatif ; inférence externalisée |
| Portable ThinkPad P16 Gen 2 reconditionné | GPU à vérifier selon configuration | 64 Go puis 128 Go | ~2 400–2 800 € | Ancienne piste « tout sur un portable » ; non retenue |
| Portable Dell Precision 7680 reconditionné | GPU à vérifier | 64 Go, extension selon CAMM | ~1 800 € | Ancienne piste ; non retenue |
| Portable HP OMEN MAX 16 RTX 5090 | 24 Go VRAM Laptop (configuration à vérifier) | 64 Go max annoncé, à confirmer | ~4 100 € | Ancienne piste ; non retenue |
| ThinkPad P16 Gen 3 / RTX PRO 5000 | 24 Go VRAM selon option | 128 Go cible | > 5 000 € selon option | Ancienne piste ; non retenue |
| Tour RTX 5060 Ti | 16 Go VRAM selon référence | 64 Go | 1 600–2 600 € | Modèles petits/moyens, limite 32B |
| **Tour RTX 3090 d'occasion** | **24 Go VRAM** | 64–128 Go | **2 200–3 200 €** | Entrée raisonnable à 24 Go, vigilance usure/thermique |
| **Tour RTX 4090** | **24 Go VRAM** | 64–128 Go | **3 400–4 500 €** | Débit plus élevé, consommation/thermique, 24 Go plafond |
| Tour RTX 5090 | 32 Go VRAM (version desktop) | 64–128 Go | 6 000–9 000 € | Plus de VRAM et débit, CAPEX élevé |
| NVIDIA DGX Spark / ASUS Ascent GX10 GB10 | 128 Go de **mémoire unifiée** (pas GDDR dédiée) | Mémoire unifiée | 4 800–6 100 € | Grands modèles ; architecture ARM, bande passante et compatibilité à benchmarker |

**Tour RTX 4090 exemple BOM indicative (TTC, ordre de grandeur) :** CPU Ryzen 9 7900 ~300–450 € ; GPU reconditionné ~2 196 € ; RAM 64 Go DDR5 ~250–400 € ; carte mère ~180–300 € ; NVMe 2 To ~150–250 € ; alimentation ATX 3.x 1 000 W ~130–230 € ; boîtier ~110–180 € ; refroidissement ~60–120 € ; assemblage/tests ~100–180 €. **Total illustratif : ~3 476–4 306 €**, sans écran/périphériques. Ne pas additionner cette BOM aux enveloppes de gamme : c'est une variante.

**OPEX local à intégrer au TCO** : consommation prise murale mesurée (système entier, pas TGP GPU), coût de l'électricité contractuel, refroidissement, garantie/remplacement, amortissement, bruit, maintenance et disponibilité. Exemple *purement hypothétique* : 500 W moyens à la prise × 120 h/mois × 0,25 €/kWh = **15 €/mois** d'électricité. Ajouter veille et charge hors inférence.

## 4. Azure / AWS / GCP — offres à qualifier

Les chiffres suivants **reprennent des estimations avancées dans la conversation**. Les prix horaires ci-dessous **n'ont pas été validés directement via les API tarifaires officielles de chacune des trois plateformes** pour région, SKU et date. Ils ne constituent ni un devis ni une comparaison GPU isoperformance. Aucune ressource n'a été provisionnée.

| Cloud | Région indicative | VM candidate | GPU | RAM VM évoquée | Prix de calcul utilisé dans le scénario ($/h, hypothèse) |
| --- | --- | --- | --- | --- | ---: |
| **GCP** | Belgique (europe-west1) | g2-standard-8 | 1 × NVIDIA L4 **24 Go** | 32 Go | **0,94** |
| **AWS** | Paris (eu-west-3) | g6.xlarge | 1 × NVIDIA L4 **24 Go** | 16 Go | **1,02** |
| **Azure** | France Central | NC4as_T4_v3 | NVIDIA T4 **16 Go** | 28 Go | **0,62** |
| **Azure** | France Central, à vérifier | NV36ads_A10_v5 | A10 **24 Go** | 440 Go évoqués, SKU exact à vérifier | **4,00** |

**Attention :** Azure T4 16 Go ne remplace pas une L4 24 Go à performances/capacité comparables ; l'option Azure A10 ci-dessus englobe une VM beaucoup plus grosse, donc le prix VM n'est **pas** comparable à isopérimètre. Explorer d'autres VM Azure 24 Go et les tailles/GPU disponibles dans les régions réellement accessibles.

### Scénarios de calcul brut (USD, HORS TOUT LE RESTE)

Hypothèses : 22 jours ouvrés ou 30 jours calendaires/mois ; à la demande ; VM réellement en marche pendant les heures affichées. **Calcul arithmétique à partir des tarifs horaires provisoires ci-dessus**, non prévision de facture validée.

| Cloud/SKU | 4h × 22j = 88h | **4h × 30j = 120h** | 8h × 22j = 176h | 24/7 ≈ 730h |
| --- | ---: | ---: | ---: | ---: |
| GCP L4 0,94 $/h | 82,72 $ | **112,80 $** | 165,44 $ | 686,20 $ |
| AWS L4 1,02 $/h | 89,76 $ | **122,40 $** | 179,52 $ | 744,60 $ |
| Azure T4 0,62 $/h | 54,56 $ | **74,40 $** | 109,12 $ | 452,60 $ |
| Azure A10 4,00 $/h | 352,00 $ | **480,00 $** | 704,00 $ | 2 920,00 $ |

**Correction de cohérence des échanges précédents :** « 4 h/jour » est ambigu entre **88h (lundi–vendredi)** et **120h (tous les jours)** ; l'ancien tableau mélangeait ces conventions, et certains montants mensuels en euros ne correspondaient pas aux heures affichées. **Le présent tableau explicite les heures et la devise USD** ; conversion EUR seulement après enregistrement du taux FX et de sa date.

**Facture réelle** = calcul GPU/vCPU + disque persistant GB-mois + snapshots/sauvegardes + buckets + IP publique éventuelle + NAT/VPN/tunnel + trafic sortant + monitoring/logs + taxes/support, en déduisant crédits/remises prouvés. Un Cloud NAT persistant peut ajouter des coûts même lorsque la VM GPU est arrêtée. Comparer aussi les coûts de temps de chargement, démarrage, interruption/Spot et latence réseau.

Les prix officiels devront être relevés séparément depuis :
- https://cloud.google.com/compute/gpus-pricing et https://cloud.google.com/products/calculator
- https://aws.amazon.com/ec2/pricing/on-demand/ et https://calculator.aws/
- https://azure.microsoft.com/pricing/details/virtual-machines/linux/ et https://azure.microsoft.com/pricing/calculator/
- https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices

### TCO et point d'équilibre

- CAPEX local : machine complète (neuve/reconditionnée) + pièces futures.
- OPEX local : électricité mesurée + maintenance + renouvellement et disponibilité.
- OPEX cloud : heures GPU/VM et **coûts résiduels hors heures de calcul**.
- Calcul : TCO_local(N mois) = CAPEX + N × OPEX_local ; TCO_cloud(N mois) = N × (heures × prix_SKU + charges_fixes + transfert) × FX + taxes/engagements.
- Les équivalences financières seules sont insuffisantes : **RTX 4090 24 Go et NVIDIA L4 24 Go ne sont pas équivalents en débit et objectifs d'usage**. Mesurer coût / 1 000 requêtes utiles, tokens/s, p95 et qualité.
- Aucune décision ferme d'achat n'est prise, faute de devis fournisseurs complets, capacité GPU régionale et protocole benchmark.

## 5. Architecture cible — hybride CRC + GPU externe

```text
HP ZBook 17 G3 / Windows 11 / OpenShift Local (CRC)
  TradeOps genai-api, RAG, agent-controller, risk-engine, HITL
       -> Shared Keycloak (OIDC) -> Kong -> AI Access
       -> LiteLLM (alias + allowlists + quotas + budget + OTel)
       -> CONNECTIVITE PRIVEE authentifiée et chiffrée
             -> variante A : station Ubuntu/NVIDIA locale sur LAN/VPN
             -> variante B : GCP VM L4 (ou équivalent AWS/Azure)
                   -> Docker/Ollama ou vLLM -> modèle quantifié
```

- Endpoint Ollama **ne doit pas être ouvert directement sur Internet** ; tunnel IAP/SSH, VPN privé ou proxy authentifié TLS avec egress contrôlé.
- Tailscale installé sur Windows ne rend pas les pods CRC automatiquement routables : vérifier la route/bridge/proxy depuis les pods, la DNS, le certificat et le NetworkPolicy egress.
- Préserver Risk Gate déterministe, HITL, isolation consommateur, tracing et deny tests. Pas de fallback fictif silencieux.
- Test minimal : liveness GPU (nvidia-smi), health Ollama, modèle chargé, appel authentifié de genai-api via Kong/LiteLLM, refus modèle/consommateur, quotas/budget, traces, arrêt/reprise et application toujours saine côté CRC.
- Le GPU n'héberge pas un deuxième OpenShift par défaut.

## 6. Automatisation du créneau 4 h/jour — GCP (candidat)

Choix de principe : **Terraform pour créer VPC/IAM/VM G2/PD/schedule ; image GPU + cloud-init (ou startup script) pour OS/NVIDIA/containers ; Docker Compose pour Ollama/vLLM ; tests/observabilité séparés**. Une VM conservée et **stoppée** chaque soir (pas destroy quotidien).

- Instance Schedule Google : démarrage et arrêt, fuseau **Europe/Paris** ; exemple **18:00–22:00** 7j/7, ou MON-FRI, à choisir explicitement ; les opérations peuvent démarrer jusqu'à ~15 minutes après l'horaire nominal.
- Attacher la ressource Terraform **google_compute_resource_policy** à la VM via **google_compute_resource_policy_attachment** ; vérifier IAM du Compute Engine service agent, statut du schedule et Audit Logs.
- **Ne pas utiliser Local SSD** pour une VM qui doit s'arrêter régulièrement : les Instance Schedules ne prennent pas en charge son arrêt. Préférer **Persistent Disk** (sauvegarde + snapshots) et ne pas compter sur GCS comme seul cache runtime haute performance.
- Conserver images et poids du modèle sur PD séparé du boot si l'instance est remplaçable ; stocker les manifests/version de modèle dans Git, les secrets hors Git ; bootstrapping idempotent.
- GCP n'offre **pas de garantie de capacité** GPU au redémarrage planifié ; qualifier quota GPU, zone, disponibilité et délai de démarrage.
- Budget/alertes, contrôle de dépassement de durée et de coûts résiduels requis, en sachant qu'une alerte budgétaire **n'arrête pas** automatiquement la VM.

Docs officielles de planification :
https://docs.cloud.google.com/compute/docs/instances/schedule-instance-start-stop
https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_resource_policy
https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_resource_policy_attachment

## 7. Dépôts publics inspectés — retours réutilisables

| Dépôt | Pattern constaté dans le code | À réutiliser | À éviter ou compléter |
| --- | --- | --- | --- |
| https://github.com/st0w/spotted-llama | Terraform GCE L4 Spot, image Deep Learning, bootstrap, VPC privé, NAT, IAP/SSH | Sécurité par défaut, usage de VM éphémère | Spot peut être interrompu ; ajouter scheduling et SLO |
| https://github.com/amosproj/amos2026ss04-taskorbit-conversational-agent | Module GPU g2-standard-8, Ollama Docker, SA, GCS, script startup | Découpage service/modèle/boot | **Ne pas copier son firewall 11434 exposé 0.0.0.0/0**, ni supposer « local SSD » = disque persistant ; séparer les garanties |
| https://github.com/amayabdaniel/gpu-lab | Terraform + Terragrunt + make up/down, benchmark Ollama/vLLM | Modules + tests et réversibilité | destroy chaque soir déconseillé si les données ne sont pas externalisées |

Ces dépôts sont des **références de code**, pas des validations de compatibilité/sécurité pour MayaBank : version, licence, vulnérabilités et reproductibilité à revoir avant réutilisation.

## 8. Responsabilités GitHub MayaBank

| Zone | Dépôt canonique |
| --- | --- |
| **Document maître coût et comparatifs matériel/cloud / FinOps** | **mayabank-multicloud-migration-finops (ce fichier)** |
| ADR transverse / portefeuille / priorités | cadrage_202682030 (pointeur, pas copie des tarifs) |
| Connexion runtime applicative / Gateway / Ollama / tests D-090 | TradeOps-GenAI-Integration |
| Modules d'infrastructure cloud GPU spécifiques | Propriétaire existant à qualifier via ADR, avant écriture ; ne pas supposer automatiquement que le dépôt FinOps porte du Terraform |
| Contrats de cluster et standards IaC mutualisés | k8s-openshift-cluster-factory, si pertinent pour les modules génériques |
| Azure landing zone et IaC existante | mayabank-azure-cloud-ai-platform |

Les limites du dépôt sont régies par **architecture/ADR-001-ownership-boundaries.md** : **aucune duplication de module Terraform et aucun code applicatif ici.**

## 9. Prochaine décision et critères de sortie

**Phase A — dossier uniquement (autorisée) :**
- [x] Consolider le comparatif portable, station fixe, Azure/AWS/GCP et les scénarios horaires.
- [x] Documenter les trois dépôts publics et l'architecture hybride envisagée.
- [ ] Vérifier **tarifs officiels** en région/SKU/date, devis stations neuves et reconditionnées, FX, TVA et coûts fixes.
- [ ] Fixer usage 4h × 22j ou 4h × 30j, nombre de modèles, volume de données, contexte/tokens/s ciblé, SLO.
- [ ] Enregistrer un ADR de choix de l'implémentation Terraform et modèle d'accès réseau.

**Phase B — préparation IaC, sans coût :**
- [ ] Terraform validate/plan de VM G2, IAM least privilege, PD, VPC, schedule, budget et teardown.
- [ ] Manifests Ollama/vLLM + bootstrap idempotent + vérifications security/retention.
- [ ] Mise à jour du contrat réseau/LiteLLM et plan de tests TradeOps.

**Phase C — exécution facturable (bloquée) :**
- [ ] **Approbation explicite** du projet/facturation, région/SKU, plafond, quotas, protection réseau et procédure d'arrêt/suppression.
- [ ] Déployer et mesurer la **facture réelle**, préemption/démarrage/arrêt, p95, débit, requêtes, poids disque, risque egress.
- [ ] Rejouer D-090, documenter les limites, puis mettre à jour le TCO réel.

**Verdict à ce stade :** préserver le ZBook/CRC ; étudier une **VM GCP L4 24 Go 4h/jour** pour essai contrôlé, et comparer à une **tour RTX 3090/4090** après devis et benchmark. **Il n'y a pas d'achat ni de déploiement cloud validé aujourd'hui.**
