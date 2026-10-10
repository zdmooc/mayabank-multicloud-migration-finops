# CRC OpenShift — Pod pressure, mémoire et stratégie de nettoyage sécurisé

Date : 2026-10-10 — **étude sans suppression**.

## Point d'entrée : capture de l'opérateur

La capture CRC reçue le 10 octobre affiche : CPU **1.68 / 8 (21 %)**, mémoire **19.25 / 23.46 GB (82 %)**, pods **239 / 269 (88.8 %)**, nœuds **1 / 1 Ready**.

- **239 < 269** : la limite affichée n'est **pas** dépassée ; il reste 30 emplacements d'après le tableau de bord. Le compteur n'est pas une preuve de 239 pods effectivement actifs ni une mesure de CPU.
- 82 % de mémoire est une pression potentielle et réclame un suivi (OOM, pods Pending, capacité hôte Windows, VM CRC). Trois redémarrages du HP/CRC ont été rapportés mais la capture seule ne permet pas d'attribuer l'instabilité au quota de pods.
- Les **27 objets Pod historiques Wero** (`*-N-build`, 24 Completed, 3 Error) ne sont **pas** 27 réplicas applicatifs et ne doivent **pas** être assimilés à 27 places actives pouvant être libérées. `wero-poc` garde 12 Deployments à 0 et PVC PostgreSQL Bound/Retain.
- Namespace Wero `wero-poc` distinct de `instant-payments-local` (Wero UI et traitements Instant Payments actifs) : ne pas confondre les deux.

