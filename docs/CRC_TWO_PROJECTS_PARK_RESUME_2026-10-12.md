# CRC — Mise en veille réversible en deux vagues : Instant Payments puis Maya Freelance

**Demande opérateur :** mettre en veille Instant Payments puis Maya Freelance jusqu'à demande de reprise. **Aucune opération live n'est accomplie par ce document ni par GitHub Actions.** Utiliser les commandes depuis le PC de l'opérateur connecté au CRC de test.

## Périmètre et effet réel

- Vague A : `instant-payments-local`. **Neuf Deployments applicatifs** répliqués 1→0 si le contrôle courant les retrouve tous. PostgreSQL, MongoDB, Kafka et autres StatefulSets/PVC/services partagés restent actifs. L'interface `wero-ui` est celle d'Instant Payments, **pas** le namespace Wero historique `wero-poc`. Le script conserve la configuration Argo avant pause d'auto-sync et la restaure au RESUME.
- Vague B : `maya-freelance`. Seulement `n8n` et `maya-dashboard` 1→0 si le contrôle courant les retrouve. Le Deployment PostgreSQL et le PVC `postgres-data` restent en service. Le script vérifie la référence PVC et le statut Bound avant PARK. n8n conserve sa clé `N8N_ENCRYPTION_KEY` dans son Secret, qui n'est pas ouvert ou modifié par le script.
- **Ces deux mises en veille ne sont pas des arrêts complets de namespaces** ; les données et bases continuent à demander et consommer des ressources.
- Les deux opérations rendent indisponibles les parcours applicatifs. Éviter transactions de paiement/consommateurs Kafka en cours et exécutions n8n/workflows actifs. Préparer une fenêtre d'inactivité ; les scripts ne peuvent pas prouver une quiescence métier.
- Mise en veille non autorisée sur un cluster de production. Aucun `crc stop`, suppression de PVC, Secret, Route, namespace, StatefulSet ou pod requis.

## Préflight initial, toujours en lecture seule

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_application_mode.py
python tests/test_crc_maya_freelance_mode.py

# conserver un baseline avant les deux vagues
oc get nodes
oc adm top nodes
oc -n instant-payments-local get deploy,sts,pvc
oc -n maya-freelance get deploy,pvc
python scripts/crc-application-mode.py plan --assess-tmp-only
python scripts/crc-maya-freelance-mode.py plan
```

Attendus Wave A : `ELIGIBLE_DEPLOYMENTS_COUNT=9`, `APPS_TO_PARK` couvre EXACTEMENT `payment-orchestrator`, `reconciliation-service`, `acceptor-service`, `consumer-psp`, `payment-read-model`, `integration-camel`, `demo-cockpit`, `dependency-simulator`, `wero-ui`. `TMP_ONLY_ASSESSMENT_NOT_PARK_AUTHORIZATION` est un avertissement voulu en PLAN. Le vrai PARK ne peut être exécuté avec `--assess-tmp-only` : la syntaxe est distincte.

Attendus Wave B : `DEPLOYMENTS_TO_PARK=n8n:1->0,maya-dashboard:1->0` (ordre et réplicas selon état live) ; `POSTGRES_DEPLOYMENT_AND_PVC_PROTECTED=true`. La présence et la vérification Argo CD sont obligatoires.

## Vague A — Instant Payments (RUNTIME MUTATION : sur autorisation explicite)

**N'exécuter qu'après constat qu'aucun paiement, replay Kafka, callback ou démonstration n'est en cours et que l'indisponibilité et la perte éventuelle de fichiers temporaires /tmp sont acceptées.** Cette procédure n'offre PAS de garantie exactly-once, de drainage automatique des messages, ni de pause transactionnelle. Conserver un terminal et le même contexte `oc` pour PARK/RESUME.

```bash
CRC_CAPACITY_PARK=YES \
CRC_PARK_ACK_PAYMENT_DOWNTIME=YES \
CRC_PARK_ACK_TMP_DATA_LOSS=YES \
CRC_PARK_ACK_PROCESSING_QUIESCED=YES \
python scripts/crc-application-mode.py park --allow-tmp-only

