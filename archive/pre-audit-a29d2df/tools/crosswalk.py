import sys, os, re, json, math, csv
from collections import Counter, defaultdict

out = sys.argv[1]
SOCLE = [
    ("wshobson/agents", "/home/claude/wshobson/agents"),
    ("VoltAgent/awesome-claude-code-subagents", "/home/claude/voltagent/awesome-claude-code-subagents"),
    ("rohitg00/awesome-claude-code-toolkit", "/home/claude/rohitg00/awesome-claude-code-toolkit"),
    ("anthropics/skills", "/home/claude/anthropics/skills"),
    ("netresearch/claude-code-marketplace", "/home/claude/netresearch/claude-code-marketplace"),
    ("disler/claude-code-hooks-mastery", "/home/claude/disler/claude-code-hooks-mastery"),
    ("karanb192/claude-code-hooks", "/home/claude/karanb192/claude-code-hooks"),
    ("affaan-m/claude-swarm", "/home/claude/affaan-m/claude-swarm"),
    ("am-will/swarms", "/home/claude/am-will/swarms"),
    ("eugeniughelbur/obsidian-second-brain", "/home/claude/eugeniughelbur/obsidian-second-brain"),
]
AITMPL = ("davila7/claude-code-templates", "/home/claude/davila7/claude-code-templates/cli-tool/components")

STOP = set("""a an the and or of to in for with on is are be as by at from that this it its you your use when
will can not do does into any all more most also such than then they their them has have had was were been
should would could may might must about over under between per via etc e g i s t d using used uses""".split())
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

def fm(txt):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", txt, re.S)
    if not m:
        return {}, txt
    head, body = m.group(1), m.group(2)
    d = {}
    for k in ("name", "description", "tools", "model"):
        mm = re.search(r"^%s:\s*(.+?)(?=^\w[\w-]*:|\Z)" % k, head, re.M | re.S)
        if mm:
            d[k] = re.sub(r"\s+", " ", mm.group(1).strip().strip('"').strip("'"))
    return d, body

def first_text(body):
    for line in body.splitlines():
        s = line.strip().lstrip("#").strip()
        if len(s) > 25 and not s.startswith(("```", "|", "<", "-", "*")):
            return s
    return ""

def classify(rel, fname):
    parts = [p.lower() for p in rel.split(os.sep)]
    f = fname.lower()
    if f == "skill.md":
        return "skill"
    if parts[:1] == ["plugins"] and f == "plugin.json" and ".claude-plugin" in parts:
        return "hook"
    if "categories" in parts and f.endswith(".md") and f not in ("readme.md", "changelog.md"):
        return "agent"
    if parts[:2] == ["src", "claude_swarm"] and f.endswith(".py") and f not in ("__init__.py", "cli.py", "ui.py", "demo.py", "types.py", "config.py"):
        return "framework"
    if "hooks" in parts and f.endswith((".py", ".js", ".sh", ".ts", ".mjs")):
        return "hook"
    if "commands" in parts and f.endswith(".md"):
        return "command"
    if any(p in ("agents", "subagents") for p in parts) and f.endswith(".md") and f not in ("readme.md", "changelog.md"):
        return "agent"
    if "mods" in parts and f == "readme.md" and len(parts) >= 4:
        return "mod"
    return None

def read(p, n=6000):
    try:
        return open(p, encoding="utf-8", errors="replace").read(n)
    except Exception:
        return ""

def scan(repo, root, commit):
    recs = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fns:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            t = classify(rel, f)
            if not t:
                continue
            txt = read(p)
            if t in ("skill", "agent", "command"):
                d, body = fm(txt)
                name = d.get("name") or (os.path.basename(os.path.dirname(p)) if t == "skill" else os.path.splitext(f)[0])
                desc = d.get("description") or first_text(body)
                text = desc + " " + body[:2000]
            elif t == "hook" and f == "plugin.json":
                try:
                    pj = json.loads(read(p, 20000))
                except Exception:
                    pj = {}
                name = pj.get("name") or os.path.basename(os.path.dirname(os.path.dirname(p)))
                desc = pj.get("description", "")
                text = desc + " " + " ".join(pj.get("keywords", []))
            elif t == "framework":
                name = os.path.splitext(f)[0]
                m = re.match(r'\s*"""(.{20,300}?)(\n\n|""")', txt, re.S)
                desc = re.sub(r"\s+", " ", m.group(1)) if m else ""
                text = name + " " + txt[:2000]
            elif t == "mod":
                name = os.path.basename(os.path.dirname(p))
                desc = first_text(txt)
                text = txt[:2500]
            else:  # hook
                name = os.path.splitext(f)[0]
                m = re.search(r'("""|\'\'\'|/\*\*?|#)\s*(.{20,200}?)(\n|\*/|"""|\'\'\')', txt, re.S)
                desc = re.sub(r"\s+", " ", m.group(2)) if m else ""
                text = name.replace("_", " ").replace("-", " ") + " " + txt[:1500]
            recs.append({"source": repo, "commit": commit, "path": rel, "type": t, "name": name,
                         "description": re.sub(r"\s+", " ", desc)[:240], "bytes": os.path.getsize(p), "_text": text})
    return recs