## Audit dédié à exécuter avant toute opération

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only &&
python tests/test_crc_pod_pressure_readonly.py &&
python scripts/audit-crc-pod-pressure-readonly.py
```

L'auditeur collecte via commandes **en lecture seule** :

1. `oc get pods -A -o json` : phases Running/Pending/Succeeded/Failed/Unknown ; distinction objets historiques vs pods non terminés affectés au nœud et classement par namespace.
2. `oc get nodes -o json` : capacité et nombre `allocatable.pods`, avec calcul `assigned_nonterminal`/nœud. Les compteurs peuvent différer du dashboard ; ne jamais forcer la correspondance.
3. `oc adm top nodes` (best-effort) : occupation ponctuelle CPU/RAM, sans déduire un pic ni expliquer à lui seul les gels du PC.
4. Identification **métadonnée seulement** de pods `*-N-build` historiques et `emptyDir` montés sur les répertoires de données TradeOps (postgres/Redpanda/Qdrant/Prometheus).

**Aucune commande** `oc apply`, `delete`, `patch`, `scale`, `exec`, `get secret`, `docker prune`, `crc stop`, `crc delete`, SQL, backup ou suppression. Le rapport est imprimé sur stdout ; le script n'écrit aucun fichier et ne lit aucune valeur de Secret.

Lignes utiles à partager : `NODE=...`, tableau `NAMESPACE...`, `POD_PHASE_COUNTS`, `BUILD_NAMESPACE` et `TRADEOPS_EPHEMERAL_MOUNT...`. Les noms de workloads restent à vérifier avant de les diffuser publiquement.

## Séquence de nettoyage — propositions soumises aux preuves et autorisation séparée

| Classe | Exemple | Politique actuelle |
| --- | --- | --- |
| Pods / builds historiques `Succeeded`, `Failed` | `wero-poc` `api-gateway-N-build` | **Candidats à archivage uniquement** ; objets terminés ne garantissent aucun gain de slots. Décider précisément après mesure taille images/BuildHistory. |
| Applications Wero | 12 Deployments déjà 0 | Gain CPU/mémoire actif **presque nul** ; ne pas effacer PVC, BuildConfig, ImageStream ni namespace sans reprise validée. |
| Pods actifs en surnombre | Un namespace ayant beaucoup de `Running` ou `Pending` | Diagnostiquer contrôleurs, ReplicaSets, quotas, Jobs, Operators avant tout plan de scale/restart. |
| Projets actifs | `instant-payments-local`, `mayabank-mq-local`, `tradeops`, `maya-freelance` | **PROTÉGÉS**, pas de suppression/scale sans procédure propre au produit et retour arrière testé. |
| Système OpenShift | `openshift-*`, `kube-*` | **PROTÉGÉ**, pas de nettoyage aveugle de pods/Operators. |
| TradeOps data | PostgreSQL, Redpanda, Qdrant en `emptyDir` dans le profil CRC | P0 : sauvegarde ou reconstruction vérifiée avant changement de pod. **PARK ne prouve pas CRC STOP sans risque**. |

Ne pas recommander `oc delete pods --all -A`, `oc delete ns wero-poc`, `docker system prune -a`, `docker volume prune`, ou nettoyage forcé des logs/registry.

## Bascule CRC → Kind et récupération mémoire

Le runbook `zdmooc/cadrage_202682030/architecture/LOCAL_DUAL_PLATFORM_CRC_KIND_SWITCHING_2026-09-28.md` et le H2 Kind↔CRC↔Kind du Lakehouse ont déjà prouvé une **bascule de plateformes**, pas la reprise de Wero.

Le profil Kind Wero a passé les tests de syntaxe, mocks et rendu Kustomize le 10 octobre, mais aucune image OCI n'a été reconstruite et aucun E2E Kind effectué. Docker Desktop / Podman étaient arrêtés dans WSL2. La bascule nécessite l'arrêt de CRC, qui a d'autres projets actifs avec des données possiblement éphémères. Ne pas arrêter CRC tant que les données requises et l'état de reprise de TradeOps et des autres services ne sont pas clarifiés.

**Décision maintenue : INVENTORY_FIRST / NO_DELETE / DO_NOT_STOP_CRC_AUTOMATICALLY.**

## Résultat réel opérateur — 2026-10-10 16h

Le test local `python tests/test_crc_pod_pressure_readonly.py` a réussi (`Ran 2 tests ... OK`). Le script `audit-crc-pod-pressure-readonly.py` a ensuite produit le premier inventaire réel du CRC sur le HP :

```text
SOURCE_POD_OBJECTS_ALL=269
SOURCE_POD_OBJECTS_NONTERMINAL=149
POD_PHASE_COUNTS={"Failed": 29, "Running": 149, "Succeeded": 91}
NODE=crc ASSIGNED_ACTIVE_OR_PENDING=149 ALLOCATABLE_PODS=250 REMAINING=101
oc adm top nodes: crc 1901m CPU (24%), 19835Mi mémoire (84%)
```

**La limite de slots du nœud n'est PAS dépassée : 149/250, soit 59,6 %.** Les 120 pods `Succeeded/Failed` sont des objets terminés, pas 120 pods en consommation active de CPU/RAM ; il n'y avait aucun Pending sur cet instantané. Le dashboard antérieur indiquait `239/269`, mais son périmètre/horodatage n'a pas été concilié avec ce relevé direct : **ne pas présenter le dénominateur 269 comme le maximum allocatable de 250**, et ne pas les comparer comme s'il s'agissait de la même métrique.

Namespaces actifs les plus nombreux : `instant-payments-local` 19 (45 objets historiques terminés), `openshift-pipelines` 18, `openshift-monitoring` 12, `openshift-gitops` 8, `mayabank-mq-local` 5, `tradeops` 4, `maya-freelance` 3. `wero-poc` **0 actif / 27 historiques**, `mayabank-mq-build` **0 actif / 8 historiques**. L'outil identifie **92 builds historiques terminés** au total (instant-payments 36, Wero 27, TradeOps 10, mayabank-mq-build 4 et autres) parmi les 120 objets terminés. La suppression de ces historiques pourrait diminuer le volume d'objets de l'API Kubernetes, mais ne libère pas des slots de pods actifs et aucun gain RAM n'est établi.

TradeOps : pods PostgreSQL `postgres-0` sur `/var/lib/postgresql/data` en `emptyDir`, Redpanda `redpanda-0` sur `/var/lib/redpanda/data` et `/etc/redpanda`, Prometheus sur `/prometheus` sont **Running**. Le rapport donne 4 montages observés, non 4 sauvegardes ni 4 bases. Le risque P0 de redémarrage/recréation de ces pods reste ouvert.

**Prochain gate = mesurer la RAM par pod avant d'éditer un plan de réduction :**

```bash
oc adm top pods -A --sort-by=memory | head -n 35
oc adm top pods -A --sort-by=cpu | head -n 25
oc get pods -A --field-selector=status.phase=Pending -o wide
oc get events -A --field-selector type=Warning --sort-by=.metadata.creationTimestamp | tail -n 35
```

Les relevés `oc adm top` sont des instantanés et ne permettent pas seuls d'attribuer la cause des gels Windows. Chercher aussi côté hôte Windows l'utilisation RAM et les erreurs/événements WSL/Hyper-V. **Aucun nettoyage n'a été effectué. Décision : RAM_DIAGNOSTIC_FIRST / INVENTORY_ONLY / NO_DELETE.**

## Inventaire additionnel des objets non-Pod — observé le 10 octobre 2026

L'utilisateur a exécuté en direct une boucle `oc get <resource> -A -o json | jq '.items | length'` et a obtenu :

| Ressource | Total observé |
| --- | ---: |
| Builds | 95 |
| BuildConfigs | 24 |
| ImageStreams | 85 |
| Jobs | 7 |
| CronJobs | 2 |
| ReplicaSets | 396 |
| PVC | 15 |
| Routes | 41 |
| **Somme de ces huit familles** | **665** |

**Ces 665 objets ne sont ni 665 ressources anciennes ni 665 objets supprimables** ; les catégories peuvent contenir objets actifs, rollback, propriétés de la plateforme et stockage critique.

Les listes suivantes `oc get builds` et `oc get replicasets` sont chacune tronquées par `head -n 80`. L'erreur Git Bash `jq: error: writing output failed: Invalid argument` en fin de sortie est compatible avec une fermeture anticipée du tube par `head` : cela ne démontre pas une corruption du cluster. Les listes ne prouvent donc pas le nombre **total** de Builds terminés ou de ReplicaSets à zéro. Parmi les premières lignes, des Builds terminés remontent à septembre pour Instant Payments, Wero, MQ, TradeOps, Maya Freelance, Insurance ; les ReplicaSets à 0 montrent beaucoup de révisions Instant Payments et Maya Freelance. Les contrôleurs encore actifs peuvent toujours les utiliser pour rollback.

### Nouvel audit de métadonnées sans suppression

Pour obtenir les décomptes **complets**, avec distinction d'objets actifs / historiques et propriétaire du ReplicaSet, un script Python en lecture seule est maintenant disponible dans ce dépôt :

- `scripts/audit-crc-legacy-objects-readonly.py` : `oc get` métadonnées de neuf catégories (huit objets ci-dessus + Deployments pour vérifier les propriétaires), aucune lecture de Secret et aucune mutation.
- `tests/test_crc_legacy_objects_readonly.py` : jeux de données synthétiques, révisions liées à un Deployment, anciens Builds, PVC et CronJobs.
- `.github/workflows/assessment-contracts.yml` : validation hors cluster.

Commande proposée à l'opérateur depuis Git Bash :

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only &&
python tests/test_crc_legacy_objects_readonly.py &&
python scripts/audit-crc-legacy-objects-readonly.py \
  | tee /c/workspaces/crc-legacy-objects-20261010.txt
```

