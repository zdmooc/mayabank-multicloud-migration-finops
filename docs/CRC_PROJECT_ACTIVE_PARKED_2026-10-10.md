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
