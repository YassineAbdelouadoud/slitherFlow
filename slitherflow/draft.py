"""Turn a `snakemake --rulegraph` (DOT) into a starter YAML spec, from the graph's shape alone."""
import re
import sys


def pretty(rule):
    words = rule.replace("-", "_").split("_")
    return " ".join([words[0].capitalize()] + words[1:]) if words else rule


def find_terminus(succ, pred):
    """The rule where the pipeline converges, read from the graph shape alone (rule names are ignored).

    Candidates are sink rules (nothing downstream except `all`) that collect from two or more rules. The one with
    the most direct inputs wins (the most lines end there); ties go to the one with the most upstream rules, then
    to the earlier rule in the rule graph. Returns None if no sink merges branches."""
    def ancestors(i):
        seen, stack = set(), list(pred[i])
        while stack:
            j = stack.pop()
            if j not in seen:
                seen.add(j)
                stack.extend(pred[j])
        return seen

    sinks = [i for i in succ if not succ[i] and len(pred[i]) >= 2]
    if not sinks:
        return None
    order = {i: k for k, i in enumerate(succ)}
    return max(sinks, key=lambda i: (len(pred[i]), len(ancestors(i)), -order[i]))


def spec_from_rulegraph(dot_text, title="My pipeline"):
    names, edges = {}, []
    for line in dot_text.splitlines():
        m = re.match(r'\s*(\d+)\s*\[\s*label\s*=\s*"([^"]+)"', line)
        if m:
            names[m.group(1)] = m.group(2)
            continue
        m = re.match(r"\s*(\d+)\s*->\s*(\d+)", line)
        if m:
            edges.append((m.group(1), m.group(2)))
    if not names:
        sys.exit("no rules found: is this the output of `snakemake --rulegraph`?")
    rules = {i: n for i, n in names.items() if n != "all"}
    succ = {i: [] for i in rules}
    pred = {i: [] for i in rules}
    for a, b in edges:
        if a in rules and b in rules and b not in succ[a]:
            succ[a].append(b)
            pred[b].append(a)
    term = find_terminus(succ, pred)
    feeds_term = set(pred[term]) if term else set()
    nodes = [i for i in rules if i != term]
    S = {i: [j for j in succ[i] if j != term] for i in nodes}
    P = {i: [j for j in pred[i] if j != term] for i in nodes}

    def descendants(i, seen=None):
        seen = set() if seen is None else seen
        for j in S[i]:
            if j not in seen:
                seen.add(j)
                descendants(j, seen)
        return seen

    memo = {}

    def longest_path(i):
        if i not in memo:
            memo[i] = [i] + max((longest_path(j) for j in S[i]), key=len, default=[])
        return memo[i]

    # topological order, and each rule's depth (longest path from a source): a rough stand-in for its x position
    order, indeg = [], {i: len(P[i]) for i in nodes}
    ready = [i for i in nodes if not indeg[i]]
    while ready:
        i = ready.pop(0)
        order.append(i)
        for j in S[i]:
            indeg[j] -= 1
            if not indeg[j]:
                ready.append(j)
    depth = {}
    for i in order:
        depth[i] = max((depth[j] + 1 for j in P[i]), default=0)

    sources = [i for i in nodes if not P[i]]
    if not sources:
        sys.exit("the rule graph has no source rule")
    main = max(sources, key=lambda i: len(descendants(i)))
    # trunk: follow the longest path while the next rule has a single input; stop after a hub (3+ successors)
    trunk, path = [], longest_path(main)
    for k, i in enumerate(path):
        trunk.append(i)
        nxt = path[k + 1] if k + 1 < len(path) else None
        if nxt is None or len(S[i]) >= 3 or len(P[nxt]) != 1:
            break
    assigned = {i: ("trunk", None) for i in trunk}

    def chain(start):
        """Rules for one line: follow the longest path; rules it passes by become branches later."""
        c, i = [], start
        while i is not None and i not in assigned:
            c.append(i)
            assigned[i] = None
            nxt = [j for j in S[i] if j not in assigned]
            i = max(nxt, key=lambda j: len(longest_path(j))) if nxt else None
        return c

    def tail_target(c, lid):
        last = c[-1]
        if last in feeds_term:
            return "terminus"
        for j in S[last]:
            if assigned.get(j) and assigned[j][0] != "trunk" and assigned[j][0] != lid:
                return {"line": assigned[j][0], "station": pretty(rules[j])}
        return "none"

    lines, row_cycle = {}, [-1, 1, 0, -2, 2, -3, 3]
    hub = trunk[-1]
    for k, j in enumerate(S[hub]):
        if j in assigned:
            continue
        c = chain(j)
        lid = f"line{len(lines) + 1}"
        for i in c:
            assigned[i] = (lid, None)
        lines[lid] = {"name": pretty(rules[c[0]]), "row": row_cycle[len(lines) % len(row_cycle)], "_chain": c,
                      "_start": depth[hub], "_origin": hub}
    for t in trunk[:-1]:
        for j in S[t]:
            if j in assigned:
                continue
            c = chain(j)
            lid = f"side{len(lines) + 1}"
            for i in c:
                assigned[i] = (lid, None)
            lines[lid] = {"name": pretty(rules[c[0]]), "from": pretty(rules[t]), "optional": True, "_chain": c,
                          "_start": depth[t], "_origin": t}
    for src in sources:
        if src in assigned:
            continue
        c = chain(src)
        lid = f"side{len(lines) + 1}"
        for i in c:
            assigned[i] = (lid, None)
        lines[lid] = {"name": pretty(rules[c[0]]), "from": "input", "optional": True, "_chain": c, "_start": -1, "_origin": None}
    # every rule still unplaced branches off the station of its latest placed input
    for j in order:
        if j in assigned:
            continue
        p = max((p for p in P[j] if assigned.get(p)), key=lambda p: depth[p], default=None)
        if p is None:
            continue
        c = chain(j)
        lid = f"branch{len(lines) + 1}"
        for i in c:
            assigned[i] = (lid, None)
        par = assigned[p][0]
        frm = pretty(rules[p]) if par == "trunk" else {"line": par, "station": pretty(rules[p])}
        lines[lid] = {"name": pretty(rules[c[0]]), "from": frm, "_chain": c, "_start": depth[p], "_origin": p}
    end_depth = max(depth.values(), default=0) + 1
    for lid, ln in lines.items():
        ln["to"] = to = tail_target(ln["_chain"], lid)
        end = max(depth[i] for i in ln["_chain"])
        if to == "terminus":
            end = end_depth
        elif isinstance(to, dict):
            end = max([end] + [depth[j] for j in S[ln["_chain"][-1]] if assigned[j][0] == to["line"]])
        ln["_end"] = end
    # connections the lines already show; every other one (except inputs to the terminus) becomes a `feeds:`
    drawn = set(zip(trunk, trunk[1:]))
    for ln in lines.values():
        c = ln["_chain"]
        drawn |= set(zip(c, c[1:]))
        if ln["_origin"] is not None:
            drawn.add((ln["_origin"], c[0]))
        to = ln["to"]
        if isinstance(to, dict):
            drawn |= {(c[-1], j) for j in S[c[-1]] if assigned.get(j) and assigned[j][0] == to["line"]
                      and pretty(rules[j]) == to["station"]}
    feeds = {i: [j for j in S[i] if (i, j) not in drawn and assigned.get(j) and assigned[j][0] != "trunk"]
             for i in nodes if i in assigned}
    # side-line rows: just outside the line they join; otherwise outside all main lines on the side of the lines
    # they feed, or alternating above and below
    main_rows = [ln["row"] for ln in lines.values() if "from" not in ln] or [0]
    used = set(main_rows)
    outside = max(abs(r) for r in main_rows) + 0.6
    flip = -1
    for lid, ln in lines.items():
        if "from" not in ln or isinstance(ln["from"], dict):
            continue
        to = ln["to"]
        if isinstance(to, dict) and "row" in lines.get(to["line"], {}):
            base = lines[to["line"]]["row"]
            direction = 1 if base >= 0 else -1
            row = base + 0.6 * direction
        else:
            fed = [lines[assigned[j][0]]["row"] for i in ln["_chain"] for j in feeds.get(i, [])
                   if "row" in lines[assigned[j][0]]]
            if fed:
                direction = 1 if sum(fed) >= 0 else -1
            elif ln["from"] == "input":
                direction = 1
            else:
                direction, flip = flip, -flip
            row = outside * direction
        while round(row, 1) in used:
            row += 0.5 * direction
        ln["row"] = round(row, 1)
        used.add(ln["row"])
    # branch rows: the nearest row next to the parent line (outwards first) that keeps 0.6 rows clear of every
    # line covering the same stretch of the pipeline (stretch = rule depth, a stand-in for x)
    def joins(ln):
        to = ln.get("to")
        return (to["line"], to["station"]) if isinstance(to, dict) else None
    occupied = [(0, -1, depth[hub], None)] + [(ln["row"], ln["_start"], ln["_end"], joins(ln))
                                              for ln in lines.values() if "row" in ln]
    flip = 1
    # (line, station) -> side its branches take: the side a line joins it from, else the side its first branch took
    sides = {}
    for ln in lines.values():
        if joins(ln) and "row" in ln and "row" in lines.get(ln["to"]["line"], {}):
            sides.setdefault(joins(ln), 1 if ln["row"] > lines[ln["to"]["line"]]["row"] else -1)
    for lid, ln in lines.items():
        if not isinstance(ln.get("from"), dict):
            continue
        pr, a, b = lines[ln["from"]["line"]]["row"], ln["_start"], ln["_end"]
        src = (ln["from"]["line"], ln["from"]["station"])
        if src in sides:                      # branches leaving the same station go to the same side, so its
            out_dir = sides[src]              # label keeps one side free
        elif pr:
            out_dir = 1 if pr > 0 else -1
        else:
            out_dir, flip = flip, -flip
        def clear(r):
            for q, a2, b2, j in occupied:
                if a < b2 and a2 < b and abs(r - q) < 0.59:        # share a stretch: keep 0.6 rows apart
                    return False
                if a <= b2 and a2 <= b and abs(r - q) < 0.01 and j != src:   # one ends where the other starts
                    return False                                 # (fine if it joins the station this one leaves)
            return True
        same_side = [round(pr + out_dir * 0.6 * k, 1) for k in range(1, 4)] if src in sides else []
        ln["row"] = next(r for r in same_side + [r for k in range(1, 100) for r in (round(pr + out_dir * 0.6 * k, 1),
                                                                                   round(pr - out_dir * 0.6 * k, 1))]
                         if clear(r))
        occupied.append((ln["row"], a, b, joins(ln)))
        sides.setdefault(src, 1 if ln["row"] > pr else -1)
    unplaced = [rules[i] for i in nodes if i not in assigned]

    # ---- write YAML with comments ----
    q = lambda v: '"' + str(v).replace('"', '\\"') + '"'
    out = ["# Starter slitherFlow spec generated from `snakemake --rulegraph`.",
           "# Rename stations, add tools/outputs, regroup lines and tune rows, then render with:",
           "#   slitherflow render this.yaml -o map.svg --png --pdf",
           "",
           f'title: {q(title)}',
           'subtitle: "v1.0  ·  Snakemake"',
           'input: {label: "Input", sublabel: "", file: "FASTQ"}',
           "",
           "trunk:                      # steps every sample goes through",
           "  stations:"]
    ref = lambda v: q(v) if isinstance(v, str) else "{line: " + v["line"] + ", station: " + q(v["station"]) + "}"

    def station(i):
        extra = ""
        if feeds.get(i):
            extra = ", feeds: [" + ", ".join(ref({"line": assigned[j][0], "station": pretty(rules[j])})
                                             for j in feeds[i]) + "]"
        return f"{{name: {q(pretty(rules[i]))}, tool: \"\"{extra}}}"

    out += [f"    - {station(i)}" for i in trunk]
    trunk_ids = sorted((l for l, v in lines.items() if "from" not in v), key=lambda l: lines[l]["row"])
    out += ["  lines: [" + ", ".join(trunk_ids) + "]   # top -> bottom on the trunk",
            "", "lines:"]
    for lid, ln in lines.items():
        branch = isinstance(ln.get("from"), dict)
        if branch:   # no name: it shares its parent's colour and legend entry
            out.append(f"  {lid}:                    # branch of {ln['from']['line']} (same colour and legend entry)")
        else:
            out.append(f"  {lid}:")
            out.append(f"    name: {q(ln['name'])}")
        if "from" in ln:
            out.append(f"    from: {ref(ln['from'])}")
        out.append(f"    row: {ln['row']}" + ("            # negative = above the trunk" if ln['row'] < 0 else ""))
        if ln.get("optional"):
            out.append("    optional: true         # dashed; delete if the step always runs")
        out.append(f"    to: {ref(ln['to'])}")
        out.append("    stations:")
        out += [f"      - {station(i)}" for i in ln["_chain"]]
    if term:
        feeding = [ln["row"] for ln in lines.values() if ln["to"] == "terminus" and "from" not in ln]
        trow = min(feeding, key=abs) if feeding else 0
        out += ["", f"# terminus: rule '{rules[term]}', the end rule that collects from the most rules "
                    f"({len(pred[term])} inputs)",
                f'terminus: {{name: {q(pretty(rules[term]))}, sublabel: "", row: {trow}}}'
                '   # add file: "<type>" for an output icon']
    out += ["", 'footnote: ""']
    if unplaced:
        out += ["", "# Rules not placed automatically (add them to a line by hand):"] + [f"#   - {r}" for r in unplaced]
    return "\n".join(out) + "\n"
