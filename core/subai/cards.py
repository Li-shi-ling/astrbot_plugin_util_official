from __future__ import annotations

from .models import PERFORMANCE_FIELDS, PRICING_FIELDS, ModelChange, ModelSnapshot

CARD_THEMES = {"analytics", "brutalist", "paper"}
CARD_THEME_LABELS = {
    "analytics": "深色数据舱",
    "brutalist": "黑白粗边框",
    "paper": "层叠纸张",
}
CARD_RENDER_OPTIONS = {
    "full_page": True,
    "type": "jpeg",
    "quality": 88,
    "animations": "disabled",
}

DETAIL_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; }
    body { width: 100vw; margin: 0; padding: 34px; min-height: 0; overflow: visible; font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; color: #f8fafc; background: #050816; }
    .shell { position: relative; width: 100%; padding: 1px; border-radius: 30px; overflow: hidden; background: linear-gradient(125deg, #6366f1, #a855f7 48%, #ec4899); box-shadow: 0 28px 90px rgba(79,70,229,.30); }
    .glow { position: absolute; width: 360px; height: 360px; border-radius: 50%; filter: blur(85px); opacity: .20; }
    .glow-a { top: -180px; right: -80px; background: #8b5cf6; }
    .glow-b { bottom: -220px; left: -100px; background: #2563eb; }
    .card { position: relative; padding: 30px; border-radius: 29px; background: linear-gradient(145deg, rgba(15,23,42,.98), rgba(2,6,23,.98)); }
    .topline { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
    .brand { display: flex; align-items: center; gap: 13px; color: #c4b5fd; font-size: 16px; font-weight: 800; letter-spacing: .13em; }
    .brand-icon { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 13px; background: linear-gradient(145deg, #6366f1, #a855f7); box-shadow: 0 10px 28px rgba(99,102,241,.35); }
    .brand-icon svg { width: 23px; height: 23px; }
    .status { display: flex; align-items: center; gap: 9px; padding: 8px 14px; border-radius: 999px; color: #6ee7b7; background: rgba(16,185,129,.10); border: 1px solid rgba(52,211,153,.20); font-size: 15px; font-weight: 750; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 16px #34d399; }
    .hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-top: 25px; }
    .event { display: inline-block; padding: 6px 11px; margin-bottom: 10px; border-radius: 8px; color: #ddd6fe; background: rgba(124,58,237,.18); border: 1px solid rgba(167,139,250,.24); font-size: 15px; font-weight: 750; }
    .event.positive { color: #a7f3d0; background: rgba(5,150,105,.16); border-color: rgba(52,211,153,.24); }
    .event.danger { color: #fecdd3; background: rgba(225,29,72,.15); border-color: rgba(251,113,133,.25); }
    h1 { max-width: 720px; margin: 0; font-size: 45px; line-height: 1.12; letter-spacing: -.025em; }
    .creator { margin-top: 10px; color: #94a3b8; font-size: 18px; }
    .version { flex: none; padding: 10px 13px; border-radius: 10px; color: #a5b4fc; background: #11182c; border: 1px solid #28334f; font-size: 15px; font-weight: 700; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 25px; }
    .metric { padding: 18px; border-radius: 18px; background: rgba(30,41,59,.58); border: 1px solid rgba(148,163,184,.12); }
    .metric-head { display: flex; justify-content: space-between; color: #94a3b8; font-size: 15px; font-weight: 700; }
    .metric-score { margin: 8px 0 12px; font-size: 36px; font-weight: 850; }
    .track { height: 6px; overflow: hidden; border-radius: 99px; background: #1e293b; }
    .fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #6366f1, #c084fc); box-shadow: 0 0 14px rgba(168,85,247,.6); }
    .content { display: grid; grid-template-columns: 1.08fr .92fr; gap: 14px; margin-top: 14px; }
    .panel { padding: 19px; border-radius: 18px; background: rgba(15,23,42,.70); border: 1px solid rgba(148,163,184,.12); }
    .panel-title { display: flex; align-items: center; gap: 9px; margin-bottom: 13px; color: #cbd5e1; font-size: 15px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
    .panel-title span { width: 7px; height: 7px; border-radius: 2px; background: #8b5cf6; }
    .changes { margin: 0; padding-left: 21px; color: #e2e8f0; font-size: 17px; line-height: 1.65; }
    .data-row { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 12px; padding: 10px 0; border-top: 1px solid rgba(148,163,184,.10); }
    .data-row:first-of-type { border-top: 0; padding-top: 0; }
    .data-label { color: #64748b; font-size: 14px; font-weight: 750; overflow-wrap: anywhere; }
    .data-value { color: #e2e8f0; font-size: 15px; line-height: 1.5; }
    .footer { display: flex; justify-content: space-between; margin-top: 18px; padding-top: 15px; border-top: 1px solid rgba(148,163,184,.10); color: #64748b; font-size: 13px; letter-spacing: .04em; }

    body.brutalist { color: #080808; background: #f3efe6; }
    .brutalist .shell { padding: 0; border: 6px solid #080808; border-radius: 0; overflow: visible; background: #fffdf8; box-shadow: 16px 16px 0 #080808; }
    .brutalist .glow { display: none; }
    .brutalist .card { padding: 30px; border-radius: 0; color: #080808; background: #fffdf8; }
    .brutalist .brand { color: #080808; }
    .brutalist .brand-icon { color: #080808; border: 4px solid #080808; border-radius: 0; background: #ffe500; box-shadow: 5px 5px 0 #080808; }
    .brutalist .status, .brutalist .event { color: #080808; border: 3px solid #080808; border-radius: 0; background: #9dd7ff; }
    .brutalist .status-dot { background: #080808; box-shadow: none; }
    .brutalist .event.positive { color: #080808; border-color: #080808; background: #8cf58c; }
    .brutalist .event.danger { color: #080808; border-color: #080808; background: #ff7f7f; }
    .brutalist .creator { color: #383838; font-weight: 700; }
    .brutalist .version { color: #080808; border: 4px solid #080808; border-radius: 0; background: #ffe500; box-shadow: 6px 6px 0 #080808; }
    .brutalist .metric, .brutalist .panel { color: #080808; border: 4px solid #080808; border-radius: 0; background: #fff; box-shadow: 6px 6px 0 #080808; }
    .brutalist .metric-head, .brutalist .panel-title, .brutalist .changes, .brutalist .data-value { color: #080808; }
    .brutalist .track { height: 8px; border: 2px solid #080808; border-radius: 0; background: #fff; }
    .brutalist .fill { border-radius: 0; background: #8cf58c; box-shadow: none; }
    .brutalist .panel-title span { border-radius: 0; background: #080808; }
    .brutalist .data-row, .brutalist .footer { border-color: #080808; }
    .brutalist .data-label, .brutalist .footer { color: #383838; }

    body.paper { padding: 52px; color: #171717; background: #ded9cf; }
    .paper .shell { padding: 0; overflow: visible; isolation: isolate; background: transparent; box-shadow: 13px 15px 0 rgba(23,23,23,.14); }
    .paper .shell::before, .paper .shell::after { content: ""; position: absolute; inset: 0; z-index: -1; border: 4px solid #171717; background: #f8f4e9; transform-origin: center; }
    .paper .shell::before { transform: rotate(-2deg) translate(-7px,-5px); }
    .paper .shell::after { transform: rotate(1.7deg) translate(8px,7px); }
    .paper .glow { display: none; }
    .paper .card { padding: 31px; border: 4px solid #171717; border-radius: 0; color: #171717; background: #fffdf5; }
    .paper .brand { color: #171717; font-family: Georgia, serif; }
    .paper .brand-icon { color: #fff; border-radius: 0; background: #171717; box-shadow: none; }
    .paper .status { color: #b91c1c; border: 3px solid #b91c1c; border-radius: 0; background: transparent; font-family: Georgia, serif; transform: rotate(2deg); }
    .paper .status-dot { background: #b91c1c; box-shadow: none; }
    .paper .event { color: #171717; border: 2px solid #171717; border-radius: 0; background: #facc15; }
    .paper .event.positive { color: #171717; border-color: #171717; background: #d9f99d; }
    .paper .event.danger { color: #171717; border-color: #171717; background: #fecaca; }
    .paper h1 { font-family: Georgia, "Times New Roman", serif; }
    .paper .creator { color: #57534e; }
    .paper .version { color: #171717; border: 2px solid #171717; border-radius: 0; background: transparent; }
    .paper .metric, .paper .panel { border: 2px solid #171717; border-radius: 0; background: rgba(255,255,255,.5); }
    .paper .metric-head, .paper .panel-title, .paper .changes, .paper .data-value { color: #171717; }
    .paper .metric-score { font-family: Georgia, serif; }
    .paper .track { border-radius: 0; background: #ded9cf; }
    .paper .fill { border-radius: 0; background: #171717; box-shadow: none; }
    .paper .panel-title span { border-radius: 0; background: #b91c1c; }
    .paper .data-row, .paper .footer { border-color: rgba(23,23,23,.3); }
    .paper .data-label, .paper .footer { color: #57534e; }
  </style>
</head>
<body class="{{ theme }}">
  <div class="shell">
    <div class="glow glow-a"></div><div class="glow glow-b"></div>
    <main class="card">
      <div class="topline">
        <div class="brand"><div class="brand-icon"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 17l6-6 4 4 8-8M14 7h7v7"/></svg></div>SUBAI MODEL ANALYTICS</div>
        <div class="status"><span class="status-dot"></span>LIVE UPDATE</div>
      </div>
      <div class="hero">
        <div><div class="event {{ event_class }}">{{ event_label }}</div><h1>{{ model.name }}</h1><div class="creator">{{ creator_line }}</div></div>
        <div class="version">INDEX v{{ index_version }}</div>
      </div>
      <section class="metrics">
        <div class="metric"><div class="metric-head"><span>INTELLIGENCE</span><span>#{{ intelligence_rank }}</span></div><div class="metric-score">{{ intelligence }}</div><div class="track"><div class="fill" style="width:{{ intelligence_width }}%"></div></div></div>
        <div class="metric"><div class="metric-head"><span>CODING</span><span>#{{ coding_rank }}</span></div><div class="metric-score">{{ coding }}</div><div class="track"><div class="fill" style="width:{{ coding_width }}%"></div></div></div>
        <div class="metric"><div class="metric-head"><span>AGENTIC</span><span>#{{ agentic_rank }}</span></div><div class="metric-score">{{ agentic }}</div><div class="track"><div class="fill" style="width:{{ agentic_width }}%"></div></div></div>
      </section>
      <section class="content">
        <div class="panel"><div class="panel-title"><span></span>变化详情</div><ul class="changes">{% for line in change_details %}<li>{{ line }}</li>{% endfor %}</ul></div>
        <div class="panel"><div class="panel-title"><span></span>定价与性能</div><div class="data-row"><div class="data-label">PRICE</div><div class="data-value">{{ pricing_summary }}</div></div><div class="data-row"><div class="data-label">PERFORMANCE</div><div class="data-value">{{ performance_summary }}</div></div></div>
      </section>
      <footer class="footer"><span>ARTIFICIAL ANALYSIS · FREE LEADERBOARD</span><span>SUBAI / HIGH-SCORE WATCH</span></footer>
    </main>
  </div>
</body>
</html>
"""

LIST_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; }
    body { width: 100vw; margin: 0; padding: 42px; min-height: 0; overflow: visible; font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; color: #070707; background: #f4f0e8; }
    .card { width: 100%; padding: 30px; background: #fffdf8; border: 6px solid #080808; box-shadow: 16px 16px 0 #080808; }
    .header { display: grid; grid-template-columns: 1fr auto; gap: 28px; align-items: end; padding-bottom: 22px; border-bottom: 5px solid #080808; }
    .kicker { display: inline-block; padding: 5px 10px; background: #080808; color: #fff; font-size: 14px; font-weight: 900; letter-spacing: .14em; }
    h1 { margin: 10px 0 0; font-size: 48px; line-height: 1; text-transform: uppercase; letter-spacing: -.04em; }
    .sub { margin-top: 10px; font-size: 17px; font-weight: 650; }
    .count { min-width: 125px; padding: 13px 16px; text-align: center; background: #ffe500; border: 4px solid #080808; box-shadow: 7px 7px 0 #080808; }
    .count strong { display: block; font-size: 40px; line-height: .95; }
    .count span { font-size: 13px; font-weight: 900; letter-spacing: .09em; }
    .items { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 24px; }
    .item { position: relative; padding: 18px; background: #fff; border: 4px solid #080808; box-shadow: 8px 8px 0 #080808; }
    .item-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .event { padding: 5px 8px; background: #8cf58c; border: 3px solid #080808; font-size: 12px; font-weight: 900; }
    .event.danger { background: #ff7f7f; }
    .event.update { background: #9dd7ff; }
    .score { font-size: 24px; font-weight: 950; }
    .title { margin-top: 14px; font-size: 25px; font-weight: 950; line-height: 1.18; }
    .provider { margin-top: 7px; color: #363636; font-size: 15px; font-weight: 700; }
    .change { margin-top: 14px; padding-top: 12px; border-top: 3px solid #080808; font-size: 14px; font-weight: 750; line-height: 1.5; }
    .footer { display: flex; justify-content: space-between; margin-top: 29px; padding-top: 16px; border-top: 4px solid #080808; font-size: 13px; font-weight: 900; letter-spacing: .06em; }

    body.analytics { color: #f8fafc; background: #050816; }
    .analytics .card { border: 1px solid #4f46e5; border-radius: 28px; background: linear-gradient(145deg, #0f172a, #020617); box-shadow: 0 28px 90px rgba(79,70,229,.3); }
    .analytics .header { border-color: rgba(148,163,184,.18); }
    .analytics .kicker { color: #ddd6fe; background: rgba(124,58,237,.25); border: 1px solid rgba(167,139,250,.3); border-radius: 7px; }
    .analytics .sub, .analytics .provider { color: #94a3b8; }
    .analytics .count { color: #f8fafc; border: 1px solid rgba(167,139,250,.35); border-radius: 16px; background: linear-gradient(145deg, #4f46e5, #9333ea); box-shadow: 0 12px 28px rgba(99,102,241,.3); }
    .analytics .items { gap: 14px; }
    .analytics .item { border: 1px solid rgba(148,163,184,.15); border-radius: 18px; background: rgba(30,41,59,.72); box-shadow: none; }
    .analytics .event { color: #a7f3d0; border: 1px solid rgba(52,211,153,.3); border-radius: 7px; background: rgba(5,150,105,.18); }
    .analytics .event.danger { color: #fecdd3; background: rgba(225,29,72,.18); }
    .analytics .event.update { color: #bfdbfe; background: rgba(37,99,235,.2); }
    .analytics .score { color: #c4b5fd; }
    .analytics .change, .analytics .footer { border-color: rgba(148,163,184,.16); }
    .analytics .change { color: #e2e8f0; }
    .analytics .footer { color: #64748b; }

    body.paper { padding: 54px; color: #171717; background: #ded9cf; }
    .paper .card { position: relative; isolation: isolate; border: 4px solid #171717; background: #fffdf5; box-shadow: 13px 15px 0 rgba(23,23,23,.14); }
    .paper .card::before, .paper .card::after { content: ""; position: absolute; inset: 0; z-index: -1; border: 4px solid #171717; background: #f8f4e9; transform-origin: center; }
    .paper .card::before { transform: rotate(-1.7deg) translate(-7px,-6px); }
    .paper .card::after { transform: rotate(1.5deg) translate(8px,7px); }
    .paper .header, .paper .footer { border-color: #171717; }
    .paper .kicker { color: #fff; background: #171717; }
    .paper h1 { font-family: Georgia, "Times New Roman", serif; text-transform: none; }
    .paper .sub, .paper .provider, .paper .footer { color: #57534e; }
    .paper .count { color: #b91c1c; border: 3px solid #b91c1c; background: transparent; box-shadow: none; font-family: Georgia, serif; transform: rotate(2deg); }
    .paper .item { border: 2px solid #171717; background: rgba(255,255,255,.48); box-shadow: none; }
    .paper .event { border: 2px solid #171717; background: #d9f99d; }
    .paper .event.danger { background: #fecaca; }
    .paper .event.update { background: #bfdbfe; }
    .paper .score { font-family: Georgia, serif; }
    .paper .change { border-color: #171717; }
  </style>
</head>
<body class="{{ theme }}">
  <main class="card">
    <header class="header"><div><span class="kicker">SUBAI / CHANGE FEED</span><h1>{{ title }}</h1><div class="sub">{{ subtitle }}</div></div><div class="count"><strong>{{ item_count }}</strong><span>MODEL EVENTS</span></div></header>
    <section class="items">{% for item in items %}<article class="item"><div class="item-head"><span class="event {{ item.event_class }}">{{ item.event_label }}</span><span class="score">{{ item.score }}</span></div><div class="title">{{ item.name }}</div><div class="provider">{{ item.provider }} · Intelligence #{{ item.rank }}</div><div class="change">{{ item.change_summary }}</div></article>{% endfor %}</section>
    <footer class="footer"><span>ARTIFICIAL ANALYSIS</span><span>ONLY HIGH-SCORE CHANGES · NO RANK-ONLY NOISE</span></footer>
  </main>
</body>
</html>
"""

RANK_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; }
    body { width: 100vw; margin: 0; padding: 54px; min-height: 0; overflow: visible; font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; color: #171717; background: #ded9cf; }
    .stack { position: relative; width: 100%; isolation: isolate; }
    .stack::before, .stack::after { content: ""; position: absolute; inset: 0; z-index: -1; background: #f8f4e9; border: 4px solid #171717; transform-origin: center; }
    .stack::before { transform: rotate(-2.2deg) translate(-7px, -5px); }
    .stack::after { transform: rotate(2deg) translate(9px, 8px); }
    .sheet { padding: 31px; background: #fffdf5; border: 4px solid #171717; box-shadow: 13px 15px 0 rgba(23,23,23,.14); }
    .header { display: grid; grid-template-columns: 1fr auto; gap: 20px; align-items: start; padding-bottom: 21px; border-bottom: 3px solid #171717; }
    .eyebrow { font-size: 13px; font-weight: 900; letter-spacing: .16em; }
    h1 { margin: 7px 0 0; font-family: Georgia, "Times New Roman", serif; font-size: 47px; line-height: 1; letter-spacing: -.035em; }
    .sub { margin-top: 10px; color: #57534e; font-size: 16px; font-weight: 700; }
    .stamp { padding: 10px 13px; color: #b91c1c; border: 3px solid #b91c1c; font-family: Georgia, serif; font-size: 17px; font-weight: 900; transform: rotate(2deg); }
    .ranking { display: grid; gap: 10px; margin-top: 22px; }
    .sheet.dense .ranking { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 18px; }
    .item { display: grid; grid-template-columns: 68px minmax(0, 1fr) 108px; gap: 13px; align-items: center; min-height: 72px; padding: 10px 13px; background: rgba(255,255,255,.46); border: 2px solid #171717; }
    .rank { display: grid; place-items: center; width: 48px; height: 48px; color: #fff; background: #171717; font-family: Georgia, serif; font-size: 22px; font-weight: 900; }
    .item:nth-child(1) .rank { color: #171717; background: #facc15; }
    .item:nth-child(2) .rank { color: #171717; background: #d6d3d1; }
    .item:nth-child(3) .rank { color: #fff; background: #b45309; }
    .name { overflow: hidden; font-size: 20px; font-weight: 900; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
    .meta { overflow: hidden; margin-top: 4px; color: #57534e; font-size: 13px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
    .score { text-align: right; font-family: Georgia, serif; font-size: 27px; font-weight: 900; }
    .score small { display: block; margin-top: 3px; color: #78716c; font-family: "Microsoft YaHei", sans-serif; font-size: 10px; letter-spacing: .08em; }
    .footer { display: flex; justify-content: space-between; margin-top: 23px; padding-top: 14px; border-top: 2px solid #171717; color: #57534e; font-size: 12px; font-weight: 800; }

    body.analytics { padding: 36px; color: #f8fafc; background: #050816; }
    .analytics .stack::before, .analytics .stack::after { display: none; }
    .analytics .sheet { border: 1px solid #4f46e5; border-radius: 28px; background: linear-gradient(145deg, #0f172a, #020617); box-shadow: 0 28px 90px rgba(79,70,229,.3); }
    .analytics .header, .analytics .footer { border-color: rgba(148,163,184,.18); }
    .analytics .eyebrow { color: #c4b5fd; }
    .analytics h1 { font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; }
    .analytics .sub, .analytics .meta, .analytics .footer, .analytics .score small { color: #94a3b8; }
    .analytics .stamp { color: #a7f3d0; border: 1px solid rgba(52,211,153,.35); border-radius: 8px; background: rgba(5,150,105,.12); font-family: "Microsoft YaHei", sans-serif; transform: none; }
    .analytics .item { border: 1px solid rgba(148,163,184,.14); border-radius: 14px; background: rgba(30,41,59,.64); }
    .analytics .rank { border-radius: 10px; background: linear-gradient(145deg, #4f46e5, #9333ea); font-family: "Microsoft YaHei", sans-serif; }
    .analytics .item:nth-child(1) .rank, .analytics .item:nth-child(2) .rank, .analytics .item:nth-child(3) .rank { color: #fff; background: linear-gradient(145deg, #4f46e5, #9333ea); }
    .analytics .score { color: #c4b5fd; font-family: "Microsoft YaHei", sans-serif; }

    body.brutalist { padding: 42px; color: #080808; background: #f4f0e8; }
    .brutalist .stack::before, .brutalist .stack::after { display: none; }
    .brutalist .sheet { border: 6px solid #080808; background: #fffdf8; box-shadow: 16px 16px 0 #080808; }
    .brutalist .header { border-bottom: 5px solid #080808; }
    .brutalist h1 { font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; text-transform: uppercase; }
    .brutalist .sub, .brutalist .meta, .brutalist .footer, .brutalist .score small { color: #383838; }
    .brutalist .stamp { color: #080808; border: 4px solid #080808; background: #ffe500; box-shadow: 6px 6px 0 #080808; font-family: "Microsoft YaHei", sans-serif; transform: none; }
    .brutalist .item { border: 4px solid #080808; background: #fff; box-shadow: 6px 6px 0 #080808; }
    .brutalist .rank { color: #080808; background: #9dd7ff; font-family: "Microsoft YaHei", sans-serif; }
    .brutalist .item:nth-child(1) .rank { color: #080808; background: #ffe500; }
    .brutalist .item:nth-child(2) .rank { color: #080808; background: #d6d3d1; }
    .brutalist .item:nth-child(3) .rank { color: #080808; background: #ff9f5a; }
    .brutalist .score { font-family: "Microsoft YaHei", sans-serif; }
    .brutalist .footer { border-top: 4px solid #080808; }
  </style>
</head>
<body class="{{ theme }}">
  <div class="stack"><main class="sheet {% if dense %}dense{% endif %}"><header class="header"><div><div class="eyebrow">SUBAI / GLOBAL LEADERBOARD</div><h1>{{ title }}</h1><div class="sub">{{ subtitle }}</div></div><div class="stamp">VERIFIED<br>RANKING</div></header><section class="ranking">{% for item in items %}<article class="item"><div class="rank">{{ item.rank }}</div><div><div class="name">{{ item.name }}</div><div class="meta">{{ item.meta }}</div></div><div class="score">{{ item.score }}<small>{{ metric_label }}</small></div></article>{% endfor %}</section><footer class="footer"><span>ARTIFICIAL ANALYSIS · INDEX {{ index_version }}</span><span>UPDATED FROM LOCAL FULL SNAPSHOT</span></footer></main></div>
</body>
</html>
"""


def _fmt_score(score: float | None) -> str:
    return "-" if score is None else f"{score:.1f}"


def normalize_card_theme(theme: str | None) -> str:
    normalized = str(theme or "analytics").strip().lower()
    return normalized if normalized in CARD_THEMES else "analytics"


def card_theme_label(theme: str | None) -> str:
    return CARD_THEME_LABELS[normalize_card_theme(theme)]


def _score_width(score: float | None) -> str:
    if score is None:
        return "0"
    return f"{min(100.0, max(0.0, score)):.1f}"


def _event_class(change: ModelChange) -> str:
    if change.event_type == "exit":
        return "danger"
    if change.event_type == "update":
        return "update"
    return "positive"


def _fmt_rank(rank: int | None) -> str:
    return "-" if rank is None else str(rank)


def _fmt_price(price: float | None) -> str:
    return "-" if price is None else f"${price:.2f}"


def _fmt_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}s"


def _fmt_speed(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} tok/s"


def _event_label(change: ModelChange) -> str:
    if change.event_type == "enter":
        return "重新进入门槛" if change.transition == "reenter" else "新进入门槛"
    if change.event_type == "exit":
        return "跌出门槛"
    return "模型信息更新"


def _creator_line(model: ModelSnapshot) -> str:
    parts = [part for part in (model.creator, model.slug, model.release_date) if part]
    return " / ".join(parts) if parts else "Artificial Analysis"


FIELD_LABELS = {
    "name": "名称",
    "slug": "Slug",
    "release_date": "发布日期",
    "creator_id": "厂商 ID",
    "creator": "厂商",
    "intelligence": "Intelligence",
    "coding": "Coding",
    "agentic": "Agentic",
    "pricing.input": "输入价格",
    "pricing.output": "输出价格",
    "pricing.cache_hit": "Cache Hit 价格",
    "pricing.cache_write": "Cache Write 价格",
    "performance.output_tps": "输出速度",
    "performance.ttft": "TTFT",
    "performance.first_answer": "首答案",
    "performance.end_to_end": "完整响应",
}


def _fmt_value(field_name: str, value: object) -> str:
    if field_name in {"intelligence", "coding", "agentic"}:
        return _fmt_score(value if isinstance(value, float | int) else None)
    if field_name.startswith("pricing."):
        return _fmt_price(value if isinstance(value, float | int) else None)
    if field_name == "performance.output_tps":
        return _fmt_speed(value if isinstance(value, float | int) else None)
    if field_name.startswith("performance."):
        return _fmt_seconds(value if isinstance(value, float | int) else None)
    if value in (None, ""):
        return "-"
    return str(value)


def change_detail_lines(change: ModelChange) -> list[str]:
    previous = change.previous_model
    current = change.model
    if previous is None:
        return ["新模型首次进入关注范围。"]

    details: list[str] = []
    for field_name in (
        "name",
        "slug",
        "release_date",
        "creator_id",
        "creator",
        "intelligence",
        "coding",
        "agentic",
    ):
        previous_value = getattr(previous, field_name)
        current_value = getattr(current, field_name)
        if previous_value == current_value:
            continue
        details.append(
            f"{FIELD_LABELS[field_name]}：{_fmt_value(field_name, previous_value)} -> {_fmt_value(field_name, current_value)}"
        )

    for key in PRICING_FIELDS:
        field_name = f"pricing.{key}"
        previous_value = previous.pricing.get(key)
        current_value = current.pricing.get(key)
        if previous_value == current_value:
            continue
        details.append(
            f"{FIELD_LABELS[field_name]}：{_fmt_value(field_name, previous_value)} -> {_fmt_value(field_name, current_value)}"
        )

    for key in PERFORMANCE_FIELDS:
        field_name = f"performance.{key}"
        previous_value = previous.performance.get(key)
        current_value = current.performance.get(key)
        if previous_value == current_value:
            continue
        details.append(
            f"{FIELD_LABELS[field_name]}：{_fmt_value(field_name, previous_value)} -> {_fmt_value(field_name, current_value)}"
        )

    return details or list(change.changed_fields)


def pricing_summary(model: ModelSnapshot) -> str:
    return " / ".join(
        [
            f"输入 {_fmt_price(model.pricing.get('input'))}",
            f"输出 {_fmt_price(model.pricing.get('output'))}",
            f"Cache Hit {_fmt_price(model.pricing.get('cache_hit'))}",
            f"Cache Write {_fmt_price(model.pricing.get('cache_write'))}",
        ]
    )


def performance_summary(model: ModelSnapshot) -> str:
    return " / ".join(
        [
            f"输出速度 {_fmt_speed(model.performance.get('output_tps'))}",
            f"TTFT {_fmt_seconds(model.performance.get('ttft'))}",
            f"首答案 {_fmt_seconds(model.performance.get('first_answer'))}",
            f"完整响应 {_fmt_seconds(model.performance.get('end_to_end'))}",
        ]
    )


async def render_detail_card(
    star,
    change: ModelChange,
    theme: str = "analytics",
) -> str:
    return await star.html_render(
        DETAIL_TEMPLATE,
        {
            "theme": normalize_card_theme(theme),
            "event_label": _event_label(change),
            "event_class": _event_class(change),
            # AstrBot serializes template data before sending it to T2I.
            "model": {"name": change.model.name},
            "creator_line": _creator_line(change.model),
            "change_details": change_detail_lines(change),
            "intelligence": _fmt_score(change.model.intelligence),
            "coding": _fmt_score(change.model.coding),
            "agentic": _fmt_score(change.model.agentic),
            "intelligence_rank": _fmt_rank(change.model.ranks.intelligence),
            "coding_rank": _fmt_rank(change.model.ranks.coding),
            "agentic_rank": _fmt_rank(change.model.ranks.agentic),
            "intelligence_width": _score_width(change.model.intelligence),
            "coding_width": _score_width(change.model.coding),
            "agentic_width": _score_width(change.model.agentic),
            "pricing_summary": pricing_summary(change.model),
            "performance_summary": performance_summary(change.model),
            "index_version": change.index_version or "未知",
        },
        return_url=False,
        options=dict(CARD_RENDER_OPTIONS),
    )


async def render_summary_card(
    star,
    changes: list[ModelChange],
    theme: str = "analytics",
) -> str:
    index_version = next((change.index_version for change in changes if change.index_version), "")
    items = [
        {
            "event_class": _event_class(change),
            "event_label": _event_label(change),
            "score": _fmt_score(change.model.intelligence),
            "name": change.model.name,
            "provider": change.model.creator or "未知厂商",
            "rank": _fmt_rank(change.model.ranks.intelligence),
            "change_summary": "；".join(change_detail_lines(change)[:2])
            or "、".join(change.changed_fields),
        }
        for change in changes
    ]
    return await star.html_render(
        LIST_TEMPLATE,
        {
            "theme": normalize_card_theme(theme),
            "title": "SubAI 高分模型更新",
            "subtitle": (
                f"本轮共 {len(changes)} 个关注模型变化"
                + (f" | Index 版本 {index_version}" if index_version else "")
            ),
            "item_count": len(changes),
            "items": items,
        },
        return_url=False,
        options=dict(CARD_RENDER_OPTIONS),
    )


async def render_rank_card(
    star,
    *,
    metric: str,
    title: str,
    limit: int,
    models: list[ModelSnapshot],
    index_version: str | None,
    theme: str = "analytics",
) -> str:
    items = [
        {
            "rank": _fmt_rank(getattr(model.ranks, metric)),
            "name": model.name,
            "meta": f"{model.creator or '未知厂商'} | {model.slug or '-'}",
            "score": _fmt_score(getattr(model, metric)),
        }
        for model in models
    ]
    subtitle = f"Top {limit}"
    if index_version:
        subtitle = f"{subtitle} | Index 版本 {index_version}"
    return await star.html_render(
        RANK_TEMPLATE,
        {
            "theme": normalize_card_theme(theme),
            "title": f"SubAI {title} 榜",
            "subtitle": subtitle,
            "metric_label": metric.upper(),
            "index_version": index_version or "未知",
            "dense": len(items) > 12,
            "items": items,
        },
        return_url=False,
        options=dict(CARD_RENDER_OPTIONS),
    )


def format_change_text(change: ModelChange) -> str:
    lines = [
        f"[SubAI] {_event_label(change)}",
        f"模型：{change.model.name}",
        f"厂商：{change.model.creator or '未知'}",
        f"Slug：{change.model.slug or '-'}",
    ]
    if change.model.creator_id:
        lines.append(f"厂商 ID：{change.model.creator_id}")
    if change.model.release_date:
        lines.append(f"发布日期：{change.model.release_date}")
    if change.index_version:
        lines.append(f"Index 版本：{change.index_version}")
    lines.append(
        f"评分：Intelligence {_fmt_score(change.model.intelligence)} / Coding {_fmt_score(change.model.coding)} / Agentic {_fmt_score(change.model.agentic)}"
    )
    lines.append(
        f"排名：Intelligence {_fmt_rank(change.model.ranks.intelligence)} / Coding {_fmt_rank(change.model.ranks.coding)} / Agentic {_fmt_rank(change.model.ranks.agentic)}"
    )
    lines.append(f"价格：{pricing_summary(change.model)}")
    lines.append(f"性能：{performance_summary(change.model)}")
    lines.append("变化字段：" + "、".join(change.changed_fields))
    lines.append("变化详情：")
    lines.extend(change_detail_lines(change))
    return "\n".join(lines)


def format_change_list_text(changes: list[ModelChange]) -> str:
    lines = [f"[SubAI] 本轮检测到 {len(changes)} 个高分模型变化"]
    index_version = next((change.index_version for change in changes if change.index_version), "")
    if index_version:
        lines.append(f"Index 版本：{index_version}")
    for index, change in enumerate(changes, start=1):
        detail = "；".join(change_detail_lines(change)[:2])
        lines.append(
            f"{index}. {_event_label(change)} | {change.model.name} | Intelligence {_fmt_score(change.model.intelligence)} | 价格 {pricing_summary(change.model)} | 变化：{'、'.join(change.changed_fields)} | 摘要：{detail}"
        )
    return "\n".join(lines)


def format_rank_text(
    *,
    metric: str,
    title: str,
    limit: int,
    models: list[ModelSnapshot],
    index_version: str | None,
) -> str:
    lines = [f"SubAI {title} 榜 Top {limit}"]
    if index_version:
        lines.append(f"Index 版本：{index_version}")
    for model in models:
        rank_value = getattr(model.ranks, metric)
        score = getattr(model, metric)
        lines.append(
            f"{rank_value}. {model.name} | {score:.1f} | {model.creator or '未知厂商'} | {model.slug}"
        )
    return "\n".join(lines)
