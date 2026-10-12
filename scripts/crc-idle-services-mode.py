#!/usr/bin/env python3
"""Park CRC lab residual Instant Payments and Keycloak services, without deleting PVCs."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.home() / ".crc-capacity"
NS = {"instant": "instant-payments-local", "keycloak": "keycloak-system"}
OLD_APPS = set("acceptor-service consumer-psp demo-cockpit dependency-simulator integration-camel payment-orchestrator payment-read-model reconciliation-service wero-ui".split())
REST = "redpanda-console grafana alloy prometheus loki kafka postgresql-consumer postgresql-acceptor postgresql-payments".split()
IP_PVCS = set("data-mongodb-read-model-0 postgresql-acceptor-data postgresql-consumer-data postgresql-payments-data".split())

def oc(*a):
    r = subprocess.run(["oc", "--request-timeout=25s", *a], text=True,
                       capture_output=True, timeout=75)
    if r.returncode: raise RuntimeError("OC_FAILED:" + " ".join(a[:5]) + ":" + r.stderr[:170])
    return json.loads(r.stdout) if a[-2:] == ("-o", "json") else r.stdout.strip()

def get(ns, kind, name): return oc("-n", ns, "get", kind, name, "-o", "json")
def listing(ns, kind): return oc("-n", ns, "get", kind, "-o", "json")["items"]
def statefile(p): return ROOT / ("crc-idle-" + p + ".json")

def store(s):
    f=statefile(s["project"]); f.parent.mkdir(parents=True, exist_ok=True)
    tmp=f.with_name(f.name+".tmp")
    tmp.write_text(json.dumps(s, indent=2, sort_keys=True)+"\n", encoding="utf8")
    os.replace(tmp, f)

def read(p):
    s=json.loads(statefile(p).read_text(encoding="utf8"))
    if s["project"]!=p or s["ns"]!=NS[p]: raise RuntimeError("SNAPSHOT_SCOPE_MISMATCH")
    return s

def guard(ns):
    nodes=oc("get", "nodes", "-o", "json")["items"]
    if len(nodes)!=1 or nodes[0]["metadata"]["name"]!="crc": raise RuntimeError("NOT_SINGLE_CRC")
    if not any(c["type"]=="Ready" and c["status"]=="True"
               for c in nodes[0]["status"]["conditions"]): raise RuntimeError("CRC_NOT_READY")
    if listing(ns,"hpa"): raise RuntimeError("HPA_PRESENT")
    if any((j.get("status") or {}).get("active",0) for j in listing(ns,"jobs")): raise RuntimeError("ACTIVE_JOBS")
    apps=[a for a in oc("get","applications.argoproj.io","-A","-o","json")["items"]
          if a.get("spec",{}).get("destination",{}).get("namespace")==ns]
    if any((a["spec"].get("syncPolicy") or {}).get("automated") is not None for a in apps):
        raise RuntimeError("ARGO_AUTOSYNC_PRESENT")
    return {"node_uid":nodes[0]["metadata"]["uid"],
            "ns_uid":oc("get","namespace",ns,"-o","json")["metadata"]["uid"]}

def check_pvcs(ns, names):
    objs={p["metadata"]["name"]:p for p in listing(ns,"pvc")}
    if set(objs)!=names or any(v["status"]["phase"]!="Bound" for v in objs.values()):
        raise RuntimeError("PVC_SET_OR_STATUS_CHANGED")
    return [{"name":n,"uid":v["metadata"]["uid"]} for n,v in sorted(objs.items())]

def inspect(p):
    ns=NS[p]; s={"project":p,"ns":ns,**guard(ns)}
    if p=="instant":
        old=ROOT/"instant-payments-local.json"
        if not old.exists() or json.loads(old.read_text(encoding="utf8")).get("status")!="PARKED":
            raise RuntimeError("INITIAL_INSTANT_PARK_SNAPSHOT_MISSING")
        ds={a["metadata"]["name"]:a for a in listing(ns,"deployments")}
        if set(ds)!=OLD_APPS|set(REST): raise RuntimeError("UNEXPECTED_INSTANT_DEPLOYMENTS")
        if any(ds[n]["spec"].get("replicas",1)!=0 for n in OLD_APPS):
            raise RuntimeError("PREVIOUS_PARKED_APPS_RESTARTED")
        sts={a["metadata"]["name"]:a for a in listing(ns,"statefulsets")}
        if set(sts)!={"mongodb-read-model"}: raise RuntimeError("UNEXPECTED_INSTANT_STS")
        s["workloads"]=[{"kind":"deployment","name":n,"uid":ds[n]["metadata"]["uid"],
                         "replicas":ds[n]["spec"].get("replicas",1)} for n in REST]
        obj=sts["mongodb-read-model"]
        s["workloads"].append({"kind":"statefulset","name":"mongodb-read-model",
                    "uid":obj["metadata"]["uid"],"replicas":obj["spec"].get("replicas",1)})
        s["cron"]=[{"name":c["metadata"]["name"],"uid":c["metadata"]["uid"],
                    "suspend":c["spec"].get("suspend")} for c in listing(ns,"cronjobs")]
        s["pvc"]=check_pvcs(ns,IP_PVCS)
    else:
        crd=oc("get","crd","keycloaks.k8s.keycloak.org","-o","json")
        vs=[v for v in crd["spec"]["versions"] if v["name"]=="v2beta1" and v.get("served")]
        if len(vs)!=1: raise RuntimeError("KEYCLOAK_CRD_VERSION_MISMATCH")
        field=vs[0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]["instances"]
        if field.get("type")!="integer" or field.get("minimum",0)>0:
            raise RuntimeError("KEYCLOAK_CRD_ZERO_NOT_ALLOWED")
        k=get(ns,"keycloaks.k8s.keycloak.org","keycloak")
        sts={a["metadata"]["name"]:a for a in listing(ns,"statefulsets")}
        deps={a["metadata"]["name"]:a for a in listing(ns,"deployments")}
        if set(sts)!={"keycloak","postgresql"} or set(deps)!={"rhbk-operator"}:
            raise RuntimeError("UNEXPECTED_KEYCLOAK_WORKLOADS")
        if not any(x.get("kind")=="Keycloak" and x.get("uid")==k["metadata"]["uid"]
                   for x in sts["keycloak"]["metadata"].get("ownerReferences",[])):
            raise RuntimeError("KEYCLOAK_STS_OWNER_MISMATCH")
        if listing(ns,"cronjobs"): raise RuntimeError("KEYCLOAK_CRONJOBS_PRESENT")
        s["cr"]={"uid":k["metadata"]["uid"],"instances":k["spec"]["instances"]}
        s["operator_uid"]=deps["rhbk-operator"]["metadata"]["uid"]
        s["workloads"]=[{"kind":"statefulset","name":"postgresql","uid":sts["postgresql"]["metadata"]["uid"],
                         "replicas":sts["postgresql"]["spec"].get("replicas",1)}]
        s["pvc"]=check_pvcs(ns,{"postgres-pvc"})
    return s

def scale(ns,kind,n,c):
    oc("-n",ns,"scale",kind+"/"+n,"--replicas="+str(c))
    if get(ns,kind,n)["spec"].get("replicas",1)!=c: raise RuntimeError("SCALE_FAILED:"+n)

def patch(ns,kind,n,spec):
    oc("-n",ns,"patch",kind,n,"--type=merge","-p",json.dumps({"spec":spec}))

def kc_instances(n):
    patch(NS["keycloak"],"keycloaks.k8s.keycloak.org","keycloak",{"instances":n})
    if get(NS["keycloak"],"keycloaks.k8s.keycloak.org","keycloak")["spec"].get("instances")!=n:
        raise RuntimeError("KEYCLOAK_PATCH_FAILED")

def wait(ns,kind,n,c):
    end=time.monotonic()+360
    while time.monotonic()<end:
        x=get(ns,kind,n); st=x.get("status",{})
        if x["spec"].get("replicas",1)==c and (
            (st.get("replicas",0)==0 and st.get("readyReplicas",0)==0) if c==0
            else st.get("readyReplicas",0)>=c): return
        time.sleep(5)
    raise RuntimeError("WAIT_TIMEOUT:"+n)

def plan(p):
    s=inspect(p)
    print("MODE=PLAN_READ_ONLY\nPROJECT="+p)
    print("WORKLOADS="+",".join(x["kind"]+"/"+x["name"]+":"+str(x["replicas"])+"->0"
                             for x in s["workloads"]))
    if p=="keycloak": print("KEYCLOAK_INSTANCES="+str(s["cr"]["instances"])+"->0")
    print("PVC_PRESERVED="+",".join(x["name"] for x in s["pvc"]))
    print("SNAPSHOT="+(read(p)["status"] if statefile(p).exists() else "NONE"))
    print("CLUSTER_MUTATED=false")

def park(p):
    if any(os.getenv(k)!="YES" for k in
           ("CRC_IDLE_PARK","CRC_IDLE_ACK_DOWNTIME","CRC_IDLE_ACK_LAB_DATA_LOSS")):
        raise RuntimeError("EXPLICIT_PARK_ACKS_REQUIRED")
    if statefile(p).exists() and read(p)["status"]!="RESUMED":
        raise RuntimeError("ACTIVE_SNAPSHOT_EXISTS")
    s=inspect(p);s["status"]="PARK_PARTIAL";store(s)
    try:
        if p=="instant":
            ns=NS[p]
            for cj in s["cron"]:
                if cj["suspend"] is not True:
                    patch(ns,"cronjob",cj["name"],{"suspend":True})
            ws={w["name"]:w for w in s["workloads"]}
            for n in REST:
                if ws[n]["replicas"]:
                    print("STOP=deployment/"+n,flush=True)
                    scale(ns,"deployment",n,0);wait(ns,"deployment",n,0)
            if ws["mongodb-read-model"]["replicas"]:
                print("STOP=statefulset/mongodb-read-model",flush=True)
                scale(ns,"statefulset","mongodb-read-model",0)
                wait(ns,"statefulset","mongodb-read-model",0)
        else:
            print("STOP=keycloak.spec.instances",flush=True)
            kc_instances(0);wait(NS[p],"statefulset","keycloak",0)
            w=s["workloads"][0]
            if w["replicas"]:
                print("STOP=statefulset/postgresql",flush=True)
                scale(NS[p],"statefulset","postgresql",0)
                wait(NS[p],"statefulset","postgresql",0)
        s["status"]="PARKED";store(s)
    except Exception:
        print("PARK_PARTIAL=YES; NO_AUTOMATIC_ROLLBACK",file=sys.stderr)
        raise
    print("PARK_RESULT=PASS\nPROJECT="+p+"\nSNAPSHOT="+str(statefile(p)))

def resume(p):
    if os.getenv("CRC_IDLE_RESUME")!="YES":raise RuntimeError("RESUME_ACK_REQUIRED")
    s=read(p)
    if s["status"]=="RESUMED":print("ALREADY_RESUMED=YES");return
    if s["status"]not in ("PARKED","PARK_PARTIAL","RESUME_PARTIAL"):
        raise RuntimeError("BAD_SNAPSHOT_STATUS")
    ident=guard(s["ns"])
    if ident["node_uid"]!=s["node_uid"] or ident["ns_uid"]!=s["ns_uid"]:
        raise RuntimeError("CRC_IDENTITY_CHANGED")
    for pvc in s["pvc"]:
        if get(s["ns"],"pvc",pvc["name"])["metadata"]["uid"]!=pvc["uid"]:
            raise RuntimeError("PVC_REPLACED")
    s["status"]="RESUME_PARTIAL";store(s)
    if p=="instant":
        for w in reversed(s["workloads"]):
            if w["replicas"]:
                scale(s["ns"],w["kind"],w["name"],w["replicas"])
                wait(s["ns"],w["kind"],w["name"],w["replicas"])
        for cj in s["cron"]:
            patch(s["ns"],"cronjob",cj["name"],{"suspend":cj["suspend"]})
    else:
        w=s["workloads"][0]
        scale(s["ns"],"statefulset","postgresql",w["replicas"])
        if w["replicas"]:wait(s["ns"],"statefulset","postgresql",w["replicas"])
        kc_instances(s["cr"]["instances"])
        if s["cr"]["instances"]:wait(s["ns"],"statefulset","keycloak",s["cr"]["instances"])
    s["status"]="RESUMED";store(s)
    print("RESUME_RESULT=PASS\nPROJECT="+p)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("mode",choices=("plan","park","resume"))
    a.add_argument("--project",choices=("instant","keycloak"),required=True)
    x=a.parse_args()
    try:{"plan":plan,"park":park,"resume":resume}[x.mode](x.project)
    except (OSError,RuntimeError,ValueError,KeyError,subprocess.TimeoutExpired) as e:
        print("CRC_IDLE_ERROR="+str(e)[:320],file=sys.stderr);sys.exit(2)
