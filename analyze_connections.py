#!/usr/bin/env python3
"""
LinkedIn Connections Analyzer
Reads Connections.csv, classifies each connection into an industry,
shows the top-10 clusters, and generates an interactive D3 force-directed
network visualization.
"""

import csv
import json
import os
import re
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Industry classifier
# Each entry: (regex_on_company_OR_position, industry_label, priority)
# Higher priority wins when multiple patterns match.
# ---------------------------------------------------------------------------
RULES: list[tuple[str, str, int]] = [
    # --- Freelance / Independent (check before generic Tech) ---
    (r"self.employ|freelance|independent contractor|sole propri|upwork|fiverr|toptal", "Freelance / Independent", 90),
    (r"^self$|^freelancer$|^consultant$|^independent$", "Freelance / Independent", 85),

    # --- Education ---
    (r"universit|college|school|academ|institut|faculty|professor|adjunct|research fellow|postdoc", "Education & Research", 80),
    (r"teach|lecturer|instructor|curriculum|student|alumni|k-12|k12|education", "Education & Research", 75),

    # --- Non-profit / Social Impact / International Development ---
    (r"non.?profit|ngo|foundation|charity|humanitarian|social impact|poverty action|world bank|unicef|united nations|un |ifc |idb |usaid|oxfam|baha.i|church|mosque|temple|diocese|ministry of|relief|aid ", "Non-profit & Social Impact", 78),
    (r"innovations for poverty|mercy corps|save the children|red cross|amnesty|peace corps|global impact|social good|advocacy|initiative|community development", "Non-profit & Social Impact", 78),

    # --- Government & Public Sector ---
    (r"government|federal|dept\.|department of|city of|county of|state of|municipality|public sector|u\.s\. army|u\.s\. navy|military|department of defense|pentagon|nasa |u\.s\. air|national guard", "Government & Public Sector", 77),

    # --- Healthcare & Life Sciences ---
    (r"health|hospital|clinic|medical|pharma|biotech|life science|wellness|therapy|therapeut|patient|nursing|surgical|dental|optom|oncol|genomic|bioscience|mental health|telehealth|medtech", "Healthcare & Life Sciences", 76),

    # --- Finance & Fintech ---
    (r"bank|financ|invest|capital|fund|asset|wealth|equity|trading|hedge|venture|private equity|insurance|actuar|credit|lending|mortgage|fintech|payment|stripe|plaid|brex|robinhood|credit karma|lazard|acquisition|series [abcd]|angel invest|\bvc\b|securities|portfolio|brokerage|accounting|cpa\b|tax\b|audit\b", "Finance & Fintech", 75),

    # --- Legal ---
    (r"law firm|legal|attorney|counsel|solicitor|barrister|litigation|court|judicial|compliance officer|paralegal|\blaw\b|esquire|juris", "Legal", 74),

    # --- Recruiting & HR ---
    (r"recruit|staffing|talent acqui|human resource|\bhr\b|headhunt|search firm|placement|executive search|people ops|workforce|career coach|resume|job board|outplacement", "Recruiting & HR", 73),

    # --- Marketing, PR & Communications ---
    (r"market|advertis|public relation|\bpr\b|brand|content strateg|social media|seo|sem|growth hacker|communications|agency|creative agency|media agency|copywr|editorial|\bmedia\b|\bstudio\b|funnel|demand gen|influencer|content creator|content marketing|b2b marketing|go-to-market", "Marketing & Communications", 72),

    # --- Design & UX ---
    (r"design|ux |ui |user experience|user interface|creative direct|art direct|graphic|visual|product design|interaction design|ideo|typography|illustration|motion|figma", "Design & UX", 71),

    # --- Publishing, Journalism & Media ---
    (r"publish|newspaper|magazine|journal|news|broadcast|television|radio|podcast|book|author|editor|writer|reporter|journalist|press|media group|harpercollins|penguin|mcgraw|wiley|substack|newsletter|storytell", "Publishing & Media", 70),

    # --- Real Estate & Construction ---
    (r"real estate|realty|property|mortgage broker|construction|architect|civil engineer|urban plan|homebuilder", "Real Estate & Construction", 69),

    # --- Retail & Consumer ---
    (r"retail|e.?commerce|consumer goods|walmart|target|costco|sam.s club|whole foods|amazon|shopify|etsy|store|shop\b|merchant|supply chain", "Retail & Consumer", 68),

    # --- Technology (broad — after specifics above) ---
    (r"tech|software|saas|cloud|devops|platform|engineer|developer|data science|machine learning|artificial intelligence|\bai\b|cyber|security|network|infrastructure|api|backend|frontend|fullstack|mobile app|ios |android |product manager|product management|startup|bitscopic|tractorbeam|squarespace|koi studio|mytrudy|spacebar|cisco|ibm|google|microsoft|apple|amazon web|meta|nvidia|adobe|airbnb|slack|zoom|salesforce|hubspot|oracle|sap|automation|workflow|no.?code|low.?code|data engineer|analytics engineer|site reliability|devrel|developer relation|airops|workato|weflow|eggseed|ignite ai", "Technology", 60),

    # --- Consulting & Strategy ---
    (r"consult|advisory|strateg|mckinsey|deloitte|bcg|bain|accenture|pwc|kpmg|\bey\b|ernst|booz|oliver wyman|pa consult|monitor|analysis group|cornerstone research|management consult|proserve|momentous", "Consulting & Strategy", 58),

    # --- Energy & Environment ---
    (r"energy|oil|gas|renewabl|solar|wind|utilities|environment|sustainab|climate|clean tech|esg|\bbp\b", "Energy & Environment", 57),

    # --- Events & Conferences ---
    (r"conference|events|speaker|summit|ted\b|forum|expo|convention|festival", "Events & Conferences", 56),

    # --- Other ---
    (r".*", "Other", 0),
]