Rapport attendu : `TOTAL_REPLICASETS`, `REPLICASETS_ZERO_DESIRED_AND_OBSERVED`, `REPLICASETS_ZERO_14_DAYS_OR_OLDER`, `REPLICASETS_ZERO_WITH_EXISTING_DEPLOYMENT`, `BUILDS_TERMINAL`, répartition complète par namespace, plus `SOURCE_DELETION_APPROVED=false`. Le script ne mesure **pas** les octets libérables dans le registry et ne teste **pas** les sauvegardes. Age de 14 jours = simple indicateur, jamais une règle automatique de suppression.

**Recommandation:** rechercher les anciennes révisions **applicatives** à zéro, vérifier leur présence dans les Deployments existants et le besoin de rollback, puis seulement préparer une réduction d'historique par produit avec procédure approuvée. Conserver les PVC, le namespace Wero et les services `openshift-*` intacts. La RAM kube-apiserver (~3486Mi) et Prometheus (~1631Mi) reste une investigation séparée de l'hygiène des anciens objets.

## 2026-10-10 14:30 UTC — audit complet historique hors Pods

Exécution **réelle** de `python scripts/audit-crc-legacy-objects-readonly.py` sur le HP (3 tests synthétiques locaux : **OK**) :

| Objet / classe | Mesure |
|---|---:|
| Builds | 95, **tous terminal** |
| Builds terminés depuis ≥14 jours | **55** |
| BuildConfigs | 24 |
| ImageStreams | 85, dont **60 dans `openshift`** (namespace système : hors nettoyage automatique) |
| Jobs | 7, **tous terminal** |
| CronJobs | 2, **0 suspendu** |
| ReplicaSets | 396 |
| ReplicaSets désirés=0 et observés=0 | **282** |
| ReplicaSets à 0 depuis ≥14 jours | **186** |
| ReplicaSets à 0 appartenant à un Deployment existant | **282/282** |
| ReplicaSets orphelins détectés | **0** |
| PVC | **15, tous Bound** |
| Routes | 41 |

