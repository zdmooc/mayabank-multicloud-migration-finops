#!/usr/bin/env python3
"""Standalone offline HTML dashboard from sanitized OpenShift CRC audit JSON.

No network, Kubernetes access, Secrets, templates, CDN, external dependencies or remote assets.
Run: python scripts/render_openshift_project_html.py evidence/local/private-.../wero-poc.report.json
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re

def e(s):
    return html.escape(str(s if s is not None else "—"), quote=True)

def tag(label, variant="neutral"):
    return '<span class="tag '+e(variant)+'">'+e(label)+'</span>'

def box_svg(x, y, w, h, title, subtitle="", cls="regular"):
    colors={"regular":("#172539","#314a64"),"ingress":("#18354a","#20a6b8"),
            "svc":("#19314c","#4978bf"),"db":("#2b2c45","#b197e8"),
            "stopped":("#3d3943","#d6a36a"),"warning":("#3e3433","#e2a36b")}
    fill,stroke=colors.get(cls,colors["regular"])
    title=e(title[:29]+("…" if len(title)>29 else ""))
    subtitle=e(subtitle[:45]+("…" if len(subtitle)>45 else ""))
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>'
            f'<text x="{x+14}" y="{y+24}" fill="#eef5fc" font-size="14" font-weight="650">{title}</text>'
            f'<text x="{x+14}" y="{y+44}" fill="#adc0d4" font-size="11">{subtitle}</text>')

def svg_shell(inner, width, height, description):
    return (f'<svg class="diagram" role="img" aria-label="{e(description)}" viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="#8da7c7" stroke-width="1.2"/></marker>'
            f'<marker id="dashed-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="#bb9ef4" stroke-width="1.2"/></marker></defs>'
            +inner+'</svg>')

def architecture(rep):
    # Service selector association is real configuration, not an observed business call.
    ws=sorted(rep.get("workloads",[]), key=lambda w:w.get("name",""))
    services=sorted(rep.get("services",[]), key=lambda s:s.get("name",""))
    if not ws:
        return '<p class="muted">Aucun Deployment/StatefulSet/DaemonSet déclaré. Les anciens Jobs et Pods peuvent subsister.</p>'
    h=90+max(len(ws),len(services),1)*60
    parts=['<text x="28" y="28" class="svg-head">Services Kubernetes</text>',
           '<text x="470" y="28" class="svg-head">Workloads et réplicas</text>']
    pts={}
    for i,s in enumerate(services):
        y=44+i*60
        parts.append(box_svg(26,y,367,51,s.get("name","?"),"Service / "+s.get("type","ClusterIP"),"svc"))
        pts[("s",s.get("name"))]=(393,y+25)
    for i,w in enumerate(ws):
        y=44+i*60
        status="stopped" if w.get("desired",0)==0 else "regular"
        if w.get("ready",0)<w.get("desired",0):status="warning"
        parts.append(box_svg(467,y,412,51,w.get("name","?"),
                w.get("kind","")+" • "+str(w.get("ready",0))+"/"+str(w.get("desired",0))+" Ready",status))
        pts[("w",w.get("name"))]=(467,y+25)
    # Edges drawn last: avoid overlapping labels, dotted means selector only.
    for s in services:
        start=pts.get(("s",s.get("name")))
        for target in s.get("workload_candidates",[]):
            end=pts.get(("w",target))
            if start and end:
                parts.append(f'<path d="M{start[0]},{start[1]} C 417,{start[1]} 443,{end[1]} {end[0]-6},{end[1]}" '
                             'fill="none" stroke="#7190be" stroke-dasharray="4 5" stroke-width="1.4" marker-end="url(#arrow)"/>')
    return svg_shell("".join(parts),910,h,"Topologie Services vers workloads selon selecteurs, pas de trafic verifie")

def network(rep):
    services=sorted(rep.get("services",[]), key=lambda x:x.get("name",""))
    routes=rep.get("routes",[])
    if not routes:
        routes=[{"name":"Routes non détaillées dans cette capture", "service":"", "tls":"unknown"}]
    h=90+max(len(routes),len(services),1)*64
    parts=['<text x="20" y="26" class="svg-head">Routes / exposition (métadonnées)</text>',
           '<text x="480" y="26" class="svg-head">Services internes</text>']
    svcy={}
    for i,r in enumerate(routes):
        y=40+i*64
        parts.append(box_svg(20,y,385,52,r.get("name","?"),
                             "→ "+r.get("service","inconnu")+" • TLS "+str(r.get("tls","?")),"ingress"))
    for i,s in enumerate(services):
        y=40+i*64
        svcy[s.get("name")]=y+26
        target=", ".join(s.get("workload_candidates",[])) or "cible non cartographiée"
        ports=", ".join(s.get("ports",[])) or "ports indisponibles"
        parts.append(box_svg(480,y,395,52,s.get("name","?"),target+" • "+ports,"svc"))
    for i,r in enumerate(routes):
        y1=40+i*64+26
        y2=svcy.get(r.get("service"))
        if y2 is not None:
            parts.append(f'<path d="M405,{y1} C435,{y1} 450,{y2} 472,{y2}" fill="none" '
                        'stroke="#20a6b8" stroke-width="1.5" marker-end="url(#arrow)"/>')
    return svg_shell("".join(parts),910,h,"Routes vers services: objets Kubernetes declares, acces effectif non prouve")

def storage(rep):
    pvcs=rep.get("pvc",[])
    ws=rep.get("workloads",[])
    mounted=[(w.get("name","?"),c) for w in ws for c in w.get("pvc_claims",[])]
    transient=[(w.get("name","?"),p) for w in ws for p in w.get("emptydir_mounts",[])]
    if not pvcs and not transient:
        return '<p class="muted">Aucun PVC ou emptyDir recensé dans les workloads du périmètre. Ne prouve pas absence de stockage externe.</p>'
    elements=pvcs+[{"name":p,"phase":"emptyDir", "requested":"éphémère","reclaim":"perdu après recréation du pod"} for _,p in transient]
    h=90+len(elements)*74
    parts=['<text x="24" y="28" class="svg-head">Références dans les workloads</text>',
           '<text x="465" y="28" class="svg-head">Stockage déclaré (pas les octets réels)</text>']
    for i,p in enumerate(elements):
        y=44+i*74
        claim=p.get("name","?")
        refs=[w for w,c in mounted if c==claim]
        if p.get("phase")=="emptyDir":
            refs=[w for w,c in transient if c==claim]
        parts.append(box_svg(24,y,368,54,", ".join(refs) or "Non relié dans ce rapport",
                             "Référence PVC" if p.get("phase")!="emptyDir" else "Montage emptyDir",
                             "regular" if p.get("phase")!="emptyDir" else "warning"))
        parts.append(box_svg(465,y,411,54,claim,
                            p.get("phase","?")+" • "+str(p.get("requested") or "?")+" • "+str(p.get("reclaim") or "?"),
                            "db" if p.get("phase")!="emptyDir" else "warning"))
        parts.append(f'<path d="M392,{y+27} L457,{y+27}" fill="none" stroke="#9d93ca" marker-end="url(#arrow)"/>')
    return svg_shell("".join(parts),910,h,"Association workloads, PersistentVolumeClaims et stockages ephemeres")

def sequence(rep):
    ns=rep.get("namespace")
    if ns=="wero-poc":
        actors=["Client","API Gateway","Payment Service","Consumer PSP","Mock Wero","Mock SCT Inst","PostgreSQL"]
        moves=[(0,1,"Requête paiement"),(1,2,"Routage API"),(2,6,"État / outbox"),(2,3,"Orchestration"),(3,4,"Simulation EPI"),(4,5,"Simulation SCT Inst"),(5,4,"Résultat simulé"),(3,2,"Réponse PSP"),(2,6,"Ledger / réconciliation"),(2,1,"Statut"),(1,0,"Réponse")]
        label="Wero V2/V6 — séquence de référence métier, entièrement illustrative : les pods actuels sont arrêtés"
    else:
        routes=rep.get("routes",[])
        svc=rep.get("services",[])
        actors=["Client","Route","Service","Workload","Dépendance"]
        moves=[(0,1,"Appel hypothétique"),(1,2,"Routage déclaré"),(2,3,"Sélecteur"),(3,4,"Dépendance à vérifier"),(4,3,"Réponse hypothétique"),(3,0,"Retour hypothétique")]
        label="Séquence pédagogique : seuls Route → Service → workload peuvent provenir de métadonnées; aucune requête tracée"
    width=max(1050,len(actors)*186)
    left=100; step=(width-150)/max(1,len(actors)-1)
    height=125+len(moves)*48
    p=[]
    for i,name in enumerate(actors):
        x=int(left+i*step)
        p.append(f'<rect x="{x-76}" y="15" width="152" height="40" rx="8" fill="#19314c" stroke="#617ab6"/>')
        p.append(f'<text x="{x}" y="40" text-anchor="middle" fill="#eef4fb" font-size="12">{e(name)}</text>')
        p.append(f'<line x1="{x}" y1="60" x2="{x}" y2="{height-30}" stroke="#627a9c" stroke-dasharray="5 5"/>')
    for i,(src,dst,txt) in enumerate(moves):
        y=86+i*48
        x1=int(left+src*step);x2=int(left+dst*step)
        dr=1 if x2>=x1 else -1
        p.append(f'<path d="M{x1},{y} L{x2-10*dr},{y}" stroke="#8aa7cd" stroke-width="1.6" fill="none" marker-end="url(#arrow)"/>')
        p.append(f'<text x="{int((x1+x2)/2)}" y="{y-10}" text-anchor="middle" fill="#dce8f9" font-size="12">{e(txt)}</text>')
    return '<p class="evidence-label">'+e(label)+'</p>'+svg_shell("".join(p),width,height,label)

def table(head, records):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join(
      '<tr>'+''.join('<td>'+str(col)+'</td>' for col in row)+'</tr>' for row in records)+'</tbody></table></div>'

def cmd_list(rep):
    ns=rep["namespace"]
    commands=[
      ("État des workloads",f"oc -n {ns} get deployments,statefulsets,daemonsets -o wide"),
      ("Pods et phases",f"oc -n {ns} get pods -o wide"),
      ("Services, routes et politiques réseau",f"oc -n {ns} get services,routes,networkpolicies"),
      ("PVC et classes de stockage",f"oc -n {ns} get pvc -o wide"),
      ("Volume utilisé par les conteneurs",f"oc -n {ns} get pods -o json | jq -r '.items[] | .metadata.name as $p | .spec.volumes[]? | [$p,.name,(if has(\"persistentVolumeClaim\") then \"PVC\" elif has(\"emptyDir\") then \"emptyDir\" else \"OTHER\" end)] | @tsv'"),
      ("Mesure instantanée des conteneurs",f"oc adm top pods -n {ns} --containers"),
      ("Événements récents",f"oc -n {ns} get events --sort-by=.metadata.creationTimestamp"),
      ("État Argo CD des applications", "oc -n openshift-gitops get applications.argoproj.io"),
      ("Contrôle PostgreSQL PVC sans changement",f"oc -n {ns} get pvc -o custom-columns=NAME:.metadata.name,PHASE:.status.phase,VOLUME:.spec.volumeName,SIZE:.spec.resources.requests.storage")
    ]
    if ns=="wero-poc":
        commands.extend([
          ("Wero : statut et problèmes Argo CD", "oc -n openshift-gitops describe application wero-poc-crc"),
          ("Wero : Source et branche GitOps", "oc -n openshift-gitops get application wero-poc-crc -o custom-columns=NAME:.metadata.name,REPO:.spec.source.repoURL,REVISION:.spec.source.targetRevision"),
          ("Wero : PVC PostgreSQL et PV lié","oc -n wero-poc get pvc postgresql-data -o wide"),
          ("Wero : anciennes images et BuildConfigs","oc -n wero-poc get imagestreams,buildconfigs"),
          ("Wero : vérification zéro réplica","oc -n wero-poc get deploy -o custom-columns=NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas")
        ])
    rows=[]
    for lab,cmd in commands:
        rows.append('<div class="command"><div class="command-head"><b>'+e(lab)+'</b><button class="copy" data-copy="'+e(cmd)+'" type="button">Copier</button></div><pre>'+e(cmd)+'</pre></div>')
    return "".join(rows)

def render_html(rep):
    ns=str(rep.get("namespace","unknown"))
    findings=rep.get("findings",[])
    counts=rep.get("counts",{})
    sample=rep.get("sample",{})
    history=rep.get("pod_history") or {}
    workloads=rep.get("workloads",[])
    sev=lambda p: sum(x.get("severity")==p for x in findings)
    counts_txt=[("Workloads",len(workloads)),("Pods totaux",counts.get("pods","—")),
                ("Pods builds",history.get("historical_build_pods","?")),
                ("Pods app Running",history.get("non_build_running_pods","?")),
                ("PVC",counts.get("pvc","—")),("Services",counts.get("services","—")),
                ("P0",sev("P0")),("P1",sev("P1"))]
    tiles="".join('<div class="stat"><span>'+e(k)+'</span><strong>'+e(v)+'</strong></div>' for k,v in counts_txt)
    wk=table(["Type","Workload","État","Images","PVC / emptyDir","CPU m req / top","RAM Mi req / top"],[
        [e(w.get("kind")),e(w.get("name")),tag(str(w.get("ready",0))+"/"+str(w.get("desired",0)),
               "amber" if w.get("desired",0)==0 else ("good" if w.get("ready",0)>=w.get("desired",0) else "bad")),
         '<div class="tiny">'+e(", ".join(w.get("images",[])))+'</div>',
         e(", ".join(w.get("pvc_claims",[])) or "—")+'<div class="tiny">emptyDir: '+e(", ".join(w.get("emptydir_mounts",[])) or "—")+'</div>',
         e(w.get("cpu_req_m"))+" / "+e(w.get("top_cpu_m_if_covered")),
         e(w.get("ram_req_mi"))+" / "+e(w.get("top_ram_mi_if_covered"))] for w in workloads])
    findings_html=table(["Priorité","Code","Diagnostic","Preuve"],[
        [tag(x.get("severity"),"bad" if x.get("severity")=="P0" else ("amber" if x.get("severity")=="P1" else "neutral")),
         '<code>'+e(x.get("code"))+'</code>',e(x.get("detail")),e(x.get("evidence"))] for x in findings]) if findings else '<p class="muted">Aucun constat remonté par les contrôles automatisés. Cela ne démontre pas l’absence de risque.</p>'
    build_rows=table(["BuildConfig","Builds visibles","Completed","Failed","Numéros visibles"], [
        [e(x.get("buildconfig")),e(x.get("visible")),e(x.get("completed")),
         e(x.get("failed")),e(", ".join(map(str,x.get("visible_build_numbers",[]))))]
        for x in history.get("build_groups",[])]) if history.get("build_groups") else (
         '<p class="muted">Aucun historique Build détecté, ou rapport JSON antérieur sans classification de builds.</p>')
    build_head=(
      '<p>Pods Build historiques : <b>'+e(history.get("historical_build_pods","non calculé"))+
      '</b> ; Completed : <b>'+e(history.get("build_completed","?"))+
      '</b> ; Failed : <b>'+e(history.get("build_failed","?"))+
      '</b> ; pods applicatifs Running (hors Build) : <b>'+
      e(history.get("non_build_running_pods","non calculé"))+'</b>.</p>'+
      '<p class="evidence-label">Les noms &lt;service&gt;-N-build désignent des exécutions de construction. '
      'N n’est jamais le numéro d’un réplica et les numéros manquants ne prouvent pas une cause de nettoyage.</p>')
    storage_rows=table(["PVC","Statut","Taille demandée","Politique PV","Occupation réelle"],[
        [e(x.get("name")),e(x.get("phase")),e(x.get("requested")),e(x.get("reclaim")),"NON MESURÉE"] for x in rep.get("pvc",[])]) if rep.get("pvc") else '<p class="muted">Aucun PVC déclaré dans cette capture.</p>'
    policy_rows=table(["Policy","Types","Ingress","Egress","Champs de sélecteur"],[
       [e(p.get("name")),e(", ".join(p.get("types",[])) or "—"),e(p.get("ingress_rules")),e(p.get("egress_rules")),
        e(", ".join(p.get("pod_selector_labels",[])) or "—")]
       for p in rep.get("network_policy_summaries",[])]) if rep.get("network_policy_summaries") else '<p class="muted">Aucune NetworkPolicy visible ou métadonnées absentes. Le filtrage réseau effectif n’a pas été testé.</p>'
    link_rows=table(["Consommateur","Clé de configuration","Service candidat","Preuve"],[
        [e(x.get("application")),e(x.get("env_key")),e(x.get("service_candidate")),e(x.get("proof"))] for x in rep.get("db_consumer_candidates",[])]) if rep.get("db_consumer_candidates") else '<p class="muted">Aucun lien de dépendance inféré des variables hôte simples. Les Secrets/envFrom ne sont pas inspectés.</p>'
    gitops=table(["Application","Sync","Health","Automatique","Conditions"],[
      [e(x.get("name")),e(x.get("sync")),e(x.get("health")),e(x.get("automated")),e(", ".join(x.get("conditions",[])))] for x in rep.get("gitops",[])]) if rep.get("gitops") else '<p class="muted">Aucune Application correspondante accessible/identifiée ; ne conclure ni à l’absence de GitOps ni à une synchronisation réussie.</p>'
    risk_extra=""
    if ns=="wero-poc":
        risk_extra='<div class="notice"><b>Contexte Wero historique :</b> le rapport local indique zéro pod métier actif et un modèle conservé pour archivage. Le PVC <code>postgresql-data</code> a été mesuré séparément à <b>64 Mio</b> dans le CSI du CRC ; cette donnée provient d’un audit antérieur, pas du collecteur HTML actuel. Argo CD a précédemment rencontré une erreur d’accès au dépôt Git privé. <b>SCALE0 / NO_DELETE</b> : pas de redémarrage, pas de suppression avant sauvegarde cohérente et test de restauration.</div>'
    if not rep.get("routes"):
        risk_extra += '<p class="tiny">La version antérieure de l’auditeur ne conservait que le nombre de Routes. Relance un audit avec la version HTML pour afficher les liaisons Route → Service.</p>'
    limitations="".join("<li>"+e(x)+"</li>" for x in rep.get("limitations",[]))
    footprint=sample.get("top_container_match","0/0")
    css=""" 
    :root{color-scheme:dark;--bg:#0b1320;--panel:#121f30;--panel2:#172638;--fg:#eaf2ff;--muted:#9eafc3;--line:#2c3c50;--accent:#4cc1c8}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,-apple-system,Segoe UI,Arial,sans-serif}
    .layout{display:grid;grid-template-columns:230px minmax(0,1fr);min-height:100vh}
    aside{position:sticky;top:0;height:100vh;overflow-y:auto;padding:25px 18px;background:#0e1928;border-right:1px solid var(--line)}
    aside strong{font-size:17px;display:block}aside small{color:var(--muted)}nav a{display:block;color:#b6c9e0;text-decoration:none;border-radius:8px;padding:8px 10px;margin:2px 0}nav a:hover{color:white;background:#1a3249}
    main{max-width:1530px;width:100%;padding:38px clamp(16px,4vw,65px);margin:auto}
    h1{font-size:31px;line-height:1.2;margin:12px 0}h2{font-size:22px;margin:0 0 14px}h3{font-size:16px;margin:0 0 12px}
    p{margin:8px 0 16px}.muted,small{color:var(--muted)}.eyebrow{color:#6ae1df;font-weight:700;letter-spacing:.09em;font-size:11px}
    .lead{color:var(--muted);max-width:950px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:24px 0}
    .stat{border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:14px}.stat span{display:block;color:var(--muted)}.stat strong{display:block;font-size:27px}
    section{padding:24px;margin:23px 0;border:1px solid var(--line);border-radius:15px;background:var(--panel)}
    .scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top}
    th{color:#b2c4d8;font-weight:650;white-space:nowrap;background:#142439}td{overflow-wrap:anywhere}.tiny{font-size:11px;color:var(--muted)}
    .tag{font-size:11px;font-weight:650;display:inline-block;border-radius:6px;padding:2px 8px;border:1px solid #405167;color:#c7d6e7;background:#233248}
    .tag.good{color:#95dccd;border-color:#2e706e;background:#173a40}.tag.amber{color:#ffdcaa;border-color:#8a6340;background:#443629}.tag.bad{color:#ffaaaa;border-color:#a85762;background:#512934}
    .notice{border-left:3px solid #d9a360;background:#2a2931;border-radius:7px;padding:15px;margin:14px 0;color:#f3e4c9}
    .evidence-label{color:#d3b98f;font-size:12px;margin:8px 0}.diagram{width:100%;height:auto;min-width:min(100%,600px);display:block;background:#101b2b;border:1px solid #33465a;border-radius:11px}
    .svg-head{font-size:14px;font-weight:650;fill:#b8cce0}
    .command{background:#0b1523;border:1px solid var(--line);border-radius:9px;margin:10px 0;overflow:hidden}
    .command-head{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--line)}
    pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;padding:14px;margin:0;color:#d1e6f8}
    .copy{background:#253954;color:#e8f2fe;border:1px solid #536c91;border-radius:6px;padding:5px 11px;cursor:pointer}
    .copy:hover{background:#365478}.actions{display:flex;gap:8px;margin:12px 0}.actions button{background:#244c65;border:1px solid #477b8b;color:#e6ffff;border-radius:6px;padding:8px 13px;cursor:pointer}
    code{font-family:ui-monospace,Consolas,monospace;color:#d4e4ff}li{margin:5px 0}
    @media(max-width:870px){.layout{display:block}aside{position:static;height:auto;padding:13px}nav{display:flex;gap:8px;overflow-x:auto}nav a{white-space:nowrap}main{padding:18px}section{padding:15px}h1{font-size:24px}}
    @media print{aside,.actions,.copy{display:none!important}.layout{display:block}main{padding:0}section{page-break-inside:avoid}body{background:white;color:#111}section,.stat{background:white;color:#111;border-color:#ccc}table,th,td{color:#111}h1,h2,h3{color:#111}.diagram{background:#101b2b}}
    """
    js="""document.querySelectorAll('button[data-copy]').forEach(b=>b.addEventListener('click',()=>{
      const s=b.getAttribute('data-copy'); if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(s).then(()=>{b.textContent='Copié';setTimeout(()=>b.textContent='Copier',1400)}).catch(()=>fallback(b,s))}
      else fallback(b,s);
    }));
    function fallback(b,s){const t=document.createElement('textarea');t.value=s;t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();try{document.execCommand('copy');b.textContent='Copié'}catch(e){b.textContent='Sélectionnez la commande'}t.remove();setTimeout(()=>b.textContent='Copier',1500)}
    document.getElementById('print').addEventListener('click',()=>window.print());"""
    def sect(i,title,body):return '<section id="'+i+'"><h2>'+e(title)+'</h2>'+body+'</section>'
    content=[
      '<div class="eyebrow">AUDIT OPENSHIFT LOCAL / CRC · LECTURE SEULE</div>',
      '<h1>'+e(ns)+' — dossier de diagnostic</h1>',
      '<p class="lead">Capture UTC : '+e(rep.get("generated_at_utc","?"))+'. Schémas construits à partir des métadonnées Kubernetes, et non de paquets réseau observés. Fonctionne hors ligne, sans CDN.</p>',
      tiles,risk_extra,
      sect("diagnostic","1. Diagnostic et constats",'<p>Couverture CPU/RAM <b>'+e(footprint)+'</b> ; '
           +'CPU demandé : '+e(sample.get("cpu_req_m_active_containers"))+' m / observé : '+e(sample.get("cpu_top_m_matched_only"))+' m. '
           +'RAM demandée : '+e(sample.get("ram_req_mi_active_containers"))+' Mio / observée : '+e(sample.get("ram_top_mi_matched_only"))+' Mio.</p>'
           +'<p class="muted">Une valeur top à 0 ne signifie pas forcément aucune consommation. Demandes = réservation scheduler, pas plafond ; aucune mesure P95.</p>'+findings_html),
      sect("architecture","2. Architecture applicative",'<p class="evidence-label">Trait plein/pointillé : liaison configurée par selector de Service, trafic non observé. Gris-orangé : scale zéro ou dégradation.</p>'+architecture(rep)),
      sect("sequence","3. Diagramme de séquence",sequence(rep)),
      sect("network","4. Architecture réseau",'<p>Routes : '+e(counts.get("routes"))+' · Services : '+e(counts.get("services"))+' · NetworkPolicies : '+e(counts.get("networkpolicies"))+'. Les objets Route peuvent exister lorsque les Pods sont arrêtés.</p>'+network(rep)+'<h3>Politiques réseau déclarées</h3>'+policy_rows),
      sect("storage","5. Stockage et durabilité",'<p class="muted">PVC Bound ≠ sauvegarde. « Retain » ≠ backup. Occupation et restaurabilité non mesurées par le script.</p>'+storage(rep)+storage_rows),
      sect("inventory","6. Inventaire des workloads",wk+'<h3>Historique de construction OpenShift (BuildConfig)</h3>'+build_head+build_rows),
      sect("dependencies","7. Dépendances candidates",'<p class="evidence-label">La présence d’une variable hôte et la correspondance Service/selector ne prouvent aucune connexion SQL, TCP ni invocation métier.</p>'+link_rows),
      sect("gitops","8. GitOps et exploitation",gitops+'<p>Événements Warning recensés : '+e(counts.get("warning_events",0))+'. Ressources inaccessibles : '+e(", ".join(rep.get("unavailable_or_forbidden_resources",[])) or "Aucune signalée")+'.</p>'),
      sect("commands","9. Commandes de contrôle à exécuter",'<p class="evidence-label">Toutes les commandes ci-dessous sont exclusivement des lectures. Copier une commande ne l’exécute pas. Les commandes de restauration, de redémarrage ou de suppression sont volontairement exclues.</p>'+cmd_list(rep)),
      sect("limits","10. Périmètre et preuves restant à obtenir",'<ul>'+limitations+'</ul><p>Green IT : aucune consommation électrique ni empreinte CO₂ fiable calculée en l’absence de facteurs et de mesures calibrées.</p>')
    ]
    navbar=[("diagnostic","Diagnostic"),("architecture","Architecture"),("sequence","Séquence"),("network","Réseau"),("storage","Stockage"),("inventory","Workloads"),("dependencies","Dépendances"),("gitops","GitOps"),("commands","Commandes"),("limits","Limites")]
    return ('<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+e(ns)+' — Audit OpenShift CRC</title><style>'+css+'</style></head><body>'
            '<div class="layout"><aside><strong>CRC Project Audit</strong><small>'+e(ns)+'<br>Rapport autonome · hors ligne</small>'
            '<nav>'+''.join('<a href="#'+i+'">'+e(n)+'</a>' for i,n in navbar)+'</nav></aside>'
            '<main><div class="actions"><button id="print" type="button">Imprimer / PDF</button></div>'
            +''.join(content)+'<p class="tiny">Généré localement · lecture seule · ne pas publier sans revue des métadonnées internes.</p>'
            '</main></div><script>'+js+'</script></body></html>')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report_json", type=Path, help="Chemin du rapport .report.json créé par le collecteur")
    p.add_argument("--output", type=Path, help="Par défaut, le même basename avec extension .html")
    a=p.parse_args(argv)
    src=a.report_json
    if not src.is_file() or not src.name.endswith(".report.json"):
        p.error("Requiert un fichier existant *.report.json issu de l'auditeur.")
    # Restrict to local private collector path to avoid inadvertently publishing internals.
    if "evidence/local/private-openshift-audit-" not in str(src).replace("\\","/"):
        p.error("Rapport attendu sous evidence/local/private-openshift-audit-*/")
    rep=json.loads(src.read_text(encoding="utf-8"))
    output=a.output or src.with_suffix("").with_suffix(".report.html")
    if output.parent.resolve()!=src.parent.resolve():
        p.error("Le HTML doit rester dans le même dossier privé que le JSON.")
    output.write_text(render_html(rep),encoding="utf-8")
    print("HTML_REPORT="+str(output))
    print("OFFLINE_NO_REMOTE_ASSETS=true")
    print("NO_CLUSTER_QUERIES_FOR_HTML=true")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
