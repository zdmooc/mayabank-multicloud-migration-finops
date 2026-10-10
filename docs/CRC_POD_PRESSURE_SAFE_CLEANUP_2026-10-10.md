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
