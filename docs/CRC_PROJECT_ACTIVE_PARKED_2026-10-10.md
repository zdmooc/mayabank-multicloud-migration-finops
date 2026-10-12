# CRC — modes ACTIVE / PARKED pour libérer la RAM (démarrage urgent de POC)

Date : 2026-10-10.

## Besoin opérationnel

Le HP ZBook a 64 Go RAM et environ 24 Gio libres selon Windows. Le nœud CRC consomme ~84 % de sa mémoire disponible (~19,8 Gi sur 23,5 Gi allocatable), mais n'est **pas** à sa limite de pods (149/250) et ses conditions MemoryPressure/DiskPressure/PIDPressure sont False. Environ 3,1 Gi sont consommés par le conteneur principal kube-apiserver et 1,6 Gi par Prometheus, services système **à ne pas couper**. L'utilisateur veut créer de la capacité sans revalider systématiquement ses POC.

Les anciens ReplicaSets / Builds sont conformes aux politiques, leur suppression ne libère pas les pods actifs. Les namespaces `wero-poc` (zéro pod actif) et `tradeops` (14 de 15 Deployments scale0, mais PostgreSQL/Redpanda `emptyDir` actifs) ne sont pas des gisements de RAM applicative significatifs pour ce besoin.

## Première vague — Instant Payments stateless uniquement

Entrée : `scripts/crc-application-mode.py` dans le dépôt FinOps. Le script est **strictement lié** au cluster CRC mono-nœud `crc` et au namespace `instant-payments-local`. Il interdit les volumes `emptyDir`, `persistentVolumeClaim`, `hostPath`, `ephemeral`, `csi` et les images typiques de bases/messaging dans les Deployments sélectionnés.

Nine targets (when live and eligible):

```text
payment-orchestrator
reconciliation-service
acceptor-service
consumer-psp
payment-read-model
integration-camel
demo-cockpit
dependency-simulator
wero-ui
```

*Les applications de paiement seront indisponibles pendant PARK.* Aucune base PostgreSQL, Kafka, MQ, Keycloak, registry, Prometheus, Grafana, système OpenShift, StatefulSet, PVC/PV, Route, Secret, ConfigMap ou namespace n'est mis à zéro ou effacé par cet outil. Si un target se révèle stateful ou soumis à un HPA, il est **ignoré**, pas modifié. Le script échoue sans agir si aucun Application Argo CD automatisé n'est détecté pour `instant-payments-local`, si une Application est propriétaire ApplicationSet, si le nœud CRC n'est pas Ready, ou s'il reste moins de deux Deployments candidats.

**Attention GitOps :** dans le dépôt Instant Payments, les Applications `instant-payments-local`, `instant-payments-shared-platform` et `instant-payments-tech-lead-shared-platform` sont déclarées en mode automated/selfHeal. Le script sauvegarde **les politiques automated réelles** des Applications Argo qui ciblent le namespace, met temporairement `spec.syncPolicy.automated` à null, puis passe à zéro uniquement les Deployments allowlistés. La mise en veille rend ces Applications volontairement `OutOfSync` jusqu'au RESUME. Cette pause de sync est une **mutation contrôlée de GitOps**, et ne doit être faite qu'en laboratoire local avec choix explicite de l'opérateur. Pas d'exécution du script en production ni modification d'ApplicationSet.

