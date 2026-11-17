# -*- coding: utf-8 -*-
"""
88918888.xyz 静态站 · 每日与小程序数据源同步

解决什么：
  小程序的数据来自 seed/（丘山录/hardware-lab-miniprogram/seed/），
  每日链路第 2 环（17:30）写云库时用 --sync-seed 回写 seed，
  **但它不重建静态站** ⇒ 88918888.xyz 会一天天落后于小程序。

怎么判「要不要同步」：
  对 seed 里参与建站的 4 个文件取 sha256 指纹：
    benchmarks.json / solutions.json / machines.json / repo_catalog.json
  与上次成功同步时记录的指纹比对。
  · 一致 → 什么都不做（退出码 0，输出 UP-TO-DATE）
  · 有变化 / 无历史状态 → 重建 + 推送

  为什么不每天无脑重建：
    gen_site.py 用 TODAY 填 lastmod，天天重建会把全站 lastmod 刷成当天 ——
    数据没变却天天报"刚更新"，是给搜索引擎发假新鲜度信号，属于负面行为。
    按指纹跳过可以让 lastmod 只在真有数据变化时前进。

用法：
  python sync_daily.py            # 同步（有变化才动）
  python sync_daily.py --dry      # 只看会做什么，不写不推
  python sync_daily.py --force    # 无视指纹强制重建+推送
  python sync_daily.py --check    # 只报告差异，绝不写

退出码：0 = 成功或无需同步 / 1 = 生成或推送失败 / 2 = 环境异常（seed 缺失）

🔴 前提：gh 已登录（push_site.py 降级走 GitHub API 时需要 token）。
"""
import io
import os
import sys
import json
import hashlib
import subprocess
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SEED = r"C:/Users/yuehancn/WorkBuddy/丘山录/hardware-lab-miniprogram/seed"
STATE = os.path.join(BASE, ".sync_state.json")
PY = sys.executable

# 只有这 4 个文件参与建站（见 gen_site.py 的 load() 调用）
WATCH = ["benchmarks.json", "solutions.json", "machines.json", "repo_catalog.json"]


def sha256_of(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def counts():
    """顺手报个量，方便人工核对，不参与判定。"""
    out = {}
    for name, key in (("benchmarks.json", None), ("solutions.json", None),
                      ("machines.json", None), ("repo_catalog.json", None)):
        p = os.path.join(SEED, name)
        try:
            with io.open(p, encoding="utf-8") as f:
                out[name] = len(json.load(f))
        except Exception:
            out[name] = -1
    return out


def fingerprint():
    fp = {}
    for name in WATCH:
        p = os.path.join(SEED, name)
        if not os.path.isfile(p):
            return None
        fp[name] = sha256_of(p)
    return fp


def load_state():
    try:
        with io.open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(fp, extra):
    data = {"seed_fingerprint": fp, "synced_at": datetime.datetime.now().isoformat(timespec="seconds")}
    data.update(extra)
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)


def run(title, cmd, cwd=BASE, timeout=1800):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        print("❌ 超时（>30 分钟）")
        return False, ""
    out = (p.stdout or "") + (p.stderr or "")
    print(out.rstrip()[-2000:])
    return p.returncode == 0, out


