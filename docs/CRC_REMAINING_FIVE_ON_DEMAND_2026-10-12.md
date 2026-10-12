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