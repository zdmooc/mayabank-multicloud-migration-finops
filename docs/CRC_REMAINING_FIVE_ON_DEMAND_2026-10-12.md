# CRC — Veille réversible des cinq derniers projets

Demande opérateur du 12 octobre 2026 : mettre les cinq projets résiduels en veille jusqu'au besoin du jour, projet ou mission. Réactiver uniquement sur ordre. Ne pas supprimer dépôts, namespaces, PVC, secrets ni images.

## Vague 1 : Trading, Decision API et API Management

Le script scripts/crc-extra-projects-mode.py implémente PLAN, PARK et RESUME avec un snapshot local indépendant par namespace dans ~/.crc-capacity/. Contrats simulés testés dans tests/test_crc_extra_projects_mode.py et CI assessment-contracts.yml.

- trading : trading-perso, Deployment rapport-horaire, CronJobs éventuellement actifs passés suspend=true avec état d'origine sauvegardé. Au diagnostic opérateur du 12/10, aucun CronJob n'était affiché. Les workflows GitHub externes ne sont pas arrêtés par ce script.
- decision : mayainsurance-decision-local, Deployment decision-api, Application Argo mayainsurance-decision automatisée ; sauvegarde et pause de spec.syncPolicy.automated avant scale.
- api : mayabank-api, Deployments api-gateway et payment-api. Kong est en mode database=off, et sa ConfigMap est conservée.

Le script refuse les namespaces autres que les trois précités, les StatefulSets, PVC, HPA, jobs actifs, données en emptyDir/PVC/CSI/hostPath, changements d'identité UID, déploiements inattendus, un Argo ApplicationSet propriétaire et l'absence d'auto-sync attendu sur Decision. Aucune mise à zéro automatique sans consentement explicite. En cas d'erreur, une tentative de rollback est prévue ; ne jamais contourner un blocage au moyen de oc scale manuel.

Commandes de précontrôle lecture seule depuis /c/workspaces/mayabank-multicloud-migration-finops :

    git pull --ff-only
    python tests/test_crc_extra_projects_mode.py
    for p in trading decision api; do
      python scripts/crc-extra-projects-mode.py plan --project "$p" || break
    done

Après précontrôle réussi et accord sur l'indisponibilité, commande PARK opérateur :

    for p in trading decision api; do
      CRC_EXTRA_PARK=YES CRC_EXTRA_ACK_DOWNTIME=YES python scripts/crc-extra-projects-mode.py park --project "$p" || break
    done

Vérification : deployments des trois namespaces à 0/0 ; CronJobs suspendus si existants ; mesure oc adm top nodes et oc describe node crc / Allocated resources. Ne déclarer PARKED que sur retour PARK_RESULT=PASS réel.

Réactivation ultérieure indépendante pour chacun, UNIQUEMENT sur demande :

    CRC_EXTRA_RESUME=YES python scripts/crc-extra-projects-mode.py resume --project trading
    CRC_EXTRA_RESUME=YES python scripts/crc-extra-projects-mode.py resume --project decision
    CRC_EXTRA_RESUME=YES python scripts/crc-extra-projects-mode.py resume --project api

RESUME restaure les réplicas initiaux, les CronJobs et la configuration Argo initiale. Les snapshots locaux ne sont pas des sauvegardes applicatives ; préserver leurs fichiers hors Git.

## Vague 2 : TradeOps et IBM MQ, protection des données

- TradeOps : sur le CRC, 14 des 15 Deployments étaient déjà à zéro. Prometheus est le seul Deployment actif ; sa TSDB est un emptyDir. Les StatefulSets postgres, redpanda et qdrant sont actifs et utilisent du stockage éphémère. Le mode normal du runbook propriétaire les conserve. Ne pas les arrêter sans sauvegarde/reconstitution validée et risque de données acceptée. Le mode deep du script propriétaire efface la TSDB de Prometheus, donc reste bloqué sans accord dédié.
- IBM MQ / EDA : cinq Deployments actifs, deux PVC Bound, deux Applications Argo automatiques (mayabank-mq-local-core et mayabank-mq-local-db). La reprise cohérente des messages/journaux MQ plus PostgreSQL n'est pas prouvée. Inspecter les files, messages en vol, dépendances R5, sauvegardes, cohérence et restauration avant un éventuel PARK coordonné. Ne pas supprimer les PVC.

Sources de référence :
https://github.com/zdmooc/TradeOps-GenAI-Integration/blob/main/docs/runbooks/CRC_TRADEOPS_PARK_RESUME.md
https://github.com/zdmooc/mayabank-ibm-mq-native-ha-openshift-eda-platform/blob/main/docs/portability/crc-rebuild/README.md

Etat : trois projets statut PARK_PREPARED_CI_TESTED / LIVE_NOT_EXECUTED ; TradeOps et MQ en PREFLIGHT_PENDING. Instant Payments et Maya Freelance restent PARKED sans reprise automatique.
LICENSE_GATE: PENDING — inventaire des droits du dépôt technique public incomplet, aucune licence modifiée.

## CRC_RUNTIME_PARK_EXTRA_THREE_20261012

**Exécution locale opérateur confirmée** : après mise à jour Git et tests offline (5 tests OK), PLAN puis PARK successifs du script `scripts/crc-extra-projects-mode.py` :
- `trading` : `PARK_RESULT=PASS`, `rapport-horaire=0/0`, `CRONJOBS=NONE`, 1 Deployment arrêté ; snapshot privé `~/.crc-capacity/crc-trading.json`.
- `decision` : `PARK_RESULT=PASS`, `decision-api=0/0`, autosync de `mayainsurance-decision` identifiée pour pause ; snapshot `~/.crc-capacity/crc-decision.json`.
- `api` : `PARK_RESULT=PASS`, `api-gateway=0/0`, `payment-api=0/0` ; snapshot `~/.crc-capacity/crc-api.json`.

