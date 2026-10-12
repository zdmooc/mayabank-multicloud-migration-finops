#!/usr/bin/env python3
"""CRC LAB ONLY: deliberately stop ephemeral TradeOps stores and IBM MQ; preserve PVC and manifests."""
import argparse, importlib.util, json, os, sys, time
from pathlib import Path
BASE = Path(__file__).with_name("crc-extra-projects-mode.py")
spec = importlib.util.spec_from_file_location("crc_extra_park", BASE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
EXPECTED = {
 "tradeops": {"ns":"tradeops",
   "dep":["agent-controller","ai-access-policy","genai-api","grafana","litellm","market-data","mcp-server","notifier","otel-collector","paper-oms","prometheus","rag-api","risk-engine","tradeops-ui","workflow-api"],
   "sts":["postgres","qdrant","redpanda"],"pvc":[]},
 "mq": {"ns":"mayabank-mq-local",
   "dep":["mq","mq-ops-api","mq-prometheus-exporter","payment-processing","payments-db"],
   "sts":[],"pvc":["mq-data","payments-db-data"]}
}
STATE = Path.home() / ".crc-capacity"
def path(p): return STATE / ("crc-deep-" + p + ".json")
def inspect(p):
 m.check_crc()
 e=EXPECTED[p]; ns=e["ns"]
 for kind,key in (("deployments","dep"),("statefulsets","sts"),("pvc","pvc")):
  got={x["metadata"]["name"]:x for x in m.ls(ns,kind)}
  if set(got)!=set(e[key]): raise RuntimeError("UNEXPECTED_"+kind+":"+str(sorted(set(got)^set(e[key]))))
  if key=="pvc" and any(x["status"]["phase"]!="Bound" for x in got.values()): raise RuntimeError("PVC_NOT_BOUND")
  e[key+"_items"]=got
 if m.ls(ns,"hpa") or m.ls(ns,"daemonsets"): raise RuntimeError("HPA_OR_DAEMONSET_PRESENT")
 if any(x.get("status",{}).get("active",0)>0 for x in m.ls(ns,"jobs")): raise RuntimeError("ACTIVE_JOBS_PRESENT")
 workloads=[{"kind":kind,"name":n,"uid":obj["metadata"]["uid"],"replicas":obj["spec"].get("replicas",1)}
   for kind,key in (("deployment","dep"),("statefulset","sts")) for n,obj in sorted(e[key+"_items"].items())]
 cron=[{"name":c["metadata"]["name"],"uid":c["metadata"]["uid"],"suspend":c["spec"].get("suspend")}
       for c in m.ls(ns,"cronjobs")]
 apps=[]
 for a in m.oc("get","applications.argoproj.io","-A","-o","json")["items"]:
  if a.get("spec",{}).get("destination",{}).get("namespace")!=ns: continue
  if any(r.get("kind")=="ApplicationSet" for r in a["metadata"].get("ownerReferences",[])): raise RuntimeError("APPSET_OWNED")
  apps.append({"namespace":a["metadata"]["namespace"],"name":a["metadata"]["name"],
    "uid":a["metadata"]["uid"],"automated":a["spec"].get("syncPolicy",{}).get("automated")})
 if p=="mq" and not {"mayabank-mq-local-core","mayabank-mq-local-db"}.issubset(
     {a["name"] for a in apps if a["automated"] is not None}): raise RuntimeError("MQ_ARGO_AUTO_MISSING")
 return {"project":p,"namespace":ns,"workloads":workloads,"cronjobs":cron,"apps":apps,
   "pvc":[{"name":n,"uid":x["metadata"]["uid"]} for n,x in e["pvc_items"].items()],
   "node_uid":m.oc("get","node","crc","-o","json")["metadata"]["uid"],
   "namespace_uid":m.oc("get","namespace",ns,"-o","json")["metadata"]["uid"]}
def snap(s): m.state_write(path(s["project"]),s)
def original(p):
 s=m.state_read(path(p))
 if s["project"]!=p or s["namespace"]!=EXPECTED[p]["ns"]: raise RuntimeError("WRONG_SNAPSHOT")
 return s
def verify(s):
 m.check_crc()
 ns=s["namespace"]
 if m.oc("get","node","crc","-o","json")["metadata"]["uid"]!=s["node_uid"]: raise RuntimeError("NODE_CHANGED")
 if m.oc("get","namespace",ns,"-o","json")["metadata"]["uid"]!=s["namespace_uid"]: raise RuntimeError("NAMESPACE_CHANGED")
 for w in s["workloads"]:
  if m.get(ns,w["kind"],w["name"])["metadata"]["uid"]!=w["uid"]: raise RuntimeError("WORKLOAD_RECREATED:"+w["name"])
 for a in s["apps"]:
  if m.get(a["namespace"],"application",a["name"])["metadata"]["uid"]!=a["uid"]: raise RuntimeError("ARGO_RECREATED")
 for c in s["cronjobs"]:
  if m.get(ns,"cronjob",c["name"])["metadata"]["uid"]!=c["uid"]: raise RuntimeError("CRON_RECREATED")
 for x in s["pvc"]:
  if m.get(ns,"pvc",x["name"])["metadata"]["uid"]!=x["uid"]: raise RuntimeError("PVC_RECREATED")
def scale(ns,kind,name,n):
 m.oc("-n",ns,"scale",kind+"/"+name,"--replicas="+str(n))
 if m.get(ns,kind,name)["spec"].get("replicas",1)!=n: raise RuntimeError("SCALE_FAILED:"+name)
def wait(ns,kind,name,count):
 end=time.monotonic()+240
 while time.monotonic()<end:
  obj=m.get(ns,kind,name); st=obj.get("status",{})
  if count==0 and st.get("replicas",0)==0 and st.get("readyReplicas",0)==0: return
  if count>0 and st.get("readyReplicas",0)>=count: return
  time.sleep(4)
 raise RuntimeError("ROLL_OUT_TIMEOUT:"+kind+"/"+name)
def auto(a,n):
 m.patch(a["namespace"],"application",a["name"],{"spec":{"syncPolicy":{"automated":n}}})
 live=m.get(a["namespace"],"application",a["name"])["spec"].get("syncPolicy",{}).get("automated")
 if live!=n: raise RuntimeError("ARGO_PATCH_FAILED")
def cron(ns,c,n):
 m.patch(ns,"cronjob",c["name"],{"spec":{"suspend":n}})
 if m.get(ns,"cronjob",c["name"])["spec"].get("suspend")!=n: raise RuntimeError("CRON_PATCH_FAILED")
def running_pods(ns):
 return [x["metadata"]["name"] for x in m.ls(ns,"pods")
         if x.get("status",{}).get("phase")=="Running"]
def wait_running_pods_gone(ns, seconds=180):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  if not running_pods(ns): return
  time.sleep(4)
 raise RuntimeError("RUNNING_PODS_REMAIN:"+",".join(running_pods(ns)))
def finalize(p):
 # Read-only Kubernetes validation. Changes only the local saved status.
 s=original(p)
 if s["status"]=="PARKED":
  print("ALREADY_PARKED=YES"); return
 if s["status"]!="PARK_PARTIAL": raise RuntimeError("FINALIZE_REQUIRES_PARK_PARTIAL")
 verify(s)
 ns=s["namespace"]
 for w in s["workloads"]:
  obj=m.get(ns,w["kind"],w["name"])
  if obj["spec"].get("replicas",1)!=0: raise RuntimeError("LIVE_REPLICAS_NOT_ZERO:"+w["name"])
  if obj.get("status",{}).get("readyReplicas",0)!=0: raise RuntimeError("READY_REPLICAS_REMAIN:"+w["name"])
 for a in s["apps"]:
  live=m.get(a["namespace"],"application",a["name"])["spec"].get("syncPolicy",{}).get("automated")
  if a["automated"] is not None and live is not None:
   raise RuntimeError("ARGO_AUTOSYNC_STILL_ACTIVE:"+a["name"])
 for c in s["cronjobs"]:
  if m.get(ns,"cronjob",c["name"])["spec"].get("suspend") is not True:
   raise RuntimeError("CRONJOB_NOT_SUSPENDED:"+c["name"])
 current=running_pods(ns)
 if current: raise RuntimeError("RUNNING_PODS_REMAIN:"+",".join(current))
 s["status"]="PARKED"; snap(s)
 print("FINALIZE_RESULT=PASS", "PROJECT="+p, "PVC_DELETED=0",
       "SNAPSHOT="+str(path(p)), sep="\\n")
def plan(p):
 s=inspect(p)
 print("MODE=PLAN_READ_ONLY", "PROJECT="+p, "ACTIVE="+",".join(w["kind"]+"/"+w["name"] for w in s["workloads"] if w["replicas"]),
       "ARGO_AUTO="+",".join(a["name"] for a in s["apps"] if a["automated"] is not None),
       "PVC_PRESERVED="+",".join(x["name"] for x in s["pvc"]),
       "DATA_LOSS_IF_EPHEMERAL=true", "LIVE_CHANGE=false",sep="\n")
def park(p):
 if any(os.getenv(x)!="YES" for x in ("CRC_DEEP_PARK","CRC_ACK_DATA_LOSS","CRC_ACK_DOWNTIME","CRC_ACK_REBUILD")):
  raise RuntimeError("EXPLICIT_DATA_LOSS_AND_DOWNTIME_ACK_REQUIRED")
 if path(p).exists() and original(p).get("status")!="RESUMED": raise RuntimeError("ACTIVE_SNAPSHOT_EXISTS")
 s=inspect(p); ns=s["namespace"]; s["status"]="PARKING"; snap(s)
 try:
  for a in s["apps"]:
   if a["automated"] is not None: auto(a,None)
  for c in s["cronjobs"]:
   if c["suspend"] is not True: cron(ns,c,True)
  order=(["payment-processing","mq-ops-api","mq-prometheus-exporter","mq","payments-db"]
         if p=="mq" else [w["name"] for w in s["workloads"] if w["kind"]=="deployment"])
  idx={(w["kind"],w["name"]):w for w in s["workloads"]}
  for name in order:
   if idx["deployment",name]["replicas"]:
    print("STOP=deployment/"+name,flush=True); scale(ns,"deployment",name,0); wait(ns,"deployment",name,0)
  for name in (["qdrant","redpanda","postgres"] if p=="tradeops" else []):
   if idx["statefulset",name]["replicas"]:
    print("STOP=statefulset/"+name,flush=True); scale(ns,"statefulset",name,0); wait(ns,"statefulset",name,0)
  for w in s["workloads"]:
   if m.get(ns,w["kind"],w["name"])["spec"].get("replicas",1)!=0: raise RuntimeError("WORKLOAD_NOT_ZERO")
  # Workload status reaches zero before terminating pods necessarily disappear.
  wait_running_pods_gone(ns)
  s["status"]="PARKED"; snap(s)
 except Exception:
  s["status"]="PARK_PARTIAL"; snap(s); print("PARTIAL_STOP_NO_AUTORESTORE=YES",file=sys.stderr); raise
 print("PARK_RESULT=PASS", "PROJECT="+p, "SNAPSHOT="+str(path(p)), "PVC_DELETED=0",sep="\n")
def resume(p):
 if os.getenv("CRC_DEEP_RESUME")!="YES": raise RuntimeError("RESUME_REQUIRES_ACK")
 s=original(p)
 if s["status"]=="RESUMED": print("ALREADY_RESUMED=YES");return
 if s["status"] not in ("PARKED","PARK_PARTIAL","RESUME_PARTIAL"): raise RuntimeError("BAD_SNAPSHOT_STATUS")
 verify(s);s["status"]="RESUME_PARTIAL";snap(s);ns=s["namespace"]
 idx={(w["kind"],w["name"]):w for w in s["workloads"]}
 if p=="tradeops":
  for name in ("postgres","redpanda","qdrant"):
   w=idx["statefulset",name];scale(ns,"statefulset",name,w["replicas"])
   if w["replicas"]:wait(ns,"statefulset",name,w["replicas"])
  names=EXPECTED[p]["dep"]
 else: names=["payments-db","mq","mq-ops-api","mq-prometheus-exporter","payment-processing"]
 for name in names:
  w=idx["deployment",name];scale(ns,"deployment",name,w["replicas"])
  if w["replicas"]:wait(ns,"deployment",name,w["replicas"])
 for c in s["cronjobs"]:cron(ns,c,c["suspend"])
 for a in s["apps"]:
  live=m.get(a["namespace"],"application",a["name"])["spec"].get("syncPolicy",{}).get("automated")
  if live is None and a["automated"] is not None:auto(a,a["automated"])
  elif live!=a["automated"]:raise RuntimeError("ARGO_POLICY_DRIFT")
 s["status"]="RESUMED";snap(s)
 print("RESUME_RESULT=PASS", "DATA_REBUILD_MAY_BE_REQUIRED=true",sep="\n")
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("mode",choices=("plan","park","resume","finalize"));a.add_argument("--project",choices=EXPECTED,required=True);v=a.parse_args()
 try: {"plan":plan,"park":park,"resume":resume,"finalize":finalize}[v.mode](v.project)
 except (RuntimeError,ValueError,KeyError,OSError) as e: print("CRC_DEEP_ERROR="+str(e)[:300],file=sys.stderr);sys.exit(2)