def infer_industry(company: str, position: str) -> str:
    """Classify a connection into an industry using company + position text."""
    combined = f"{company} {position}".lower()
    best_label, best_priority = "Other", -1
    for pattern, label, priority in RULES:
        if priority > best_priority and re.search(pattern, combined, re.IGNORECASE):
            best_label, best_priority = label, priority
    return best_label


def load_connections(csv_path: str) -> list[dict]:
    """Parse the LinkedIn Connections CSV, tolerating BOM and preamble lines."""
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        lines = [l for l in fh if not l.strip().startswith("Notes:")]
    reader = csv.DictReader(lines)
    connections = []
    for row in reader:
        norm = {k.strip(): v.strip() for k, v in row.items() if k}
        connections.append(norm)
    return connections


def build_industry_clusters(connections: list[dict]) -> dict[str, list]:
    """Group connections by inferred industry."""
    clusters: dict[str, list] = defaultdict(list)
    for row in connections:
        company  = row.get("Company", "").strip()
        position = row.get("Position", "").strip()
        industry = infer_industry(company, position)
        person = {
            "name":     f"{row.get('First Name','').strip()} {row.get('Last Name','').strip()}".strip(),
            "title":    position,
            "company":  company or "—",
        }
        clusters[industry].append(person)
    return clusters


def top_clusters(clusters: dict, n: int = 10) -> tuple[list[tuple], int]:
    """Return top-N named industry clusters and the count of unclassified connections."""
    named = [(k, v) for k, v in clusters.items() if k != "Other"]
    ranked = sorted(named, key=lambda x: len(x[1]), reverse=True)[:n]
    other_count = len(clusters.get("Other", []))
    return ranked, other_count


def build_graph_json(top: list[tuple]) -> dict:
    """
    Nodes = top-10 industries.
    Links = all pairs (fully connected mesh so the graph layout spreads well).
    """
    nodes = []
    for i, (industry, members) in enumerate(top):
        # top-5 companies within this industry
        co_count = Counter(m["company"] for m in members if m["company"] != "—")
        top_cos = [{"company": co, "count": cnt} for co, cnt in co_count.most_common(5)]
        nodes.append({
            "id":       i,
            "label":    industry,
            "size":     len(members),
            "topCos":   top_cos,
            "members":  members,
        })

    # Fully-connected links with weight proportional to smaller cluster
    links = []
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            links.append({"source": a, "target": b,
                          "strength": min(nodes[a]["size"], nodes[b]["size"]) / max(nodes[a]["size"], nodes[b]["size"])})

    return {"nodes": nodes, "links": links}


def print_report(top: list[tuple], total: int, other_count: int) -> None:
    classified = total - other_count
    print("\n" + "=" * 65)
    print("  TOP 10 CLUSTERS BY INDUSTRY")
    print(f"  ({total} total · {classified} classified · {other_count} unclassified)")
    print("=" * 65)
    for rank, (industry, members) in enumerate(top, 1):
        co_count = Counter(m["company"] for m in members if m["company"] != "—")
        print(f"\n#{rank:2d}  {industry}  ({len(members)} connections)")
        for co, cnt in co_count.most_common(5):
            bar = "█" * cnt
            print(f"        {co[:38]:<38} {bar} {cnt}")
        remainder = len(members) - sum(c for _, c in co_count.most_common(5))
        if remainder > 0:
            print(f"        … {remainder} more across other companies")
    print(f"\n  + {other_count} connections at niche/unclassified companies (not shown)")
    print("=" * 65)


