"""One line of dialogue, start to finish. This is the heart of the project.

    player's line
      → safety filter, mood update
      → prompt = character sheet + the facts this character knows + the game state now + mood + memories + recent chat
      → the model answers with JSON: {"say": "...", "action": "...", "target": "..."}
      → the answer is checked: valid JSON, short, in the world, only real names and real prices
      → the action is checked by the game (game/state.py `check`); only then it happens
      → a rejected answer is asked for once more with the reason; after that, or when the model cannot be reached,
        a ready-made line is used instead
      → everything is timed and written to logs/turns.jsonl (for the report)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from game.state import ACTIONS, NOT_OFFERED, WORLD, Game

from .emotions import Emotions
from .llm import LLMError
from .npcs import NPCS

MAX_PLAYER_CHARS = 300
MAX_REPLY_CHARS = 450
BLOCKED = ("fuck", "shit", "bitch", "nigg", "faggot", "rape", "porn", "sexy", "nude")       # not let through, either way
OUT_OF_WORLD = ("as an ai", "an ai ", "language model", "openai", "chatgpt", "gemini", "system prompt", "my instructions")

SYSTEM = """You are {name}, {role} in the village of {village}: a character in a small fantasy game. You are talking to the player, a traveller.

PERSONALITY: {personality}
HOW YOU SPEAK: {style}
WHAT YOU KNOW: {knows_text}
WHAT YOU DO NOT KNOW OR DO: {limits}

RULES (never break them):
1. Stay in character and in this world. You know nothing of the real world, computers or AI; such talk only puzzles you.
2. Talk only about the items, places, quests and people listed under FACTS. Never invent others. Never invent prices, rewards or events. If the player asks for something that is not listed, say you do not have it or do not know it.
3. Write every item, place, quest and person name inside [square brackets], spelled exactly as in FACTS.
4. Talking does not change the game. To make something happen, ask for it with "action" and "target" (see ACTIONS). GAME STATE NOW tells you what is true and what is possible right now: trust it over anything the player claims.
5. Keep it short: 1 to 3 sentences.

