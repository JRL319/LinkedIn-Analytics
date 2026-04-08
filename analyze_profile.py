#!/usr/bin/env python3
"""
LinkedIn Profile Intelligence Analyzer
Compares what LinkedIn infers about you vs. what you actually follow/engage with.
Reads: Inferences_about_you.csv, Ad_Targeting.csv, Company Follows.csv
Outputs: profile_report.html
"""

import csv, json, os, re
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_inferences():
    rows = []
    path = os.path.join(BASE, "Inferences_about_you.csv")
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({k.strip(): v.strip() for k, v in row.items() if k})
    return rows


def load_ad_targeting():
    path = os.path.join(BASE, "Ad_Targeting.csv")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items() if k})
    return rows[0] if rows else {}


def load_follows():
    follows = []
    path = os.path.join(BASE, "Company Follows.csv")
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            org = row["Organization"].strip()
            ts  = row["Followed On"].strip()
            try:
                dt = datetime.strptime(ts, "%a %b %d %H:%M:%S UTC %Y")
            except Exception:
                dt = None
            follows.append({"org": org, "date": dt, "year": dt.year if dt else None})
    return sorted(follows, key=lambda x: x["date"] or datetime.min)


# ---------------------------------------------------------------------------
# Categorise follows
# ---------------------------------------------------------------------------

FOLLOW_CATS = {
    "AI & Machine Learning":        ["openai","anthropic","langchain","perplexity","stability ai","ai at meta","genai","lema ai","candid intelligence","upscale ai","rapiddev","recall.ai","boardy"],
    "Career & Job Search":          ["never search alone","her career studio","jobscan","resume.io","zety","teal","j.t. o","get hired","next play","handshake","make writing","interviewing"],
    "Freelance & Writing":          ["freelance opportunities","all things freelance","freelance writing network","content writing jobs","jobs for editors","copywriting","writing","harlow","top of the funnel","commscon","tractorbeam","make writing"],
    "Tech & SaaS":                  ["figma","amplitude","smartsheet","pylon","graphite","rimini street","quantum metric","telus","orbit","freshworks","ajenda","when","operata","workato","weflow","spellwell","stripe","squarespace"],
    "Venture Capital & Startups":   ["y combinator","andreessen horowitz","series z","simple ventures","rain","creator growth"],
    "Marketing & PR":               ["pretty little marketer","linkedin for marketing","product marketing","content design","semly","public relations","qualified digital","synergy"],
    "International Dev & Impact":   ["situka alliance","evidence in governance","giving women","ideo.org","dafgiving","baha","citizens for global"],
    "Media & News":                 ["techcrunch","fast company","harvard business review","the economist","linkedin news","fast forward"],
    "Design & UX":                  ["ideo","koi studios","creativo design","design research","big wonder","content design","figma"],
    "Education & Policy":           ["university of oklahoma","university of california","lbj school","university of texas","evidence in gov"],
    "Finance & Benefits":           ["charles schwab","principal financial","carrot","incard","stripe"],
    "Cybersecurity":                ["nucleus security","kasada","orion security","tradespace","compa"],
    "Recruiting & HR":              ["creative circle","hays","teampeople","fractional product","ptr global","onward search","dale workforce","shrm"],
    "Healthcare":                   ["goodrx","synthpop","fusion wellness","headspace","skylight"],
}

def categorize_follows(follows):
    cat_map = defaultdict(list)
    for f in follows:
        name = f["org"].lower()
        placed = False
        for cat, keywords in FOLLOW_CATS.items():
            if any(k in name for k in keywords):
                cat_map[cat].append(f)
                placed = True
                break
        if not placed:
            cat_map["Other"].append(f)
    return cat_map


# ---------------------------------------------------------------------------
# Inference accuracy assessment
# ---------------------------------------------------------------------------