# ---------------------------------------------------------------------------
# HTML / D3 visualization
# ---------------------------------------------------------------------------
INDUSTRY_COLORS = {
    "Technology":              "#4A90D9",
    "Marketing & Communications": "#E94B7B",
    "Finance & Fintech":       "#F5A623",
    "Education & Research":    "#7ED321",
    "Consulting & Strategy":   "#9B59B6",
    "Non-profit & Social Impact": "#1ABC9C",
    "Freelance / Independent": "#E67E22",
    "Healthcare & Life Sciences": "#2ECC71",
    "Design & UX":             "#E74C3C",
    "Publishing & Media":      "#3498DB",
    "Recruiting & HR":         "#F39C12",
    "Government & Public Sector": "#1A7B5E",
    "Legal":                   "#8E44AD",
    "Real Estate & Construction": "#795548",
    "Retail & Consumer":       "#00BCD4",
    "Energy & Environment":    "#4CAF50",
    "Other":                   "#95A5A6",
}


def build_html(graph: dict, total: int) -> str:
    graph_json = json.dumps(graph)
    colors_json = json.dumps(INDUSTRY_COLORS)

    used = {n["label"] for n in graph["nodes"]}
    legend_items = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{INDUSTRY_COLORS.get(ind,"#95A5A6")}"></span>'
        f'<span>{ind}</span></div>'
        for ind in sorted(used)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>LinkedIn Connections Network</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:#0d1117;color:#e0e0e0;overflow:hidden}}

#header{{position:absolute;top:0;left:0;right:0;z-index:10;
  background:rgba(13,17,23,0.94);padding:14px 24px;
  border-bottom:1px solid #21262d;display:flex;align-items:center;gap:16px}}
#header h1{{font-size:17px;font-weight:600;color:#f0f6fc;letter-spacing:.3px}}
#header .sub{{font-size:12px;color:#8b949e;margin-left:auto}}

#legend{{position:absolute;top:62px;left:14px;z-index:10;
  background:rgba(13,17,23,0.94);border:1px solid #21262d;
  border-radius:10px;padding:12px 14px;min-width:200px;max-height:calc(100vh - 90px);
  overflow-y:auto}}
#legend h3{{font-size:10px;text-transform:uppercase;letter-spacing:1px;
            color:#484f58;margin-bottom:8px}}
.legend-item{{display:flex;align-items:center;gap:8px;font-size:12px;
              margin-bottom:5px;color:#c9d1d9}}
.dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0}}

#tooltip{{position:absolute;pointer-events:none;z-index:20;
  background:rgba(13,17,23,0.97);border:1px solid #30363d;
  border-radius:10px;padding:14px 16px;max-width:280px;
  box-shadow:0 8px 24px rgba(0,0,0,0.6);display:none}}
#tooltip h4{{font-size:14px;color:#f0f6fc;margin-bottom:2px}}
#tooltip .count{{font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:10px}}
#tooltip .co-row{{display:flex;justify-content:space-between;align-items:center;
                  font-size:12px;color:#8b949e;margin-bottom:4px}}
#tooltip .co-row span.name{{color:#c9d1d9;max-width:180px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
#tooltip .co-row span.bar{{font-size:10px;color:#58a6ff;letter-spacing:-.5px}}
#tooltip .sample{{margin-top:8px;border-top:1px solid #21262d;padding-top:8px;
  font-size:11px;color:#484f58}}
#tooltip .sample div{{color:#8b949e;margin-bottom:2px}}

#controls{{position:absolute;bottom:20px;right:16px;z-index:10;display:flex;gap:8px}}
#controls button{{background:rgba(13,17,23,0.94);border:1px solid #30363d;
  color:#c9d1d9;border-radius:6px;padding:7px 14px;cursor:pointer;
  font-size:12px;transition:background .2s}}
#controls button:hover{{background:#21262d}}