### Commande immédiate — plan sans écriture

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_application_mode.py
python scripts/crc-application-mode.py plan
```

La section `APPS_TO_PARK` expose les Deployments sélectionnés, `GITOPS_APPLICATIONS_TO_PAUSE` affiche les Applications qui seraient mises en pause, `SKIPPED_UNSAFE_OR_ABSENT` détaille les exclusions, `BLOCKERS` doit afficher `NONE`. Les tests offline n'établissent pas que le cluster est réellement parké.

### PARK — intervention réelle et reversible, confirmation explicite

Uniquement si la liste est correcte, `BLOCKERS=NONE` et l'indisponibilité d'Instant Payments est acceptable :

```bash
CRC_CAPACITY_PARK=YES python scripts/crc-application-mode.py park
oc adm top nodes
oc -n instant-payments-local get deploy
```

Un snapshot local durable est sauvegardé sous `~/.crc-capacity/instant-payments-local.json` (ou emplacement explicite `CRC_CAPACITY_STATE_FILE`), avec réplicas/UID des Deployments et ancienne configuration Argo `automated` (aucune valeur de Secret). Le script garde le snapshot en cas d'échec et tente de restaurer la configuration initiale et les réplicas. L'exécution utilise le contexte `oc` actuel : **ne pas changer de cluster entre PARK et RESUME**.

### RESUME — retour automatique aux réplicas et à GitOps

```bash
CRC_CAPACITY_RESUME=YES python scripts/crc-application-mode.py resume
oc -n instant-payments-local get deploy
oc adm top nodes
```

Restaure d'abord les réplicas exacts enregistrés et **ensuite** les valeurs `automated` initiales, de sorte qu'Argo puisse reprendre la réconciliation. Vérifie l'identité (UID) des Deployments ; un changement de propriétaire bloque au lieu de toucher une nouvelle ressource. Si l'état Argo a été modifié ailleurs entre PARK et RESUME, la reprise bloque et doit être examinée. Conserver le snapshot. RESUME ne prouve pas à lui seul un E2E paiement ; refaire les tests de non-régression du dépôt de référence au besoin.

### Attente réaliste / prochaine vague

La mise en veille des services de paiement listés peut libérer de l'ordre de 1–2+ GiB selon les pods effectivement éligibles et leur terminaison effective ; **aucun gain chiffré n'est garanti** avant `oc adm top nodes` après l'opération. Kafka et les PostgreSQL restent actifs et consommeront de la mémoire. Pour davantage de place, une seconde vague devrait examiner `maya-freelance` et des observabilités locales **après** vérification de l'état des données, de GitOps et de la reprise ; jamais détruire PostgreSQL/Redpanda TradeOps `emptyDir` pour gagner 100Mi.

**PARK et RESUME du nouveau script ont des tests simulés réussis en GitHub Actions, mais n'ont PAS encore été exécutés en live sur le HP.** La commande `plan` est la première étape opérationnelle; dès que son résultat est connu, on peut passer à `park` sans recommencer les anciens audits.

## Réalité du premier PLAN exécuté — 2026-10-12

L'opérateur a exécuté `python scripts/crc-application-mode.py plan` sur le CRC démarré, sans modification (`MODE=PLAN_READ_ONLY`) :

- **Seul candidat** : `wero-ui`, 1 replica vers 0.
- **Huit exclus** : `payment-orchestrator`, `reconciliation-service`, `acceptor-service`, `consumer-psp`, `payment-read-model`, `integration-camel`, `demo-cockpit`, `dependency-simulator`, tous `DATA_OR_EPHEMERAL_VOLUME` dans leurs templates de Deployment.
- **Argo CD** : `instant-payments-tech-lead-shared-platform` serait modifiée seulement si PARK devait avoir lieu.
- **Aucun snapshot** : `EXISTING_SNAPSHOT=NONE`.
- **Problème d'ergonomie corrigé** : l'ancien PLAN affichait `BLOCKERS=NONE` malgré seulement une cible. Le vrai mode PARK exige depuis l'origine au moins **deux Deployments éligibles** et échouerait avant toute mutation. Le PLAN affiche désormais `BLOCKERS=LESS_THAN_TWO_ELIGIBLE_RUNNING_DEPLOYMENTS` lorsque ce seuil n'est pas atteint, plus un avertissement `PARK_BLOCKED_NO_CLUSTER_ACTION`.
- **Décision** : `NO_PARK`, aucune libération RAM démontrée ; ne pas assouplir automatiquement le test `emptyDir` avant classification de sa destination, reconstructibilité et absence de données applicatives à perdre.

Première vérification en lecture seule des volumes exclus (pas de valeurs de Secret) :

```bash
oc -n instant-payments-local get deployment -o json | jq -r '
  .items[]
  | select(.metadata.name as $n |
      ["payment-orchestrator","reconciliation-service","acceptor-service",
       "consumer-psp","payment-read-model","integration-camel",
       "demo-cockpit","dependency-simulator"] | index($n))
  | .metadata.name as $name
  | .spec.template.spec as $spec
  | ($spec.volumes // [])[]? as $vol
  | select($vol | has("emptyDir") or has("persistentVolumeClaim") or
                       has("hostPath") or has("ephemeral") or has("csi"))
  | [$name, $vol.name,
     ($vol | keys | map(select(. != "name")) | join(",")),
     ([$spec.containers[]? | .volumeMounts[]? |
       select(.name == $vol.name) | .mountPath] | unique | join(","))]
  | @tsv'
```

Interprétation à faire ensuite **cas par cas**, avec preuve de backup ou caractère jetable de chaque dossier : il peut s'agir de caches/reports temporaires ou de données métier non persistées. Les huit services ne sont pas prouvés stateful du seul fait de la présence d'un `emptyDir` ; mais les exclure reste correct tant que les volumes ne sont pas qualifiés.

**Sécurité** : le log d'initialisation CRC affiché dans la conversation contient un identifiant administrateur sensible ; ne jamais le copier dans ce dépôt, la CI ou un rapport public. Envisager une rotation/régénération conforme au mode d'authentification CRC en vigueur.



## Analyse read-only des huit volumes /tmp — 12 octobre 2026

**Preuve locale opérateur :** les huit Deployments précédemment exclus (`payment-orchestrator`, `reconciliation-service`, `acceptor-service`, `consumer-psp`, `payment-read-model`, `integration-camel`, `demo-cockpit`, `dependency-simulator`) exposent tous exactement un volume `tmp` de type `emptyDir`, monté sur `/tmp`. Aucun PVC/hostPath/CSI n'était listé dans cette sélection, mais la commande ciblait uniquement ces huit templates et ne validait ni la réversibilité des traitements métier ni le stockage externe.

**Rapprochement du code owner** `zdmooc/mayabank-instant-payments-resilience-platform` :
- `gitops/base/workloads.yaml` déclare le volume `tmp` sur `/tmp` avec `readOnlyRootFilesystem: true` pour les services principaux.
- `gitops/tech-lead/base/workloads.yaml` décrit aussi un `tmp` pour `integration-camel` et `payment-read-model`.
- `platform/helm/instant-payments/templates/workloads.yaml` documente le même pattern pour le packaging Helm (Kustomize overlay = source de vérité runtime).
- `docs/architecture/05-kubernetes-openshift-gitops.md` explicite que `/tmp` est la zone en écriture d'un root filesystem en lecture seule. **Ce n'est pas une preuve de quiescence E2E et ne dit rien sur les transactions en cours.**
- Des queues Kafka, des bases de données et des statuts de paiement restent exploités par ces services ; la reprise métier/UNKNOWN et le traitement des messages en vol doivent être validés avant leur arrêt.

**Nouveau mode statique proposé (ne modifie pas Kubernetes)** :

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only
python tests/test_crc_application_mode.py
python scripts/crc-application-mode.py plan --assess-tmp-only
```

Le classifieur optionnel accepte pour **analyse seulement** un unique volume `tmp` avec `emptyDir: {}`, exclusivement monté sur `/tmp` dans chaque conteneur, sans `subPath` ni volume data/CSI/PVC, avec `readOnlyRootFilesystem: true`. Il bloque en cas d'autre `emptyDir`, d'image de datastores, ou de doute de template.

La sortie optionnelle doit toujours contenir `TMP_ONLY_ASSESSMENT=REPORT_ONLY`, `TMP_ONLY_PARK_ENABLED=false` et `BLOCKERS=TMP_ONLY_ASSESSMENT_NOT_PARK_AUTHORIZATION` : ce ne sont **pas** des autorisations de PARK. Le mode `park` ordinaire continue à refuser tout `emptyDir`, même `/tmp` ; le CLI rejette `park --assess-tmp-only`.

**Gates à fermer avant un éventuel assouplissement opérationnel** : confirmer le template runtime de chacun des huit, le nombre de réplicas/labels/owner GitOps et absence HPA/PDB contradictoire ; la terminaison de traitements en cours, publication Kafka/outbox, aucune information unique stockée dans `/tmp`, ainsi que tests de reprise E2E et mesures réelles de RAM libérable. Tout changement PARK/RESUME doit être approuvé explicitement par l'opérateur avec fenêtre de service et rollback. Aucun scale, pause Argo CD, `crc stop` ou nettoyage effectué ici.

**Verdict : `I1_TMP_ONLY_VOLUME_DISCOVERY_CONFIRMED / ASSESSMENT_ONLY / NO_PARK`.**