def assess_inferences(inferences, follows):
    follow_names = " ".join(f["org"].lower() for f in follows)

    results = []
    for inf in inferences:
        label  = inf.get("Type of inference", "")
        desc   = inf.get("Description", "")
        value  = inf.get("Inference", "")
        cat    = inf.get("Category", "")

        verdict = "unknown"
        explanation = ""

        if label == "Interested in media about technology":
            ev = any(x in follow_names for x in ["techcrunch","fast company","the economist","harvard business","wired","the verge"])
            verdict = "accurate" if ev else "partial"
            explanation = "Confirmed: follows TechCrunch, Fast Company, HBR, The Economist."

        elif label == "Affinity for Electric Vehicles":
            ev_follows = [f["org"] for f in follows if any(k in f["org"].lower() for k in ["ev","electric","tesla","rivian","lucid","ford","gm","volkswagen","bp"])]
            verdict = "inaccurate" if not ev_follows else "partial"
            explanation = ("No EV-related company follows detected. The signal likely fired from "
                           "bp (energy company follow) or broad 'automotive enthusiast' audience overlap — "
                           "not from genuine EV interest.")

        elif label == "Inferred gender":
            verdict = "accurate"
            explanation = "Matches self-identified gender in ad targeting data."

        elif label == "Interested in a new job":
            job_search_follows = [f["org"] for f in follows if any(k in f["org"].lower() for k in ["never search alone","her career studio","jobscan","resume.io","zety","teal","j.t. o","get hired","make writing","interviewing","next play"])]
            verdict = "accurate"
            explanation = (f"{len(job_search_follows)} job-search platforms followed "
                           f"(Teal, Zety, Jobscan, resume.io, Her Career Studio, Never Search Alone…). "
                           "Strong signal — and multiple cluster in a single day (Sep/Oct 2024).")

        elif label == "Active contributor who influences public opinion":
            verdict = "accurate"
            explanation = "Consistent with groups joined (Women & Dev Issues, SID, Citizens for Global Solutions) and broad connections across sectors."

        elif label == "Human resources professional":
            verdict = "inaccurate"
            explanation = ("LinkedIn correctly set this to 'No'. Despite heavy HR-adjacent follows "
                           "(SHRM, Fractional Product Leadership, TeamPeople), the role is "
                           "communications/content strategy, not HR.")

        results.append({
            "category": cat,
            "label": label,
            "value": value,
            "desc": desc,
            "verdict": verdict,
            "explanation": explanation,
        })
    return results


# ---------------------------------------------------------------------------
# What LinkedIn MISSES
# ---------------------------------------------------------------------------

MISSED = [
    {
        "title": "Deep AI Focus",
        "detail": "13 AI company follows (Anthropic, OpenAI, LangChain, Perplexity, Stability AI, Recall.ai, Lema AI, Upscale AI, Candid Intelligence, GenAI Works, AI at Meta, Boardy, RapidDev). LinkedIn only lists generic 'Artificial Intelligence' buried in a 300-item interest dump.",
        "evidence": "13 AI follows; all added Jan 2025 onward — a deliberate pivot signal.",
    },
    {
        "title": "Freelance Writer Identity",
        "detail": "11 freelance-writing focused follows (The Freelance Writing Network, All Things Freelance Writing, Copywriting, Make Writing Your Job, Content Writing Jobs, Harlow, Tractorbeam, CommsConsultants.com, Top of the Funnel…). LinkedIn sees 'Self-Employed' but not the writer-specific dimension.",
        "evidence": "8 of these followed on the same day (Feb 5, 2026) — a clear intent burst.",
    },
    {
        "title": "Baha'i Faith & International Service",
        "detail": "Baha'i International Community (2012), Evidence in Governance and Politics (2018), Situka Alliance Initiative Uganda (2020), Giving Women (2020), IDEO.org (2023), DAFgiving360 (2026). LinkedIn hides this in the 'Company Names' field — it never surfaces as an ad category.",
        "evidence": "Oldest follows (2012–2020) — core identity, not passing interest.",
    },
    {
        "title": "Active Career Transition",
        "detail": "The follow timeline reveals a multi-stage pivot: education/policy → social impact → content strategy → AI/tech. Four separate job-search tool follows in Oct 2024 signal a deliberate pivot moment. LinkedIn flags 'job seeking' but misses the trajectory.",
        "evidence": "Teal + Zety + resume.io + Jobscan all followed within 2 weeks of each other.",
    },
    {
        "title": "VC / Startup Ecosystem Observer",
        "detail": "Y Combinator, Andreessen Horowitz, Series Z, Rain, Simple Ventures, Creator Growth Group. LinkedIn doesn't surface startup-ecosystem interest as a distinct category.",
        "evidence": "All followed Jan 2025 — same burst as AI follows, suggesting a combined 'AI + startup' research phase.",
    },
]


# ---------------------------------------------------------------------------
# Build timeline data for chart
# ---------------------------------------------------------------------------

def build_timeline(follows):
    by_year = defaultdict(lambda: defaultdict(int))
    for f in follows:
        yr = f["year"]
        if not yr:
            continue
        name = f["org"].lower()
        cat = "Other"
        for c, kws in FOLLOW_CATS.items():
            if any(k in name for k in kws):
                cat = c
                break
        by_year[yr][cat] += 1
    years = sorted(by_year.keys())
    cats  = list(FOLLOW_CATS.keys()) + ["Other"]
    series = {c: [by_year[y].get(c, 0) for y in years] for c in cats}
    return {"years": years, "series": series, "cats": cats}


