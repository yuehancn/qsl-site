# -*- coding: utf-8 -*-
"""
丘山录 · 实测数据库静态站生成器

数据源（只读，绝不写入）：
  C:/Users/yuehancn/WorkBuddy/丘山录/hardware-lab-miniprogram/seed/
    benchmarks.json   1111 条真机实测
    solutions.json    109 条排错方案
    repo_catalog.json 141 条开源仓库许可证核验
    machines.json     16 台机器规格

设计原则：
  1. 只发布「买家会搜」的内容。运维类指标（磁盘容量/缓存体积/网络带宽）不单独成页，
     否则会生成几百个无人检索的薄页 —— 那对搜索引擎是负面信号，不是资产。
  2. 每条内容一个独立 URL，标题直接写成用户会搜的句子。
  3. 全部纯静态 HTML，零 JS 依赖也能读（渐进增强），确保爬虫抓得到正文。
  4. 数字全部来自 seed 文件直读，禁止估算。查不到就写「未采集」。

用法：python gen_site.py
"""
import io
import os
import re
import json
import html
import shutil
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SEED = r"C:/Users/yuehancn/WorkBuddy/丘山录/hardware-lab-miniprogram/seed"
OUT = os.path.join(BASE, "docs")
# 🔴 2026-11-15 域名从 361365365.xyz 换成 88918888.xyz（旧域名弃用）。
#    全站 URL / canonical / sitemap 都由这个常量派生，改这里即可，不要手改 docs/*.html。
DOMAIN = "88918888.xyz"
SITE = "丘山录实测库"
SITE_DESC = "真机实测的 AI 硬件选型数据：能不能跑、跑多快、多少钱，全部给数字和失效边界。"
TODAY = datetime.now().strftime("%Y-%m-%d")


