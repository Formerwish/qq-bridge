"""config.toml 的**定向文本改写**（保留注释与顺序）。

为什么不直接 `tomllib.load` → 序列化写回：
  TOML 标准库没有 writer，第三方 writer 必然丢注释。用户手写的注释、空行、
  表格顺序都是配置的一部分（可读性）。所以这里只替换目标 `key = value` 行，
  其余字节原样保留；写前用 tomllib 校验整份文件，校验失败绝不落盘。

局限（够用即可）：
  - 只支持"表 + 标量/数组"的键值行，不支持改 `[[periods]]` 这类数组表（P4 单独实现）。
  - 键必须唯一出现在其表内；重复键本身也是非法 TOML，校验会拦住。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

CONFIG_TOML = Path(__file__).resolve().parent.parent / "config.toml"


class ConfigEditError(RuntimeError):
    pass


def load(path: Path = CONFIG_TOML) -> dict:
    if not path.exists():
        raise ConfigEditError(f"配置文件不存在：{path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def get_path(dotted: str, path: Path = CONFIG_TOML, default=None):
    node = load(path)
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {_literal(v)}" for k, v in value.items()) + " }"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    raise ConfigEditError(f"不支持写入的类型：{type(value).__name__}")


def _table_span(lines: list[str], table: str) -> tuple[int, int] | None:
    """返回 (header_index, block_end_index)；block_end 是下一个表头或文件尾。"""
    header = f"[{table}]"
    start = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == header:
            start = idx
            break
    if start is None:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = idx
            break
    return start, end


def set_values(items: dict[str, object], path: Path = CONFIG_TOML) -> dict:
    """按 {"表.键": 值} 批量改写；全部成功才写盘。返回 {写入的键: 旧值}。"""
    if not items:
        return {}
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed: dict[str, object] = {}

    for dotted, value in items.items():
        if "." not in dotted:
            raise ConfigEditError(f"键必须写成 表.键 形式：{dotted}")
        table, key = dotted.rsplit(".", 1)
        literal = _literal(value)
        span = _table_span(lines, table)
        if span is None:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"\n[{table}]\n{key} = {literal}\n")
            changed[dotted] = None
            continue

        start, end = span
        pattern = re.compile(rf"^(\s*){re.escape(key)}\s*=\s*(.*?)(\r?\n)?$")
        replaced = False
        for idx in range(start + 1, end):
            match = pattern.match(lines[idx])
            if not match:
                continue
            changed[dotted] = _peek_value(lines[idx], key)
            lines[idx] = f"{match.group(1)}{key} = {literal}{match.group(3) or ''}"
            replaced = True
            break
        if not replaced:
            insert_at = start + 1
            # 插到该表最后一个非空行之后，保持整块紧凑
            for idx in range(start + 1, end):
                if lines[idx].strip():
                    insert_at = idx + 1
            if not lines[insert_at - 1].endswith("\n"):
                lines[insert_at - 1] += "\n"
            lines.insert(insert_at, f"{key} = {literal}\n")
            changed[dotted] = None

    candidate = "".join(lines)
    try:
        tomllib.loads(candidate)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigEditError(f"改写后 TOML 校验失败，已取消写入：{exc}") from exc

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(candidate, encoding="utf-8")
    tmp.replace(path)
    return changed


def _peek_value(line: str, key: str):
    """尽量取旧值（用于日志）；解析失败返回 None。"""
    match = re.match(rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*$", line)
    if not match:
        return None
    raw = match.group(1)
    try:
        return tomllib.loads(f"v = {raw}")["v"]
    except Exception:
        return None

def set_periods(periods: list[dict], path: Path = CONFIG_TOML) -> None:
    """整体替换 `[[periods]]` 数组表（峰谷策略）。

    只重建 periods 块，其余内容（注释、其它表）原样保留；写前 tomllib 校验。
    每个 period 是 dict，键：name/start/end/days/replyProbability/reasoningEffort/
    model/proactive/sendMaxPerMinute/sendMaxPerHour；值为 None 的键跳过。
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[[periods]]":
            skipping = True
            continue
        if skipping and stripped.startswith("["):
            skipping = False
        if skipping:
            continue
        out.append(line)

    base = "".join(out).rstrip("\n")
    blocks = []
    for period in periods:
        body = ["[[periods]]"]
        for key, value in period.items():
            if value is None:
                continue
            body.append(f"{key} = {_literal(value)}")
        blocks.append("\n".join(body))

    candidate = base + ("\n\n" + "\n\n".join(blocks) + "\n" if blocks else "\n")
    try:
        tomllib.loads(candidate)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigEditError(f"时段配置校验失败，已取消写入：{exc}") from exc

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(candidate, encoding="utf-8")
    tmp.replace(path)