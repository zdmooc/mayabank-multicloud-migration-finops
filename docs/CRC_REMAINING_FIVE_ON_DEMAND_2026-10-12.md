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


## 12 octobre — MQ à zéro, snapshot encore PARTIAL : correction du faux négatif de terminaison

L'opérateur a exécuté la mise en veille profonde avec les quatre acquittements. Toutes les étapes `STOP` de `mq` (payment-processing, mq-ops-api, mq-prometheus-exporter, mq, payments-db) se sont exécutées. Le script initial signalait `RUNNING_PODS_REMAIN`, alors qu'un relevé ultérieur sur `mayabank-mq-local` montre les **cinq Deployments 0/0, aucun pod listé**, et `mq-data` + `payments-db-data` toujours `Bound`. Cet échec apparaît cohérent avec un décalage entre la disparition des replicas gérés et la fin de terminaison d'un pod, mais la cause exacte n'a pas été capturée. **Snapshot `crc-deep-mq.json` = `PARK_PARTIAL` jusqu'à revalidation.** Ne pas relancer `park --project mq` : le snapshot non-RESUMED serait justement bloquant.

Aucune opération TradeOps n'a eu lieu : la boucle `for ... || break` a interrompu l'exécution après l'échec MQ ; TradeOps conserve `prometheus=1` et `postgres/qdrant/redpanda=1`.

Mesures après arrêt MQ, non stabilisées : `CPU requests=6058m (77%)`, `memory requests=18979Mi (80%)`, consommation nœud `17619Mi (74%)`. Baseline antérieure `6908m CPU requests`, `20771Mi memory requests` ; différence de réservations `-850m CPU` / `-1792Mi RAM`, correspondant aux 5 pods MQ.

Correction FinOps : `scripts/crc-deep-sleep.py` attend désormais la fin des pods encore `Running` avant `PARK_RESULT=PASS`, et expose `finalize --project mq` exclusivement pour un snapshot `PARK_PARTIAL`. **Finalize vérifie sans modifier le cluster** : UID du nœud/namespace/Deployments/Argo/PVC, zéro replica désiré et ready pour chaque workload, CronJobs suspendus, auto-sync des Argo qui étaient AUTO toujours absent, absence de pod Running ; seule l'étiquette de statut du snapshot local est modifiée en `PARKED`. Si le contrôle échoue, aucun snapshot marqué `PARKED`, et ne pas poursuivre.

Prochaine intervention opérateur :

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_deep_sleep.py
python scripts/crc-deep-sleep.py finalize --project mq

# UNIQUEMENT SI FINALIZE_RESULT=PASS
CRC_DEEP_PARK=YES CRC_ACK_DATA_LOSS=YES CRC_ACK_DOWNTIME=YES CRC_ACK_REBUILD=YES \
  python scripts/crc-deep-sleep.py park --project tradeops

oc -n mayabank-mq-local get deploy,pods,pvc
oc -n tradeops get deploy,sts,pods
oc adm top nodes
oc describe node crc | sed -n '/Allocated resources:/,/Events:/p' | head -11
```

Statuts `MQ_WORKLOADS_ZERO_PODS_ABSENT / MQ_SNAPSHOT_PARTIAL_TO_FINALIZE / TRADEOPS_NOT_TOUCHED`, pas encore `ALL_SEVEN_PARKED`. Les sources Git et les PVC subsistent. Réactivation uniquement sur ordre ultérieur.



## CRC_ALL_SEVEN_SLEEP_RUNTIME_PROVEN_20261012

**Dernière observation réelle du 12/10/2026 — tous les sept projets du périmètre mis en veille selon leurs modes respectifs.** La preuve est la sortie locale communiquée par l'opérateur et non une exécution de GitHub Actions.

- `mq` : après le `PARK_PARTIAL` initial lié à `RUNNING_PODS_REMAIN`, le correctif a été récupéré et `python scripts/crc-deep-sleep.py finalize --project mq` a rendu `FINALIZE_RESULT=PASS`, `PVC_DELETED=0`. Dans `mayabank-mq-local`, les cinq Deployments `mq`, `mq-ops-api`, `mq-prometheus-exporter`, `payment-processing`, `payments-db` sont `0/0` ; les PVC `mq-data` et `payments-db-data` restent `Bound` (capacité affichée 79Gi chacun, pas occupation disque). Le snapshot `~/.crc-capacity/crc-deep-mq.json` est à préserver.
- `tradeops` : l'opérateur a exécuté `park --project tradeops` avec acquittements de perte de données labo. `PARK_RESULT=PASS`, `PVC_DELETED=0`. Tous les 15 Deployments, dont `prometheus`, sont désormais `0/0`. Les trois StatefulSets `postgres`, `qdrant`, `redpanda` sont également `0/0`. Le snapshot `~/.crc-capacity/crc-deep-tradeops.json` est à préserver. Les pods `Completed`, `Error` et `ContainerStatusUnknown` restant listés dans `tradeops` ne sont pas des pods applicatifs Running ; leur suppression n'est pas nécessaire pour récupérer la RAM.
- Les cinq projets précédemment mis en veille (Instant Payments, Maya Freelance, Trading personnel, Decision AI/ODM, API Management) n'ont pas été réactivés. **Total : 7/7 en veille selon le périmètre d'arrêt approuvé.** Attention : cela ne signifie pas que toutes les dépendances de ces sept namespaces sont arrêtées (PostgreSQL, Kafka, monitoring, etc. restent présents sur certains projets).

**Dernier relevé de capacité :**

| Mesure | Avant arrêt MQ + TradeOps | Après deux arrêts | Variation |
|---|---:|---:|---:|
| CPU requests | 6908m (88%) | 5833m (74%) | -1075m |
| Memory requests | 20771Mi (88%) | 18211Mi (77%) | -2560Mi |
| Mémoire réellement consommée | 16582Mi (70%) | 16684Mi (70%) | +102Mi |

Les réservations sont bien libérées ; la RAM réellement consommée varie indépendamment, donc ne pas annoncer 2,5Gi de RAM physique récupérés. Le socle OpenShift demeure actif et consomme l'essentiel. Dernier CPU utilisé : `1598m (20%)`.

**Suite** : ne réactiver aucun projet sans demande explicite. Faire un contrôle de capacité/readiness à l'arrivée de la prochaine mission et reprendre uniquement les composants nécessaires. Une reprise ne garantit pas le retour des données `emptyDir`/messages MQ perdus ; reconstruction/test E2E nécessaires. Aucun namespace, PVC ou Secret n'a été supprimé par les procédures et le socle OpenShift n'a pas été mis en veille. Les anciens marqueurs historiques `OPEN/PARTIAL/PENDING` dans les sections précédentes sont supplantés par ce compte rendu final, mais la validation de reconstruction après reprise reste ouverte.