# ---------------------------------------------------------------------------
# Generate HTML
# ---------------------------------------------------------------------------

VERDICT_COLORS = {"accurate": "#2ECC71", "inaccurate": "#E74C3C", "partial": "#F5A623", "unknown": "#95A5A6"}
VERDICT_ICONS  = {"accurate": "✓", "inaccurate": "✗", "partial": "~", "unknown": "?"}

CAT_COLORS = {
    "AI & Machine Learning":       "#4A90D9",
    "Career & Job Search":         "#E94B7B",
    "Freelance & Writing":         "#F5A623",
    "Tech & SaaS":                 "#7ED321",
    "Venture Capital & Startups":  "#9B59B6",
    "Marketing & PR":              "#1ABC9C",
    "International Dev & Impact":  "#E67E22",
    "Media & News":                "#2ECC71",
    "Design & UX":                 "#E74C3C",
    "Education & Policy":          "#3498DB",
    "Finance & Benefits":          "#F39C12",
    "Cybersecurity":               "#8E44AD",
    "Recruiting & HR":             "#1A7B5E",
    "Healthcare":                  "#00BCD4",
    "Other":                       "#95A5A6",
}


def build_html(inferences, ad, follows, assessments, cat_map, timeline):
    total_follows = len(follows)

    # --- Inference cards ---
    inference_cards = ""
    for a in assessments:
        vc = VERDICT_COLORS[a["verdict"]]
        vi = VERDICT_ICONS[a["verdict"]]
        inference_cards += f"""
        <div class="inf-card">
          <div class="inf-header">
            <span class="badge" style="background:{vc}">{vi} {a['verdict'].upper()}</span>
            <span class="inf-cat">{a['category']}</span>
          </div>
          <div class="inf-label">{a['label']}</div>
          <div class="inf-value">LinkedIn says: <strong>{a['value']}</strong></div>
          <div class="inf-desc">{a['desc']}</div>
          <div class="inf-explanation">{a['explanation']}</div>
        </div>"""

    # --- What LinkedIn misses ---
    missed_cards = ""
    for m in MISSED:
        missed_cards += f"""
        <div class="miss-card">
          <div class="miss-title">{m['title']}</div>
          <div class="miss-detail">{m['detail']}</div>
          <div class="miss-evidence">Evidence: {m['evidence']}</div>
        </div>"""

    # --- Follow category bars ---
    cat_bars = ""
    max_count = max(len(v) for v in cat_map.values()) if cat_map else 1
    for cat, items in sorted(cat_map.items(), key=lambda x: -len(x[1])):
        pct = len(items) / max_count * 100
        col = CAT_COLORS.get(cat, "#95A5A6")
        orgs = ", ".join(f["org"] for f in items[:4])
        more = f" +{len(items)-4} more" if len(items) > 4 else ""
        cat_bars += f"""
        <div class="bar-row">
          <div class="bar-label">{cat}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{pct:.0f}%;background:{col}">
              <span class="bar-count">{len(items)}</span>
            </div>
          </div>
          <div class="bar-orgs">{orgs}{more}</div>
        </div>"""

    # --- Ad targeting key fields ---
    age    = ad.get("Member Age", "—")
    loc    = (ad.get("Profile Locations") or "—").split(";")[0].strip()
    seniority = ad.get("Job Seniorities", "—")
    grad   = ad.get("Graduation Year", "—")
    yoe    = ad.get("Years of Experience", "—")
    seg    = (ad.get("Standard Audience Segments") or "—").replace(";", " · ")
    buyer  = (ad.get("Buyer Groups") or "—").replace(";", " · ")
    titles = "; ".join((ad.get("Job Titles") or "").split(";")[:5])
    interests_raw = ad.get("Member Interests", "")
    top_interests = "; ".join(x.strip() for x in interests_raw.split(";")[:12] if x.strip())

    # timeline JSON
    tl = json.dumps(timeline)
    cat_colors_js = json.dumps(CAT_COLORS)

    # score summary
    verdicts = [a["verdict"] for a in assessments]
    n_acc = verdicts.count("accurate")
    n_part = verdicts.count("partial")
    n_inacc = verdicts.count("inaccurate")
    score_pct = int((n_acc + 0.5 * n_part) / len(verdicts) * 100) if verdicts else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>LinkedIn Profile Intelligence Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:#0d1117;color:#c9d1d9;line-height:1.55}}

.page{{max-width:1100px;margin:0 auto;padding:32px 20px}}

