# -*- coding: utf-8 -*-
"""
抖音码专用裁剪：从深色底图里提出白色圆形码，放到白底方形画布。

为什么单独处理：
  抖音导出图是深青色底 + 白色圆盘码。直接按矩形裁会带上四角深色背景，
  和其他两张白底码放在一起视觉不统一；而且圆盘贴边，扫码容错不足。
  这里用「找白色像素包围盒」定位圆盘，四周留 10% 白边再输出。
"""
import os
from PIL import Image
import numpy as np

SRC = r"C:\Users\yuehancn\Desktop\新建文件夹 (10)\微信图片_20261115225755_515_49.jpg"
DST = r"C:\Users\yuehancn\WorkBuddy\qsl-site\assets-src\douyin-code.png"
OUT_SIZE = 512
MARGIN = 0.10


def main():
    im = Image.open(SRC).convert("RGB")
    arr = np.asarray(im).astype(int)

    # 🔴 只在二维码所在的行段里找白盘（y 210-1060）。
    #    全图搜会把底部白色说明文字（"保存图片到相册"等）也当成白盘，
    #    实测导致包围盒高度 1649（正确约 800），裁出来完全错位。
    y_lo, y_hi = 210, 1060
    sub = arr[y_lo:y_hi]

    # 白盘判据：三通道都高
    white = (sub[:, :, 0] > 200) & (sub[:, :, 1] > 200) & (sub[:, :, 2] > 200)
    rows = np.where(white.sum(axis=1) > 30)[0]
    cols = np.where(white.sum(axis=0) > 30)[0]
    if len(rows) == 0 or len(cols) == 0:
        print("未找到白色圆盘")
        return

    y0, y1 = int(rows[0]) + y_lo, int(rows[-1]) + y_lo
    x0, x1 = int(cols[0]), int(cols[-1])
    print("白盘包围盒: x %d-%d, y %d-%d  (%dx%d)"
          % (x0, x1, y0, y1, x1 - x0 + 1, y1 - y0 + 1))

    crop = im.crop((x0, y0, x1 + 1, y1 + 1))

    # 🔴 把圆盘四角的深色背景刷白。
    #    包围盒按白色像素算，但圆的四角天然是背景（深青），
    #    不刷掉会留下四个深色尖角，和其他白底码视觉不统一。
    ca = np.asarray(crop).astype(int)
    dark = (ca[:, :, 0] < 120) & (ca[:, :, 1] < 140) & (ca[:, :, 2] < 160)
    # 只刷「靠近画布边缘」的深色，避免误伤圆盘内部的深色圆环/logo
    hh, ww = dark.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    cx, cy, r = ww / 2.0, hh / 2.0, min(ww, hh) / 2.0
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    outside = dist > r * 0.94          # 圆外区域
    to_white = dark & outside
    ca[to_white] = [255, 255, 255]
    crop = Image.fromarray(ca.astype(np.uint8))

    cw, ch = crop.size
    side = max(cw, ch)

    # 白底画布，四周留 10%
    pad = int(side * MARGIN)
    canvas_side = side + pad * 2
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    canvas.paste(crop, (pad + (side - cw) // 2, pad + (side - ch) // 2))
    canvas = canvas.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

    canvas.save(DST, "PNG", optimize=True)
    print("输出:", DST, os.path.getsize(DST), "bytes")


if __name__ == "__main__":
    main()