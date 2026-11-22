# -*- coding: utf-8 -*-
"""知乎码：四点透视变换。

为什么必须是透视变换，而不是旋转：
  原图二维码是菱形且横向被拉宽（实测四顶点）：
      上 (652, 636)  下 (652, 1190)  -> 竖直对角 554
      左 (256, 879)  右 (1052, 879)  -> 水平对角 796
      比值 1.437
  说明存在透视压缩，不是单纯旋转。
  旋转是刚体变换，转多少度都消不掉压缩 ——
  这正是前面在 35.6 / 41.5 / 45 度之间反复找不到「完美角度」的根本原因。
  唯一正确做法：四角映射到正方形（文档扫描同一原理）。

四个踩过的坑（全部已修正）：
  1. 搜索范围太窄：早期 x1=1090，右顶点被切，四角全错、竖直对角只剩 72px。
  2. s=x+y / d=x-y 极值法对菱形不成立：菱形顶点不在 45 度对角方向，
     实测左角的 s 比上角还小，argmin(s) 会选到左角。改用 min/max x、y。
  3. percentile 过滤太狠会削掉尖角：菱形尖角本就是最外层少数像素。
  4. 最致命：直接取极值会抓到无关白物。二维码正上方有一个插画人物的白衬衫，
     argmin(y) 抓到的是衬衫而不是 QR 上顶点（y 差 100+ px）。
     必须先按最大连通块锁定二维码面板，再在其内部取极值。

四角角色（决定映射顺序，错了会旋转 90 度或镜像）：
  QR 标准：定位块在 左上 / 右上 / 左下，右下无定位块。
  本图菱形：上、右、左 = 定位块；下 = 无定位块。
  所以：上角->左上，右角->右上，下角->右下，左角->左下。
"""
import os
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

SRC = r"C:\Users\yuehancn\Desktop\新建文件夹 (10)\微信图片_20261116063620_520_49.jpg"
OUT = r"//192.168.11.178/我的文档-699065053/岳晗/WorkBuddy\qsl-site\assets-src\zhihu-code.png"
FINAL = 512
INNER = 456
MARKED = r"//192.168.11.178/我的文档-699065053/岳晗/WorkBuddy\qsl-site\_zh_corners.png"

REGION = (200, 560, 1190, 1280)


def largest_white_pixels(a, step=2):
    """取最大白色连通块的精确白像素坐标 (xs, ys)。"""
    m = (a[:, :, 0] > 232) & (a[:, :, 1] > 228) & (a[:, :, 2] > 228)
    h, w = m.shape
    sm = m[::step, ::step]
    sh, sw = sm.shape
    vis = np.zeros((sh, sw), dtype=bool)
    best = [0, None]

    for sy in range(sh):
        for sx in range(sw):
            if not sm[sy, sx] or vis[sy, sx]:
                continue
            q = deque([(sy, sx)])
            vis[sy, sx] = True
            cells = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < sh and 0 <= nx < sw and sm[ny, nx] and not vis[ny, nx]:
                        vis[ny, nx] = True
                        q.append((ny, nx))
            if len(cells) > best[0]:
                best = [len(cells), cells]

    if best[1] is None:
        return None, None

    comp = np.zeros_like(m)
    for cy, cx in best[1]:
        comp[cy * step:(cy + 1) * step, cx * step:(cx + 1) * step] = True

    final = m & comp
    ys, xs = np.where(final)
    return xs, ys


def find_corners(im):
    x0, y0 = REGION[0], REGION[1]
    a = np.asarray(im.crop(REGION)).astype(int)
    xs, ys = largest_white_pixels(a)
    if xs is None or len(xs) < 5000:
        raise RuntimeError("找不到二维码白面板")

    i_top = int(np.argmin(ys))
    i_bot = int(np.argmax(ys))
    i_left = int(np.argmin(xs))
    i_right = int(np.argmax(xs))

    return {
        "top": (float(xs[i_top] + x0), float(ys[i_top] + y0)),
        "right": (float(xs[i_right] + x0), float(ys[i_right] + y0)),
        "bot": (float(xs[i_bot] + x0), float(ys[i_bot] + y0)),
        "left": (float(xs[i_left] + x0), float(ys[i_left] + y0)),
    }


def persp_coeffs(src, dst):
    mm = []
    for (x, y), (u, v) in zip(src, dst):
        mm.append([u, v, 1, 0, 0, 0, -x * u, -x * v])
        mm.append([0, 0, 0, u, v, 1, -y * u, -y * v])
    A = np.array(mm, dtype=float)
    B = np.array([c for p in src for c in p], dtype=float)
    return np.linalg.solve(A, B).tolist()


def main():
    im = Image.open(SRC).convert("RGB")
    c = find_corners(im)

    for k in ("top", "right", "bot", "left"):
        print("  %-5s (%.1f, %.1f)" % (k, c[k][0], c[k][1]))

    dh = abs(c["right"][0] - c["left"][0])
    dv = abs(c["bot"][1] - c["top"][1])
    print("  水平对角 %.1f  竖直对角 %.1f  比值 %.3f"
          % (dh, dv, dh / dv if dv else 0))

    vis = im.copy()
    d = ImageDraw.Draw(vis)
    for k in ("top", "right", "bot", "left"):
        x, y = c[k]
        d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=(255, 0, 0), width=4)
        d.text((x + 17, y - 7), k, fill=(255, 0, 0))
    vis.save(MARKED)

    src = [c["top"], c["right"], c["bot"], c["left"]]
    dst = [(0.0, 0.0), (float(INNER), 0.0),
           (float(INNER), float(INNER)), (0.0, float(INNER))]

    coeffs = persp_coeffs(src, dst)
    warped = im.transform((INNER, INNER), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

    canvas = Image.new("RGB", (FINAL, FINAL), (255, 255, 255))
    off = (FINAL - INNER) // 2
    canvas.paste(warped, (off, off))
    canvas.save(OUT, "PNG", optimize=True)

    print("输出 %s  %dx%d  %d bytes（静区 %d px/边）"
          % (OUT, FINAL, FINAL, os.path.getsize(OUT), off))
    print("四角标记图 %s" % MARKED)


if __name__ == "__main__":
    main()