# contrôler les réplicas et la mémoire après terminaison réelle des pods
oc -n instant-payments-local get deploy
oc adm top nodes
```

Résultat attendu : `PARK_RESULT=PASS` avec `PARKED_DEPLOYMENTS=9` et snapshot `~/.crc-capacity/instant-payments-local.json`. En cas de `PARK_ERROR`, ne pas poursuivre ; le script tente rollback et peut demander une reprise manuelle.

## Vague B — Maya Freelance (APRÈS preuve de succès de la vague A)

**Avant B** : laisser se terminer les exécutions planifiées n8n. n8n stocke `N8N_USER_FOLDER=/tmp/n8n-home` dans le template connu et des fichiers locaux non exportés peuvent être perdus. Les workflows et credentials conservés dans PostgreSQL requièrent toujours leur base et `N8N_ENCRYPTION_KEY` d'origine. Contrôler ce risque avant B.

```bash
CRC_MAYA_PARK=YES \
CRC_MAYA_ACK_N8N_DOWNTIME=YES \
CRC_MAYA_ACK_EPHEMERAL_HOME_LOSS=YES \
CRC_MAYA_ACK_WORKFLOWS_QUIESCED=YES \
python scripts/crc-maya-freelance-mode.py park

oc -n maya-freelance get deploy,pvc
oc adm top nodes
```

Résultat attendu : `PARK_RESULT=PASS`, `PARKED_DEPLOYMENTS=2`, et snapshot `~/.crc-capacity/maya-freelance.json`. Ne pas supprimer ces fichiers d'état. Le script refuse une entrée Maya sans PVC PostgreSQL Bound ou si un target a un volume PV/CSI/emptyDir, une image DB ou un HPA.

## Reprise à la demande, en sens inverse si possible

```bash
# reprise de Maya Freelance
CRC_MAYA_RESUME=YES python scripts/crc-maya-freelance-mode.py resume
oc -n maya-freelance get deploy,pvc

# reprise Instant Payments
CRC_CAPACITY_RESUME=YES python scripts/crc-application-mode.py resume
oc -n instant-payments-local get deploy,sts,pvc

