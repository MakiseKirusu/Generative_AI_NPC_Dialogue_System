# Maple Hollow

A small village of AI characters (school project: Generative AI NPC Dialogue System). The design is in [DESIGN.md](DESIGN.md).

## Run it

1. Install Python 3.10 or newer (on Windows: tick "Add python.exe to PATH" in the installer).
2. In this folder: `pip install -r requirements.txt` (on Windows: `py -m pip install -r requirements.txt`)
3. Get a free Gemini API key at <https://aistudio.google.com/apikey>. Copy `.env.example` to `.env` and paste the key into it.
4. `python start.py` (on Windows: `py start.py`, or double-click `start.bat`) and choose:
   - **1 Terminal demo**: text only, in the terminal window.
   - **2 Full game**: a village you walk around in. It opens in your web browser; keep the terminal window open while you play.

Both use the same characters, the same rules and the same saved game, so you can switch between them.

You can also start one directly: `python play.py` or `python run_game.py` (add `--new` to start over).

Without a key the game still runs: the characters answer with their ready-made fallback lines.

### The full game

Arrow keys or WASD walk · `E` talks to the character next to you · `F` searches where you stand · `Esc` leaves a conversation.

The panel on the right shows what the game knows: the **Next** step, gold, bag, quests, and the mood of the character
you are talking to. On the map, a gold ring or arrow marks the next step, `!` over a character means they have a task
for you and `?` that you carry what their task asks for; a place's danger shows next to its name once someone warned
you. All of that comes from the game's own facts, not from the AI. Under every answer you see where it came from: the
AI model and how long it took, or a ready-made line and why.

## Check the rules

`python tests/test_rules.py` runs 17 checks with a fake model that lies and makes things up; the game must never act on it. No key needed.

`python tests/scenarios.py` plays five whole scenarios with the **real** model (the full story, 12 trick lines, money,
the same question five times, asking the wrong person) and checks what the game says is true at the end. It needs a
key, takes about a minute, never touches your saved game, and writes every line with its timing to
`logs/scenarios.jsonl`. `python tests/scenarios.py --list` shows them; `python tests/scenarios.py tricks` runs one.

## Folders

- `game/`: the world (`world.json`) and its rules (`state.py`). No AI here.
- `brain/`: the characters (`npcs.py`), the dialogue pipeline (`dialogue.py`), moods (`emotions.py`), the model (`llm.py`).
- `start.py`: asks which way you want to play.
- `play.py`: the text version of the game.
- `run_game.py` and `web/`: the full game. `run_game.py` is a small web server on your own computer; `web/game.js` draws the village and sends what you do to it.
- `logs/turns.jsonl`: every line of dialogue with its time, model and problems (made while you play; for the report).
- `save.json`: the saved game, including what each character remembers (made while you play).
