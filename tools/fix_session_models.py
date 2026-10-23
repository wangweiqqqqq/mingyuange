# -*- coding: utf-8 -*-
"""修复会话缓存里不支持的模型/思考档位组合。

规则（依据 list_models 实测）：
- raccoon/sn-sensenova-6-8-flash、raccoon/sn-deepseek-v4-1-flash-1017：支持 on/off，默认 on
- buddy/*、lobsterai/*、trae/*、qodercn/*、loomy/*、codearts/*、our-free-model/*：清单里没有思考档位 → 不接受 reasoningEffort
故：凡 provider 是 buddy/lobsterai，统一改成
    raccoon/sn-deepseek-v4-1-flash-1017 + reasoningEffort=on（免费且实测可用）。
"""
import json
import pathlib

DIR = pathlib.Path(r"C:\Users\ZhuanZ1\.dsh\storages\session_projcache\sessions")

SUPPORTED = {  # model -> allowed effort values
    "raccoon/sn-sensenova-6-8-flash": {"on", "off"},
    "raccoon/sn-deepseek-v4-1-flash-1017": {"on", "off"},
    "raccoon/sn-sensenova-6-8-flash-lite": {"on", "off"},
}
FALLBACK = {"provider": "raccoon", "model": "sn-deepseek-v4-1-flash-1017", "reasoningEffort": "on"}
BAD_PROVIDERS = {"buddy", "lobsterai"}
changed = []


def fix(node, path):
    if isinstance(node, dict):
        prov = node.get("provider")
        model = node.get("model")
        if isinstance(prov, str) and isinstance(model, str):
            key = f"{prov}/{model}"
            if prov in BAD_PROVIDERS:
                old = key
                node.clear()
                node.update(FALLBACK)
                changed.append(f"{path}: {old} -> {FALLBACK['provider']}/{FALLBACK['model']}")
            elif "reasoningEffort" in node:
                allowed = SUPPORTED.get(key)
                if allowed and node["reasoningEffort"] not in allowed:
                    node["reasoningEffort"] = "on"
                    changed.append(f"{path}: {key} effort -> on")
                elif allowed is None:
                    node.pop("reasoningEffort", None)
                    changed.append(f"{path}: {key} dropped unsupported effort")
        for k, v in list(node.items()):
            fix(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            fix(v, f"{path}[{i}]")


for f in sorted(DIR.glob("*.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP {f.name}: {exc}")
        continue
    fix(data, f.name)
    f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print("\n".join(changed) if changed else "NOTHING CHANGED")
