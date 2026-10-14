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

**Statut actuel : `RUNTIME_PARK_PROVEN` au 12/10/2026 ; voir le relevé de clôture ci-dessous.**

`LICENSE_GATE: PENDING` : code original de pilotage, sans redistribution des binaires tiers, aucune licence modifiée ni attribuée.


## Résultat runtime confirmé — 12 octobre 2026

Le propriétaire a exécuté les deux commandes `park` sur le CRC Windows/OpenShift Local, avec les trois variables d'acquittement. **Le runtime est prouvé**, à distinguer des `PARK_RESULT=PASS` simulés lors des tests unitaires.

- `CRC_IDLE_PARK=YES CRC_IDLE_ACK_DOWNTIME=YES CRC_IDLE_ACK_LAB_DATA_LOSS=YES python scripts/crc-idle-services-mode.py park --project instant` : **`PARK_RESULT=PASS`**. L'inventaire runtime montre **18 Deployments à `0/0` et `statefulset/mongodb-read-model` à `0/0`**. Les quatre PVC `data-mongodb-read-model-0`, `postgresql-acceptor-data`, `postgresql-consumer-data`, `postgresql-payments-data` restent `Bound`. Snapshot distinct : `~/.crc-capacity/crc-idle-instant.json`. Snapshot originel des 9 apps préservé.
- `... park --project keycloak` : **`PARK_RESULT=PASS`**. CR `Keycloak.spec.instances` ramené à 0 via le contrôleur et `statefulset/keycloak=0/0`, `statefulset/postgresql=0/0`. L'opérateur `deployment/rhbk-operator=1/1` reste actif intentionnellement ; PVC `postgres-pvc` reste `Bound`. Snapshot : `~/.crc-capacity/crc-idle-keycloak.json`.

**Mesures prises par l'opérateur après ces deux PARK** (comparées au relevé précédent après les sept projets en veille) :

| Indicateur | Avant arrêt résiduel | Après arrêt résiduel | Écart |
|---|---:|---:|---:|
| RAM utilisée, `oc adm top nodes` | 16684Mi (70%) | 15853Mi (67%) | **-831Mi**, variation observée |
| CPU utilisé | 1598m (20%) | 1431m (18%) | -167m |
| CPU requests, `oc describe node` | 5833m (74%) | 5103m (65%) | **-730m** |
| Memory requests | 18211Mi (77%) | 15203Mi (64%) | **-3008Mi** |
| Memory limits | 20522Mi (87%) | 12330Mi (52%) | -8192Mi |

Ces relevés ne prouvent pas une réduction strictement imputable de la consommation du nœud (métriques temporelles). Les *requests* en baisse représentent la capacité potentielle libérée pour le scheduler, sans garantie qu'un nouveau projet rentre compte tenu de ses propres requests/affinités/PVC.

**Conclusion** : les sept POC personnels et leurs derniers services résiduels Instant Payments et Keycloak sont en veille selon le périmètre approuvé. Certains services OpenShift `openshift-*` et l'opérateur Keycloak restent actifs. **Ne pas tenter une nouvelle mise en veille** tant que ces snapshots sont `PARKED`. Reprise exclusivement sur ordre utilisateur, avec possible reconstruction des données éphémères. Ne pas confondre mise en veille de projets et arrêt de la VM CRC.

## Observation de fin de séance — 14 octobre 2026 : arrêt CRC et Docker/Kind

**Source : sortie opérateur sur le HP ZBook (pas une mesure automatique du dépôt).**

- `crc stop` a retourné `Stopped the instance` ; `crc status` a confirmé `CRC VM: Stopped` et `OpenShift: Stopped (v4.22.7)`. C'est la **première preuve de CRC arrêté explicitement** remontée dans ce suivi après la politique du 12 octobre.
- Docker Desktop a ensuite été démarré **séparément**, Docker Engine Linux 28.3.2 prêt (Docker Desktop 4.43.2). L'exécution d'un PostgreSQL 16 **éphémère** du cas CAPS REST/MQ a été validée, `CASE01_POSTGRES_DOCKER_TEST=PASS` (9 tests JDBC, 5 HTTP/DB, 1 test deuxième JVM). La sortie annonce le nettoyage du conteneur jetable, sans contrôle de son absence par `docker ps` après exécution.
- **Effet de bord constaté au démarrage Docker :** les trois conteneurs du cluster Kind `edl-lab-control-plane`, `edl-lab-worker` et `edl-lab-worker2` étaient tous `Up`. Ce cluster Kind n'était **pas nécessaire** au test PostgreSQL ; il peut contribuer à la consommation mémoire. Il n'y a **pas** de preuve de suppression, de mise en veille ou d'arrêt de ces trois conteneurs après le test.
- **Règle de capacité inchangée :** ne pas exécuter CRC et Docker/Kind simultanément ; arrêter Docker Desktop après le laboratoire **si aucune autre charge n'en dépend**, sans supprimer Kind ni les ressources persistantes. Lors des prochains démarrages de Docker, refaire `docker ps` car des conteneurs Kind peuvent se relancer automatiquement.
- Les applications des sept projets CRC restent consignées comme `PARKED`. Le `crc stop` n'est **pas** une réactivation, et il ne supprime ni PVC ni snapshots.

Pour les preuves applicatives exactes, voir [formation-was — cas 01, section PostgreSQL](https://github.com/zdmooc/formation-was/blob/caps-case01-postgres-durability/phase-14-rest-vs-mq-case01/README.md). Aucun traitement sur CRC, MQ ou Kind n'a été lancé par cette mise à jour documentaire.