Ces huit familles font **665 objets**, dont **282 ReplicaSets inactifs + 95 Builds terminés + 7 Jobs terminés = 384** candidats à **revue** (non pas suppression). Les critères `>=14 jours` ne suffisent jamais à autoriser le retrait, et aucun octet libérable n'a été mesuré.

### Classement des historiques et politique avant retrait

| Namespace | RS 0 | RS 0 ≥14j | Builds terminés | Builds ≥14j | Classement |
|---|---:|---:|---:|---:|---|
| `tradeops` | 52 | 30 | 10 | 4 | PROTECTED (P0 données `emptyDir`, revenir sur rollback) |
| `instant-payments-local` | 51 | 17 | 37 | 13 | PROTECTED (runtime GitOps) |
| `wero-poc` | **38** | **38** | **27** | **27** | ARCHIVE FIRST, NO_DELETE (Kind reconstructibilité non prouvée) |
| `mayabank-mq-local` | 24 | 24 | 0 | 0 | PROTECTED (messaging) |
| `maya-freelance` | 11 | 11 | 5 | 5 | PROTECTED |
| `mayabank-api` | 8 | 0 | 2 | 0 | REVIEW (récents, faible priorité) |
| `mayainsurance-decision-local` | 5 | 3 | 6 | 4 | REVIEW du propriétaire/dépôt et usage réel |
| `mayabank-mq-build` | 0 | 0 | 5 | 2 | REVIEW des builds et images, distinct de MQ runtime |

**Plan conditionnel :**
1. Relever les politiques `revisionHistoryLimit`, identités des Deployments propriétaires, annotations de révision/rollback et imageIDs référencés par les ReplicaSets. Éviter `oc delete rs` ad hoc : le gestionnaire de Deployment est responsable du cycle de vie des révisions, et les changements doivent être alignés dans GitOps.
2. Pour Builds et Jobs terminal, identifier provenance, logs/preuves de build, références ImageStreams et politique d'archivage avant décision de conservation ou retrait.
3. Pour Wero, archiver 38 RS + 27 Builds comme preuve et **maintenir le namespace, ses ImageStreams/BuildConfigs/Routes et son PVC** jusqu'à démonstration de reconstruction sur Kind. Une fois la reconstruction prouvée, décider d'un retrait source séparé : pas de suppression anticipée de rollback.
4. Mesurer indépendamment l'espace disque (images registry/PVC/hostpath) ; ne pas annoncer de gain RAM de la suppression de 384 métadonnées. L'occupation réelle mémoire 84 % vient essentiellement des workloads actifs (kube-apiserver ~3486Mi, Prometheus ~1631Mi).

