# -*- coding: utf-8 -*-
"""
把 qsl-site 推到 GitHub —— 带自动降级。

为什么需要这个而不是直接 git push：
  实测本机到 github.com 的通路**不稳定**：
    · 直连经常超时
    · 走代理时 git 的 CONNECT 隧道偶发 502（但 api.github.com 通常通）
    · 代理端口每次会话会变（见过 58650 / 54573 / 60678 / 63664）

  所以策略是：先试 git push（正常路径），失败则自动降级到 REST API 提交
  （blobs → tree → commit → PATCH ref）。两条路都能把文件送上去。

用法：
  python push_site.py            # 提交本地改动 + 推送
  python push_site.py --dry      # 只显示会推什么
  python push_site.py --api      # 强制走 API（跳过 git push）
  python push_site.py --msg "xxx"  # 自定义 commit message
"""
import io
import os
import sys
import json
import time
import base64
import subprocess

SITE = os.path.dirname(os.path.abspath(__file__))
REPO = "yuehancn/qsl-site"
BRANCH = "main"


def proxy_port():
    """每次现取代理端口 —— 硬编码必失败。"""
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    return p.rsplit(":", 1)[-1] if p else ""


def proxy_url():
    port = proxy_port()
    return "http://127.0.0.1:" + port if port else ""


def sh(args, cwd=SITE, timeout=120, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, env=e)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as ex:
        return -2, str(ex)


def gh_token():
    rc, out = sh(["gh", "auth", "token"], timeout=30)
    return out.strip() if rc == 0 and out.strip() else ""


def has_changes():
    rc, out = sh(["git", "status", "--porcelain"])
    return rc == 0 and bool(out.strip())


def stage_and_commit(msg):
    rc, out = sh(["git", "add", "-A"])
    if rc != 0:
        return False, "git add 失败: " + out[-300:]
    rc, out = sh(["git", "-c", "user.name=yuehancn",
                  "-c", "user.email=yuehancn@users.noreply.github.com",
                  "commit", "-m", msg])
    if rc != 0:
        if "nothing to commit" in out or "无需提交" in out:
            return True, "无改动需提交"
        return False, "git commit 失败: " + out[-400:]
    return True, out.strip().splitlines()[0] if out.strip() else "committed"


def try_git_push():
    """正常路径。返回 (ok, 说明)。

    🔴 若上一次是用 API 推的，本地与远端历史会分叉，git push 会被拒（non-fast-forward）。
       这里先尝试普通 push，被拒则自动 fetch + rebase 后再试一次。
       内容一致，rebase 不会丢东西（API 提交的文件和本地一致）。
    """
    port = proxy_port()
    proxies = []
    if port:
        proxies.append(["-c", "http.proxy=" + proxy_url(),
                        "-c", "https.proxy=" + proxy_url()])
    proxies.append([])

    def one(extra):
        args = ["git"] + extra + ["push", "origin", BRANCH]
        rc, out = sh(args, timeout=150, env={"GIT_TERMINAL_PROMPT": "0"})
        return rc, out

    last = ""
    for extra in proxies:
        rc, out = one(extra)
        if rc == 0 and "->" in out:
            return True, "git push 成功"
        if "Everything up-to-date" in out or "up to date" in out or "up-to-date" in out:
            return True, "已是最新，无需推送"
        last = out.strip()[-400:]

        # non-fast-forward → 先对齐再试一次
        if "non-fast-forward" in out or "fetch first" in out or "rejected" in out:
            fe = ["git"] + extra + ["fetch", "origin", BRANCH]
            rc2, out2 = sh(fe, timeout=150, env={"GIT_TERMINAL_PROMPT": "0"})
            if rc2 == 0:
                rb = ["git"] + extra + ["rebase", "origin/" + BRANCH]
                rc3, out3 = sh(rb, timeout=150, env={"GIT_TERMINAL_PROMPT": "0"})
                if rc3 == 0:
                    rc4, out4 = one(extra)
                    if rc4 == 0 and "->" in out4:
                        return True, "git push 成功（已自动 rebase 对齐远端）"
                    last = out4.strip()[-400:]
                else:
                    # rebase 冲突：中止，保持工作区干净，交给 API 兜底
                    sh(["git", "rebase", "--abort"], timeout=60)
                    last = "rebase 冲突，已中止: " + out3.strip()[-200:]
    return False, last


def api_call(method, path, payload=None, token="", timeout=45):
    url = "https://api.github.com" + path
    cmd = ["curl", "-s", "-X", method, "--max-time", str(timeout),
           "-H", "Authorization: Bearer " + token,
           "-H", "Accept: application/vnd.github+json",
           "-H", "Content-Type: application/json"]
    pu = proxy_url()
    if pu:
        cmd += ["-x", pu]
    tmp = None
    if payload is not None:
        tmp = os.path.join(SITE, "_payload.json")
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        cmd += ["--data-binary", "@" + tmp]
    cmd.append(url)
    try:
        rc, out = sh(cmd, timeout=timeout + 30)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    if rc != 0:
        return {}
    try:
        return json.loads(out) if out.strip() else {}
    except Exception:
        return {"_raw": out[:400]}


