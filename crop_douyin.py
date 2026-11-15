# -*- coding: utf-8 -*-
"""
抖音码裁剪（v4，最终版）—— 2026-11-15

三次试错记录：
  v1  按 `r > 0.94r` 刷白        -> 刷掉最外圈码点 -> 扫不出
  v2  不刷白只缩放                -> 四角留深青背景，脏
  v3  逐角度扫描圆盘边界          -> 边缘被切出锯齿毛刺，更糟

v4 为什么对：
  实测圆周像素统计（容差 60 判背景）：
    r=370 -> 98.7% 非背景
    r=380 -> 98.5% 非背景
    r=384 -> 98.4% 非背景
  说明**白色圆盘一直延伸到 r≈385，边缘本身是纯白，不含码点**。
  码点最外只到 r≈380 左右，且都在白色圆盘内部。

  所以正确做法极简：
    · 半径 386 的圆形遮罩（略大于实测 385，容错）
    · 圆内：原样保留，一个像素不动
    · 圆外：刷纯白（那里是深青背景）

  然后外扩 8% 白边，缩放到 512×512。
"""
import os
from PIL import Image
import numpy as np

SRC = r"C:\Users\yuehancn\Desktop\新建文件夹 (10)\微信图片_20261115225755_515_49.jpg"
DST = r"C:\Users\yuehancn\WorkBuddy\qsl-site\assets-src\douyin-code.png"

OUT_SIZE = 512
Y_LO, Y_HI = 210, 1060
# 圆盘 bbox 770x770，半径 385；取 386 略有余量
MASK_R = 386


def main():
    im = Image.open(SRC).convert("RGB")
    arr = np.asarray(im).astype(int)

    sub = arr[Y_LO:Y_HI]
    white = (sub[:, :, 0] > 200) & (sub[:, :, 1] > 200) & (sub[:, :, 2] > 200)
    rows = np.where(white.sum(axis=1) > 30)[0]
    cols = np.where(white.sum(axis=0) > 30)[0]
    x0, y0 = int(cols[0]), int(rows[0]) + Y_LO
    x1, y1 = int(cols[-1]), int(rows[-1]) + Y_LO

    disc = arr[y0:y1 + 1, x0:x1 + 1]
    hh, ww, _ = disc.shape
    cy, cx = (hh - 1) / 2.0, (ww - 1) / 2.0
    print("白盘 bbox: (%d,%d)-(%d,%d)  %dx%d" % (x0, y0, x1, y1, ww, hh))

    yy, xx = np.mgrid[0:hh, 0:ww]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    outside = dist > MASK_R

    out = disc.copy()
    out[outside] = [255, 255, 255]
    print("遮蔽半径 %d，刷白像素 %d（圆周外）" % (MASK_R, int(outside.sum())))

    # 验证：圆内非白像素数（码点+圆环+logo），应与原图一致
    inner = ~outside
    nz_before = int((np.abs(disc - 255).sum(axis=2)[inner] > 60).sum())
    nz_after = int((np.abs(out - 255).sum(axis=2)[inner] > 60).sum())
    print("圆内非白像素: 原图 %d / 输出 %d  %s"
          % (nz_before, nz_after,
             "一致 OK" if nz_before == nz_after else "不一致 异常"))

    img = Image.fromarray(out.astype(np.uint8))
    pad = int(max(ww, hh) * 0.08)
    canvas = Image.new("RGB", (ww + pad * 2, hh + pad * 2), (255, 255, 255))
    canvas.paste(img, (pad, pad))
    canvas = canvas.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

    canvas.save(DST, "PNG", optimize=True)
    print("输出:", DST, os.path.getsize(DST), "bytes")


if __name__ == "__main__":
    main()