**Aucune action destructive exécutée / données source conservées / NO_DELETE.**

## Validation revisionHistoryLimit live — 10/10/2026

L'opérateur a relevé la politique **live** de 50 Deployments au total dans quatre namespaces : `instant-payments-local` (18, tous à 1, `revisionHistoryLimit=3` pour 8 services métiers et `10` pour 10 autres), `mayabank-mq-local` (5, tous à 1, limite 10), `tradeops` (15, 14 à 0 et Prometheus à 1, limite 2 pour dix services métier et 10 pour cinq autres), `wero-poc` (12, tous à 0, limite 10).

**Révision de la stratégie :** toutes les 282 ReplicaSets à 0 recensées restent rattachées à des Deployments existants. Le nombre global de RS à 0 n'est pas comparable directement à une seule valeur de `revisionHistoryLimit`. Une RS à zéro peut inclure la révision actuelle d'un Deployment arrêté ; compter par propriétaire UID et tenir compte de la progression du rollout, puis distinguer révision courante et ancien rollback avant toute réduction. Ne pas modifier `revisionHistoryLimit` en direct, afin d'éviter le drift GitOps et la suppression automatique de révisions nécessaires.

`tradeops` conserve 52 RS à zéro malgré une limite 2 sur la plupart des services : cela justifie un diagnostic **par Deployment** des RS réelles, de leur révision et du statut rollout (pas une suppression automatique). `wero-poc` garde 38 RS à zéro, 12 Deployments SCALE0 et un PVC PostgreSQL Bound/Retain ; reconstruction Kind et retention des données non validées, donc NO_DELETE.

Commande de diagnostic sans mutation :

```bash
oc get deploy,rs -A -o json | jq -r '
  .items as $items
  | [$items[] | select(.kind == "ReplicaSet")] as $allrs
  | ("NAMESPACE\tDEPLOYMENT\tDESIRED\tREVISION_LIMIT\tRS_TOTAL\tRS_ZERO\tRS_NONZERO\tPROGRESSING_REASON"),
    (
      $items[]
      | select(.kind == "Deployment")
      | select(.metadata.namespace == "wero-poc" or .metadata.namespace == "tradeops" or .metadata.namespace == "instant-payments-local" or .metadata.namespace == "mayabank-mq-local")
      | . as $d
      | [$allrs[] | select(.metadata.namespace == $d.metadata.namespace and any(.metadata.ownerReferences[]?; .kind == "Deployment" and .uid == $d.metadata.uid))] as $owned
      | [$owned[] | select((.spec.replicas // 1) == 0 and (.status.replicas // -1) == 0)] as $zero
      | [$d.metadata.namespace, $d.metadata.name, ($d.spec.replicas // 1), ($d.spec.revisionHistoryLimit // 10), ($owned | length), ($zero | length), (($owned | length) - ($zero | length)), ([$d.status.conditions[]? | select(.type=="Progressing") | .reason][0] // "UNKNOWN")]
      | @tsv
    )
'
```

Cette sortie ne permet pas à elle seule d'autoriser un nettoyage. La RAM à 84% est un problème séparé, porté surtout par des pods en fonctionnement.

## 2026-10-10 — contrôle des ReplicaSets par Deployment : aucune dérive manifeste

Un second contrôle réel sur HP a corrélé les ReplicaSets aux Deployments via **owner UID**, sans modification des ressources, dans `tradeops` et `wero-poc`.

