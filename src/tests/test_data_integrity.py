"""Content lives in src/data/*.json; make sure it stays consistent with the code."""

import json
import re
from pathlib import Path

from src.core.achievements import achievement_index
from src.shell.registry import build_registry, load_json, registered_handlers
from src.unix.filesystem import VirtualFileSystem

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def test_every_json_file_parses():
    for path in DATA.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_commands_metadata_matches_handlers():
    build_registry()
    handlers = set(registered_handlers())
    meta = {k for k in load_json("commands.json") if not k.startswith("_")}
    eggs = set(load_json("easter_eggs.json")["commands"])
    assert meta - handlers == set(), "metadata without a handler"
    assert handlers - meta - eggs == set(), "handler without metadata"


def test_aliases_do_not_shadow_commands():
    meta = {k: v for k, v in load_json("commands.json").items() if not k.startswith("_")}
    names = set(meta)
    for name, info in meta.items():
        for alias in info.get("aliases", []):
            assert alias not in names, f"{name}: alias {alias} shadows a command"


def test_every_achievement_id_used_in_code_exists():
    ids = set(achievement_index())
    pattern = re.compile(r"""(?:achieve|unlock|_achieve)\(\s*["']([a-z0-9_]+)["']""")
    used = set()
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        used |= set(pattern.findall(path.read_text(encoding="utf-8")))
    for path in DATA.glob("*.json"):
        used |= set(re.findall(r'"achievement":\s*"([a-z0-9_]+)"', path.read_text(encoding="utf-8")))
    assert used - ids == set()


def test_achievement_ids_are_unique_and_described():
    data = load_json("achievements.json")
    ids = [a["id"] for a in data]
    assert len(ids) == len(set(ids))
    assert all(a["name"] and a["description"] for a in data)


def test_on_read_achievements_point_at_real_files():
    fs = VirtualFileSystem()
    fs.set_user("root")
    for a in load_json("achievements.json"):
        for path in a.get("on_read", []):
            assert fs.file_exists(path), path


def test_filesystem_secrets_present():
    fs = VirtualFileSystem()
    for path in ["/home/pilot/.bash_history", "/home/wally/diary.txt", "/etc/shadow", "/var/mail/pilot",
                 "/usr/share/games/fortunes", "/opt/walnut/ai/README.md",
                 "/home/pilot/blthll/data/secret/.transmission"]:
        assert fs.file_exists(path), path
    assert fs.get_file_owner("/home/wally/diary.txt") == "wally"
    assert fs.read_file("/home/wally/diary.txt")[0] is False  # needs sudo
    assert "WallySmith" in fs.read_file("/home/pilot/.bash_history")[1]


def test_man_pages_have_headers():
    for topic, page in load_json("man_pages.json").items():
        assert page and re.match(r"^[A-Z0-9-]+\(\d\)$", page[0]), topic


def test_ai_personas_are_parodies_with_disclaimers():
    data = load_json("ai_clis.json")
    turing = next(r for r in data["common_rules"] if r.get("achievement") == "turing_test")
    assert any("parody" in line for line in turing["reply"])
    for key, persona in data["personas"].items():
        assert persona["display"].lower() != key, "display names must be parody names"
        assert persona["fallback"], key


def test_wave_content_references_resolve():
    data = load_json("waves.json")
    known_patterns = {"aimed", "ring", "spiral", "flower", "drop", "rain", "random", "wall"}
    for name, enemy in data["enemies"].items():
        for p in enemy["patterns"]:
            assert p["type"] in known_patterns, name
            assert p.get("bullet", "small") in data["bullets"], name
    for wave in data["waves"]:
        if "boss" in wave:
            assert wave["boss"] in data["bosses"]
        else:
            assert all(s["enemy"] in data["enemies"] for s in wave["spawns"])
    for name, boss in data["bosses"].items():
        for phase in boss["phases"]:
            assert phase["duration"] > 0
            for p in phase["patterns"]:
                assert p["type"] in known_patterns, (name, phase["name"])