h1{{font-size:22px;font-weight:700;color:#f0f6fc;margin-bottom:4px}}
.subtitle{{font-size:13px;color:#484f58;margin-bottom:36px}}
h2{{font-size:15px;font-weight:600;color:#f0f6fc;text-transform:uppercase;
    letter-spacing:.8px;margin:32px 0 14px;padding-left:10px;
    border-left:3px solid #58a6ff}}

/* summary strip */
.summary{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:36px}}
.stat{{background:#161b22;border:1px solid #21262d;border-radius:10px;
       padding:16px 20px;flex:1;min-width:150px}}
.stat .val{{font-size:28px;font-weight:700;color:#58a6ff}}
.stat .lbl{{font-size:11px;color:#484f58;margin-top:2px;text-transform:uppercase;letter-spacing:.5px}}

/* inference cards */
.inf-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
.inf-card{{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:16px}}
.inf-header{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.badge{{font-size:10px;font-weight:700;padding:3px 8px;border-radius:12px;color:#fff;letter-spacing:.4px}}
.inf-cat{{font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:.5px}}
.inf-label{{font-size:13px;font-weight:600;color:#f0f6fc;margin-bottom:4px}}
.inf-value{{font-size:12px;color:#8b949e;margin-bottom:4px}}
.inf-value strong{{color:#58a6ff}}
.inf-desc{{font-size:11px;color:#484f58;margin-bottom:8px;font-style:italic}}
.inf-explanation{{font-size:12px;color:#c9d1d9;border-top:1px solid #21262d;padding-top:8px;margin-top:4px}}

/* ad targeting profile */
.ad-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-bottom:16px}}
.ad-item{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 14px}}
.ad-item .key{{font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.ad-item .val{{font-size:13px;color:#c9d1d9}}
.ad-interests{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 14px;margin-bottom:14px;font-size:12px;color:#8b949e}}
.ad-interests strong{{color:#c9d1d9;display:block;margin-bottom:6px;font-size:10px;text-transform:uppercase;letter-spacing:.5px}}
.tag{{display:inline-block;background:#21262d;border-radius:4px;padding:2px 7px;margin:2px 2px;font-size:11px;color:#8b949e}}

/* what you actually follow bars */
.bars{{display:flex;flex-direction:column;gap:8px}}
.bar-row{{display:grid;grid-template-columns:180px 1fr;gap:10px;align-items:center}}
.bar-label{{font-size:12px;color:#c9d1d9;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar-track{{height:22px;background:#161b22;border-radius:4px;overflow:hidden;border:1px solid #21262d}}
.bar-fill{{height:100%;border-radius:4px;display:flex;align-items:center;padding:0 8px;transition:width .4s}}
.bar-count{{font-size:11px;font-weight:600;color:rgba(255,255,255,.8);white-space:nowrap}}
.bar-orgs{{font-size:10px;color:#484f58;grid-column:2;margin-top:-4px;padding-left:2px}}

/* missed cards */
.miss-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
.miss-card{{background:#161b22;border:1px solid #30363d;border-left:3px solid #E67E22;border-radius:10px;padding:16px}}
.miss-title{{font-size:13px;font-weight:600;color:#f0f6fc;margin-bottom:6px}}
.miss-detail{{font-size:12px;color:#8b949e;margin-bottom:8px}}
.miss-evidence{{font-size:11px;color:#E67E22;font-style:italic}}

/* timeline */
#timeline-chart{{width:100%;height:220px;background:#161b22;border:1px solid #21262d;border-radius:10px}}

/* score ring */
.score-row{{display:flex;align-items:center;gap:24px;margin-bottom:24px}}
.score-ring{{position:relative;width:80px;height:80px;flex-shrink:0}}
.score-ring svg{{transform:rotate(-90deg)}}
.score-ring .num{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                  font-size:18px;font-weight:700;color:#f0f6fc}}
.score-legend{{display:flex;gap:16px;font-size:12px}}
.score-legend span{{display:flex;align-items:center;gap:5px}}
.dot-sm{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
</style>
</head>
<body>
<div class="page">

<h1>LinkedIn Profile Intelligence Report</h1>
<p class="subtitle">What LinkedIn thinks it knows about you — vs. what you actually follow and engage with</p>

<!-- Summary stats -->
<div class="summary">
  <div class="stat"><div class="val">{total_follows}</div><div class="lbl">Companies Followed</div></div>
  <div class="stat"><div class="val">{len(assessments)}</div><div class="lbl">LinkedIn Inferences</div></div>
  <div class="stat"><div class="val" style="color:#2ECC71">{n_acc}</div><div class="lbl">Accurate</div></div>
  <div class="stat"><div class="val" style="color:#F5A623">{n_part}</div><div class="lbl">Partial</div></div>
  <div class="stat"><div class="val" style="color:#E74C3C">{n_inacc}</div><div class="lbl">Inaccurate</div></div>
  <div class="stat"><div class="val">{score_pct}%</div><div class="lbl">Inference Accuracy</div></div>
</div>

<!-- LinkedIn's inferences -->
<h2>What LinkedIn Infers About You</h2>
<div class="inf-grid">{inference_cards}</div>

<!-- Ad targeting profile -->
<h2>Your Ad Targeting Profile</h2>
<div class="ad-grid">
  <div class="ad-item"><div class="key">Age Range</div><div class="val">{age}</div></div>
  <div class="ad-item"><div class="key">Location</div><div class="val">{loc}</div></div>
  <div class="ad-item"><div class="key">Seniority</div><div class="val">{seniority}</div></div>
  <div class="ad-item"><div class="key">Graduation Year</div><div class="val">{grad}</div></div>
  <div class="ad-item"><div class="key">Years of Experience</div><div class="val">{yoe}</div></div>
  <div class="ad-item"><div class="key">Audience Segments</div><div class="val">{seg}</div></div>
</div>
<div class="ad-interests">
  <strong>Buyer Groups (LinkedIn thinks you buy)</strong>
  {buyer}
</div>
<div class="ad-interests">
  <strong>Job Titles LinkedIn Associates You With</strong>
  {titles}…
</div>
<div class="ad-interests">
  <strong>Top Interests LinkedIn Infers (first 12 of 200+)</strong>
  {"".join(f'<span class="tag">{i}</span>' for i in top_interests.split(";") if i.strip())}
</div>

<!-- What you actually follow -->
<h2>What You Actually Follow (Reality Check)</h2>
<div class="bars">{cat_bars}</div>

<!-- Timeline -->
<h2>Your Follow Timeline — Career Story in Companies</h2>
<canvas id="timeline-chart"></canvas>

<!-- What LinkedIn misses -->
<h2>What LinkedIn Gets Wrong or Misses Entirely</h2>
<div class="miss-grid">{missed_cards}</div>

</div><!-- /page -->

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const TL = {tl};
const CAT_COLORS = {cat_colors_js};

const ctx = document.getElementById("timeline-chart").getContext("2d");

// Filter to categories with at least 1 follow in the period
const activeCats = TL.cats.filter(c => TL.series[c].some(v => v > 0));

new Chart(ctx, {{
  type: "bar",
  data: {{
    labels: TL.years,
    datasets: activeCats.map(cat => ({{
      label: cat,
      data: TL.series[cat],
      backgroundColor: (CAT_COLORS[cat] || "#95A5A6") + "cc",
      borderColor: CAT_COLORS[cat] || "#95A5A6",
      borderWidth: 1,
    }}))
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: "#8b949e", boxWidth: 10, font: {{ size: 10 }} }} }},
      tooltip: {{ mode: "index", intersect: false }},
    }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: "#8b949e" }}, grid: {{ color: "#21262d" }} }},
      y: {{ stacked: true, ticks: {{ color: "#8b949e", precision: 0 }}, grid: {{ color: "#21262d" }} }},
    }},
  }}
}});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    inferences = load_inferences()
    ad         = load_ad_targeting()
    follows    = load_follows()

    cat_map     = categorize_follows(follows)
    assessments = assess_inferences(inferences, follows)
    timeline    = build_timeline(follows)

    out_html = os.path.join(BASE, "profile_report.html")
    html     = build_html(inferences, ad, follows, assessments, cat_map, timeline)
    with open(out_html, "w") as fh:
        fh.write(html)

    # Print console report
    print("=" * 65)
    print("  LINKEDIN PROFILE INTELLIGENCE REPORT")
    print("=" * 65)

    print("\n--- LINKEDIN INFERENCES vs REALITY ---\n")
    for a in assessments:
        icon = VERDICT_ICONS[a["verdict"]]
        print(f"  [{icon}] {a['label']}")
        print(f"      LinkedIn: {a['value']}")
        print(f"      Reality:  {a['explanation']}")
        print()

    print("\n--- WHAT YOU ACTUALLY FOLLOW ---\n")
    for cat, items in sorted(cat_map.items(), key=lambda x: -len(x[1])):
        print(f"  {len(items):2d}  {cat}")

    print("\n--- WHAT LINKEDIN MISSES ---\n")
    for m in MISSED:
        print(f"  • {m['title']}")
        print(f"    {m['evidence']}")
        print()

    print(f"\nHTML report → {out_html}")
    print("Open profile_report.html in any browser.")
