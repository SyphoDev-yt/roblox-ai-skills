# roblox-vfx local settings (copy to LOCAL.md and fill in)

- ROBLOX_VFX_LIB (a folder path; also settable as an environment variable of the same name): your VFX library folder. It holds `harvested/`, `recipes/`, `compositions/`, `index.json` and `.cache/`. Pick a folder OUTSIDE this skill folder, ideally not inside a cloud-synced folder. Every script reads it when `--lib` is not given. Value:
- Studio bridge: which MCP server runs `execute_luau` and `capture_screenshot` for you (Roblox's built-in Studio MCP, or the third-party `robloxstudio-mcp`). Value:
- Sink port: the localhost port `recipe_server.py` listens on (default 48752; change it only if it clashes). Value:
- Studio window: you need Studio maximised and in the foreground for screenshots (see trap 5). Nothing to fill in.
- Blender: full path to `blender.exe` (or just `blender` if it is on PATH). The mesh generators in `sim/mesh/` run it headless. On Windows it is usually under `C:/Program Files/Blender Foundation/Blender <version>/`. Value:
- Lune folder: a folder whose `aftman.toml` or `rokit.toml` lists Lune, so `lune run sim/tools/lune/*.luau` works from there (the pre-Studio compile and build checks). Value:
- VFX research folder: where your reference downloads, frame strips and corpus batches go (heavy files, never inside the skill). Pick a folder OUTSIDE this skill folder. Value:
- Open Cloud key: only the NAME of the environment variable that holds your Roblox Open Cloud API key, if you upload meshes and textures with a script. Never write the key itself here. Value:
- Texture library and meshes: built once by the "First run" commands in SKILL.md. Write "built" here when done. Value:
