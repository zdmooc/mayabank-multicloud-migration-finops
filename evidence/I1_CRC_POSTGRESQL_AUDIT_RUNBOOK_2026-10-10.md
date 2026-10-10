# I1 — Audit en lecture seule des PostgreSQL CRC (mode opératoire)

**Objectif :** préciser le nombre de workloads PostgreSQL, leur état et consommation instantanée, leurs PVC, ainsi que les **candidats** consommateurs. Le cluster CRC n'est pas accessible au runner GitHub. Le script est exécuté uniquement sur le poste ayant un contexte `oc` valide.

## Contexte de départ vérifié

Inventaire opérateur : **9 workloads PostgreSQL (8 Ready, 1 SCALE0 historique Wero)** dans 7 namespaces. Le volume Wero ancien occupe ~64MiB (mesure `du -sh`) et contient `userdata/PG_VERSION`; sa restauration n'est pas prouvée. Les dépendances applicatives listées jusqu'ici résultent d'indices de configuration, non de connexions SQL mesurées.

## Exécution sur HP ZBook Git Bash

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python -m unittest discover -s tests -p test_postgresql_readonly_audit.py -v
python scripts/audit-crc-postgresql-readonly.py
```

Le script n'utilise que `oc get ... -o json` et `oc adm top pods -A --containers`. **Aucun `oc exec`, `oc scale`, `oc patch`, `oc delete`, `oc apply`, `oc logs`, `psql` ou connexion PostgreSQL**. Il ne lit pas les valeurs de Secrets/ConfigMaps. Il filtre en mémoire les variables DB, et n'enregistre que les **noms**, le hostname sécurisé extrait de façon indirecte (pas les URL ni les mots de passe) et un état de résolution. Il ne conserve pas le JSON brut des objets.

## Fichiers créés sous evidence/local/private-postgresql-... (ignorés par Git)

- `SUMMARY.txt`: chiffres consolidés sans noms d'objets ni Secrets ; copier ce contenu dans le chat en priorité.
- `postgresql-workloads.csv`: workloads et images, replicas, PVC déclarés, requests CPU/RAM (conteneurs Running), métriques oc top par serveur si disponibles, couverture top.
- `database-consumer-candidates.csv`: noms de consommateurs et de variables, association au Service sélectionnant un serveur PostgreSQL, ou état indéterminé. Ne contient aucun nom d'utilisateur, mot de passe ni chaîne JDBC complète.

Les CSV contiennent néanmoins des **noms internes de namespaces, services, volumes ou projets** : les examiner avant diffusion publique. Ne jamais les pousser sur GitHub; l'ignore `evidence/local/` est actif.

## Classes de preuve et limites

- `SVC_SELECTOR_CANDIDATE_NOT_PROVEN_SQL`: la valeur littérale d'une variable hôte pointe vers un Service qui sélectionne une instance PostgreSQL selon les étiquettes Kubernetes. Cela ne prouve **pas** un TCP établi, un authentification ni une requête SQL.
- `UNRESOLVED_LITERAL_HOST`: le serveur de destination ne peut pas être rattaché par sélection de Service.
- `UNRESOLVED_CONFIG_OR_REF`, `UNRESOLVED_ENVFROM`: référence non résolue, par design pour éviter d'extraire des secrets.
- La requête et capacité PVC ne sont **pas des octets réellement utilisés**. Un volume absent du pod template peut échapper au rapprochement.
- `oc adm top` est un échantillon **instantané**, pas P95, P99, CPU peak, période d'activité ni mesure de transactions.
- `READY=1` atteste la disponibilité Kubernetes, non un usage métier réel.
- Le scan couvre Deployments/StatefulSets et leurs Pods associés, pas les services PostgreSQL externes, les Pods isolés sans contrôleur, ni tous les opérateurs et instances custom.
- Pour établir l'usage réel, instrumenter ensuite des métriques de sessions/queries après autorisation explicite ; aucune action sur les bases n'est comprise dans cet audit initial.

## Interprétation FinOps

Comparer requests/usage **par PostgreSQL**, intégrer la RAM système des StatefulSets et les réservations mémoire, puis seulement qualifier candidats scale-down, consolidation ou migration managed DB. **Aucune décision de suppression ni de redimensionnement** n'est justifiée par le seul statut Ready ou un seul `oc top`.

## Gates

`PG-I1` données de topologie et métriques : **PREPARED / WAITING_OPERATOR_RUN**.
`PG-I2` connexions effectives : **NOT_PROVEN**.
`PG-I3` occupied PVC bytes / backup : **NOT_PROVEN** sauf 64MiB Wero (volume de service arrêté).
`PG-I4` optimisation / consolidation : **BLOCKED_BY_I2_I3**.

Conserver `wero-poc` SCALE0/NO_DELETE, protéger `instant-payments-local` et les sept autres dépendances actives.
