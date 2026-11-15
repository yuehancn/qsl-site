# -*- coding: utf-8 -*-
"""
域名切换验收脚本（88918888.xyz）

用法：
  python check_domain.py            # 查一次
  python check_domain.py --watch    # 每 30 秒查一次，直到通过

检查五项：
  1. 权威 NS 是否返回 GitHub Pages 的 4 个 IP
  2. www 是否 CNAME 到 yuehancn.github.io
  3. 本机能否解析（可能被运营商劫持，故单独标注）
  4. https 是否已响应 200
  5. 旧域名是否已清空

🔴 为什么要指定权威 NS：本机 DNS 会被运营商劫持到重定向页（如 36.155.149.35 /
   1.13.76.35），直接 nslookup 得到的 IP 是假的，必须向 wallpaper.dnspod.net 查询。
"""
import io
import sys
import time
import subprocess

DOMAIN = "88918888.xyz"
OLD = "361365365.xyz"
AUTH_NS = "wallpaper.dnspod.net"
GH_IPS = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"}
GH_CNAME = "yuehancn.github.io"


def resolve(name, rtype="A", ns=None):
    cmd = ["nslookup", "-type=" + rtype, name]
    if ns:
        cmd.append(ns)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=20)
    except Exception:
        return []
    out = r.stdout.decode("utf-8", "replace")
    vals = []
    for ln in out.splitlines():
        ln = ln.strip()
        if "Address" in ln or "Addresses" in ln:
            v = ln.split()[-1].rstrip(".")
            if rtype == "A" and v.count(".") == 3:
                vals.append(v)
            elif rtype != "A" and "." in v:
                vals.append(v)
        if "canonical name" in ln.lower():
            v = ln.split()[-1].rstrip(".")
            if "." in v:
                vals.append(v)
    # 去掉 NS 服务器自身的地址
    return [v for v in vals if v != AUTH_NS and not v.startswith("127.")]


def http_code(url, timeout=15):
    proxy = ""
    import os
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    cmd = ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
           "--max-time", str(timeout)]
    if p:
        cmd += ["-x", p]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return "timeout"


def check():
    print("=" * 62)
    print("域名验收 ｜ %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 62)

    ok = {}

    # 1) 权威 A 记录
    print("\n[1] 权威 A 记录（向 %s 查询）" % AUTH_NS)
    ips = resolve(DOMAIN, "A", AUTH_NS)
    print("    实际返回: %s" % (ips or "无"))
    hit = set(ips) & GH_IPS
    if hit:
        print("    ✅ 已指向 GitHub Pages（命中 %d 个）: %s" % (len(hit), sorted(hit)))
        ok["A"] = True
    elif ips:
        print("    ❌ 仍不是 GitHub IP。当前是 %s" % ips)
        print("       期望: 185.199.108/109/110/111.153")
        ok["A"] = False
    else:
        print("    ❌ 无 A 记录（记录可能被删光了）")
        ok["A"] = False

    # 2) www CNAME
    print("\n[2] www CNAME")
    c = resolve("www." + DOMAIN, "CNAME", AUTH_NS)
    print("    实际返回: %s" % (c or "无"))
    if any(GH_CNAME in x for x in c):
        print("    ✅ www 已 CNAME 到 %s" % GH_CNAME)
        ok["CNAME"] = True
    else:
        print("    ⚠️  未配置或指向别处（不影响主域名访问）")
        ok["CNAME"] = False

    # 3) 本机解析
    print("\n[3] 本机解析（可能被运营商劫持，仅供参考）")
    local = resolve(DOMAIN, "A")
    print("    实际返回: %s" % (local or "无"))
    if set(local) & GH_IPS:
        print("    ✅ 本机已能解析到 GitHub")
    elif local:
        print("    ⚠️  本机解析结果与权威不一致 → 大概率是运营商劫持/缓存")
        print("       判断真实状态请只看第 [1] 项")

    # 4) HTTPS
    print("\n[4] HTTPS 可访问性")
    code = http_code("https://" + DOMAIN + "/")
    print("    HTTP 状态: %s" % code)
    if code == "200":
        print("    ✅ 站点已上线")
        ok["HTTPS"] = True
    elif code in ("0", "timeout", "000"):
        print("    ❌ 连不上（DNS 未生效或证书未签发）")
        ok["HTTPS"] = False
    else:
        print("    ⚠️  返回 %s（DNS 刚生效时常见 404/502，稍等再试）" % code)
        ok["HTTPS"] = False

    # 5) 旧域名
    print("\n[5] 旧域名 %s 是否已清空" % OLD)
    old_ips = resolve(OLD, "A", AUTH_NS)
    print("    实际返回: %s" % (old_ips or "无"))
    if not old_ips:
        print("    ✅ 已无 A 记录（符合「彻底弃用」预期）")
    elif set(old_ips) & GH_IPS:
        print("    ℹ️  旧域名也指向了 GitHub（若想跳转则可保留）")
    else:
        print("    ⚠️  仍指向 %s —— 若已决定弃用，建议删掉" % old_ips)

    # 总结
    print("\n" + "=" * 62)
    passed = sum(1 for v in ok.values() if v)
    print("结果：%d/%d 项通过" % (passed, len(ok)))
    if ok.get("A") and ok.get("HTTPS"):
        print("🎉 域名切换完成，站点可正常访问")
        print("   下一步：GitHub 仓库 → Settings → Pages → 勾选 Enforce HTTPS")
        return True
    if not ok.get("A"):
        print("⏳ 卡在 DNS：请到腾讯云 DNSPod 控制台改 %s 的 A 记录" % DOMAIN)
    elif not ok.get("HTTPS"):
        print("⏳ DNS 已对，等证书签发（通常 15–60 分钟）")
        print("   可稍后重跑本脚本")
    print("=" * 62)
    return False


def main():
    watch = "--watch" in sys.argv
    if not watch:
        sys.exit(0 if check() else 1)
    for i in range(40):
        if check():
            sys.exit(0)
        print("\n第 %d 次未通过，30 秒后重试...\n" % (i + 1))
        time.sleep(30)
    sys.exit(1)


if __name__ == "__main__":
    main()