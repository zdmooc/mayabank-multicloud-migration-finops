# CRC — Mise en veille des services résiduels Instant Payments et Keycloak

Décision du propriétaire du 12 octobre 2026 : après mise en veille des sept projets de laboratoire, il est autorisé d'arrêter les dépendances résiduelles Instant Payments et Keycloak, y compris en acceptant la perte éventuelle de données LAB temporaires, afin de comprendre et reconstruire les plateformes au besoin. **Jamais sur un environnement de production.**

## Périmètre et garde-fous

- Script : `scripts/crc-idle-services-mode.py`. Modes `plan`, `park`, `resume`. Projets `instant` et `keycloak`, indépendants.
- Instant Payments : 9 Deployments techniques (`redpanda-console`, `grafana`, `alloy`, `prometheus`, `loki`, `kafka`, `postgresql-consumer`, `postgresql-acceptor`, `postgresql-payments`) et StatefulSet `mongodb-read-model`. Ne réveille pas les 9 Deployments applicatifs déjà mis à zéro par la première vague.
- Keycloak : mettre `keycloak.spec.instances` à 0 via CRD et opérateur (sans scaler directement le StatefulSet opérateur), puis `statefulset/postgresql` à 0. L'opérateur `deployment/rhbk-operator` reste actif.
- Les quatre PVC Instant Payments (`data-mongodb-read-model-0`, `postgresql-acceptor-data`, `postgresql-consumer-data`, `postgresql-payments-data`) et `keycloak-system/postgres-pvc` doivent rester Bound ; ne les supprimer ni les réinitialiser.
- Bloque hors CRC mononœud Ready, si HPA/Jobs actifs, Argo CD autosync, déploiements/StatefulSets/PVC inattendus, CRD Keycloak incompatible avec `instances=0`, ou snapshot déjà PARKED. Le script n'arrête pas les composants `openshift-*`.
- Les snapshots de la première vague `~/.crc-capacity/instant-payments-local.json` et les autres snapshots des sept projets demeurent intacts. Nouveaux snapshots séparés : `~/.crc-capacity/crc-idle-instant.json` et `crc-idle-keycloak.json`.
- Les tests GitHub Actions sont **hors cluster** ; seule une sortie opérateur `PARK_RESULT=PASS` suivie des contrôles `oc` prouve l'arrêt réel.

## Sur le HP — mise à jour, tests et plans sans mutation

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_idle_services.py
python scripts/crc-idle-services-mode.py plan --project instant
python scripts/crc-idle-services-mode.py plan --project keycloak
```

Les deux plans doivent réussir, afficher `MODE=PLAN_READ_ONLY`, `CLUSTER_MUTATED=false`, les composants attendus et les PVC conservés. En cas de divergence, ne pas contourner les gardes.

## Après les deux plans : arrêt séquentiel et volontaire

```bash
CRC_IDLE_PARK=YES CRC_IDLE_ACK_DOWNTIME=YES CRC_IDLE_ACK_LAB_DATA_LOSS=YES \
  python scripts/crc-idle-services-mode.py park --project instant

# Seulement si PARK_RESULT=PASS pour instant
CRC_IDLE_PARK=YES CRC_IDLE_ACK_DOWNTIME=YES CRC_IDLE_ACK_LAB_DATA_LOSS=YES \
  python scripts/crc-idle-services-mode.py park --project keycloak
```

Toute erreur laisse `PARK_PARTIAL` dans le snapshot. Ne pas relancer PARK par-dessus ce snapshot ; diagnostiquer l'état actuel. Le script n'exécute pas de rollback automatique risquant de réactiver les services.

## Vérifications et capacité

```bash
oc -n instant-payments-local get deployments,statefulsets,pods,pvc
oc -n keycloak-system get deployments,statefulsets,pods,pvc
oc -n keycloak-system get keycloak keycloak -o jsonpath='{.spec.instances}{"\\n"}'
oc adm top nodes
oc describe node crc | sed -n '/Allocated resources:/,/Events:/p' | head -11
```

Dans Instant Payments les services techniques ciblés doivent être à `0/0`, et dans Keycloak les deux StatefulSets doivent être à `0/0` alors que l'opérateur peut rester à `1/1`. Les mesures mémoire sont à comparer avant/après ; ne pas confondre RAM réellement consommée et `requests` Kubernetes.

## Reprise uniquement sur ordre, si nouvelle mission ou POC

```bash
CRC_IDLE_RESUME=YES python scripts/crc-idle-services-mode.py resume --project keycloak
CRC_IDLE_RESUME=YES python scripts/crc-idle-services-mode.py resume --project instant
```

La reprise tente de remettre les réplicas des composants techniques avant les applications métier et peut nécessiter reconstitution de Kafka ou des données LAB temporaires. Les neuf applications métier restent PARKED jusqu'à ordre distinct via leur script d'origine.

**Statut documentaire actuel : `SCRIPT_COMMITTED_CI_PENDING_OR_TESTED / RUNTIME_PARK_NOT_EXECUTED`.** Aucun arrêt de ces deux périmètres n'a encore été constaté.

`LICENSE_GATE: PENDING` : code original de pilotage, sans redistribution des binaires tiers, aucune licence modifiée ni attribuée.
