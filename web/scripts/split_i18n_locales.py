"""Split monolithic locale TS files into page-group modules.

Usage (from web/):
  python scripts/split_i18n_locales.py
"""

from __future__ import annotations

from pathlib import Path

GROUPS: dict[str, tuple[str, ...]] = {
    "common": ("app", "locale", "theme", "nav", "common", "error", "action", "card"),
    "guide": ("guide", "firstRun", "metricHint"),
    "experiment": (
        "experiment",
        "control",
        "compare",
        "stage",
        "config",
        "gamesTab",
        "playersTab",
    ),
    "game": ("game", "filter", "explain"),
    "analyze": ("puzzle", "decision", "trace", "data", "training", "prompt"),
    "settings": ("settings", "preflight"),
}


def _find_object_body(src: str) -> str:
    """Return the interior of the top-level messages object literal."""
    markers = ("export default {", "const en: typeof zhCN = {")
    start = -1
    marker_len = 0
    for marker in markers:
        idx = src.find(marker)
        if idx >= 0:
            start = idx
            marker_len = len(marker)
            break
    if start < 0:
        raise ValueError("could not find messages object literal")
    return src[start + marker_len :]


def _extract_top_level_blocks(src: str) -> dict[str, str]:
    """Return top-level `key: { ... }` blocks from the messages object."""
    body = _find_object_body(src)
    depth = 1
    i = 0
    blocks: dict[str, str] = {}
    while i < len(body) and depth >= 1:
        ch = body[i]
        if ch == "{":
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            continue
        if ch in " \t\r\n,":
            i += 1
            continue
        # read identifier
        j = i
        while j < len(body) and (body[j].isalnum() or body[j] in "_$"):
            j += 1
        key = body[i:j]
        k = j
        while k < len(body) and body[k] in " \t\r\n":
            k += 1
        if k >= len(body) or body[k] != ":":
            raise ValueError(f"expected ':' after key {key!r} at {i}")
        k += 1
        while k < len(body) and body[k] in " \t\r\n":
            k += 1
        if k >= len(body) or body[k] != "{":
            raise ValueError(f"expected object for key {key!r}")
        obj_start = k
        d = 0
        p = k
        in_str: str | None = None
        escape = False
        while p < len(body):
            c = body[p]
            if in_str:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == in_str:
                    in_str = None
                p += 1
                continue
            if c in ("'", '"', "`"):
                in_str = c
                p += 1
                continue
            if c == "{":
                d += 1
            elif c == "}":
                d -= 1
                if d == 0:
                    p += 1
                    break
            p += 1
        blocks[key] = body[obj_start:p]
        i = p
    return blocks


def _write_locale(locale_dir: Path, blocks: dict[str, str]) -> None:
    locale_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for group, keys in GROUPS.items():
        parts: list[str] = []
        for key in keys:
            if key not in blocks:
                raise KeyError(f"missing key {key!r} for group {group}")
            parts.append(f"  {key}: {blocks[key]},")
            used.add(key)
        content = "export default {\n" + "\n".join(parts) + "\n}\n"
        (locale_dir / f"{group}.ts").write_text(content, encoding="utf-8")
    missing = set(blocks) - used
    if missing:
        raise SystemExit(f"unassigned keys: {sorted(missing)}")

    imports = "\n".join(f"import {g} from './{g}'" for g in GROUPS)
    spreads = ",\n".join(f"  ...{g}" for g in GROUPS)
    index = f"{imports}\n\nexport default {{\n{spreads},\n}}\n"
    (locale_dir / "index.ts").write_text(index, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "i18n" / "locales"
    for locale in ("zh-CN", "en"):
        src_path = root / f"{locale}.ts"
        text = src_path.read_text(encoding="utf-8")
        if "export { default } from" in text and (root / locale / "index.ts").exists():
            print(f"skip {locale}: already split")
            continue
        blocks = _extract_top_level_blocks(text)
        out_dir = root / locale
        _write_locale(out_dir, blocks)
        if locale == "en":
            src_path.write_text(
                "import type zhCN from './zh-CN'\n"
                "import messages from './en/index'\n\n"
                "const en: typeof zhCN = messages\n"
                "export default en\n",
                encoding="utf-8",
            )
        else:
            src_path.write_text(
                f"export {{ default }} from './{locale}/index'\n",
                encoding="utf-8",
            )
        print(f"split {locale}: {len(blocks)} keys -> {out_dir}")


if __name__ == "__main__":
    main()