def try_api_push(msg):
    """降级路径：把**本次 commit 涉及的文件**用 API 提交。"""
    token = gh_token()
    if not token:
        return False, "拿不到 GitHub token（gh auth token 失败）"

    # 本次 commit 改了哪些文件（相对上一个 commit）
    rc, out = sh(["git", "diff", "--name-only", "HEAD~1", "HEAD"])
    if rc != 0:
        rc, out = sh(["git", "show", "--name-only", "--pretty=format:", "HEAD"])
    files = [f.strip() for f in out.splitlines() if f.strip() and not f.startswith("_")]
    if not files:
        return False, "没有可提交的文件"

    ref = api_call("GET", "/repos/%s/git/ref/heads/%s" % (REPO, BRANCH), token=token)
    base = (ref.get("object") or {}).get("sha")
    if not base:
        return False, "取远端 base sha 失败: %s" % str(ref)[:200]

    entries = []
    for path in files:
        full = os.path.join(SITE, path)
        if not os.path.isfile(full):
            continue   # 已删除的文件这里跳过（API 删除需另一套逻辑）
        try:
            content = io.open(full, "rb").read()
        except Exception:
            continue
        blob = api_call("POST", "/repos/%s/git/blobs" % REPO, {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64"}, token=token)
        sha = blob.get("sha")
        if not sha:
            return False, "blob 上传失败 %s: %s" % (path, str(blob)[:200])
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})

    if not entries:
        return False, "没有成功上传任何文件"

    tree = api_call("POST", "/repos/%s/git/trees" % REPO,
                    {"base_tree": base, "tree": entries}, token=token)
    if not tree.get("sha"):
        return False, "tree 创建失败: %s" % str(tree)[:200]

    commit = api_call("POST", "/repos/%s/git/commits" % REPO,
                      {"message": msg, "tree": tree["sha"], "parents": [base]},
                      token=token)
    if not commit.get("sha"):
        return False, "commit 创建失败: %s" % str(commit)[:200]

    upd = api_call("PATCH", "/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
                   {"sha": commit["sha"], "force": False}, token=token)
    if (upd.get("object") or {}).get("sha") == commit["sha"]:
        return True, "API 推送成功（%d 个文件，commit %s）" % (len(entries), commit["sha"][:8])
    return False, "ref 更新失败: %s" % str(upd)[:250]


def main():
    dry = "--dry" in sys.argv
    force_api = "--api" in sys.argv
    msg = "data: 同步数据与页面"
    for i, a in enumerate(sys.argv):
        if a == "--msg" and i + 1 < len(sys.argv):
            msg = sys.argv[i + 1]

    print("=" * 62)
    print("推送 qsl-site → GitHub")
    print("=" * 62)

    changed = has_changes()
    print("工作区有未提交改动: %s" % ("是" if changed else "否"))

    if dry:
        rc, out = sh(["git", "status", "--short"])
        print("\n将提交的文件:")
        print(out.rstrip() or "  （无）")
        print("\n[DRY] 未提交、未推送")
        return 0

    if changed:
        ok, info = stage_and_commit(msg)
        print("提交: %s" % info)
        if not ok:
            print("❌ 提交失败")
            return 1
    else:
        print("无需提交，尝试推送已有 commit")

    if not force_api:
        ok, info = try_git_push()
        print("git push: %s" % ("✅ " + info if ok else "❌ " + info))
        if ok:
            print("\n" + "=" * 62)
            print("✅ 推送完成。GitHub Pages 会在 1–3 分钟内自动重建。")
            print("=" * 62)
            return 0
        print("\n↘ git push 不通，降级到 REST API…")

    ok, info = try_api_push(msg)
    print("API 推送: %s" % ("✅ " + info if ok else "❌ " + info))
    if not ok:
        print("\n" + "=" * 62)
        print("❌ 两条通道都失败。可尝试：")
        print("   1. 确认代理可用：echo $HTTPS_PROXY，并试探端口")
        print("   2. 手动：git push origin main")
        print("=" * 62)
        return 1

    # API 推送后本地与远端历史会分叉，提示但不自动修
    print("\n⚠️  API 推送已让本地与远端历史分叉（远端是新的 sha）。")
    print("   文件内容一致。下次同步前建议先对齐：")
    print("     git fetch origin main && git reset --hard origin/main")
    print("\n" + "=" * 62)
    print("✅ 推送完成。GitHub Pages 会在 1–3 分钟内自动重建。")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())