def live_counts():
    """读线上首页的四个数字，用于推送后自证。失败返回 None（不算致命）。"""
    try:
        p = subprocess.run(["curl", "-s", "--noproxy", "*", "--max-time", "30",
                            "https://88918888.xyz/"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60)
        html = p.stdout or ""
    except Exception:
        return None
    nums = []
    key = '<td class="num">'
    i = 0
    while True:
        i = html.find(key, i)
        if i < 0:
            break
        i += len(key)
        j = html.find("</td>", i)
        if j < 0:
            break
        nums.append(html[i:j].strip())
    return nums[:4] if len(nums) >= 4 else None


def main():
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv
    check = "--check" in sys.argv

    print("=" * 62)
    print("88918888.xyz ← seed 每日同步")
    print("=" * 62)
    print("seed: %s" % SEED)

    if not os.path.isdir(SEED):
        print("❌ seed 目录不存在，环境异常")
        return 2

    fp = fingerprint()
    if fp is None:
        print("❌ seed 关键文件缺失（需要 %s），环境异常" % ", ".join(WATCH))
        return 2

    c = counts()
    print("当前 seed：" + " / ".join("%s=%d" % (k.replace(".json", ""), v) for k, v in c.items()))

    st = load_state()
    old = st.get("seed_fingerprint") or {}
    changed = force or (not old) or (old != fp)

    if not changed:
        print("\n指纹一致，数据未变 → 无需重建（lastmod 保持不变）")
        print("UP-TO-DATE  last_sync=%s" % st.get("synced_at", "?"))
        if st.get("site_counts"):
            print("上次同步后站点计分：%s" % json.dumps(st["site_counts"], ensure_ascii=False))
        return 0

    diff = [n for n in WATCH if old.get(n) != fp.get(n)]
    print("\n判定：需要同步  %s" % ("（--force）" if force else ""))
    if old:
        print("  变化文件：" + (", ".join(diff) if diff else "（仅新建状态文件）"))
    else:
        print("  变化文件：无历史同步记录 → 首次建立基线")

    if check:
        print("\n[CHECK] 只报告，未做任何写操作")
        return 0

    if dry:
        print("\n[DRY] 将执行：")
        print("  1) %s gen_site.py" % PY)
        print("  2) %s push_site.py --msg \"data: 静态站同步 <日期>\"")
        return 0

    ok, _ = run("① 重建静态站（gen_site.py）", [PY, "gen_site.py"])
    if not ok:
        print("\n❌ 重建失败，未推送。docs/ 可能处于半新状态，可重跑本脚本修复。")
        return 1

    msg = "data: 静态站同步（方案 %d / 跑分 %d / 机型 %d / 仓库 %d）" % (
        c.get("solutions.json", 0), c.get("benchmarks.json", 0),
        c.get("machines.json", 0), c.get("repo_catalog.json", 0))
    ok, out = run("② 推送上线（push_site.py）", [PY, "push_site.py", "--msg", msg])
    if not ok:
        print("\n❌ 推送失败。站点已在本地重建，可手动重试：")
        print("   cd %s && python push_site.py" % BASE)
        return 1

    pushed = "无改动需推送" not in out and "已是最新" not in out
    live = None
    if pushed:
        print("\n等待 GitHub Pages 重建（最多 180 秒）…")
        import time
        want = [str(c.get("benchmarks.json")), str(c.get("solutions.json")),
                str(c.get("repo_catalog.json")), str(c.get("machines.json"))]
        for _ in range(18):
            time.sleep(10)
            live = live_counts()
            if live and live[0] == want[0] and live[1] == want[1]:
                break
        print("线上首页计数：%s" % (live if live else "读取失败（不影响提交结果）"))
        if live:
            match = (live[0] == want[0] and live[1] == want[1]
                     and live[2] == want[2] and live[3] == want[3])
            print("与 seed 对齐：%s（seed 应为 跑分%s / 方案%s / 仓库%s / 机器%s）"
                  % ("✅ 一致" if match else "⚠️ 未对齐（Pages 可能仍在重建，稍后复查）",
                     want[0], want[1], want[2], want[3]))
        else:
            match = None
    else:
        match = None

    save_state(fp, {"site_counts": {"benchmarks": c.get("benchmarks.json"),
                                    "solutions": c.get("solutions.json"),
                                    "machines": c.get("machines.json"),
                                    "repo_catalog": c.get("repo_catalog.json")},
                    "commit_msg": msg, "pushed": pushed,
                    "live_verified": match})
    print("\n" + "=" * 62)
    print("✅ 同步完成  commit=\"%s\"" % msg)
    print("   状态已记录：%s" % STATE)
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())