# -*- coding: utf-8 -*-
"""CSDN 码：用三个定位块精确确定二维码边界。

为什么不能直接用黑色包围盒：
  会带进下方的 CSDN logo（实测 y 下界 1519，而二维码实际底部约 1440），
  裁出来不是正方形（289x370），且框进无关内容。

定位块特征（QR 标准，7x7 模块）：
    外圈全黑 / 次圈全白 / 中心 3x3 全黑
  三个定位块位于 左上 / 右上 / 左下。

方法：
  扫描候选窗口，按「外圈黑 + 次圈白 + 中心黑」打分，
  取最高分尺度下呈 L 形分布的三块；
  左上块外沿 = QR 左上角，右上块 + 块宽 = QR 右边，左下块 + 块宽 = QR 下边。
"""
import os

import numpy as np
from PIL import Image, ImageDraw

SRC = r"C:\Users\yuehancn\Desktop\新建文件夹 (10)\微信图片_20261116063708_521_49.jpg"
OUT = r"E:\workbuddy\qsl-site\assets-src\csdn-code.png"
MARKED = r"E:\workbuddy\qsl-site\_csdn_mark2.png"
SIZE = 512

RX0, RY0, RX1, RY1 = 440, 1080, 840, 1480


def finder_score(black, x, y, w):
    if x < 0 or y < 0 or x + w > black.shape[1] or y + w > black.shape[0]:
        return -1.0
    win = black[y:y + w, x:x + w]
    m = w / 7.0
    mi = max(1, int(m))
    m2 = max(2, int(2 * m))
    m5 = max(3, int(5 * m))

    outer = np.concatenate([
        win[0:mi, :].ravel(),
        win[-mi:, :].ravel(),
        win[:, 0:mi].ravel(),
        win[:, -mi:].ravel(),
    ])
    ring2 = np.concatenate([
        win[mi:m2, mi:-mi].ravel(),
        win[-m2:-mi, mi:-mi].ravel(),
        win[mi:-mi, mi:m2].ravel(),
        win[mi:-mi, -m2:-mi].ravel(),
    ])
    core = win[m2:m5, m2:m5].ravel()
    if len(ring2) == 0 or len(core) == 0:
        return -1.0
    return float(outer.mean() - ring2.mean() + core.mean())


def main():
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    lum = a.mean(axis=2)
    black = (lum < 95) & (np.abs(a[:, :, 0] - a[:, :, 2]) < 45)

    sub = black[RY0:RY1, RX0:RX1]
    sh, sw = sub.shape
    print("搜索区 %dx%d，黑像素 %d" % (sw, sh, int(sub.sum())))

    cands = []
    for w in range(50, 111, 4):
        for y in range(0, sh - w, 3):
            for x in range(0, sw - w, 3):
                s = finder_score(sub, x, y, w)
                if s > 0.0:
                    cands.append((s, x, y, w))

    cands.sort(reverse=True)
    print("\n候选定位块（前 10）:")
    for s, x, y, w in cands[:10]:
        print("  score %.2f  (%d,%d) w=%d" % (s, x + RX0, y + RY0, w))

    if not cands:
        raise RuntimeError("找不到定位块")

    w_use = cands[0][3]
    same = [c for c in cands if c[3] == w_use][:60]
    print("\n块宽 w=%d，同尺度候选 %d 个" % (w_use, len(same)))

    xs = np.array([c[1] for c in same])
    ys = np.array([c[2] for c in same])
    tl = same[int(np.argmin(xs + ys))]
    tr = same[int(np.argmax(xs - ys))]
    bl = same[int(np.argmax(ys - xs))]

    print("  左上 (%d,%d)  右上 (%d,%d)  左下 (%d,%d)"
          % (tl[1] + RX0, tl[2] + RY0, tr[1] + RX0, tr[2] + RY0,
             bl[1] + RX0, bl[2] + RY0))

    x0 = tl[1] + RX0
    y0 = tl[2] + RY0
    x1 = tr[1] + RX0 + w_use
    y1 = bl[2] + RY0 + w_use
    print("二维码外框: x %d-%d  y %d-%d  (%dx%d)"
          % (x0, x1, y0, y1, x1 - x0, y1 - y0))

    vis = im.copy()
    d = ImageDraw.Draw(vis)
    d.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=5)
    for (s, x, y, w) in (tl, tr, bl):
        d.rectangle([x + RX0, y + RY0, x + RX0 + w, y + RY0 + w],
                    outline=(0, 255, 0), width=3)
    vis.save(MARKED)
    print("标记图 %s" % MARKED)

    side = max(x1 - x0, y1 - y0)
    pad = int(side * 0.10)
    crop = im.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    cw, ch = crop.size
    s2 = max(cw, ch)
    canvas = Image.new("RGB", (s2, s2), (255, 255, 255))
    canvas.paste(crop, ((s2 - cw) // 2, (s2 - ch) // 2))
    canvas.resize((SIZE, SIZE), Image.LANCZOS).save(OUT, "PNG", optimize=True)


    print("输出 %s  %dx%d  %d bytes" % (OUT, SIZE, SIZE, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()