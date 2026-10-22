"""config_edit（定向 TOML 改写）单测，不需要起服务。

cd web && .venv\\Scripts\\python selftest_toml.py
"""

from __future__ import annotations

import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_edit  # noqa: E402

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} {detail}")


SAMPLE = """# 顶部注释，必须保留
ownerQQ = 123

[socialV2.tools]
kbSearch = true
sendPoke = true

[socialV2]
# 段内注释
replyProbability = 0.05
"""


def main() -> int:
    print("config_edit 单测：")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        path.write_text(SAMPLE, encoding="utf-8")

        changed = config_edit.set_values({"socialV2.tools.kbSearch": False}, path)
        text = path.read_text(encoding="utf-8")
        check("改已有键", changed.get("socialV2.tools.kbSearch") is True and "kbSearch = false" in text)
        check("保留顶部注释", "# 顶部注释，必须保留" in text)
        check("保留段内注释", "# 段内注释" in text)
        check("其它键不变", "sendPoke = true" in text and "ownerQQ = 123" in text)
        check("写后仍是合法 TOML", tomllib.loads(text)["socialV2"]["tools"]["kbSearch"] is False)

        config_edit.set_values({"socialV2.tools.newFlag": True}, path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        check("新增键落到对应表", data["socialV2"]["tools"]["newFlag"] is True)

        config_edit.set_values({"dsh.model": "deepseek-flash"}, path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        check("缺失表自动创建", data["dsh"]["model"] == "deepseek-flash")

        config_edit.set_values({"socialV2.tools.keywords": ["a", "b"]}, path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        check("写入字符串数组", data["socialV2"]["tools"]["keywords"] == ["a", "b"])

        config_edit.set_periods([
            {"name": "峰", "start": "08:30", "end": "00:30", "replyProbability": 0.3, "reasoningEffort": "high", "proactive": False},
            {"name": "谷", "start": "00:30", "end": "08:30", "replyProbability": 0.9, "days": ["mon", "tue"]}
        ], path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        check("写入峰谷时段", [p["name"] for p in data["periods"]] == ["峰", "谷"])
        check("时段字段完整", data["periods"][0]["proactive"] is False and data["periods"][1]["days"] == ["mon", "tue"])
        check("写时段不动其它配置", data["ownerQQ"] == 123 and data["socialV2"]["tools"]["kbSearch"] is False)

        config_edit.set_periods([], path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        check("清空时段", "periods" not in data)

        path.write_text("broken = [\n", encoding="utf-8")
        try:
            config_edit.set_values({"a.b": 1}, path)
            check("坏文件拒绝写入", False)
        except config_edit.ConfigEditError:
            check("坏文件拒绝写入", True)
            check("坏文件不被改写", path.read_text(encoding="utf-8") == "broken = [\n")

    print(f"\n通过 {passed} 项，失败 {failed} 项。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
