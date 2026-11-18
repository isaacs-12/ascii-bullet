"""Game launchers, scores, stats and achievements."""

from __future__ import annotations

from src.core.achievements import load_achievements
from src.shell.registry import command
from src.shell.text import Styled


# Static imports (inside functions to keep startup fast) so PyInstaller can find them.
def _galaga():
    from src.states.games.galaga_gameplay import GalagaGameplayState

    return GalagaGameplayState


def _minesweeper():
    from src.states.games.minesweeper import MinesweeperState

    return MinesweeperState


def _set_game():
    from src.states.games.set_game import SetGameState

    return SetGameState


def _oregon():
    from src.states.games.oregon_trail import OregonTrailState

    return OregonTrailState


# name typed after `start` -> (unlock key, achievement id, state class loader)
_EXTRA_GAMES = {
    "spacebullets": ("virus", "arcade_master", _galaga),
    "minesweeper": ("minesweeper", "minesweeper", _minesweeper),
    "set": ("set", "set_player", _set_game),
    "oregon": ("oregon_trail", "oregon_trail", _oregon),
    "oregon_trail": ("oregon_trail", "oregon_trail", _oregon),
}


def _launch_bullet_hell(ctx, start_wave: int = 1, demo: bool = False):
    from src.states.games.gameplay import GameplayState

    practice = ctx.shell.practice_mode
    ctx.launch(lambda game, back: GameplayState(game, back, start_wave=start_wave, practice=practice, demo=demo))


@command("start")
def start(ctx):
    if not ctx.args or ctx.args[0] in ("game", "bullethell", "bullet-hell"):
        if ctx.shell.practice_mode:
            ctx.out(Styled.plain("godmode is ON: you can't die, and scores won't be saved.", "warn"))
        _launch_bullet_hell(ctx)
        return 0
    name = ctx.args[0].lower()
    if name in ("demo", "--demo", "attract"):
        ctx.out(Styled.plain("Demo mode: the autopilot plays. Press any key to stop.", "dim"))
        _launch_bullet_hell(ctx, demo=True)
        return 0
    entry = _EXTRA_GAMES.get(name)
    unlocked = False
    if entry:
        key = entry[0]
        unlocked = ctx.save.is_virus_killed() if key == "virus" else ctx.save.is_game_unlocked(key)
    if not entry or not unlocked:
        ctx.err(f"start: '{name}': no such game (yet)")
        return 1
    state_cls = entry[2]()
    ctx.achieve(entry[1])
    ctx.launch(lambda game, back: state_cls(game, back))
    return 0


@command("continue")
def continue_cmd(ctx):
    wave = ctx.save.get_checkpoint_wave()
    if wave <= 1:
        ctx.out("No checkpoint yet. Beat a boss to save one. Starting from wave 1...")
        wave = 1
    else:
        ctx.out(Styled.plain(f"Resuming from checkpoint: wave {wave}", "accent"))
    _launch_bullet_hell(ctx, start_wave=wave)


@command("godmode")
def godmode(ctx):
    shell = ctx.shell
    shell.practice_mode = not shell.practice_mode
    if shell.practice_mode:
        ctx.out(Styled.plain("godmode ON. Invincible. Scores are not recorded. QA approved.", "warn"))
    else:
        ctx.out("godmode OFF. Back to mortal.")


@command("highscores")
def highscores(ctx):
    scores = ctx.save.get_high_scores(10)
    if not scores:
        ctx.out("No high scores yet. Type 'start' to play!")
        return 0
    ctx.out(Styled.plain("  #     SCORE   WAVE   TIME   DATE", "title"))
    for i, e in enumerate(scores, 1):
        color = "warn" if i == 1 else None
        ctx.out(Styled.plain(f"{i:>3}  {e['score']:>8,}   {e.get('wave', 0):>4}  {e['time'] // 1000:>4}s   "
                             f"{e['date'][:10]}", color))


def _fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")


@command("stats")
def stats(ctx):
    save = ctx.save
    st = save.get_all_stats()
    data = save.data
    found, total = ctx.shell.achievements.summary()
    explore = save.get_exploration_stats()

    def section(title: str, rows: list[tuple[str, object]]) -> None:
        rows = [(k, v) for k, v in rows if v not in (0, None, "0s")]
        if not rows:
            return
        ctx.out(Styled.plain(title, "title"))
        for k, v in rows:
            ctx.out(Styled(("  " + k.ljust(22), "dim"), (str(v), None)))
        ctx.out("")

    section("Overall", [("Total playtime", _fmt_time(st.get("total_playtime_seconds", 0))),
                        ("Achievements", f"{found}/{total}")])
    section("Bullet Hell", [
        ("Runs", data.get("total_games_played", 0)),
        ("Best score", f"{save.get_best_score():,}" if save.get_best_score() else 0),
        ("Best wave", st.get("best_wave", 0)),
        ("Checkpoint", save.get_checkpoint_wave() if save.get_checkpoint_wave() > 1 else 0),
        ("Bullets grazed", st.get("grazes", 0)),
        ("Bombs used", st.get("bombs_used", 0)),
        ("Bosses outlasted", st.get("bosses_defeated", 0)),
        ("Enemies depleted", st.get("enemies_depleted", 0)),
        ("Time survived", _fmt_time(data.get("total_time_survived", 0) / 1000)),
    ])
    sg = st.get("set_games_played", 0)
    section("Set", [("Games", sg), ("Won", st.get("set_games_won", 0)),
                    ("Sets found", st.get("total_sets_found", 0)), ("Best", st.get("best_set_score", 0))])
    section("Playtime by game", [
        ("Bullet Hell", _fmt_time(st.get("bullet_hell_playtime_seconds", 0))),
        ("Set", _fmt_time(st.get("set_game_playtime_seconds", 0))),
        ("Oregon Trail", _fmt_time(st.get("oregon_trail_playtime_seconds", 0))),
    ])
    section("Exploration", [("Directories visited", explore["dirs_visited"]),
                            ("Files read", explore["files_read"]),
                            ("AI prompts", st.get("ai_prompts", 0))])


@command("achievements")
def achievements(ctx):
    show_all = "--all" in ctx.args or "-a" in ctx.args
    tracker = ctx.shell.achievements
    found, total = tracker.summary()
    ctx.out(Styled.plain(f"ACHIEVEMENTS  {found}/{total}", "title"))
    bar_w = 30
    filled = int(bar_w * found / max(1, total))
    ctx.out(Styled(("  [", "dim"), ("#" * filled, "warn"), ("." * (bar_w - filled), "dim"), ("]", "dim")))
    ctx.out("")
    hidden_left = 0
    for a in load_achievements():
        unlocked = tracker.is_unlocked(a["id"])
        if unlocked:
            ctx.out(Styled(("  [x] ", "warn"), (a["name"].ljust(30), "accent"), (a["description"], None)))
        elif a.get("hidden") and not show_all:
            hidden_left += 1
        else:
            desc = a["description"] if not a.get("hidden") else "???"
            ctx.out(Styled(("  [ ] ", "dim"), (a["name"].ljust(30), "dim"), (desc, "dim")))
    if hidden_left:
        ctx.out("", Styled.plain(f"  + {hidden_left} hidden achievements. Poke around.", "dim"))
