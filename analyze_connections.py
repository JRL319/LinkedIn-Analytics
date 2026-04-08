#!/usr/bin/env python3
"""
LinkedIn Connections Analyzer
Reads Connections.csv, groups by company/industry,
finds top 10 clusters, and generates JSON for network visualization.
"""

import csv
import json
import os
import re
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Industry mapping (keyword → industry label)
# ---------------------------------------------------------------------------
INDUSTRY_MAP = {
    r"google|alphabet|deepmind|waymo": "Big Tech",
    r"microsoft|azure|github|linkedin": "Big Tech",
    r"amazon|aws": "Big Tech",
    r"meta|facebook|instagram|whatsapp": "Big Tech",
    r"apple|icloud": "Big Tech",
    r"netflix|hulu|disney\+|spotify": "Media & Streaming",
    r"airbnb|uber|lyft|doordash|instacart": "Consumer Tech",
    r"stripe|square|paypal|plaid|brex": "Fintech",
    r"salesforce|hubspot|zendesk|servicenow": "Enterprise SaaS",
    r"mckinsey|bcg|bain|deloitte|pwc|ey|kpmg|accenture": "Consulting",
    r"goldman|morgan stanley|jp morgan|blackrock|bloomberg": "Finance",
    r"openai|anthropic|cohere|hugging face": "AI / ML",
    r"nvidia|intel|amd|qualcomm|arm": "Semiconductors",
    r"pfizer|moderna|merck|johnson|roche|novartis": "Healthcare / Pharma",
    r"university|college|institute|school|edu": "Academia",
}


def infer_industry(company: str) -> str:
    """Return an industry label for a given company name."""
    if not company:
        return "Other"
    c = company.lower()
    for pattern, label in INDUSTRY_MAP.items():
        if re.search(pattern, c):
            return label
    return "Other"


def load_connections(csv_path: str) -> list[dict]:
    """Parse the LinkedIn Connections CSV, tolerating BOM and variant headers."""
    connections = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        # Skip LinkedIn's preamble lines that start with "Notes:"
        lines = [l for l in fh if not l.strip().startswith("Notes:")]
    reader = csv.DictReader(lines)
    for row in reader:
        # Normalise column names (strip whitespace)
        norm = {k.strip(): v.strip() for k, v in row.items() if k}
        connections.append(norm)
    return connections


def build_clusters(connections: list[dict]) -> dict:
    """
    Returns:
        company_members : {company: [person_dict, ...]}
        industry_members: {industry: [company, ...]}
    """
    company_members: dict[str, list] = defaultdict(list)
    for row in connections:
        company = row.get("Company", "").strip() or "Unknown"
        person = {
            "name": f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip(),
            "title": row.get("Position", ""),
            "company": company,
        }
        company_members[company].append(person)

    return company_members


def top_clusters(company_members: dict, n: int = 10) -> list[tuple]:
    """Return the top-N companies by connection count."""
    return sorted(company_members.items(), key=lambda x: len(x[1]), reverse=True)[:n]


def build_graph_json(company_members: dict, top: list[tuple]) -> dict:
    """
    Build a D3-compatible graph JSON:
      nodes: [{id, label, industry, size, members}, ...]
      links: [{source, target, strength}, ...]

    Edges connect companies within the same industry.
    """
    top_names = {company for company, _ in top}
    nodes = []
    node_index = {}

    for i, (company, members) in enumerate(top):
        industry = infer_industry(company)
        nodes.append({
            "id": i,
            "label": company,
            "industry": industry,
            "size": len(members),
            "members": members,
        })
        node_index[company] = i

    # Edges: companies in the same industry share a link
    links = []
    seen = set()
    for a_idx, (company_a, _) in enumerate(top):
        industry_a = infer_industry(company_a)
        for b_idx, (company_b, _) in enumerate(top):
            if a_idx >= b_idx:
                continue
            industry_b = infer_industry(company_b)
            if industry_a == industry_b:
                key = (a_idx, b_idx)
                if key not in seen:
                    links.append({"source": a_idx, "target": b_idx, "strength": 0.8})
                    seen.add(key)

    return {"nodes": nodes, "links": links}


