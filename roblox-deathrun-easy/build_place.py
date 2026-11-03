#!/usr/bin/env python3
"""Assemble les scripts de src/ dans un fichier DeathrunEasy.rbxlx à ouvrir dans Roblox Studio.

    python3 build_place.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "DeathrunEasy.rbxlx"

_ref = 0


def ref():
    global _ref
    _ref += 1
    return f"RBX{_ref:08X}"


def name_prop(name):
    return f'<string name="Name">{name}</string>'


def script(cls, name, path):
    source = path.read_text(encoding="utf-8")
    if "]]>" in source:
        raise ValueError(f"{path} contient ']]>' (interdit dans un CDATA)")
    return (
        f'<Item class="{cls}" referent="{ref()}"><Properties>{name_prop(name)}'
        f'<ProtectedString name="Source"><![CDATA[{source}]]></ProtectedString>'
        f"</Properties></Item>"
    )


def item(cls, name, children="", extra=""):
    return f'<Item class="{cls}" referent="{ref()}"><Properties>{name_prop(name)}{extra}</Properties>{children}</Item>'


def scripts_in(folder):
    """Même convention que Rojo : .server.luau = Script, .client.luau = LocalScript, sinon ModuleScript."""
    out = []
    for path in sorted(folder.glob("*.luau")):
        if path.name.endswith(".server.luau"):
            out.append(script("Script", path.name[: -len(".server.luau")], path))
        elif path.name.endswith(".client.luau"):
            out.append(script("LocalScript", path.name[: -len(".client.luau")], path))
        else:
            out.append(script("ModuleScript", path.stem, path))
    return "".join(out)


def main():
    body = "".join(
        [
            item("ReplicatedStorage", "ReplicatedStorage", item("Folder", "DeathrunShared", scripts_in(SRC / "shared"))),
            item("ServerScriptService", "ServerScriptService", item("Folder", "DeathrunServer", scripts_in(SRC / "server"))),
            item(
                "StarterPlayer",
                "StarterPlayer",
                item("StarterPlayerScripts", "StarterPlayerScripts", item("Folder", "DeathrunClient", scripts_in(SRC / "client"))),
            ),
            item(
                "Lighting",
                "Lighting",
                extra='<float name="ClockTime">14.5</float><Color3 name="Ambient"><R>0.35</R><G>0.35</G><B>0.4</B></Color3>',
            ),
        ]
    )
    xml = (
        '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
        f"{body}</roblox>\n"
    )
    OUT.write_text(xml, encoding="utf-8")
    print(f"OK -> {OUT.name}")


if __name__ == "__main__":
    main()
