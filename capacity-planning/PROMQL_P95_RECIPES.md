# Optional PromQL capacity recipes (execute in a trusted local monitoring UI)

These are examples to adapt to real metric labels. They were **not executed by this repository**.

- CPU per namespace and pod, 5-minute rate, 7-day quantile of repeated observations:

```promql
quantile_over_time(0.95,
  (sum by (namespace,pod) (rate(container_cpu_usage_seconds_total{container!="",image!=""}[5m])))[7d:5m])
```

- Memory working set per namespace and pod, 7-day sample distribution:

```promql
quantile_over_time(0.95,
  (sum by (namespace,pod) (container_memory_working_set_bytes{container!="",image!=""}))[7d:5m])
```

- CPU request per pod (check cluster metric label availability):

```promql
sum by (namespace,pod) (kube_pod_container_resource_requests{resource="cpu",unit="core"})
```

- Memory request per pod:

```promql
sum by (namespace,pod) (kube_pod_container_resource_requests{resource="memory",unit="byte"})
```

**Important:** an aggregation of per-pod P95 values is *not* equal to the P95 of total concurrent demand. For pool planning, also query the historical **sum first, quantile second**, per zone and under failure load. Verify scrape intervals, metric label names, counter reset and exclusion of completed jobs before using outputs.