svg{{width:100vw;height:100vh;display:block}}
.link{{stroke:#21262d;stroke-opacity:.5}}
.node circle{{cursor:grab;stroke-width:2.5;transition:filter .15s}}
.node circle:hover{{filter:brightness(1.25)}}
.node text{{pointer-events:none;text-anchor:middle;dominant-baseline:central}}
</style>
</head>
<body>

<div id="header">
  <h1>LinkedIn Connections Network</h1>
  <span class="sub">Top 10 industry clusters · {total} total connections</span>
</div>

<div id="legend">
  <h3>Industry</h3>
  {legend_items}
</div>

<div id="tooltip"></div>

<div id="controls">
  <button onclick="resetZoom()">Reset</button>
  <button onclick="toggleLabels()">Labels</button>
</div>

<svg id="graph"></svg>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const RAW    = {graph_json};
const COLORS = {colors_json};

const nodes = RAW.nodes.map(d => ({{...d}}));
const links = RAW.links.map(d => ({{...d}}));

const svg   = d3.select("#graph");
const W = window.innerWidth, H = window.innerHeight;
const g = svg.append("g");

const zoom = d3.zoom().scaleExtent([.25,6]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

const maxSz  = d3.max(nodes, d => d.size);
const rScale = d3.scaleSqrt().domain([1, maxSz]).range([28, 75]);

// Force simulation
const sim = d3.forceSimulation(nodes)
  .force("link",    d3.forceLink(links).id(d=>d.id).distance(180).strength(d=>d.strength*.4))
  .force("charge",  d3.forceManyBody().strength(-600))
  .force("center",  d3.forceCenter(W/2, H/2))
  .force("collide", d3.forceCollide().radius(d=>rScale(d.size)+14));

// Links
const link = g.append("g").selectAll("line")
  .data(links).join("line").attr("class","link").attr("stroke-width",1.2);

// Node groups
const node = g.append("g").selectAll("g")
  .data(nodes).join("g").attr("class","node")
  .call(d3.drag()
    .on("start",(e,d)=>{{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y}})
    .on("drag", (e,d)=>{{d.fx=e.x;d.fy=e.y}})
    .on("end",  (e,d)=>{{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}}));

// Circles
node.append("circle")
  .attr("r", d=>rScale(d.size))
  .attr("fill", d=>COLORS[d.label]||"#95A5A6")
  .attr("fill-opacity",.82)
  .attr("stroke", d=>d3.color(COLORS[d.label]||"#95A5A6").brighter(.7));

// Industry label (wrapped)
node.append("text")
  .attr("dy", d => rScale(d.size) > 48 ? -10 : -4)
  .style("font-size", d => rScale(d.size) > 55 ? "11px" : "10px")
  .style("font-weight","600")
  .style("fill","#f0f6fc")
  .each(function(d) {{
    const words = d.label.split(" & ").join("\n& ").split("\n");
    const el = d3.select(this);
    words.forEach((w,i) => {{
      el.append("tspan")
        .attr("x",0).attr("dy", i===0 ? 0 : "1.2em")
        .text(w);
    }});
  }});

// Count badge
node.append("text")
  .attr("dy", d => rScale(d.size) > 48 ? rScale(d.size)*.38 : rScale(d.size)*.42)
  .style("font-size","10px")
  .style("fill","rgba(255,255,255,.55)")
  .text(d => d.size + " connections");

// Tooltip
const tip = document.getElementById("tooltip");

node.on("mouseover", (event,d) => {{
  const coRows = (d.topCos||[]).slice(0,5).map(c =>
    `<div class="co-row"><span class="name">${{c.company}}</span><span class="bar">${{"█".repeat(Math.min(c.count,12))}}&nbsp;${{c.count}}</span></div>`
  ).join("");
  const sample = d.members.slice(0,3).map(m =>
    `<div>${{m.name}} — ${{m.title.slice(0,38)}}</div>`
  ).join("");
  tip.innerHTML = `
    <h4>${{d.label}}</h4>
    <div class="count">${{d.size}} connection${{d.size!==1?"s":""}}</div>
    ${{coRows}}
    <div class="sample"><div style="color:#484f58;margin-bottom:4px">Sample members</div>${{sample}}</div>`;
  tip.style.display = "block";
}})
.on("mousemove", e => {{
  tip.style.left = (e.pageX+18)+"px";
  tip.style.top  = (e.pageY-10)+"px";
}})
.on("mouseleave", () => tip.style.display="none");

// Tick
sim.on("tick", () => {{
  link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
      .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("transform",d=>`translate(${{d.x}},${{d.y}})`);
}});

function resetZoom() {{
  svg.transition().duration(500)
     .call(zoom.transform, d3.zoomIdentity.translate(0,0).scale(1));
}}
let labelsOn = true;
function toggleLabels() {{
  labelsOn = !labelsOn;
  node.selectAll("text").style("opacity", labelsOn ? 1 : 0);
}}
window.addEventListener("resize", () => {{
  sim.force("center", d3.forceCenter(window.innerWidth/2, window.innerHeight/2));
  sim.alpha(.2).restart();
}});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "Connections.csv")
    out_json = os.path.join(base, "graph_data.json")
    out_html = os.path.join(base, "network_visualization.html")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Connections.csv not found at {csv_path}")

    connections = load_connections(csv_path)
    total = len(connections)
    print(f"Loaded {total} connections from {csv_path}")

    clusters = build_industry_clusters(connections)
    top, other_count = top_clusters(clusters, n=10)

    print_report(top, total, other_count)

    graph = build_graph_json(top)
    with open(out_json, "w") as fh:
        json.dump(graph, fh, indent=2)
    print(f"\nGraph JSON  → {out_json}")

    html = build_html(graph, total)
    with open(out_html, "w") as fh:
        fh.write(html)
    print(f"Visualization → {out_html}")
    print("\nOpen network_visualization.html in any browser to explore.")