**Attention à la lecture des logs** : les lignes `PARK_RESULT=PASS` et `RESUME_RESULT=PASS` imprimées **avant** `Ran 5 tests ... OK` sont les tests simulés qui emploient des fichiers temporaires, et **pas une reprise réelle sur le CRC**. Les trois PARK runtime sont prouvés par les sorties de la boucle et les contrôles `oc` qui suivent. Aucune reprise n'a été demandée.

**Mesures locales** : avant ces trois PARK : `oc adm top nodes` `RAM=17221Mi (73%)` et requests mémoire `21315Mi (90%)` à la dernière baseline ; après : `RAM=16582Mi (70%)`, CPU `2253m (28%)`, requests `20771Mi (88%)`, requests CPU `6908m (88%)`. Écarts entre mesures espacées : RAM utilisée -639Mi ; réservée -544Mi ; CPU requests -185m. **Ne pas les assimiler à des économies exclusivement imputables aux 3 PARK**.

**État consolidé** : 15 Deployments applicatifs arrêtés sur cinq projets (Instant Payments 9, Maya Freelance 2, Trading 1, Decision 1, API 2). Les bases et composants partagés de certains projets restent actifs. **Reste à préparer : TradeOps et IBM MQ** ; protection des StatefulSets sur emptyDir, messages/journaux MQ et base persistante toujours obligatoire. Statut `TRADING_DECISION_API_PARK_RUNTIME_PROVEN_20261012 / MQ_TRADEOPS_PENDING`.


## 12 octobre 2026 : autorisation explicite de perte de données LAB

L'utilisateur a demandé de mettre aussi TradeOps et IBM MQ en veille, même si les quatre messages MQ en attente, les bases locales ou les volumes `emptyDir` de laboratoire sont perdus. Objectif : comprendre les plateformes, les arrêter et les reconstruire au besoin, sans garantir une conservation transactionnelle complète. Il ne s'agit **pas d'une procédure de production**.

La procédure mise en place est `scripts/crc-deep-sleep.py` avec les modes `plan`, `park`, `resume`, les seuls `--project mq|tradeops`, et un snapshot indépendant `~/.crc-capacity/crc-deep-<project>.json`.

Contrôles : mono-nœud CRC Ready ; allowlists exactes des Deployments, StatefulSets et PVC ; HPA/DaemonSet/Jobs actifs interdits ; conservation des UID du nœud, namespace, workloads, PVC et Applications Argo ; arrêt automatique des CronJobs présents avec restauration ultérieure ; pause des Applications Argo automatisées (deux requises pour MQ). Aucun `delete`, `oc apply`, nettoyage de PV/PVC/Secrets, ni modification du socle OpenShift.

Ordre MQ : payment-processing puis mq-ops-api, exporter, mq et payments-db. Les PVC `mq-data` et `payments-db-data` restent Bound. Après scale à zéro, l'absence de donnée/message ne constitue pas un échec selon l'autorisation du lab. Ordre TradeOps : tous les Deployments (14 déjà à zéro, Prometheus seul actif) puis qdrant, redpanda et postgres. Les fichiers TSDB/PostgreSQL/Redpanda/Qdrant sur `emptyDir` peuvent disparaître : toute reprise fonctionnelle de leurs données est un **exercice de reconstruction**.

Depuis Git Bash :

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_deep_sleep.py
python scripts/crc-deep-sleep.py plan --project mq
python scripts/crc-deep-sleep.py plan --project tradeops
```

Après accord explicite et sortie PLAN conforme, lancer MQ puis TradeOps, avec arrêt au premier échec :

```bash
for p in mq tradeops; do
  CRC_DEEP_PARK=YES CRC_ACK_DATA_LOSS=YES \
  CRC_ACK_DOWNTIME=YES CRC_ACK_REBUILD=YES \
    python scripts/crc-deep-sleep.py park --project "$p" || break
done

for ns in mayabank-mq-local tradeops; do
  echo "== $ns =="
  oc -n "$ns" get deploy,sts,pods,pvc
done
oc adm top nodes
oc describe node crc | sed -n '/Allocated resources:/,/Events:/p' | head -11
```

**Verdict `PARK_RESULT=PASS` requis séparément pour MQ et TradeOps**, avec réplicas zéro et aucun pod Running. Si `PARK_PARTIAL` : ne jamais relancer un PARK par-dessus son snapshot ; vérifier état et décider du mode de reprise. Le script n'effectue pas de rollback aveugle des StatefulSets éphémères.

À la demande uniquement, reprendre un projet avec :

```bash
CRC_DEEP_RESUME=YES python scripts/crc-deep-sleep.py resume --project mq
CRC_DEEP_RESUME=YES python scripts/crc-deep-sleep.py resume --project tradeops
```

La reprise tente de restaurer les réplicas et attend la readiness des bases/queues avant de relancer les consommateurs et la synchronisation automatique Argo. **Elle ne restaure pas les données perdues**. Le test métier JMS, les files, les règles de trading et les pipelines nécessitent éventuellement reconstruction/rejeu depuis les GitHub repos originaux.

**Statut de ce document : `DEEP_PARK_IMPLEMENTED / CRC_EXECUTION_PENDING`** jusqu'à réception des sorties de l'opérateur.
**LICENSE_GATE: PENDING** pour la licence racine et provenance globale du dépôt public ; aucun tiers n'est ajouté, aucune licence attribuée ni changée.