def load(name):
    with io.open(os.path.join(SEED, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 买家相关性闸门
# include 才单独成页；exclude 只在机器详情页做附表，不生成任何 URL。

SPEED_UNITS = {
    "token/s", "tok/s", "K token", "万 token", "CJK/s",
    "秒", "秒/张", "秒/批", "秒/请求", "秒/个", "秒/段",
    "ms", "ms/张", "ms/步", "ms/文件", "步/秒", "份/秒", "张/秒", "μs", "s",
}
OPS_PREFIX = re.compile(
    r"^(dgx_|uma_|hf_|seq_|rand|4k_|nas_|disk_|shard_|weight_|transfer_|nccl_|"
    r"cpu_|ram_|st_|nb43|d6_|d7_)"
)


def is_buyer_relevant(b):
    tk = str(b.get("task_key") or "")
    label = str(b.get("task_label") or "")
    if OPS_PREFIX.match(tk):
        return False
    if "vram" in tk.lower() or "显存" in label:
        return True
    return b.get("unit") in SPEED_UNITS



def cut_text(t, n):
    """按句子边界截断，避免切在半个词上。"""
    # 先压掉原文里已经重复的标点，避免「。。」「，。」这类
    t = re.sub(r"([。！？；])\1+", r"\1", str(t or ""))
    # 先压掉原文里已经重复的标点，避免「。。」「，。」这类
    t = re.sub(r"([。！？；])\1+", r"\1", str(t or ""))
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if len(t) <= n:
        return t
    seg = t[:n]
    for mark in ("。", "；", "！", "？", ".", "；"):
        i = seg.rfind(mark)
        if i >= n * 0.5:
            return seg[:i + 1]
    i = max(seg.rfind("，"), seg.rfind(","))
    if i >= n * 0.5:
        return seg[:i] + "…"
    return seg.rstrip("。；，、") + "…"







def inline(t):
    """行内格式：**粗体** -> strong，`代码` -> code，其余转义。"""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t




def inline(t):
    """行内格式：**粗体** -> strong，`代码` -> code，其余转义。"""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong></strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code></code>", t)
    return t



def esc(s):
    return html.escape(str(s if s is not None else ""))


def machine_name(m):
    return m.get("gpu_short") or m.get("gpu_name") or ("机器 %s" % m.get("id"))


def numfmt(v):
    s = str(v if v is not None else "").strip()
    return s or "—"


def write(rel, content):
    p = os.path.join(OUT, rel)
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return p


# ---------------------------------------------------------------- 版式

CSS = """
:root{--ink:#1a1a1a;--sub:#5b6570;--line:#e3e6ea;--bg:#fff;--soft:#f7f8fa;
--accent:#b03a2e;--ok:#1e7b45;--warn:#9a6b00;--danger:#a11b1b;--none:#6b7280}
*{box-sizing:border-box}
body{margin:0;font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
"Hiragino Sans GB","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
a{color:#1a4f8a;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
header.site{border-bottom:1px solid var(--line);padding:18px 0;margin-bottom:32px}
header.site .wrap{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap}
header.site .logo{font-weight:700;font-size:18px;color:var(--ink)}
header.site nav{font-size:14px}
header.site nav a{color:var(--sub);margin-right:16px}
h1{font-size:27px;line-height:1.4;margin:0 0 10px;letter-spacing:-.2px}
h2{font-size:19px;margin:34px 0 12px;padding-top:6px}
h3{font-size:16px;margin:22px 0 8px}
p{margin:0 0 14px}
.meta{color:var(--sub);font-size:13px;margin-bottom:22px;line-height:1.9}
.meta span{margin-right:14px;white-space:nowrap}
.lede{font-size:17px;line-height:1.8;background:var(--soft);border-left:3px solid var(--accent);
padding:16px 18px;margin:0 0 26px}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;font-size:12px;padding:1px 7px;border:1px solid var(--line);
border-radius:3px;color:var(--sub);margin:0 6px 6px 0;background:#fff}
.card{border:1px solid var(--line);border-radius:5px;padding:17px 19px;margin:0 0 14px}
.card h3{margin:0 0 7px;font-size:16px;line-height:1.5}
.card h3 a{color:var(--ink)}
.card p{font-size:14px;color:var(--sub);margin:0 0 8px}
.card .kv{font-size:12.5px;color:var(--sub)}
ul,ol{padding-left:22px}li{margin-bottom:7px}
code{background:var(--soft);padding:1px 5px;border-radius:3px;font-size:13.5px;
font-family:ui-monospace,Consolas,monospace}
pre{background:var(--soft);padding:14px;border-radius:4px;overflow-x:auto;font-size:13px;
line-height:1.6}
pre code{background:none;padding:0}
.lv{display:inline-block;font-size:11.5px;padding:0 6px;border-radius:3px;
border:1px solid currentColor;font-weight:600}
.lv-L1{color:var(--ok)}.lv-L0{color:var(--warn)}.lv-none{color:var(--none)}
.v-ok{color:var(--ok)}.v-warn{color:var(--warn)}.v-danger{color:var(--danger)}
.v-limited{color:#7a4b00}.v-none{color:var(--none)}
.note{border-left:3px solid var(--warn);background:#fffdf5;padding:13px 16px;
margin:18px 0;font-size:14.5px}
.caveat{border-left:3px solid var(--accent);background:#fdf7f6;padding:13px 16px;margin:18px 0}
.caveat strong{color:var(--accent)}
footer{border-top:1px solid var(--line);margin-top:56px;padding:26px 0 44px;
font-size:13px;color:var(--sub)}
footer a{color:var(--sub)}
.qr-box{margin:26px 0 6px;padding:20px 0 4px;border-top:1px solid var(--line);
display:flex;gap:30px;flex-wrap:wrap;align-items:flex-start}
.qr-item{text-align:center;flex:0 0 auto}
.qr-item img{width:108px;height:108px;object-fit:contain;display:block;
background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px}
.qr-item span{display:block;margin-top:9px;font-size:12.5px;color:var(--sub)}
@media(max-width:560px){.qr-box{gap:22px}.qr-item img{width:92px;height:92px}}
.pager{display:flex;justify-content:space-between;gap:16px;margin:36px 0 0;
padding-top:20px;border-top:1px solid var(--line);font-size:14px}
.pager a{max-width:46%}
.count{color:var(--sub);font-size:13.5px;margin:-8px 0 18px}
.tw{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;margin:16px 0}
.tw table{margin:0;min-width:100%}
body{overflow-x:hidden}
@media(max-width:600px){h1{font-size:22px}.wrap{padding:0 15px}table{font-size:13px}
th,td{padding:7px 9px}pre{font-size:12px}}
"""

NAV = ('<a href="/bench/">跑分</a><a href="/fix/">排错</a>'
       '<a href="/license/">许可证</a><a href="/machines/">机器</a>'
       '<a href="/about/">口径</a>')


def page(title, desc, body, canonical="", jsonld=None):
    # 所有表格套横向滚动容器，避免手机端撑破版心
    body = re.sub(r"<table>", '<div class="tw"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)
    # 所有表格套横向滚动容器，避免手机端撑破版心
    body = re.sub(r"<table>", '<div class="tw"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)
    ld = ""
    if jsonld:
        ld = ('<script type="application/ld+json">%s</script>'
              % json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")))
    canon = ('<link rel="canonical" href="https://%s/%s">' % (DOMAIN, canonical)
             if canonical else "")
    # 🔴 页脚二维码区合规约束（2026-11-15 加，详见 二维码合规说明.md）
    #   ① 文案禁用「扫码」「长按识别」「扫一扫」等诱导动词 —— 触发微信「诱导关注」判定
    #   ② 图片宽度封顶 108px（约手机屏宽 1/3，微信建议的安全尺寸）
    #   ③ 只指向微信生态内部（公众号 / 小程序），绝不指向外部平台
    #   ④ 静态图，不用动图 / 强艺术变形（机器识别失败会被判风险）
    #   ⚠️ 约束写在这里而不是 CSS 注释里 —— CSS 会内联进 HTML 发给浏览器，
    #      注释既占体积又会让 grep 合规词检查误报。
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
%s
%s
<style>%s</style>
</head>
<body>
<body>
<header class="site"><div class="wrap">
<a class="logo" href="/">丘山录实测库</a>
<nav>%s</nav>
</div></header>
<main class="wrap">
%s
</main>
<footer><div class="wrap">
<p>本站数字均为真机实测，逐条标注验证等级（<span class="lv lv-L1">L1</span> 多次复测取中位 /
<span class="lv lv-L0">L0</span> 单次测量）。查不到的写「未采集」，不估算。</p>
<p>数据源自丘山录硬件实测库 · 本页生成于 %s · <a href="/about/">数据口径与方法</a></p>
<div class="qr-box">
<div class="qr-item">
<img decoding="async" src="/assets/gzh-qr.jpg" width="108" height="108" alt="丘山录公众号二维码">
<span>丘山录 · 公众号</span>
</div>
<div class="qr-item">
<img decoding="async" src="/assets/mp-code.png" width="108" height="108" alt="丘山录小程序码">
<span>丘山录 · 小程序</span>
</div>
<div class="qr-item">
<img decoding="async" src="/assets/shipinhao-code.png" width="108" height="108" alt="丘山录视频号二维码">
<span>丘山录 · 视频号</span>
</div>
<div class="qr-item">
<img decoding="async" src="/assets/xiaohongshu-code.png" width="108" height="108" alt="丘山录小红书二维码">
<span>丘山录 · 小红书</span>
</div>
<div class="qr-item">
<img decoding="async" src="/assets/douyin-code.png" width="108" height="108" alt="丘山录抖音号二维码">
<span>丘山录 · 抖音号</span>
</div>
<div class="qr-item">
<img decoding="async" src="/assets/bilibili-code.png" width="108" height="108" alt="丘山录B站号二维码">
<span>丘山录 · B站号</span>
</div>
</div>
</div></footer>
</body>
</html>""" % (esc(title), esc(desc), canon, ld, CSS, NAV, body, TODAY)


def lv_badge(level):
    lv = (level or "").strip()
    if lv == "L1":
        return '<span class="lv lv-L1">L1</span>'
    if lv == "L0":
        return '<span class="lv lv-L0">L0</span>'
    return '<span class="lv lv-none">未标注</span>'


# ---------------------------------------------------------------- 首页

def build_index(benches, sols, repos, machines):
    l1 = [s for s in sols if s.get("verify_level") == "L1"]
    hot = l1[:6] if len(l1) >= 6 else sols[:6]
    cards = "".join(
        '<div class="card"><h3><a href="/fix/%s/">%s</a></h3><p>%s</p>'
        '<div class="kv">%s · %s</div></div>'
        % (esc(s["slug"]), esc(s["title"]), esc(cut_text(s.get("summary"), 110)),
           esc(s.get("group", "")), lv_badge(s.get("verify_level")))
        for s in hot)
    n_buyer = sum(1 for b in benches if is_buyer_relevant(b))
    n_l1 = sum(1 for b in benches if b.get("verify_level") == "L1")
    bad = sum(1 for r in repos if r.get("license_risk"))
    danger = sum(1 for r in repos if r.get("verdict_level") == "danger")

    body = """
<h1>AI 硬件能不能跑、跑多快、多少钱 —— 全部给实测数字</h1>
<p class="lede">这一站只做一件事：把「我到底要不要买这张卡」拆成可以验证的数字。
每条结论都标明是在哪台机器上、用什么版本、跑了几次得出的；每条都写清失效边界 ——
什么情况下这个数不能用。</p>

<table>
<tr><th>数据</th><th>条数</th><th>说明</th></tr>
<tr><td>真机实测跑分</td><td class="num">%d</td><td>其中 %d 条直接关系「跑不跑得动」，
%d 条为 L1 级多次复测取中位</td></tr>
<tr><td>排错方案</td><td class="num">%d</td><td>每条含触发条件、版本指纹、失效边界</td></tr>
<tr><td>开源仓库许可证核验</td><td class="num">%d</td><td>其中 %d 条有传染性/受限风险，
%d 条判定为不整改不能商用</td></tr>
<tr><td>实测机器</td><td class="num">%d</td><td>从 4 卡 DGX 集群到端侧 J3455</td></tr>
</table>

<h2>先查你的卡能不能跑</h2>
<p><a href="/bench/">→ 跑分查询</a>：%d 条与选型直接相关的实测，按任务和机器列出，
每条给数值、单位、验证等级。</p>

<h2>许可证风险榜</h2>
<p>%d 个 AI 开源项目里，<strong>%d 个</strong>许可证带传染性或商用限制，
<strong>%d 个</strong>判定为不整改不能商用 —— 包括几个十几万星的项目。
<a href="/license/">→ 看完整风险榜</a></p>

<h2>最近整理的排错方案</h2>
%s
<p><a href="/fix/">→ 全部 %d 条排错方案</a></p>

<h2>这个站不做什么</h2>
<ul>
<li>不转载别人的评测。没有我自己机器上的原始数据，就不写。</li>
<li>不给「大概」「应该」这类估算值。查不到就写未采集。</li>
<li>不推荐购买渠道。我只回答「这张卡够不够」，不回答「去哪买最便宜」。</li>
</ul>
""" % (len(benches), n_buyer, n_l1, len(sols), len(repos), bad, danger,
       len(machines), n_buyer, len(repos), bad, danger, cards, len(sols))
    write("index.html", page(
        "%s · AI 硬件真机实测数据" % SITE, SITE_DESC, body, "",
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE,
         "url": "https://%s/" % DOMAIN, "description": SITE_DESC}))


# ---------------------------------------------------------------- 排错方案

GROUP_NAME = {"setup": "环境与安装", "fix": "排障", "perf": "性能",
              "make": "产出质量", "money": "成本账", "craft": "工程习惯"}


def render_content(raw):
    """content 混有纯文本、表格、命令块。保守渲染，不丢内容。"""
    if not raw:
        return ""
    lines = str(raw).replace("\r\n", "\n").split("\n")
    blocks, buf, mode = [], [], None
    for ln in lines:
        is_tbl = ln.strip().startswith("|")
        if is_tbl:
            if mode != "table":
                if buf:
                    blocks.append((mode or "p", buf))
                buf, mode = [ln], "table"
            else:
                buf.append(ln)
        else:
            if mode == "table":
                blocks.append(("table", buf))
                buf, mode = [], None
            if mode is None:
                mode = "p"
            buf.append(ln)
    if buf:
        blocks.append((mode or "p", buf))

    out = []
    for kind, ls in blocks:
        if kind == "table":
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in ls]
            if len(rows) >= 2 and re.match(r"^[-: ]+$", rows[1][0] or ""):
                head, body = rows[0], rows[2:]
            else:
                head, body = rows[0], rows[1:]
            t = ['<table><tr>%s</tr>' % "".join("<th>%s</th>" % esc(c) for c in head)]
            for r in body:
                t.append("<tr>%s</tr>" % "".join(
                    ('<td class="num">%s</td>' % esc(c))
                    if re.match(r"^[\d.,%×/~\-+ ]+$", c or "") else ("<td>%s</td>" % esc(c))
                    for c in r))
            t.append("</table>")
            out.append("".join(t))
        else:
            chunk = "\n".join(ls).strip("\n")
            if not chunk.strip():
                continue
            for part in re.split(r"\n\s*\n", chunk):
                part = part.strip()
                if not part:
                    continue
                cmdlike = bool(re.match(
                    r"^(sudo |pip |python |npm |npx |docker |curl |wget |export |"
                    r"cd |git |systemctl |nvidia-smi|\$ )", part))
                tbl = looks_table(part)
                if tbl:
                    out.append(tbl)
                elif cmdlike:
                    out.append("<pre><code>%s</code></pre>"
                               % esc(part).replace("**", ""))
                else:
                    out.append(render_para(part))
    return "\n".join(out)




def looks_table(part):
    """把 # 开头的伪表格 / 多空格对齐表识别成 <table>，否则返回 None。

    规则（宁可漏判，不可误判 —— 误判会把正常句子塞进表格）：
      · >= 4 行，每行能切出 >= 2 列，且列数完全一致
      · 第一行若形如「表一：xxx」标题，剥离出来单独成段
      · 命令行块、含长句（>30 字且无多空格）的块一律不判为表格
    """
    lines = [l for l in part.split("\n") if l.strip()]
    if len(lines) < 3:
        return None
    if any(re.match(r"^(sudo |pip |python |npm |npx |docker |curl |wget |export |"
                    r"cd |git |systemctl |nvidia-smi|\$ )", l.strip())
           for l in lines):
        return None

    caption = ""
    body_lines = list(lines)

    def split_cells(t):
        t = t.strip()
        if t.startswith("#"):
            t = t.lstrip("#").strip()
        return [c.strip() for c in re.split(r"\s{2,}", t)]

    # 第一行是「表X：」标题 -> 剥离成 caption
    if len(body_lines) > 1:
        first = body_lines[0].strip().lstrip("#").strip()
        if re.match(r"^表[一二三四五六七八九十\d]+[：:]", first):
            caption = first
            body_lines = body_lines[1:]

    rows = [split_cells(l) for l in body_lines]
    if len(rows) < 3:
        return None
    widths = {len(r) for r in rows}
    if len(widths) != 1 or min(widths) < 2:
        return None
    # 单元格平均长度过长 -> 是句子不是表格
    flat = [c for r in rows for c in r]
    if flat and sum(len(c) for c in flat) / len(flat) > 26:
        return None
    # 数据行必须以数字/符号开头（真正的表格第一列不会是长句）
    data_rows = rows[1:]
    if data_rows:
        numeric_lead = sum(
            1 for r in data_rows
            if r and re.match(r"^[\d\u4e00-\u9fffA-Za-z#*\-+<>=~]", r[0])
            and len(r[0]) <= 30)
        if numeric_lead < len(data_rows) * 0.8:
            return None
    # 单行长度超过 60 字的列 -> 是句子
    if any(len(c) > 60 for r in rows for c in r):
        return None
    # 数据行必须以数字/符号开头（真正的表格第一列不会是长句）
    data_rows = rows[1:]
    if data_rows:
        numeric_lead = sum(
            1 for r in data_rows
            if r and re.match(r"^[\d\u4e00-\u9fffA-Za-z#*\-+<>=~]", r[0])
            and len(r[0]) <= 30)
        if numeric_lead < len(data_rows) * 0.8:
            return None
    # 单行长度超过 60 字的列 -> 是句子
    if any(len(c) > 60 for r in rows for c in r):
        return None
    head = "<p class=\"count\">%s</p>" % inline(caption) if caption else ""
    return head + _table(rows)


def render_para(part):
    """纯段落渲染。表格判断统一由 looks_table 负责，此处不再自作主张。"""
    lines = [l for l in part.split("\n") if l.strip()]
    if not lines:
        return ""
    # 命令词出现在任意一行 -> 整段按代码块渲染
    cmd_words = re.compile(
        r"^(env |curl |wget |setx |export |nvidia-smi|docker |sudo |pip |python |"
        r"npm |npx |git |systemctl |ls |cat |rm |cp |mv |chmod |df |du |ss |netstat )")
    if any(cmd_words.match(l.strip()) for l in lines):
        return "<pre><code>%s</code></pre>" % esc(part).replace("**", "")

    # 命令词出现在任意一行 -> 整段按代码块渲染
    cmd_words = re.compile(
        r"^(env |curl |wget |setx |export |nvidia-smi|docker |sudo |pip |python |"
        r"npm |npx |git |systemctl |ls |cat |rm |cp |mv |chmod |df |du |ss |netstat )")
    if any(cmd_words.match(l.strip()) for l in lines):
        return "<pre><code>%s</code></pre>" % esc(part).replace("**", "")

    # 含代码特征（= / # 行内注释 / 缩进赋值）-> 交给代码块，别当段落
    codeish = any(
        re.search(r"\s#\s|^\s{2,}\S|=\s*[\w'\"]|^[A-Za-z_]+\s*[:=]", l)
        or l.strip().startswith("$ ")          # shell 提示符行
        or l.strip().startswith("&gt; ")
        for l in lines)
    if codeish:
        return "<pre><code>%s</code></pre>" % esc(part).replace("**", "")

    # # 开头的整句（非表格）：单行做小标题，多行去掉井号后作段落
    stripped = [l.strip().lstrip("#").strip() for l in lines]
    if len(stripped) == 1 and lines[0].strip().startswith("#"):
        return "<h3>%s</h3>" % inline(stripped[0])
    # 首行是 # 说明、其余是数据行 -> 首行做小标题，其余按段落
    if lines[0].strip().startswith("#") and len(lines) > 1:
        head = lines[0].strip().lstrip("#").strip()
        rest = "\n".join(l.strip().lstrip("#").strip()
                          if l.strip().startswith("#") else l
                          for l in lines[1:])
        return ('<h3>%s</h3><p>%s</p>'
                % (inline(head), inline(rest).replace("\n", "<br>")))
    text = ("\n".join(stripped)
            if all(l.strip().startswith("#") for l in lines) else part)
    return "<p>%s</p>" % inline(text).replace("\n", "<br>")


def _table(rows):
    head, body = rows[0], rows[1:]
    t = ["<table><tr>%s</tr>" % "".join("<th>%s</th>" % inline(c) for c in head)]
    for r in body:
        t.append("<tr>%s</tr>" % "".join(
            ('<td class="num">%s</td>' % esc(c))
            if re.match(r"^[\d.,%×/~\-+ ]+$", c or "") else ("<td>%s</td>" % inline(c))
            for c in r))
    t.append("</table>")
    return "".join(t)


def build_fix_index(sols):
    groups = {}
    for s in sols:
        groups.setdefault(s.get("group") or "other", []).append(s)
    parts = ["<h1>排错方案 · %d 条</h1>" % len(sols),
             '<p class="lede">每一条都来自一次真实排障：先说触发条件，'
             '再给版本指纹，最后写失效边界 —— 也就是「什么情况下这条不要照搬」。</p>']
    for g in ["setup", "fix", "perf", "make", "money", "craft", "other"]:
        items = groups.get(g)
        if not items:
            continue
        parts.append("<h2>%s（%d）</h2>" % (GROUP_NAME.get(g, g), len(items)))
        for s in items:
            parts.append(
                '<div class="card"><h3><a href="/fix/%s/">%s</a></h3><p>%s</p>'
                '<div class="kv">%s · %s</div></div>'
                % (esc(s["slug"]), esc(s["title"]), esc(cut_text(s.get("summary"), 120)),
                   esc(s.get("size_display", "")), lv_badge(s.get("verify_level"))))
    body = "".join(parts).replace("%\u200b", "%")
    write("fix/index.html", page(
        "AI 本地部署排错方案 · %d 条真机实测" % len(sols),
        "AI 本地部署与出图产线的排错方案合集，每条含触发条件、版本指纹、失效边界。",
        body, "fix/"))


def build_fix_detail(sols):
    order = sorted(sols, key=lambda s: (s.get("group") or "", s.get("sort_order") or 0))
    idx = {s["slug"]: i for i, s in enumerate(order)}
    for s in sols:
        pre = s.get("preconditions") or []
        pre_html = ("<h2>这条适用于</h2><ul>%s</ul>"
                    % "".join("<li>%s</li>" % inline(p) for p in pre)) if pre else ""
        tags = [t.strip() for t in str(s.get("tags") or "").split(",") if t.strip()]
        tag_html = "".join('<span class="tag">%s</span>' % esc(t) for t in tags)
        caveat = str(s.get("caveat") or "").strip()
        cav = ('<div class="caveat"><strong>失效边界</strong><br>%s</div>'
               % inline(caveat).replace("\n", "<br>")) if caveat else ""
        fp = str(s.get("versionFingerprint") or "").strip()
        fp_html = ('<h2>版本指纹</h2><p><code>%s</code></p>' % esc(fp)) if fp else ""

        i = idx[s["slug"]]
        pager = ['<div class="pager">']
        pager.append(('<a href="/fix/%s/">← %s</a>'
                      % (esc(order[i - 1]["slug"]), esc(order[i - 1]["title"])))
                     if i > 0 else "<span></span>")
        pager.append(('<a href="/fix/%s/" style="text-align:right">%s →</a>'
                      % (esc(order[i + 1]["slug"]), esc(order[i + 1]["title"])))
                     if i + 1 < len(order) else "<span></span>")
        pager.append("</div>")

        body = """
<h1>%s</h1>
<div class="meta"><span>%s · %s</span><span>%s</span><span>整理于 %s</span>
<span>有效期 %s</span></div>
<p class="lede">%s</p>
%s
%s
%s
<h2>具体做法</h2>
%s
%s
%s
<p style="margin-top:30px"><a href="/fix/">← 返回全部排错方案</a></p>
""" % (esc(s["title"]), esc(GROUP_NAME.get(s.get("group"), s.get("group"))),
       esc(s.get("size_display", "")), lv_badge(s.get("verify_level")),
       esc(s.get("reviewedAt", "")), esc(s.get("shelfLife", "")),
       esc(s.get("summary", "")), tag_html, pre_html, fp_html,
       render_content(s.get("content")), cav, "".join(pager))
        write("fix/%s/index.html" % s["slug"], page(
            "%s · 丘山录实测库" % s["title"], cut_text(s.get("summary"), 150),
            body, "fix/%s/" % s["slug"],
            {"@context": "https://schema.org", "@type": "TechArticle",
             "headline": s["title"], "datePublished": s.get("reviewedAt"),
             "description": cut_text(s.get("summary"), 200),
             "author": {"@type": "Person", "name": "丘山录"}}))


# ---------------------------------------------------------------- 跑分

def build_bench_index(benches, machines):
    mname = {m["id"]: machine_name(m) for m in machines}
    rel = [b for b in benches if is_buyer_relevant(b)]
    by_task = {}
    for b in rel:
        by_task.setdefault(str(b.get("task_label") or b.get("task_key")), []).append(b)
    rows = []
    for task, items in sorted(by_task.items(), key=lambda x: -len(x[1])):
        cells = []
        for b in sorted(items, key=lambda x: x.get("machine_id") or 0):
            mn = mname.get(b.get("machine_id"), "机器 %s" % b.get("machine_id"))
            cells.append("<strong>%s</strong> %s %s %s" % (
                esc(mn), numfmt(b.get("value")), esc(b.get("unit") or ""),
                lv_badge(b.get("verify_level"))))
        rows.append('<tr><td>%s</td><td>%s</td></tr>' % (esc(task), "<br>".join(cells)))
    body = """
<h1>跑分查询 · %d 条与选型相关的实测</h1>
<p class="lede">同一件事在不同机器上跑，差多少 —— 直接看数。<br>
全库 %d 条实测里，另有 %d 条是磁盘容量、缓存体积、集群同步这类内部运维指标，
它们决定「能不能部署」，不决定「跑得快不快」，所以不在本页展开，
需要时到 <a href="/machines/">机器详情</a> 查。</p>
<p class="count">按「同一任务的实测条数」降序排列 —— 条数越多，说明这个任务被反复验证过。</p>
<table>
<tr><th style="width:34%%">任务</th><th>各机器实测值</th></tr>
%s
</table>
<h2>怎么读这张表</h2>
<ul>
<li><span class="lv lv-L1">L1</span> = 多次测量取中位并记录波动区间，可直接用于决策。</li>
<li><span class="lv lv-L0">L0</span> = 单次测量。方向可信，换版本或驱动可能偏 10%% 以上。</li>
<li>显存类数值是<strong>峰值</strong>，不是平均值 —— 选卡要按峰值卡余量。</li>
<li>同一任务同机器只出现一条时，说明尚未复测，参考价值低于标 L1 的。</li>
</ul>
""" % (len(rel), len(benches), len(benches) - len(rel), "".join(rows))
    write("bench/index.html", page(
        "AI 硬件跑分查询 · %d 条真机实测横向对比" % len(rel),
        "SDXL、大模型推理、TTS 等任务在不同显卡与 DGX 集群上的真机实测数值对比。",
        body, "bench/"))


# ---------------------------------------------------------------- 机器

def build_machines(machines, benches):
    cards = []
    for m in machines:
        mine = [b for b in benches if b.get("machine_id") == m["id"]]
        rel = [b for b in mine if is_buyer_relevant(b)]
        cards.append(
            '<div class="card"><h3><a href="/machines/%s/">%s</a></h3>'
            '<p>%s · %s · %s</p>'
            '<div class="kv">%d 条实测 · 其中 %d 条与选型相关 · %s</div></div>'
            % (esc(m.get("slug")), esc(machine_name(m)),
               esc(m.get("vram_display") or ""), esc(m.get("cpu_short") or ""),
               esc(m.get("role_group") or ""), len(mine), len(rel),
               "有数据" if mine else "尚无实测记录"))
    body = ("<h1>实测机器 · %d 台</h1>"
            '<p class="lede">所有跑分都出自这些机器。同一台机器上的数字可以互相比较，'
            '跨机器比较时要确认任务一致。</p>%s'
            % (len(machines), "".join(cards)))
    write("machines/index.html", page(
        "实测机器清单 · %d 台" % len(machines),
        "丘山录实测库的全部测试机器规格：显卡、显存、CPU、操作系统与驱动版本。",
        body, "machines/"))

    for m in machines:
        mine = [b for b in benches if b.get("machine_id") == m["id"]]
        rel = [b for b in mine if is_buyer_relevant(b)]
        ops = [b for b in mine if not is_buyer_relevant(b)]

        def tbl(items):
            if not items:
                return "<p>尚无实测记录。</p>"
            r = ['<table><tr><th>任务</th><th>数值</th><th>等级</th></tr>']
            for b in sorted(items, key=lambda x: str(x.get("task_label") or "")):
                r.append('<tr><td>%s</td><td class="num">%s %s</td><td>%s</td></tr>'
                         % (esc(b.get("task_label") or b.get("task_key")),
                            numfmt(b.get("value")), esc(b.get("unit") or ""),
                            lv_badge(b.get("verify_level"))))
            r.append("</table>")
            return "".join(r)

        spec = []
        for k, label in [("gpu_name", "GPU"), ("vram_display", "显存"),
                         ("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘"),
                         ("os", "系统"), ("driver", "驱动"), ("cuda", "CUDA"),
                         ("arch", "架构")]:
            if m.get(k):
                spec.append("<tr><th>%s</th><td>%s</td></tr>" % (label, esc(m[k])))
        caveat = str(m.get("caveat") or "").strip()
        cav = ('<div class="caveat"><strong>这台机器的坑</strong><br>%s</div>'
               % inline(caveat).replace("\n", "<br>")) if caveat else ""
        body = """
<h1>%s</h1>
<div class="meta"><span>%s</span><span>%d 条实测</span></div>
<table>%s</table>
%s
%s
<h2>与选型相关的实测（%d 条）</h2>
%s
<h2>部署与运维相关（%d 条）</h2>
<p class="count">磁盘、缓存、网络层面的数据，决定「能不能装下、传得快不快」，
不代表算力强弱。</p>
%s
<p style="margin-top:30px"><a href="/machines/">← 返回机器清单</a></p>
""" % (esc(machine_name(m)), esc(m.get("role_group") or ""), len(mine),
       "".join(spec), cav, esc(m.get("note") or ""), len(rel), tbl(rel),
       len(ops), tbl(ops))
        write("machines/%s/index.html" % m.get("slug"), page(
            "%s 实测数据 · %d 条" % (machine_name(m), len(mine)),
            "%s 的真机实测记录：%d 条跑分与显存数据。" % (machine_name(m), len(rel)),
            body, "machines/%s/" % m.get("slug")))


# ---------------------------------------------------------------- 许可证榜

VL_NAME = {"ok": "可商用", "limited": "有条件", "warn": "有传染性",
           "danger": "不能商用", "none": "无法判定"}
NO_LIC = {"", "none", "unknown", "not specified",
          "not identifiable by github", "invalid", "noassertion"}


def build_license(repos):
    order = {"danger": 0, "warn": 1, "none": 2, "limited": 3, "ok": 4}
    rs = sorted(repos, key=lambda r: (order.get(r.get("verdict_level"), 9),
                                      -(r.get("stars") or 0)))
    cnt = {}
    for r in rs:
        k = r.get("verdict_level") or "none"
        cnt[k] = cnt.get(k, 0) + 1
    no_lic = sum(1 for r in repos
                 if str(r.get("license") or "").strip().lower() in NO_LIC)
    rows = []
    for r in rs:
        vl = r.get("verdict_level") or "none"
        stars = r.get("stars") or 0
        star_s = ("%.1f万" % (stars / 10000.0)) if stars >= 10000 else str(stars)
        rows.append(
            '<tr><td><a href="https://github.com/%s" rel="nofollow noopener" '
            'target="_blank">%s</a></td><td>%s</td><td class="num">%s</td>'
            '<td class="v-%s">%s</td><td>%s</td></tr>'
            % (esc(r.get("repo")), esc(r.get("repo")),
               esc(r.get("license") or "未声明"), star_s,
               esc(vl), esc(VL_NAME.get(vl, vl)), esc(r.get("verdict") or "")))
    body = """
<h1>AI 开源项目许可证风险榜 · %d 个</h1>
<p class="lede">这份榜回答一个具体问题：<strong>这个项目我能不能直接塞进商业产品里。</strong><br>
不是「它的许可证叫什么」，而是「敢不敢上线」。所以每行给的是判定结论，
不是罗列许可证名字让你自己去查。</p>

<table>
<tr><th>判定</th><th>个数</th><th>含义</th></tr>
<tr><td class="v-danger">不能商用</td><td class="num">%d</td>
<td>AGPL 等强传染性协议，或明确禁止商业使用。必须改造或换替代</td></tr>
<tr><td class="v-warn">有传染性</td><td class="num">%d</td>
<td>GPL 系。独立进程调用通常安全，链接进产品会把整个产品拖下水</td></tr>
<tr><td class="v-none">无法判定</td><td class="num">%d</td>
<td>仓库未声明许可证。法律上默认保留所有权利 —— 比 GPL 更麻烦</td></tr>
<tr><td class="v-limited">有条件</td><td class="num">%d</td>
<td>MIT/Apache 为主，但要看清附加条款（商标、专利、署名）</td></tr>
<tr><td class="v-ok">可商用</td><td class="num">%d</td><td>结论明确，直接可用</td></tr>
</table>

<div class="note"><strong>%d 个仓库没有可用许可证信息</strong>（占 %.1f%%）。
「没写许可证」不等于「随便用」—— 按伯尔尼公约，无许可证即默认保留所有权利，
商用前必须联系作者取得授权。这是比 GPL 更容易被忽略的坑。</div>

<h2>完整榜单</h2>
<p class="count">按风险高低排序，同风险内按星数降序。共 %d 个。</p>
<table>
<tr><th>仓库</th><th>许可证</th><th>星数</th><th>判定</th><th>依据</th></tr>
%s
</table>

<h2>怎么用这份榜</h2>
<ol>
<li><strong>先看你的用法</strong>：只本地跑着玩，GPL 和 AGPL 都无所谓；
要嵌进卖给客户的产品，AGPL 基本等于禁止。</li>
<li><strong>再看调用方式</strong>：AGPL 的触发条件是「通过网络提供服务」，
即使不分发代码，只要用户通过网络用了它，就得开源整个服务端。</li>
<li><strong>最后看星数</strong>：星数高的项目诉讼风险也高，别指望「这么多人用应该没事」。</li>
</ol>
<p class="count">判定基于仓库 LICENSE 文件与 GitHub API 元数据，采样日期见各仓库最后提交时间。
许可证会变，上线前请自行复核最新版本。</p>
""" % (len(repos), cnt.get("danger", 0), cnt.get("warn", 0), cnt.get("none", 0),
       cnt.get("limited", 0), cnt.get("ok", 0), no_lic,
       100.0 * no_lic / max(len(repos), 1), len(rs), "".join(rows))
    write("license/index.html", page(
        "AI 开源项目许可证风险榜 · %d 个项目能不能商用" % len(repos),
        "%d 个 AI 开源项目的许可证商用判定，含 %d 个不能商用、%d 个无许可证的高星项目。"
        % (len(repos), cnt.get("danger", 0), no_lic), body, "license/"))


# ---------------------------------------------------------------- 口径

def build_about(benches, sols, repos):
    body = """
<h1>数据口径与方法</h1>
<p class="lede">这一页说明每个数字是怎么来的、什么情况下不能用。
要拿这里的数做采购决策，请先读完这一页。</p>

<h2>验证等级</h2>
<table>
<tr><th>等级</th><th>含义</th><th>能不能用来决策</th></tr>
<tr><td><span class="lv lv-L1">L1</span></td>
<td>同一任务多次测量，取中位数，并记录波动区间与复测日期</td>
<td>可以。波动区间就是你能预期的误差</td></tr>
<tr><td><span class="lv lv-L0">L0</span></td>
<td>单次测量</td><td>方向可信。换驱动、换版本可能偏 10%% 以上</td></tr>
<tr><td><span class="lv lv-none">未标注</span></td>
<td>早期记录，未回填等级</td><td>仅供参考，不要作为唯一依据</td></tr>
</table>

<h2>数字是怎么测的</h2>
<ul>
<li>全部在本机或本机集群上跑，不引用厂商宣传值，不转载第三方评测。</li>
<li>每个数值都绑定「版本指纹」：框架版本、驱动版本、模型精度、分辨率、步数。
换掉任何一项，数字就不可直接比较。</li>
<li>显存类数值是<strong>峰值</strong>。选卡按峰值算余量，不要按平均值。</li>
<li>耗时类数值标注是否含模型加载。冷启动与稳态是两个数，混用会差出数倍。</li>
</ul>

<h2>为什么有些数据不公开成页</h2>
<p>库里 %d 条实测中，只有 %d 条与「买不买这张卡」直接相关。
其余是磁盘容量、缓存体积、集群同步带宽这类部署运维指标 ——
它们对该不该买没有解释力，单独成页只会制造噪音，所以只在机器详情页做附表。</p>

<h2>本站的失效边界</h2>
<div class="caveat"><strong>这些结论什么情况下不成立</strong><br>
① 换显卡型号：所有数字都不能直接套用，包括同系列不同显存版本。<br>
② 换驱动或框架大版本：性能可能变化 10%%–30%%，不保证跨版本可比。<br>
③ 换量化精度：Q4 和 Q8 的速度与显存占用是两套数，不通用。<br>
④ 生产环境并发：本站多数为单请求测量，高并发下的吞吐与延迟需另行测试。<br>
⑤ 样本量：部分结论基于小样本（如 8 张图一组），方向可信，精确值仅供参考。</div>

<h2>数据规模</h2>
<table>
<tr><th>数据集</th><th>条数</th></tr>
<tr><td>真机实测跑分</td><td class="num">%d</td></tr>
<tr><td>排错方案</td><td class="num">%d</td></tr>
<tr><td>开源仓库许可证核验</td><td class="num">%d</td></tr>
</table>

<h2>联系</h2>
<p>数据有错、或你有某张卡想让我测，可以在公众号「丘山录」留言。
报上显卡型号和想跑的任务，我直接说跑不跑得动。</p>
""" % (len(benches), sum(1 for b in benches if is_buyer_relevant(b)),
       len(benches), len(sols), len(repos))
    write("about/index.html", page(
        "数据口径与方法 · 丘山录实测库",
        "本站所有实测数据的验证等级、测量方法、失效边界与已知局限。", body, "about/"))


# ---------------------------------------------------------------- sitemap / robots

def build_sitemap(urls):
    items = "".join(
        "<url><loc>https://%s/%s</loc><lastmod>%s</lastmod>"
        "<changefreq>%s</changefreq><priority>%s</priority></url>"
        % (DOMAIN, u, TODAY, cf, pr) for u, cf, pr in urls)
    write("sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>'
          % items)
    write("robots.txt",
          "User-agent: *\nAllow: /\n\nSitemap: https://%s/sitemap.xml\n" % DOMAIN)
    # GitHub Pages 自定义域名；必须在生成时写入，否则 rmtree 会删掉
    write("CNAME", DOMAIN + "\n")


# ---------------------------------------------------------------- main

def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 🔴 静态资源必须由这里复制，不能手工往 docs/ 里放 ——
    #    上面 rmtree(OUT) 会清空整个 docs/，手放的图下次生成就没了。
    #    源图放 assets-src/（不被清理），生成时拷到 docs/assets/。
    src_assets = os.path.join(BASE, "assets-src")
    if os.path.isdir(src_assets):
        dst_assets = os.path.join(OUT, "assets")
        os.makedirs(dst_assets, exist_ok=True)
        copied = 0
        for fn in sorted(os.listdir(src_assets)):
            p = os.path.join(src_assets, fn)
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(dst_assets, fn))
                copied += 1
        if copied:
            print("  assets: 复制 %d 个" % copied)

    benches = load("benchmarks.json")
    sols = [s for s in load("solutions.json") if s.get("slug")]
    repos = load("repo_catalog.json")
    machines = load("machines.json")

    for b in benches:
        try:
            b["machine_id"] = int(float(b.get("machine_id")))
        except (TypeError, ValueError):
            pass

    build_index(benches, sols, repos, machines)
    build_fix_index(sols)
    build_fix_detail(sols)
    build_bench_index(benches, machines)
    build_machines(machines, benches)
    build_license(repos)
    build_about(benches, sols, repos)

    urls = [("", "daily", "1.0"), ("bench/", "weekly", "0.9"),
            ("license/", "weekly", "0.9"), ("fix/", "weekly", "0.8"),
            ("machines/", "monthly", "0.7"), ("about/", "monthly", "0.5")]
    urls += [("fix/%s/" % s["slug"], "monthly", "0.7") for s in sols]
    urls += [("machines/%s/" % m.get("slug"), "monthly", "0.6") for m in machines]
    build_sitemap(urls)

    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    print("OK files=%d" % n)
    print("  solutions=%d benchmarks=%d(buyer=%d) repos=%d machines=%d"
          % (len(sols), len(benches),
             sum(1 for b in benches if is_buyer_relevant(b)), len(repos), len(machines)))
    print("  out=%s" % OUT)


if __name__ == "__main__":
    main()