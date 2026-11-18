# Content files (spoilers)

Everything a player reads is JSON in `src/data/`. Behaviour stays in Python; these files are meant to be
reusable by another front-end (e.g. a TypeScript port).

| File | What | Shape |
| --- | --- | --- |
| `filesystem.json` | Default VFS tree | `{dirs: {name: {owner?, permissions?, dirs?, files?: {name: {content: [lines], permissions, owner?}}}}}` |
| `commands.json` | Help/`which`/completion metadata | `{_categories: {...}, name: {category, usage, summary, aliases?, hidden?, path, completion?}}` |
| `man_pages.json` | Manual pages | `{topic: [lines]}`; first line is the `NAME(n)` header |
| `achievements.json` | Achievements | `[{id, name, description, hidden, on_command?: [cmd], on_read?: [abs path]}]` |
| `easter_eggs.json` | Static joke commands and exact-match phrases | `{commands: {name: {output, achievement?, color?, typed?}}, phrases: {...}}` |
| `ai_clis.json` | Parody AI personas | `personas.{key}: banner, prompt, spinner, slash, rules[{match, reply}], fallback`; shared `common_rules`, `hints[{when, text}]`, `jokes` |
| `waves.json` | Bullet hell tuning, bullets, enemies, waves, bosses | see below |
| `themes.json` | Colour themes | `{name: {colour key: [r, g, b]}}` |
| `dialogue.json` | Boot log, intro pages, title art | |
| `art.json` | Block font, cows, train, logo | |

`waves.json`: world units are isotropic (x = one cell width; the renderer divides y by the cell aspect).
Patterns: `aimed`, `ring`, `spiral`, `flower` (curving ring), `drop`, `rain`, `random`, `wall`; times in ms.
Bullet modifiers: `curve` (deg/s), `accel`, `stop_after`, `aim_after` + `aim_speed`, `telegraph`.
AI reply templates can use `{topic} {file} {n} {n2} {prompt} {completion} {hint} {joke} {time} {greeting}`.

## Hidden commands

`claude`, `gemini`, `codex`, `copilot`, `ollama` (and `ai` to list them), `godmode`, `start demo`, `sl`,
`cmatrix`, `neofetch`, `rot13`, `su`, `nano`, `hello`, `hack`, `matrix`, `konami`, `xyzzy`, `please`, `42`,
`coffee`, `skynet`, `lol`, `make`.
Phrases: `sudo make me a sandwich`, `hack the planet`, `:(){ :|:& };:`, `:q` / `:wq` / `:q!` / `:x`,
`touch grass`, `rm -rf /`, `i am root`. Keyboard: the Konami code.

## Secrets

| Where | What |
| --- | --- |
| `/home/pilot/.bash_history` | Wally typed his password at the prompt: `WallySmith` (sudo) |
| `/var/mail/pilot` | Same hint, ROT13-"encrypted" (`mail \| rot13`) |
| `~/blthll/data/secret/.transmission` | Base64; decodes to the `godmode` cheat |
| `/home/wally/diary.txt`, `.plan` | Lore + virus hint; needs sudo |
| `/etc/shadow` | Needs sudo; Wally's "hash" |
| `/var/log/auth.log`, `/etc/passwd`, `/opt/walnut/ai/` | AI Division lore |
| `/proc/*`, `/usr/share/games/fortunes` | Flavour; `fortune` reads the latter |

Puzzles: kill the CPU-hogging process (`top`) for Spacebullets; delete the two "mine" nodes in
`games/minesweeper` for Minesweeper; make the three card files' permissions a "set" for Set; install
`systemctl` from `/usr/local/deprecated` and add a `cooler.service.d/override.conf` with
`Conflicts=laser.service` for Oregon Trail.
