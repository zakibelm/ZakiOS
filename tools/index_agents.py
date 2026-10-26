import sys, os, re, json, math
from collections import Counter, defaultdict

root, outdir = sys.argv[1], sys.argv[2]
THRESH = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55

STOP = set("""a an the and or of to in for with on is are be as by at from that this it its you your use when
will can not do does into any all more most also such than then they their them has have had was were been
should would could may might must about over under between per via etc e g i s t d""".split())

def parse(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", txt, re.S)
    fm, body = ("", txt) if not m else (m.group(1), m.group(2))
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+?)(?=^\w+:|\Z)", fm, re.M | re.S)
    tools = re.search(r"^tools:\s*(.+)$", fm, re.M)
    model = re.search(r"^model:\s*(.+)$", fm, re.M)
    d = desc.group(1).strip().strip('"') if desc else ""
    d_short = re.split(r"\\n|\n|<example>", d)[0].strip()
    return {
        "name": (name.group(1).strip().strip('"') if name else os.path.splitext(os.path.basename(path))[0]),
        "description": d_short[:300],
        "tools": tools.group(1).strip() if tools else "",
        "model": model.group(1).strip() if model else "",
        "bytes": len(txt.encode()),
        "text": (d_short + " " + body)[:2500],
    }

items = []
for dp, _, fs in os.walk(root):
    for f in fs:
        if f.endswith(".md"):
            p = os.path.join(dp, f)
            rec = parse(p)
            rec["category"] = os.path.relpath(dp, root).split(os.sep)[0]
            rec["path"] = os.path.relpath(p, root)
            items.append(rec)
items.sort(key=lambda r: r["path"])

def toks(t):
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", t.lower()) if w not in STOP]

docs = [Counter(toks(r["text"])) for r in items]
df = Counter()
for d in docs:
    df.update(d.keys())
N = len(docs)
vecs = []
for d in docs:
    v = {w: (1 + math.log(c)) * math.log(N / df[w]) for w, c in d.items()}
    n = math.sqrt(sum(x * x for x in v.values())) or 1
    vecs.append({w: x / n for w, x in v.items()})

def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0) for w, x in a.items())

parent = list(range(N))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    parent[find(a)] = find(b)

pairs = []
by_name = defaultdict(list)
for i, r in enumerate(items):
    by_name[re.sub(r"[^a-z0-9]", "", r["name"].lower())].append(i)
exact = 0
for ids in by_name.values():
    for j in ids[1:]:
        union(ids[0], j)
        exact += 1
for i in range(N):
    for j in range(i + 1, N):
        s = cos(vecs[i], vecs[j])
        if s >= THRESH:
            union(i, j)
            pairs.append((round(s, 3), i, j))

groups = defaultdict(list)
for i in range(N):
    groups[find(i)].append(i)
dups = sorted([g for g in groups.values() if len(g) > 1], key=lambda g: -len(g))

index = [{k: v for k, v in r.items() if k != "text"} for r in items]
json.dump(index, open(os.path.join(outdir, "agents_index.json"), "w"), ensure_ascii=False, indent=1)
out = []
for g in dups:
    out.append([{"name": items[i]["name"], "path": items[i]["path"], "bytes": items[i]["bytes"],
                 "description": items[i]["description"][:160]} for i in g])
json.dump(out, open(os.path.join(outdir, "agents_groups.json"), "w"), ensure_ascii=False, indent=1)

print("agents:", N)
print("categories:", len(set(r["category"] for r in items)))
print("exact-name merges:", exact)
print("groups >1:", len(dups), "| agents inside groups:", sum(len(g) for g in dups))
print("sizes:", Counter(len(g) for g in dups))
print("unique after merging (one canonical per group):", N - sum(len(g) - 1 for g in dups))
