# Auditeur universel OpenShift / CRC — projet / namespace

**Version :** 1.0 (10 octobre 2026)

Ce paquet comprend :
- `audit_openshift_project.py` : script Python autonome, bibliothèque standard uniquement ; **aucune mutation Kubernetes** ;
- `test_audit_openshift_project.py` : quatre tests unitaires sur des données Kubernetes entièrement synthétiques.

## Pré-requis

- Python 3.10+ (testé avec Python 3.11 ici ; prévu compatible Windows Python 3.14).
- OpenShift CLI `oc` accessible dans Git Bash et session `oc login` déjà valide.
- Droits **lecture seule** sur le ou les namespaces à auditer. Certaines ressources (PV, Applications Argo CD) nécessitent des droits supplémentaires : les preuves manquantes seront signalées, pas contournées.

## Démarrage — Git Bash Windows

Option recommandée : utiliser directement le fichier déjà commité dans GitHub après `git pull`. Option autonome : extraire le ZIP et copier les deux fichiers `.py` dans le dossier `scripts/` ; dans ce cas conserver leur nom d’origine. Se placer dans le dépôt qui ignore **`evidence/local/`**.

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python scripts/audit-openshift-project-readonly.py --namespace tradeops --repo-root /c/workspaces/TradeOps-GenAI-Integration
```

Autres exemples :

```bash
# Wero historique, arrêter à l'inventaire : le script ne redémarre aucun pod.
python scripts/audit-openshift-project-readonly.py --namespace wero-poc

# Projet réparti sur plusieurs namespaces
python scripts/audit-openshift-project-readonly.py \
  --namespace instant-payments-local \
  --namespace shared-platform-services

# Se limiter à la couche du projet lorsque la lecture des Applications Argo est interdite
python scripts/audit-openshift-project-readonly.py --namespace mayabank-mq-local --no-gitops
```

Le script affiche un résumé et le répertoire privé sous `evidence/local/private-openshift-audit-<UTC>/` ; pour l'inspecter :

```bash
OUT="$(ls -dt evidence/local/private-openshift-audit-* | head -1)"
cat "$OUT/SUMMARY.txt"
cat "$OUT/tradeops.report.md"
```

Le rapport structuré correspondant est `tradeops.report.json`. **Ne pas pousser les rapports sur GitHub sans une revue des noms internes d'applications, des images et des PV.** Les rapports ne contiennent pas de valeurs d'environnement, de Secret ou de ConfigMap et n'exportent pas les objets JSON OpenShift bruts.

## Couverture

| Axe | Contrôles | Limites |
|---|---|---|
| État du namespace | existence, principaux objets | pas de preuve de disponibilité métier |
| Workloads | Deployments, StatefulSets, DaemonSets, replicas, pods, images, sondes | contrôleurs personnalisés non inventoriés |
| Capacité | requests, sample `oc adm top` CPU/RAM, matching exact | pas de P95, pics ou courbes historiques |
| Résilience | restarts, OOM, HPA, PDB, readiness, événements Warning | pas de chaos test ou test charge |
| Données | PVC, état Bound, capacité demandée, reclaim PV, emptyDir | occupation réelle, cohérence et restore NON PROUVÉS |
| Sécurité | container privilégié, NetworkPolicy, quotas, LimitRanges, Service types | pas d'audit RBAC complet, scanner CVE, pentest |
| Réseau | Services/sélecteurs, Routes/Ingress (comptes), hôtes DB littéraux autorisés | aucune session SQL ou connectivité prouvée |
| GitOps | applications Argo associées au namespace, Sync, Health, auto-sync, conditions | API peut être inaccessible ; pas de mutation Argo |
| Git et CI optionnel | détection de fichiers du dépôt local, HEAD, worktree dirty count | **pas** de preuve de bonne qualité du code/test |
| Green IT | requests/usage instantanés et risque de ressources inactives | **pas de kWh/CO2 chiffré sans modèle et données validés** |

## Règles de sécurité

- Le script exécute uniquement `oc whoami`, des `oc get -o json`, et `oc adm top pods --containers`.
- Pas de `oc exec`, `oc scale`, `oc apply`, `oc delete`, `oc patch`, `oc debug`, `pg_dump`, `psql`, ni d'accès aux valeurs de Secrets/ConfigMaps.
- Par sécurité le dossier de sortie doit commencer par `evidence/local/private-`, avec `umask` à configurer localement si nécessaire.
- Les PV peuvent être restreints en lecture RBAC ; dans ce cas le reclaim est `UNKNOWN` et non une estimation.
- Le code ne prétend pas qu'un objet `Ready` est utilisé en SQL, qu'un PVC Bound est sauvegardé, ou qu'un `emptyDir` est récupérable après recréation.

## Tests hors cluster

```bash
python tests/test_openshift_project_audit.py
```

**Statut :** tests synthétiques réussis dans l'environnement de préparation ; exécution sur un CRC réel et certification de chaque analyse restent à réaliser.

Si tu utilises plutôt le ZIP autonome hors dépôt, lance `python audit_openshift_project.py --namespace tradeops` depuis la racine du dépôt et `python test_audit_openshift_project.py` pour les tests.