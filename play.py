"""Week 1 prototype: the village as a text game in the terminal. No graphics yet; everything else is real.

    python play.py            continue the saved game (save.json)
    python play.py --new      start over

Commands:  go <place>   talk <name>   search   look   bag   quests   help   quit
While talking, just type what you want to say (type  bye  to stop talking).
"talk bram hello" and "hey bram" also work: they walk up to Bram and say it.
"""
import re
import sys
from pathlib import Path

from brain.dialogue import Brain
from brain.llm import GeminiLLM
from brain.npcs import NPCS
from game.state import WORLD

HERE = Path(__file__).parent


PEOPLE = {k: {"name": n["name"], "place": n["place"]} for k, n in NPCS.items()}


def look(game) -> str:
    place = WORLD["places"][game.place]
    here = [n["name"] for n in NPCS.values() if n["place"] == game.place]
    others = ", ".join(f"{k} ({p['name']})" for k, p in WORLD["places"].items() if k != game.place)
    return (f"\n== {place['name']} ==\nHere: {', '.join(here) or 'nobody'}.  Gold: {game.gold}.\n"
            f"You can go to: {others}\nNext: {game.next_step(PEOPLE)['text']}")


def name_words(npc_id: str) -> set[str]:
    return {npc_id} | set(NPCS[npc_id]["name"].lower().split())


def who_is_meant(text: str) -> str | None:
    """The character named in what the player typed ("bram", "the captain", "Elder Mira"…)."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return next((k for k in NPCS if words & name_words(k)), None)


def main() -> None:
    save = HERE / "save.json"
    if "--new" in sys.argv and save.exists():
        save.unlink()
    llm = GeminiLLM()
    brain = Brain(llm, save_path=save, log_path=HERE / "logs" / "turns.jsonl")
    game, talking_to = brain.game, None
    print(f"Welcome to {WORLD['village']}. Type  help  for the commands.")
    if not llm.keys:
        print("\n!! No AI key found, so the characters can only say their ready-made lines.\n"
              "!! Put a key in a file called  .env  in this folder (see README.md), then start again.")
    print(look(game))

    def say(line: str) -> None:
        out = brain.talk(talking_to, line)
        print(f"{out['name']}: {out['text']}")
        for event in out["events"]:
            print(f"   * {event}")
        why = f": {out['problems'][-1]}" if out["source"] == "fallback" and out["problems"] else ""
        print(f"   ({out['source']}{why}, {out['latency_ms']} ms)")

    while True:
        try:
            line = input(f"\n[{NPCS[talking_to]['name']}] you: " if talking_to else "\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if talking_to:
            if line.lower() in ("bye", "leave", "exit"):
                talking_to = None
                continue
            say(line)
            continue
        word, _, rest = line.partition(" ")
        word, rest = word.lower(), rest.strip().lower()
        if word in ("quit", "exit"):
            break
        elif word == "help":
            print(__doc__)
        elif word == "look":
            print(look(game))
        elif word == "bag":
            print("You carry:", ", ".join(WORLD["items"][i]["name"] for i in game.inventory) or "nothing", f"| Gold: {game.gold}")
        elif word == "quests":
            for q, status in game.quests.items():
                print(f"  {WORLD['quests'][q]['name']}: {status.replace('_', ' ')}")
            print(f"  Next: {game.next_step(PEOPLE)['text']}")
        elif word == "go":
            place = next((k for k, p in WORLD["places"].items() if rest in (k, p["name"].lower()) or rest.replace(" ", "_") == k), rest)
            print(game.go(place)[1])
            brain.save()
            if game.place == place:
                print(look(game))
        elif word == "search":
            print(game.search()[1])
            brain.save()
        elif word == "talk" or who_is_meant(line):  # "talk bram", "talk bram hey", or just "hey bram"
            who = who_is_meant(rest if word == "talk" else line)
            if not who:
                print("Talk to whom? " + ", ".join(NPCS))
            elif NPCS[who]["place"] != game.place:
                print(f"{NPCS[who]['name']} is not here. Go to: {NPCS[who]['place']}")
            else:
                talking_to = who
                print(f"(you walk up to {NPCS[who]['name']}; type  bye  to stop talking)")
                first = line.split()[1:] if word == "talk" else line.split()
                while word == "talk" and first and first[0].lower().strip(",.!?:") in name_words(who):
                    first.pop(0)  # "talk bram hey" → say "hey"
                if first:
                    say(" ".join(first))
        else:
            here = ", ".join(n["name"] for n in NPCS.values() if n["place"] == game.place)
            print("I don't know that command. Type  help." + (f"  To talk to someone here, type  talk  and a name ({here})." if here else ""))
    print("\nSaved. See you next time!")


if __name__ == "__main__":
    main()
