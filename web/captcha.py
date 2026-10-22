"""登录验证码（从参考项目 minitor 迁移）。

- 4 位随机字母数字，PIL 绘制（随机颜色/位置/干扰线），字体用仓库内 ZCOOL 字体。
- 文本存 Flask session（`session['captcha']`），登录时大小写不敏感校验并立即清除（一次性）。
- 空 session / 缺验证码 → 校验失败（fail-closed）。
"""

from __future__ import annotations

import io
import random

from flask import session
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = str(Path(__file__).resolve().parent / "assets" / "ZCOOLKuaiLe-Regular.ttf")
LETTERS = "ABCEFGHJKMNOPQRTUVWXYZabcdefhjkmnpqrtwxyz23478"


def generate_captcha(width: int = 150, height: int = 50) -> bytes:
    text = "".join(random.choice(LETTERS) for _ in range(4))
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    font_size = int(height * 0.8)
    font = ImageFont.truetype(FONT_PATH, font_size)

    avg_width = (width - 20) / len(text)
    offset = 10
    for char in text:
        y = random.randint(0, max(0, height - font_size - 5))
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.text((offset, y), char, fill=color, font=font)
        offset += avg_width
    draw.rectangle([0, 0, width - 1, height - 1], outline="black")
    for _ in range(5):
        draw.line(
            (random.randint(0, width), random.randint(0, height),
             random.randint(0, width), random.randint(0, height)),
            fill="black", width=1,
        )

    session["captcha"] = text
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def verify_captcha(value: str) -> bool:
    expected = str(session.pop("captcha", "") or "")
    if not expected:
        return False
    return str(value or "").strip().lower() == expected.lower()
