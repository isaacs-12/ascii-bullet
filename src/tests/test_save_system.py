import json

from src.core.save_system import SAVE_VERSION, SaveSystem


def test_fresh_save_and_atomic_write(tmp_path):
    s = SaveSystem(tmp_path)
    assert s.save()
    data = json.loads((tmp_path / "save.json").read_text())
    assert data["version"] == SAVE_VERSION
    assert not list(tmp_path.glob(".save-*.tmp"))


def test_old_saves_are_merged_with_new_defaults(tmp_path):
    (tmp_path / "save.json").write_text(json.dumps({
        "version": "0.1.0", "high_scores": [{"score": 5, "time": 1000, "date": "2026-01-01"}],
        "stats": {"grazes": 7}, "secret_commands_found": ["konami"],
    }))
    s = SaveSystem(tmp_path)
    assert s.get_best_score() == 5
    assert s.get_stat("grazes") == 7
    assert s.get_stat("bosses_defeated") == 0  # new key filled from defaults
    assert s.has_secret("konami")
    assert s.get_checkpoint_wave() == 0


def test_corrupt_save_is_quarantined(tmp_path):
    (tmp_path / "save.json").write_text("{not json")
    s = SaveSystem(tmp_path)
    assert s.data["high_scores"] == []
    assert (tmp_path / "save.corrupt.json").exists()


def test_per_game_playtime_does_not_double_count_total(tmp_path):
    s = SaveSystem(tmp_path)
    s.add_playtime(10, "total")
    s.add_playtime(5, "bullet_hell")
    assert s.get_stat("total_playtime_seconds") == 10
    assert s.get_stat("bullet_hell_playtime_seconds") == 5


def test_high_scores_sorted_and_capped(tmp_path):
    s = SaveSystem(tmp_path)
    for score in range(15):
        s.add_score(score * 10, 1000, wave=score)
    scores = [e["score"] for e in s.get_high_scores()]
    assert scores == sorted(scores, reverse=True) and len(scores) == 10
    assert s.is_high_score(1000) and not s.is_high_score(0)


def test_checkpoint_only_moves_forward(tmp_path):
    s = SaveSystem(tmp_path)
    s.set_checkpoint_wave(6)
    s.set_checkpoint_wave(3)
    assert s.get_checkpoint_wave() == 6
    s.reset_stats()
    assert s.get_checkpoint_wave() == 0


def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCII_BULLET_SAVE_DIR", str(tmp_path / "x"))
    s = SaveSystem()
    assert s.save_file == tmp_path / "x" / "save.json"