def print_report(top: list[tuple]) -> None:
    """Pretty-print the top-10 clusters to stdout."""
    print("\n" + "=" * 60)
    print("  TOP 10 CLUSTERS BY COMPANY SIZE")
    print("=" * 60)
    for rank, (company, members) in enumerate(top, 1):
        industry = infer_industry(company)
        print(f"\n#{rank:2d}  {company} ({len(members)} connections) — {industry}")
        for m in members[:5]:
            print(f"       • {m['name']} — {m['title']}")
        if len(members) > 5:
            print(f"       … and {len(members) - 5} more")
    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "Connections.csv")
    out_json = os.path.join(base_dir, "graph_data.json")
    out_html = os.path.join(base_dir, "network_visualization.html")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Connections.csv not found at {csv_path}")

    connections = load_connections(csv_path)
    print(f"Loaded {len(connections)} connections from {csv_path}")

    company_members = build_clusters(connections)
    top = top_clusters(company_members, n=10)

    print_report(top)

    graph = build_graph_json(company_members, top)
    with open(out_json, "w") as fh:
        json.dump(graph, fh, indent=2)
    print(f"\nGraph JSON written to {out_json}")

    # Inline the JSON into the HTML so it works without a local server
    graph_json_str = json.dumps(graph)

    # Industry → color palette (kept in sync with HTML)
    industry_colors = {
        "Big Tech": "#4A90D9",
        "Media & Streaming": "#E94B7B",
        "Consumer Tech": "#F5A623",
        "Fintech": "#7ED321",
        "Enterprise SaaS": "#9B59B6",
        "Consulting": "#1ABC9C",
        "Finance": "#E67E22",
        "AI / ML": "#2ECC71",
        "Semiconductors": "#E74C3C",
        "Healthcare / Pharma": "#3498DB",
        "Academia": "#F39C12",
        "Other": "#95A5A6",
    }

    # Build legend entries
    used_industries = {n["industry"] for n in graph["nodes"]}
    legend_items = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{industry_colors.get(ind,"#95A5A6")}"></span>{ind}</div>'
        for ind in sorted(used_industries)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>LinkedIn Connections Network</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: #0f1117; color: #e0e0e0; overflow: hidden; }}

  #header {{
    position: absolute; top: 0; left: 0; right: 0; z-index: 10;
    background: rgba(15,17,23,0.92); padding: 14px 24px;
    border-bottom: 1px solid #2a2d3a;
    display: flex; align-items: center; gap: 16px;
  }}
  #header h1 {{ font-size: 18px; font-weight: 600; color: #fff; letter-spacing: 0.3px; }}
  #header .sub {{ font-size: 13px; color: #888; margin-left: auto; }}

  #legend {{
    position: absolute; top: 70px; left: 16px; z-index: 10;
    background: rgba(20,22,30,0.92); border: 1px solid #2a2d3a;
    border-radius: 10px; padding: 12px 16px; min-width: 170px;
  }}
  #legend h3 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                color: #666; margin-bottom: 8px; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px;
                  font-size: 12px; margin-bottom: 5px; color: #ccc; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}

  #tooltip {{
    position: absolute; pointer-events: none; z-index: 20;
    background: rgba(20,22,30,0.97); border: 1px solid #3a3d4a;
    border-radius: 10px; padding: 12px 16px; max-width: 260px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5); display: none;
  }}
  #tooltip h4 {{ font-size: 14px; color: #fff; margin-bottom: 4px; }}
  #tooltip .ind {{ font-size: 11px; color: #888; margin-bottom: 8px; }}
  #tooltip .count {{ font-size: 12px; font-weight: 600; color: #4A90D9; margin-bottom: 8px; }}
  #tooltip .member {{ font-size: 12px; color: #bbb; line-height: 1.6; }}
  #tooltip .member span {{ color: #888; }}

  #controls {{
    position: absolute; bottom: 20px; right: 20px; z-index: 10;
    display: flex; gap: 8px;
  }}
  #controls button {{
    background: rgba(20,22,30,0.92); border: 1px solid #3a3d4a;
    color: #ccc; border-radius: 6px; padding: 7px 14px; cursor: pointer;
    font-size: 13px; transition: background 0.2s;
  }}
  #controls button:hover {{ background: #2a2d3a; }}

  svg {{ width: 100vw; height: 100vh; display: block; }}
  .link {{ stroke: #2a2d3a; stroke-opacity: 0.6; }}
  .node circle {{ cursor: pointer; stroke-width: 2; transition: opacity 0.2s; }}
  .node circle:hover {{ stroke-width: 3; }}
  .node text {{ pointer-events: none; font-size: 11px; fill: #ddd;
                text-anchor: middle; dominant-baseline: central; }}
  .node .rank-badge {{ pointer-events: none; font-size: 10px; fill: rgba(255,255,255,0.5); }}
</style>
</head>
<body>

<div id="header">
  <h1>LinkedIn Connections Network</h1>
  <span class="sub">Top 10 clusters · {len(connections)} total connections</span>
</div>

<div id="legend">
  <h3>Industry</h3>
  {legend_items}
</div>

<div id="tooltip"></div>

<div id="controls">
  <button onclick="resetZoom()">Reset Zoom</button>
  <button onclick="toggleLabels()">Toggle Labels</button>
</div>

<svg id="graph"></svg>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const RAW = {graph_json_str};

const COLOR = {{
  "Big Tech":            "#4A90D9",
  "Media & Streaming":   "#E94B7B",
  "Consumer Tech":       "#F5A623",
  "Fintech":             "#7ED321",
  "Enterprise SaaS":     "#9B59B6",
  "Consulting":          "#1ABC9C",
  "Finance":             "#E67E22",
  "AI / ML":             "#2ECC71",
  "Semiconductors":      "#E74C3C",
  "Healthcare / Pharma": "#3498DB",
  "Academia":            "#F39C12",
  "Other":               "#95A5A6",
}};

const nodes = RAW.nodes.map(d => ({{ ...d }}));
const links = RAW.links.map(d => ({{ ...d }}));

const svg = d3.select("#graph");
const width  = window.innerWidth;
const height = window.innerHeight;

const g = svg.append("g");

// Zoom
const zoom = d3.zoom().scaleExtent([0.3, 5]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

// Size scale (radius)
const maxSize = d3.max(nodes, d => d.size);
const rScale  = d3.scaleSqrt().domain([1, maxSize]).range([22, 62]);

// Sort nodes by size for rank badge
const sorted = [...nodes].sort((a,b) => b.size - a.size);
sorted.forEach((d, i) => {{ d.rank = i + 1; }});

// Simulation
const sim = d3.forceSimulation(nodes)
  .force("link",   d3.forceLink(links).id(d => d.id).distance(d => 160).strength(d => d.strength))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collide", d3.forceCollide().radius(d => rScale(d.size) + 10));

// Links
const link = g.append("g").selectAll("line")
  .data(links).join("line").attr("class","link").attr("stroke-width", 1.5);

// Nodes
const node = g.append("g").selectAll("g")
  .data(nodes).join("g").attr("class","node")
  .call(d3.drag()
    .on("start", (e,d) => {{ if (!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on("drag",  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
    .on("end",   (e,d) => {{ if (!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

node.append("circle")
  .attr("r", d => rScale(d.size))
  .attr("fill", d => COLOR[d.industry] || "#95A5A6")
  .attr("fill-opacity", 0.85)
  .attr("stroke", d => d3.color(COLOR[d.industry] || "#95A5A6").brighter(0.6));

// Company label
node.append("text")
  .attr("dy", d => rScale(d.size) < 30 ? -4 : -6)
  .text(d => d.label.length > 12 ? d.label.slice(0,11)+"…" : d.label)
  .style("font-weight","600");

// Count label
node.append("text")
  .attr("dy", d => rScale(d.size) < 30 ? 10 : 12)
  .text(d => d.size + " conns")
  .style("font-size","10px")
  .style("fill","rgba(255,255,255,0.6)");

// Rank badge (top-left of circle)
node.append("text")
  .attr("class","rank-badge")
  .attr("dx", d => -rScale(d.size) + 4)
  .attr("dy", d => -rScale(d.size) + 12)
  .text(d => "#" + d.rank);

// Tooltip
const tip = document.getElementById("tooltip");

node.on("mouseover", (event, d) => {{
  const preview = d.members.slice(0,5)
    .map(m => `<div class="member">• ${{m.name}} <span>— ${{m.title}}</span></div>`).join("");
  const extra   = d.members.length > 5 ? `<div class="member" style="color:#666">… and ${{d.members.length-5}} more</div>` : "";
  tip.innerHTML = `
    <h4>${{d.label}}</h4>
    <div class="ind">${{d.industry}}</div>
    <div class="count">${{d.size}} connection${{d.size!==1?"s":""}}</div>
    ${{preview}}${{extra}}`;
  tip.style.display = "block";
}})
.on("mousemove", event => {{
  tip.style.left = (event.pageX + 16) + "px";
  tip.style.top  = (event.pageY - 10) + "px";
}})
.on("mouseleave", () => {{ tip.style.display = "none"; }});

// Tick
sim.on("tick", () => {{
  link
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});

// Controls
function resetZoom() {{
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(0,0).scale(1));
}}

let labelsVisible = true;
function toggleLabels() {{
  labelsVisible = !labelsVisible;
  node.selectAll("text").style("opacity", labelsVisible ? 1 : 0);
}}

window.addEventListener("resize", () => {{
  sim.force("center", d3.forceCenter(window.innerWidth/2, window.innerHeight/2));
  sim.alpha(0.2).restart();
}});
</script>
</body>
</html>
"""

    with open(out_html, "w") as fh:
        fh.write(html)
    print(f"Network visualization written to {out_html}")
    print("\nOpen network_visualization.html in any browser to explore the graph.")
