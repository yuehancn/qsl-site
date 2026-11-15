# -*- coding: utf-8 -*-
"""
B 站码裁剪（最终版）—— 2026-11-15

原图结构（1027x1459）：
  y 60-160    头像 + 「丘山录 / UID: 2100520926」
  y 450-470   顶部装饰点（蓝色波浪 + 黄点）
  y 507-951   **二维码本体**（蓝白方格 + 中心 B 站 logo）
  y 975-1010  底部装饰点
  外围         黑色电视框描边、人物插画（2233 娘举电视）

裁剪边界（实测逐列/逐行扫描蓝点数量得出）：
  x 291-735   （左：x=289 及以前归零；右：x=738 及以后归零）
  y 507-951   （上：y=504 归零；下：y=954 归零）
  => 445 x 445，天然正方形

关键教训（v1 踩过）：
  不能用「行/列密度阈值」定边界 —— 两侧装饰点密度也过阈值，
  会裁出一条装饰点带。必须用「密度归零点」作边界。

B 站码是标准方形 QR，绝不能用圆形遮罩（会切掉四角定位块，扫不出）。
抖音那种圆盘码才需要圆形遮罩。

四边外验证：左/右/上/下外侧 3px 处蓝点数均为 0。
"""
import os
from PIL import Image
import numpy as np

SRC = r"C:\Users\yuehancn\.workbuddy\clipboard-images\clipboard-2026-11-15T15-28-05-769Z-6b6e9fb7.jpg"
DST = r"C:\Users\yuehancn\WorkBuddy\qsl-site\assets-src\bilibili-code.png"

OUT_SIZE = 512
PAD_RATIO = 0.08
BOX = (291, 507, 735, 951)


def main():
    im = Image.open(SRC).convert("RGB")
    arr = np.asarray(im).astype(int)
    blue = ((arr[:, :, 2] > 120) &
            (arr[:, :, 2] > arr[:, :, 0] + 40) &
            (arr[:, :, 2] > arr[:, :, 1] + 30))

    x0, y0, x1, y1 = BOX
    cw, ch = x1 - x0 + 1, y1 - y0 + 1

    print("裁剪框: x %d-%d (%d)  y %d-%d (%d)  宽高差 %d"
          % (x0, x1, cw, y0, y1, ch, abs(cw - ch)))

    checks = [
        ("左", int(blue[y0:y1 + 1, x0 - 3].sum())),
        ("右", int(blue[y0:y1 + 1, x1 + 3].sum())),
        ("上", int(blue[y0 - 3, x0:x1 + 1].sum())),
        ("下", int(blue[y1 + 3, x0:x1 + 1].sum())),
    ]
    for tag, v in checks:
        print("  %s外: %d %s" % (tag, v, "OK" if v < 5 else "!! 仍有码点"))

    crop = im.crop((x0, y0, x1 + 1, y1 + 1))
    pad = int(max(cw, ch) * PAD_RATIO)

    if cw == ch:
        final = Image.new("RGB", (cw + pad * 2, ch + pad * 2), (255, 255, 255))
        final.paste(crop, (pad, pad))
    else:
        side = max(cw, ch)
        cv = Image.new("RGB", (side, side), (255, 255, 255))
        cv.paste(crop, ((side - cw) // 2, (side - ch) // 2))
        final = Image.new("RGB", (side + pad * 2, side + pad * 2), (255, 255, 255))
        final.paste(cv, (pad, pad))

    final = final.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    final.save(DST, "PNG", optimize=True)
    print("输出:", DST, os.path.getsize(DST), "bytes")


if __name__ == "__main__":
    main()