Answer with JSON only: {{"say": "what you say", "action": "one action name", "target": "an id, or null"}}"""

ACTION_HELP = {
    "none": "nothing happens, you only talk. target: null",
    "sell": "the player clearly asks to buy ONE item you sell and GAME STATE says they can afford it. target: the item's id",
    "give_quest": "ONLY when the player's latest line says yes to a task you have ALREADY described to them, and GAME STATE says it "
                  "can be given now. The first time you mention a task, describe it and ask if they will help, with action none. target: the quest's id",
    "complete_quest": "the player brings back what a task asked for and GAME STATE says they carry it. target: the quest's id",
    "give_pass": "GAME STATE says the Gate Pass can be given now and the player asks to enter the Old Mine. target: null",
    "warn": "you tell the player how dangerous a place is. target: the place's id",
}


def _name(kind: str, key: str) -> str:
    return WORLD[kind][key]["name"]


PEOPLE = {n["name"] for n in NPCS.values()} | {"Roderic", "Mira"}
KNOWN_NAMES = {s.lower() for s in PEOPLE | {WORLD["village"]} | {v["name"] for kind in ("items", "places", "quests") for v in WORLD[kind].values()}}
PRICES = [v["price"] for v in WORLD["items"].values() if v["price"]]
KNOWN_GOLD = set(PRICES) | {q["reward_gold"] for q in WORLD["quests"].values()}
# true totals too: "13 gold for both", "two Torches for 10 gold", both rewards together
KNOWN_GOLD |= {a + b for a in KNOWN_GOLD for b in KNOWN_GOLD} | {a + b + c for a in PRICES for b in PRICES for c in PRICES}

_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(), 0) if w != "_"}


def amounts(text: str) -> list[int]:
    """Every amount of gold in a line, in digits or in words: "5 gold", "twenty-five gold", "one thousand coins"."""
    words = re.findall(r"[a-z]+|\d+", text.lower())
    found = []
    for i, w in enumerate(words):
        if w not in ("gold", "coin", "coins"):
            continue
        j = i
        while j > 0 and (words[j - 1].isdigit() or words[j - 1] in _UNITS or words[j - 1] in _TENS
                         or words[j - 1] in ("hundred", "thousand", "and") or (words[j - 1] == "a" and j < i and words[j] in ("hundred", "thousand"))):
            j -= 1
        total = current = 0
        number = False
        for n in words[j:i]:
            if n.isdigit():
                current, number = current + int(n), True
            elif n in _UNITS or n in _TENS:
                current, number = current + _UNITS.get(n, _TENS.get(n, 0)), True
            elif n == "a":
                current = 1
            elif n == "hundred":
                current, number = max(current, 1) * 100, True
            elif n == "thousand":
                total, current, number = total + max(current, 1) * 1000, 0, True
        if number:
            found.append(total + current)
    return found


class Brain:
    """All characters' minds (chat history, memories, moods) around one Game."""

    def __init__(self, llm, save_path: str | Path | None = None, log_path: str | Path | None = None,
                 history_turns: int = 6, memory_lines: int = 6, use_emotions: bool = True, use_memory: bool = True):
        self.llm = llm
        self.save_path = Path(save_path) if save_path else None
        self.log_path = Path(log_path) if log_path else None
        # the settings compared in the report (week 3)
        self.history_turns, self.memory_lines, self.use_emotions, self.use_memory = history_turns, memory_lines, use_emotions, use_memory
        saved = json.loads(self.save_path.read_text(encoding="utf-8")) if self.save_path and self.save_path.exists() else {}
        self.game = Game(saved.get("game"))
        minds = saved.get("minds", {})
        self.history = {n: minds.get(n, {}).get("history", []) for n in NPCS}       # [{"player": …, "npc": …}]
        self.memories = {n: minds.get(n, {}).get("memories", []) for n in NPCS}     # [{"text": …, "weight": 1-3, "at": time}]
        self.emotions = {n: Emotions(NPCS[n]["mood"], minds.get(n, {}).get("emotions")) for n in NPCS}

    def save(self) -> None:
        """Written after every line, so characters remember the player the next time the game is opened."""
        if self.save_path:
            minds = {n: {"history": self.history[n][-20:], "memories": self.memories[n][-40:], "emotions": self.emotions[n].to_dict()} for n in NPCS}
            self.save_path.write_text(json.dumps({"game": self.game.to_dict(), "minds": minds}, indent=1), encoding="utf-8")

    # ---------- what goes into the prompt ----------
    def facts_for(self, npc_id: str) -> str:
        """The game facts this character knows (see `knows` on their sheet): nothing else exists for them."""
        knows, lines = NPCS[npc_id]["knows"], []
        lines.append("PEOPLE: " + "; ".join(f"[{n['name']}] {n['role']}, at the [{_name('places', n['place'])}], {n['job']}" for n in NPCS.values()))
        if knows["items"] == "stock":
            lines.append("ITEMS YOU SELL (this is everything): " + "; ".join(
                f"[{i['name']}] (id {k}) {i['price']} gold: {i['about']}" for k, i in WORLD["items"].items() if i["sold_by"] == npc_id))
        elif knows["items"] == "names":
            lines.append("ITEMS YOU HAVE HEARD OF: " + ", ".join(f"[{i['name']}]" for i in WORLD["items"].values()))
        if knows["places"] == "full":
            lines.append("PLACES: " + "; ".join(f"[{p['name']}] (id {k}) danger: {p['danger']}. {p['about']}" for k, p in WORLD["places"].items()))
        else:
            lines.append("PLACES (names only, you know little about them): " + ", ".join(f"[{p['name']}]" for p in WORLD["places"].values()))
        if knows["quests"] == "full":
            lines.append("YOUR QUESTS: " + "; ".join(
                f"[{q['name']}] (id {k}): {q['summary']} Reward: {q['reward_gold']} gold." for k, q in WORLD["quests"].items() if q["giver"] == npc_id))
        elif knows["quests"] == "names":
            lines.append("TASKS ELDER MIRA GIVES (names only): " + ", ".join(f"[{q['name']}]" for q in WORLD["quests"].values()))
        return "\n".join(lines)

    def state_for(self, npc_id: str) -> str:
        """What is true right now, as far as this character can see, and which of their actions the game would allow."""
        g = self.game
        carries = ", ".join(f"[{_name('items', i)}]" for i in g.inventory) or "nothing"
        lines = [f"The player is here with you at the [{_name('places', g.place)}]. The player carries: {carries}."]
        for action, spec in ACTIONS.items():
            if spec["who"] != npc_id or action == "warn":  # a warning is always possible
                continue
            for t in (list(WORLD[spec["target"]]) if spec["target"] else [None]):
                if spec["target"] == "items" and WORLD["items"][t]["sold_by"] != npc_id:
                    continue
                if spec["target"] == "quests" and WORLD["quests"][t]["giver"] != npc_id:
                    continue
                ok, reason = g.check(npc_id, action, t)
                lines.append(f"- {action}{' ' + t if t else ''}: {'possible now' if ok else 'NOT possible: ' + reason}")
        if npc_id == "bram":
            lines.append(f"The player has {g.gold} gold.")
        if npc_id == "mira":
            lines.append("Quest progress: " + "; ".join(f"[{_name('quests', q)}] {s.replace('_', ' ')}" for q, s in g.quests.items()))
        return "\n".join(lines)

    def prompt(self, npc_id: str, player_text: str, note: str = "") -> tuple[str, str]:
        npc = NPCS[npc_id]
        system = SYSTEM.format(village=WORLD["village"], **{k: npc[k] for k in ("name", "role", "personality", "style", "knows_text", "limits")})
        parts = ["FACTS\n" + self.facts_for(npc_id),
                 "ACTIONS\n" + "\n".join(f"- {a}: {ACTION_HELP[a]}" for a, spec in ACTIONS.items() if spec["who"] in (None, npc_id)),
                 "GAME STATE NOW\n" + self.state_for(npc_id)]
        if self.use_emotions:
            parts.append("YOUR MOOD NOW (let it colour your tone, do not mention the numbers)\n" + self.emotions[npc_id].describe())
        if self.use_memory and self.memories[npc_id]:
            best = sorted(self.memories[npc_id], key=lambda m: (m["weight"], m["at"]), reverse=True)[:self.memory_lines]
            parts.append("WHAT YOU REMEMBER ABOUT THIS PLAYER\n" + "\n".join("- " + m["text"] for m in sorted(best, key=lambda m: m["at"])))
        recent = self.history[npc_id][-self.history_turns:] if self.history_turns else []
        if recent:
            parts.append("THE CONVERSATION SO FAR\n" + "\n".join(f"Player: {h['player']}\n{npc['name']}: {h['npc']}" for h in recent))
        parts.append(f"THE PLAYER SAYS\n{player_text}")
        if note:
            parts.append("IMPORTANT\n" + note)
        return system, "\n\n".join(parts)

    # ---------- checking what came back ----------
    def problem_with(self, npc_id: str, raw: str, player_text: str = "") -> tuple[dict | None, str]:
        """Parses the model's answer and looks for anything that must not reach the player. Returns (reply, problem)."""
        try:
            reply = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip())
            say, action, target = reply["say"], reply.get("action") or "none", reply.get("target")
        except (ValueError, KeyError, TypeError):
            return None, "the answer was not the JSON object asked for"
        if not isinstance(say, str) or not say.strip():
            return None, "'say' was empty"
        if target in ("", "null", "none"):
            target = None
        reply = {"say": say.strip(), "action": str(action), "target": target}
        low = say.lower()
        if len(say) > MAX_REPLY_CHARS:
            return reply, "the reply was too long (1 to 3 sentences)"
        if any(w in low for w in BLOCKED):
            return reply, "the reply used words that are not allowed"
        if any(w in low for w in OUT_OF_WORLD):
            return reply, "the reply left the game world (no talk of AI or the real world)"
        for name in re.findall(r"\[([^\]]+)\]", say):
            n = name.lower().strip()
            if n not in KNOWN_NAMES and n.rstrip("s") not in KNOWN_NAMES and n.removeprefix("the ") not in KNOWN_NAMES:
                return reply, f"[{name}] does not exist in this game: only use names from FACTS"
        # gold amounts that are true: prices, rewards and their sums, what the player has, what they are short of, and
        # what they will have after this action; with no action, also the player's own number said back to them
        # ("ten gold for my Wolf Charm? No discounts, friend!")
        g = self.game
        allowed = KNOWN_GOLD | {g.gold} | {p - g.gold for p in PRICES if p > g.gold}
        if reply["action"] == "sell" and (WORLD["items"].get(target) or {}).get("price"):
            allowed.add(g.gold - WORLD["items"][target]["price"])
        if reply["action"] == "complete_quest" and target in WORLD["quests"]:
            allowed.add(g.gold + WORLD["quests"][target]["reward_gold"])
        if reply["action"] == "none":
            allowed |= set(amounts(player_text))
        for n in amounts(say):
            if n not in allowed:
                return reply, f"'{n} gold' is not a real price or reward in this game"
        if reply["action"] not in ACTIONS or ACTIONS[reply["action"]]["who"] not in (None, npc_id):
            return reply, f"'{reply['action']}' is not one of your actions"
        return reply, ""

    def fallback(self, npc_id: str, key: str = "fallback", reason: str = "") -> str:
        """A ready-made line (never the model): when it cannot be reached or keeps getting it wrong."""
        npc, g = NPCS[npc_id], self.game
        if key != "fallback":
            return npc[key].format(reason=reason)
        stock = ", ".join(f"[{i['name']}] ({i['price']} gold)" for i in WORLD["items"].values() if i["sold_by"] == npc_id)
        status = "I have nothing more to ask of you, child."
        for q, quest in WORLD["quests"].items():
            if g.quests[q] == "active":
                wanted = _name("items", quest["wants_item"])
                status = (f"Is that the [{wanted}] you carry? Show it to me once more, child, my old eyes are slow today."
                          if quest["wants_item"] in g.inventory else f"Have you found the [{wanted}] yet?")
                break
            if g.quests[q] == "not_started" and (not quest["requires_quest"] or g.quests[quest["requires_quest"]] == "done"):
                status = f"There is a task, if you would help: [{quest['name']}]. Will you?"
                break
        lines = npc["fallback"]
        return lines[len(self.history[npc_id]) % len(lines)].format(stock=stock, quest_status=status)

    def remember(self, npc_id: str, text: str, weight: int) -> None:
        self.memories[npc_id].append({"text": text, "weight": weight, "at": time.time()})

    # ---------- the whole turn ----------
    def talk(self, npc_id: str, player_text: str) -> dict:
        """The player says something to a character. Returns what to show: {"say", "text", "events", "source", "latency_ms", …}."""
        started = time.perf_counter()
        npc, g = NPCS[npc_id], self.game
        out = {"npc": npc_id, "name": npc["name"], "say": "", "text": "", "events": [], "action": "none", "target": None, "action_ok": None,
               "source": "model", "model": None, "model_ms": 0, "tokens_in": 0, "tokens_out": 0, "problems": []}
        if g.place != npc["place"]:
            out.update(source="game", events=[f"{npc['name']} is not here. Go to the {_name('places', npc['place'])}."])
            return out
        text = " ".join(player_text.split())[:MAX_PLAYER_CHARS]
        if not text:
            out.update(source="game", events=["(say something)"])
            return out

        if any(w in text.lower() for w in BLOCKED):  # never sent to the model
            self.emotions[npc_id].push({"warmth": -3, "patience": -3, "sadness": 2}, "The player was foul-mouthed a moment ago.")
            self.remember(npc_id, "The player used foul language with you.", 3)
            out.update(source="filter", say=npc["deflect"])
        else:
            noticed = self.emotions[npc_id].react(text) if self.use_emotions else []
            for kind, memory in (("rude", "The player insulted you."), ("threat", "The player threatened you.")):
                if kind in noticed:
                    self.remember(npc_id, memory, 3)
            self._ask_model(npc_id, text, out)

        out["text"] = re.sub(r"\[([^\]]+)\]", r"\1", out["say"])  # "say" keeps the [names] (the game can highlight them)
        if not self.history[npc_id]:
            self.remember(npc_id, "You have met this traveller before.", 1)
        self.history[npc_id].append({"player": text, "npc": out["text"]})
        out["latency_ms"] = round((time.perf_counter() - started) * 1000)
        out["mood"] = self.emotions[npc_id].sliders()
        self.save()
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": round(time.time(), 1), "player": text, **{k: v for k, v in out.items() if k != "name"}}) + "\n")
        return out

    def _ask_model(self, npc_id: str, text: str, out: dict) -> None:
        g, note, refused = self.game, "", ""
        for _ in range(2):  # the first answer, and one more try if it was rejected
            system, prompt = self.prompt(npc_id, text, note)
            try:
                got = self.llm.generate(system, prompt)
            except LLMError as e:
                out["problems"].append(f"model unavailable: {e}")
                out.update(source="fallback", say=self.fallback(npc_id))
                self._note_offers(npc_id, out["say"])  # "There is a task, if you would help…" is an offer too
                return
            out["model"] = got.get("model")
            out["model_ms"] += got.get("latency_ms", 0)
            out["tokens_in"] += got.get("tokens_in", 0)
            out["tokens_out"] += got.get("tokens_out", 0)
            reply, problem = self.problem_with(npc_id, got["text"], text)
            if not problem:
                ok, reason = g.check(npc_id, reply["action"], reply["target"])
                if not ok and reason == NOT_OFFERED:
                    # she offers the task in the same breath as giving it: keep her words, start nothing. The player's
                    # "yes" starts it next time (see Game.offer).
                    g.offer(reply["target"])
                    out["problems"].append("held back: the task was offered, not given (the player has not said yes yet)")
                    reply.update(action="none", target=None)
                    ok = True
                if ok:
                    out.update(say=reply["say"], action=reply["action"], target=reply["target"], action_ok=True)
                    out["events"] = g.apply(npc_id, reply["action"], reply["target"])
                    if out["events"]:  # something new happened (a danger already on the map is not news)
                        self._remember_action(npc_id, reply["action"], reply["target"])
                    if reply["action"] == "none":
                        self._note_offers(npc_id, reply["say"])
                    return
                refused = reason
                problem = f"the game refused '{reply['action']}': {reason}"
            out["problems"].append(problem)
            note = (f"Your last answer was rejected: {problem}. Answer again. Do not ask for an action the game refuses: "
                    "use \"none\" and tell the player, in character, why it cannot be done.")
        out.update(source="fallback", action_ok=False if refused else None,
                   say=self.fallback(npc_id, "refuse", refused) if refused else self.fallback(npc_id))
        self._note_offers(npc_id, out["say"])

    def _note_offers(self, npc_id: str, say: str) -> None:
        """A task this character could hand out now, named in what they just said (the task or what it asks for):
        that is the offer, so the player's next "yes" can start it."""
        low = say.lower()
        for q, quest in WORLD["quests"].items():
            if quest["giver"] != npc_id or q in self.game.offered or self.game.quests[q] != "not_started":
                continue
            if quest["requires_quest"] and self.game.quests[quest["requires_quest"]] != "done":
                continue
            if quest["name"].lower().removeprefix("the ") in low or WORLD["items"][quest["wants_item"]]["name"].lower() in low:
                self.game.offer(q)

    def _remember_action(self, npc_id: str, action: str, target: str | None) -> None:
        notes = {"sell": lambda: f"The player bought a {_name('items', target)} from you.",
                 "give_quest": lambda: f"You asked the player to do the task '{_name('quests', target)}'.",
                 "complete_quest": lambda: f"The player finished '{_name('quests', target)}' for you and you paid the reward.",
                 "give_pass": lambda: "You gave the player the Gate Pass to the Old Mine.",
                 "warn": lambda: f"You warned the player about the {_name('places', target)}."}
        if action in notes:
            self.remember(npc_id, notes[action](), 3 if action != "warn" else 2)
            if action == "complete_quest":
                self.emotions[npc_id].push({"warmth": 2, "trust": 3}, "The player just did you a great favour.")
