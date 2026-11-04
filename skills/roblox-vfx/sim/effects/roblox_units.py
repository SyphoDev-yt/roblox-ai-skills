"""Convert an authored effect definition to Roblox's real units before it is
written. Measured in Studio, 2026-10-27 (studio-test calibration P1): a
ParticleEmitter with Size 4 draws a particle 8 studs wide, so Roblox's Size is
HALF the drawn width. Builders author the width they want to SEE; this halves
every emitter Size (value and envelope, including timeline tweens/sets of an
emitter's Size) once, and marks the definition so it is never halved twice.
The sim draws particles at 2 x Size, like Roblox.
"""


def _halve_ns(v):
    if isinstance(v, (int, float)):
        return v * 0.5
    if isinstance(v, dict) and "NumberSequence" in v:
        return {"NumberSequence": [[k[0], k[1] * 0.5] + ([k[2] * 0.5] if len(k) > 2 else []) for k in v["NumberSequence"]]}
    return v


def to_roblox_units(d):
    if d.get("sizeConvention") == "roblox":
        return d
    emitters = set()

    def walk(items, prefix):
        for it in items:
            path = f"{prefix}.{it['name']}" if prefix else it["name"]
            if it.get("class") == "ParticleEmitter":
                emitters.add(path)
                props = it.setdefault("props", {})
                if "Size" in props:
                    props["Size"] = _halve_ns(props["Size"])
            walk(it.get("children", []), path)

    walk(d.get("instances", []), "")
    for e in d.get("timeline", []):
        if e.get("prop") == "Size" and e.get("target") in emitters:
            for k in ("value", "to", "from"):
                if k in e:
                    e[k] = _halve_ns(e[k])
    d["sizeConvention"] = "roblox"
    return d