- **TradeOps : 15 Deployments, 52 ReplicaSets à zéro.** Quatorze Deployments ont 0 réplica ; Prometheus garde 1. Dix services utilisant `revisionHistoryLimit=2` ont deux ou trois ReplicaSets chacun (le plus souvent trois = révision courante + deux précédentes), tous à zéro lorsqu'ils sont scale0. Pour les limites 10 : `litellm` 11 RS (tous à zéro), `ai-access-policy` 6, `grafana` 3, `otel-collector` 2 et `prometheus` 2 dont une RS non nulle. Pas de dépassement manifeste de la politique de conservation. `status.conditions[type=Progressing].reason=NewReplicaSetAvailable` est une preuve historique de rollout, **pas** de disponibilité actuelle.
- **Wero historique : 12 Deployments scale0, 38 ReplicaSets à zéro.** Chaque Deployment a entre 2 et 6 RS et une limite de 10 anciennes révisions. Les 38 RS sont toujours liés par owner UID à leurs Deployments et ne sont pas une anomalie de rétention démontrée.

**Rectification de la priorité de nettoyage :** ne pas diminuer `revisionHistoryLimit` ni effacer directement ces 90 RS ; la majorité relève d'un historique de rollback conforme, et certains incluent vraisemblablement la révision courante scale0. Les **282 RS à zéro** recensés sur tout CRC ne sont pas équivalents à 282 anciens artefacts sans utilité. Le bénéfice RAM immédiat de retirer cet historique n'est pas démontré.

**Suite prioritaire :** audit de BuildConfig `successfulBuildsHistoryLimit` et `failedBuildsHistoryLimit` (valeurs live / propriétaire GitOps), métadonnées ImageStream et consommation réelle du registre/PVC ; investigation RAM de kube-apiserver (~3486Mi) et Prometheus (~1631Mi), sans modifier les opérateurs. Wero reste **NO_DELETE** tant que les six images OCI et la reconstruction Kind ne sont pas prouvées.

## 2026-10-10 — live BuildConfig retention policy 24/24

Operator read-only `oc get buildconfigs -A -o json | jq` revealed **all 24 BuildConfigs have explicit history limits**, **23 configured with `successfulBuildsHistoryLimit=5` and `failedBuildsHistoryLimit=5`**, while `mayabank-mq-build/payments` has **2/2**. This is per success/failure group, **not a single combined quota**, and never authorizes pruning from a mere age/count match. Previous cluster audit: 95 terminal Builds, 55 aged ≥14 days. Aggregate 95 does not establish a breach of any individual BuildConfig limit.

Extended existing `scripts/audit-crc-legacy-objects-readonly.py` to report a new **`=== BUILDCONFIG HISTORY LIMITS (READ-ONLY, PER CONFIG) ===`** table: each BuildConfig, its Complete/Failed+Error+Cancelled counts, both live retention limits, other-phase builds, excess only as **review signals**, and any Builds whose BuildConfig metadata link is missing/unmatched. It joins via explicit `openshift.io/build-config.name` metadata, not guessed name-prefix mapping. Synthetic regression tests `tests/test_crc_legacy_objects_readonly.py` now cover status grouping, per-type limit comparison and missing/deleted BuildConfig links. No changes to workloads, no Secret access, no delete commands.

