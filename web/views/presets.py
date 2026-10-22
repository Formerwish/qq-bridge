"""预设页：展示 DSH 可用预设与当前配置（只读；改动请在部署时改 config.toml presets 段）。"""

from __future__ import annotations

import control
from flask import Blueprint, render_template

from views.auth import login_required

bp = Blueprint("presets", __name__)


@bp.get("/presets")
@login_required
def index():
    error = None
    info = None
    try:
        info = control.presets()
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("presets.html", info=info, error=error)
