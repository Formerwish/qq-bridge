"""qq-bridge 统一控制台（Flask 入口）。

运行：
    web\run.bat            # Windows 双击/后台
    cd web && .venv\\Scripts\\python app.py

端口/绑定来自 config.toml 的 [web] 段（默认 0.0.0.0:3211）。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, render_template  # noqa: E402

import db  # noqa: E402
from settings import settings  # noqa: E402
from logging_setup import setup_logging  # noqa: E402
from views.auth import bp as auth_bp  # noqa: E402
from views.dashboard import bp as dashboard_bp  # noqa: E402
from views.sessions import bp as sessions_bp  # noqa: E402
from views.tools import bp as tools_bp  # noqa: E402
from views.logs import bp as logs_bp  # noqa: E402
from views.periods import bp as periods_bp  # noqa: E402
from views.kb import bp as kb_bp  # noqa: E402
from views.slang import bp as slang_bp  # noqa: E402
from views.users import bp as users_bp  # noqa: E402
from views.roles import bp as roles_bp  # noqa: E402
from views.presets import bp as presets_bp  # noqa: E402
from views.tokens import bp as tokens_bp  # noqa: E402
from views.stickers import bp as stickers_bp
from views.internal_usage import bp as internal_usage_bp  # noqa: E402
from views.settings import bp as settings_bp  # noqa: E402
from views.config import bp as config_bp  # noqa: E402



# 编辑者（editor）只能填知识库与黑话；其余页面/接口仅管理员可用。
EDITOR_ALLOWED_PREFIXES = ('/kb', '/slang')
EDITOR_ALLOWED_EXACT = {'/', '/logout', '/healthz', '/login', '/captcha'}


def _editor_allowed(path: str) -> bool:
    if path in EDITOR_ALLOWED_EXACT:
        return True
    if path.startswith('/static/'):
        return True
    return any(path == p or path.startswith(p + '/') for p in EDITOR_ALLOWED_PREFIXES)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.jwt_secret,
        JSON_AS_ASCII=False,
        SESSION_COOKIE_HTTPONLY=True,
    )
    setup_logging()

    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(internal_usage_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(periods_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(slang_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(presets_bp)
    app.register_blueprint(tokens_bp)
    app.register_blueprint(stickers_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(config_bp)

    @app.errorhandler(404)
    def not_found(_exc):
        return render_template("error.html", message="页面不存在"), 404

    @app.errorhandler(500)
    def server_error(exc):
        app.logger.exception("unhandled error: %s", exc)
        return render_template("error.html", message="服务器内部错误，请查看日志"), 500

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})


    @app.before_request
    def _enforce_editor_scope():
        from flask import g, request, redirect, url_for, flash
        from views.auth import current_claims
    
        claims = current_claims()
        if not claims:
            return None
        if claims.get('role') == 'admin':
            return None
        path = request.path
        if _editor_allowed(path):
            return None
        if request.method == 'GET':
            flash('该页面仅管理员可用', 'error')
            return redirect(url_for('dashboard.index'))
        return ('仅管理员可执行该操作', 403)
    return app


app = create_app()

if __name__ == "__main__":
    print(f"qq-bridge 控制台启动：http://127.0.0.1:{settings.port}/  （bridge={settings.bridge_url}）")
    app.run(host=settings.bind, port=settings.port, threaded=True, debug=settings.debug, use_reloader=False)
