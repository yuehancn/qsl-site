# -*- coding: utf-8 -*-
"""
从平台导出的整张二维码图里，裁出二维码主体（去掉上下的头像/标题/说明文字）。

用法：
  python crop_codes.py

为什么不用目测坐标：
  三张图尺寸、底色、留白都不同（抖音是深色底），目测必然裁歪。
  这里用「与底色差异 → 找非底色像素包围盒」，自动定位。
  二维码必须保持正方形，否则扫码会失败，所以裁完统一垫正方形再缩放。
"""
import os
from PIL import Image
import numpy as np

SRC = r"C:\Users\yuehancn\Desktop\新建文件夹 (10)"
DST = r"//192.168.11.178/我的文档-699065053/岳晗/WorkBuddy\qsl-site\assets-src"

JOBS = [
    ("shipinhao-code.png",   "微信图片_20261115224227_513_49.jpg", (452, 1241), "视频号"),
    ("xiaohongshu-code.png", "微信图片_20261115225402_514_49.jpg", (137, 809),  "小红书"),
    ("douyin-code.png",      "微信图片_20261115225755_515_49.jpg", (234, 1035), "抖音"),
]

OUT_SIZE = 512


def bg_color(arr):
    a = np.concatenate([arr[0:3, 0:3].reshape(-1, 3), arr[0:3, -3:].reshape(-1, 3)])
    return np.median(a, axis=0)


def main():
    os.makedirs(DST, exist_ok=True)
    for out_name, src_name, (y0, y1), tag in JOBS:
        path = os.path.join(SRC, src_name)
        if not os.path.isfile(path):
            print("跳过（文件不存在）:", path)
            continue

        im = Image.open(path).convert("RGB")
        arr = np.asarray(im).astype(int)
        h, w, _ = arr.shape

        seg = arr[y0:y1 + 1]
        bg = bg_color(seg)
        diff = np.abs(seg - bg).sum(axis=2)
        mask = diff > 40

        cols = np.where(mask.sum(axis=0) > (y1 - y0) * 0.03)[0]
        if len(cols) == 0:
            print(tag, "未能定位左右边界，跳过")
            continue
        x0, x1 = int(cols[0]), int(cols[-1])

        pad = int((y1 - y0) * 0.03)
        box = (max(0, x0 - pad), max(0, y0 - pad),
               min(w, x1 + 1 + pad), min(h, y1 + 1 + pad))

        crop = im.crop(box)
        cw, ch = crop.size
        side = max(cw, ch)
        canvas = Image.new("RGB", (side, side), tuple(int(v) for v in bg))
        canvas.paste(crop, ((side - cw) // 2, (side - ch) // 2))
        canvas = canvas.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

        outp = os.path.join(DST, out_name)
        canvas.save(outp, "PNG", optimize=True)
        print("%-6s -> %-22s box=%s  side=%d  %d bytes"
              % (tag, out_name, box, side, os.path.getsize(outp)))


if __name__ == "__main__":
    main()