oc adm top nodes
```

La reprise restaure les réplicas enregistrés, puis les politiques Argo automatisées correspondantes. Vérifier ensuite les tests de santé, opérations métier et flux Kafka/n8n. Un RESUME ne prouve pas seul l'absence de perte ou une validation métier E2E. Si le snapshot est absent, ne pas improviser des réplicas ni activer tous les Applications GitOps.

## Limites/risques à assumer

- Les données PostgreSQL/queues MongoDB/Kafka et PVC ne sont ni sauvegardées ni restaurées par cette procédure ; seules les applications sont arrêtées. Une sauvegarde consistante est recommandée si l'état est important.
- Les valeurs des Secrets ne sont jamais exportées. Le local STATE contient UID/réplicas et ancienne valeur des paramètres Argo `spec.syncPolicy.automated`, donc garder le fichier hors GitHub.
- Pendant PARK, Argo est volontairement sans auto-sync pour les Applications détectées ; Git et cluster sont temporairement divergents. Une synchronisation manuelle, un re-création de Deployment, une politique ApplicationSet ou un changement de contexte `oc` entre PARK et RESUME peut rendre la reprise incorrecte. Avant RESUME, consulter le snapshot et le cluster ; ne pas utiliser le script sur un autre cluster.
- Le gain mémoire n'est **pas** 100% des requests. Seule la différence `oc adm top nodes` et `oc adm top pods` avant/après, à charge comparable, le démontre ; tous les services système et les deux bases restent actifs.

## Livrable de vérité

- `A_PLANNED` -> `A_PARKED` ou `A_BLOCKED`.
- `B_PLANNED` -> `B_PARKED` ou `B_BLOCKED`.
- Aucun état PARKED n'est déclaré avant réception d'une sortie locale attestant les réplicas à zéro et le résultat des scripts.
- Aucun Cloud provisionné. `I1` reste ouvert pour P95 et BOM.


## Exécution opérateur du 12 octobre — vague A réellement PARKED

L'opérateur a exécuté sur OpenShift Local CRC le PARK des neuf Deployments Instant Payments avec approbations explicites de l'indisponibilité, des fichiers temporaires et de la quiescence. **Résultats runtime observés :**

- `PARK_RESULT=PASS`, `PARKED_DEPLOYMENTS=9`, `SKIPPED_UNSAFE_OR_ABSENT=NONE`.
- Les neuf Deployments visés sont en `READY=0/0`, `UP-TO-DATE=0` et `AVAILABLE=0` dans `oc -n instant-payments-local get deploy`.
- Une copie locale du snapshot de reprise a été créée dans `~/.crc-capacity/instant-payments-local.json`. **Ne pas publier le chemin machine ni les données privées du snapshot.**
- Les Deployments non ciblés (Kafka, PostgreSQL, Grafana, Prometheus, Loki, Alloy et autres) étaient toujours à `1/1` dans la sortie. Les StatefulSets et PVC n'ont pas été modifiés par le script.
- Consommation nœud juste avant : CPU `3795m (48%)`, mémoire `18646Mi (79%)`.
- Consommation nœud juste après : CPU `3306m (42%)`, mémoire `17470Mi (74%)`.
- **Écarts instantanés** : CPU `-489m` et RAM `-1176Mi` (~`1.15Gi`). Non imputables intégralement aux workloads sans contrôle de charge identique et mesures temporelles, mais cohérents avec une libération réelle. Les métriques pré-/post- ne sont pas un P95.
- Le snapshot n'est pas une sauvegarde des données métier. Aucun `RESUME` n'a été demandé, ne pas réactiver les services automatiquement.

**Verdict A : `INSTANT_PAYMENTS_APP_TIER_PARKED_CRC_RUNTIME_PROVEN`.**
**Verdict B : `MAYA_FREELANCE_PLAN_PENDING`** : passer au `python scripts/crc-maya-freelance-mode.py plan` et à `oc -n maya-freelance get deploy,pvc`, vérifier le gel des workflows n8n avant la prochaine opération. Ne pas exécuter le PARK B en l'absence de ces preuves.


## Exécution opérateur du 12 octobre — vague B Maya Freelance réellement PARKED

Préflight observé : `DEPLOYMENTS_TO_PARK=n8n:1->0,maya-dashboard:1->0`, `ARGO_APPS_TO_PAUSE=NONE`, PVC `postgres-data` Bound, 79 Gi provisionnés (capacité, **pas** occupation réelle). L'opérateur a confirmé les quatre acquittements requis puis exécuté `python scripts/crc-maya-freelance-mode.py park` sur son CRC.

Preuves runtime :
- `PARK_RESULT=PASS`, `PARKED_DEPLOYMENTS=2`, `DATABASE_AND_PVC_UNCHANGED=true`.
- `deployment.apps/n8n=0/0` et `deployment.apps/maya-dashboard=0/0` ; `deployment.apps/postgres=1/1`.
- PVC `postgres-data` reste `Bound`, provisionné 79Gi via `crc-csi-hostpath-provisioner`.
- Snapshot de reprise créé et conservé localement hors Git : `~/.crc-capacity/maya-freelance.json` (ne pas publier de chemin personnel).
- Sortie pods : ancien historique de 5 pods `Completed` pour les builds du dashboard et un pod PostgreSQL `Running`. Ces anciens builds ne sont pas une charge CPU/RAM active.
- `oc adm top nodes` : avant `CPU=2336m/RAM=17692Mi (75%)` ; immédiatement après `CPU=2336m/RAM=17692Mi (75%)`. **Aucun gain additionnel établi par ces deux instantanés** ; métriques potentiellement temporisées et bruit de charge, réévaluer après stabilisation.
- Les deux applications restent indisponibles jusqu'à l'ordre de reprise de l'utilisateur ; ne pas lancer `resume` sans demande. Le snapshot constitue un état de réplicas et de politique Argo, **pas** un backup PostgreSQL ou une preuve E2E de restauration.

**Statuts consolidés** : `INSTANT_PAYMENTS_APP_TIER_PARKED_CRC_RUNTIME_PROVEN` (9 Deployments), `MAYA_APP_TIER_PARKED_CRC_RUNTIME_PROVEN` (2 Deployments). Infrastructure stateful (DB, Kafka/MongoDB, observabilité) toujours active. L'objectif de désactivation complète de tous les composants gourmands en ressources n'est pas atteint ; requiert gate distinct de sauvegarde, arrêt contrôlé et restauration.

Prochain relevé strictement read-only :

```bash
oc adm top nodes
oc -n instant-payments-local get deploy
oc -n maya-freelance get deploy,pvc
oc adm top pods -n maya-freelance --containers
```

**LICENSE_GATE: NOT_APPLICABLE** pour la documentation de mesures opérateur fournie sans nouveau contenu tiers ; le dépôt public demeure à revoir pour sa politique racine globale.