Next operator local verification:

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only &&
python tests/test_crc_legacy_objects_readonly.py &&
python scripts/audit-crc-legacy-objects-readonly.py | tee /c/workspaces/crc-legacy-objects-20261010.txt
```

The action above **only inventories metadata**; no cleanup candidates are promoted automatically. Real per-BC counts must be observed before proposing any history shrink. Target Wero cannot be retired until cold Kind reconstruction and data-retention gates pass. The HP memory pressure (84%, apiserver ~3.5 GiB, Prometheus ~1.6 GiB) remains separate.

## 2026-10-10 — résultat réel des limites Builds

Audit local exécuté et 4 tests OK. 95 Builds terminés / 24 BuildConfigs ; **0 dépassement de la limite des succès**, **0 dépassement de la limite des échecs/annulations** pour chaque BuildConfig. Aucun Build sans lien BuildConfig et aucun lien vers un BuildConfig disparu. Wero : 27 Builds terminés (24 réussis, 3 non réussis), six politiques 5/5 respectées. **BUILD_RETENTION_COMPLIANT — aucun nettoyage correctif justifié.** Décision : conserver l'historique ; pas de suppression automatique ; pas d'économie de RAM mesurée. Prochaine enquête : espace réellement utilisé dans le registre d'images, puis mémoire kube-apiserver et Prometheus. Wero reste NO_DELETE.

## 2026-10-10 — diagnostic containerStatuses API Server et Prometheus

L'opérateur a interrogé `oc get pod -o json` en lecture seule sur les deux premiers consommateurs mémoire, après son relevé `oc adm top pods -A` :

- `openshift-kube-apiserver/kube-apiserver-crc` : **3486Mi** pour le **pod entier** selon `oc adm top`, **5 containers**, tous `restartCount=17`, tous `lastState={}`. Container principal request `265m CPU, 1Gi mémoire`; auxiliaires : trois requests `50Mi` + un `50Mi` supplémentaire (quatre à 50Mi). Aucun champ `limits` dans les ressources affichées.
- `openshift-monitoring/prometheus-k8s-0` : **1631Mi** au niveau **pod entier**, **6 containers**, tous `restartCount=16`, tous `lastState={}`. Container Prometheus principal request `70m CPU, 1Gi mémoire`; autres : 10Mi config-reloader, 25Mi thanos, 15Mi proxy web, 15Mi autre proxy, 10Mi proxy thanos. Aucun `limits` affiché.

**Interprétation prudente** : une request mémoire de 1Gi **n'est pas une limite de consommation ni une preuve d'OOM**. Comparer `top pod` (somme des containers) uniquement aux requests **agrégées** du pod, et préférer le prochain `oc adm top pods -A --containers --sort-by=memory` pour attribuer la RAM à chaque container. La synchronisation de cinq containers à 17 redémarrages et six containers à 16 suggère des événements communs (pod runtime/VM/nœud), mais **ne prouve ni crash du système ni OOM**. Ces comptes peuvent couvrir toute la durée de vie des pods, pas uniquement les trois reboots récents du PC. `lastState={}` ne contient pas la cause du dernier arrêt; les événements historiques et logs peuvent avoir expiré.

Contrôles suivants, **read-only** :

```bash
oc adm top pods -A --containers --sort-by=memory | sed -n '1,40p'
oc get nodes -o json | jq -r '
  .items[] | .metadata.name as $node
  | .status.conditions[]?
  | select(.type=="MemoryPressure" or .type=="DiskPressure" or .type=="PIDPressure" or .type=="Ready")
  | [$node,.type,.status,.reason,(.lastTransitionTime // "unknown")] | @tsv
'
for ref in "openshift-kube-apiserver kube-apiserver-crc" "openshift-monitoring prometheus-k8s-0"; do
  read -r ns pod <<< "$ref"
  oc -n "$ns" get pod "$pod" -o json | jq -r '
    "POD=\(.metadata.namespace)/\(.metadata.name) CREATED=\(.metadata.creationTimestamp)",
    (.status.containerStatuses[]? |
      "CONTAINER=\(.name) RESTARTS=\(.restartCount) CURRENT_STARTED=\(.state.running.startedAt // "unknown") LAST_TERMINATED_REASON=\(.lastState.terminated.reason // "unknown") LAST_EXIT=\(.lastState.terminated.exitCode // "unknown")")
  '
done
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory,LastBootUpTime'
```

Le dernier relevé Windows exprime la mémoire en **Kio** ; ne pas comparer directement les valeurs Windows en Kio aux MiB du `oc adm top`. En complément de l'état des nœuds, garder les journaux d'événements Windows si le HP a réellement gelé. Ne pas modifier les ressources du kube-apiserver, les quotas Prometheus ou les Operators tant que la causalité n'est pas prouvée.

**Statut : mémoire élevée confirmée / anomalie ou OOM non prouvés / investigation RAM ET hôte ouverte / NO_MUTATION.**