def commit_of(root):
    d = root
    while d != "/" and not os.path.isdir(os.path.join(d, ".git")):
        d = os.path.dirname(d)
    h = os.path.join(d, ".git", "HEAD")
    try:
        ref = open(h).read().strip()
        if ref.startswith("ref:"):
            return open(os.path.join(d, ".git", ref.split(" ")[1])).read().strip()[:12]
        return ref[:12]
    except Exception:
        return "?"

socle = []
for repo, root in SOCLE:
    socle += scan(repo, root, commit_of(root))
aitmpl = scan(AITMPL[0], AITMPL[1], commit_of(AITMPL[1]))
# in aitmpl, 'hooks' and 'mods' folders sit under components/<type>/..., keep scan results as is

def toks(t):
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", t.lower()) if w not in STOP]

allrecs = socle + aitmpl
N = len(allrecs)
docs = [Counter(toks(r["_text"])) for r in allrecs]
df = Counter()
for d in docs:
    df.update(d.keys())
vecs = []
for d in docs:
    v = {w: (1 + math.log(c)) * math.log(N / df[w]) for w, c in d.items()}
    n = math.sqrt(sum(x * x for x in v.values())) or 1
    vecs.append({w: x / n for w, x in v.items()})

# inverted index over Socle per type
post = defaultdict(lambda: defaultdict(list))
for i, r in enumerate(socle):
    for w, x in vecs[i].items():
        post[r["type"]][w].append((i, x))

LAYER = {"agent": "Agent", "skill": "Skill", "command": "Commande", "hook": "Hook/Mod", "mod": "Hook/Mod", "framework": "Socle/Orchestration"}
rows = []
for k, r in enumerate(aitmpl):
    i = len(socle) + k
    v = vecs[i]
    scores = Counter()
    # cross-family match: agent<->agent, skill<->skill, ... ; mods compared with hooks
    fam = "hook" if r["type"] == "mod" else r["type"]
    for w, x in v.items():
        for j, y in post[fam].get(w, ()):
            scores[j] += x * y
    if scores:
        j, s = scores.most_common(1)[0]
        e = socle[j]
        s = round(s, 3)
    else:
        e, s = None, 0.0
    if s >= 0.60:
        dec, why = "Remplacer par le Socle (ou écarter)", "Fonction très proche d'un composant déjà présent dans le Socle"
    elif s >= 0.40:
        dec, why = "Fusionner / Variante", "Chevauchement partiel : garder l'apport distinct, fusionner le reste"
    else:
        dec, why = "Adopter (apport unique probable)", "Aucun équivalent proche dans le Socle des 10"
    # unique contribution: top distinctive tokens not in equivalent
    uniq = ""
    if e is not None:
        ej = socle.index(e)
        mine = sorted(v.items(), key=lambda kv: -kv[1])
        uniq = ", ".join(w for w, _ in mine if w not in vecs[ej])[:0] or ", ".join([w for w, _ in mine if w not in vecs[ej]][:6])
    else:
        uniq = ", ".join([w for w, _ in sorted(v.items(), key=lambda kv: -kv[1])][:6])
    rows.append({
        "source": r["source"], "commit": r["commit"], "path": r["path"], "type": r["type"], "name": r["name"],
        "fonction_reelle": r["description"], "couche_cible": LAYER[r["type"]],
        "equivalent_existant": (e["source"] + ":" + e["path"]) if e else "", "similarite": s,
        "apport_unique_termes": uniq, "decision": dec + " — provisoire (comparaison ZAKI OS manquante)",
        "justification": why,
    })

json.dump([{k: v for k, v in r.items() if k != "_text"} for r in socle], open(os.path.join(out, "socle_index.json"), "w"), ensure_ascii=False, indent=1)
with open(os.path.join(out, "aitmpl_vs_socle.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("Socle composants:", len(socle), dict(Counter(r["type"] for r in socle)))
for repo, _ in SOCLE:
    print("  ", repo, Counter(r["type"] for r in socle if r["source"] == repo).most_common())
print("aitmpl composants:", len(aitmpl), dict(Counter(r["type"] for r in aitmpl)))
bt = defaultdict(Counter)
for r in rows:
    bt[r["type"]][r["decision"].split(" — ")[0]] += 1
for t, c in bt.items():
    print(t, dict(c))
