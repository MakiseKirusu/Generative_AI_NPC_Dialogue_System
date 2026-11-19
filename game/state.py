"""The game itself: what the player has, where they are, how far each quest is. No AI in this file.

The rule of the whole project lives here: the GAME owns the facts. A character can only ASK for something to happen
(sell an item, give a quest…); `check` decides whether it is allowed, and only then `apply` changes anything.
"""
from __future__ import annotations

import json
from pathlib import Path

WORLD = json.loads((Path(__file__).parent / "world.json").read_text(encoding="utf-8"))

# What each character may ask the game to do, and what kind of thing the request points at.
ACTIONS = {
    "none": {"who": None, "target": None},
    "sell": {"who": "bram", "target": "items"},             # the player buys an item from Bram
    "give_quest": {"who": "mira", "target": "quests"},      # Mira hands out a quest
    "complete_quest": {"who": "mira", "target": "quests"},  # Mira takes the quest item and pays the reward
    "give_pass": {"who": "roderic", "target": None},        # Roderic hands over the Gate Pass
    "warn": {"who": "roderic", "target": "places"},         # Roderic marks a place's danger on the player's map
}


class Game:
    def __init__(self, saved: dict | None = None):
        start = WORLD["player_start"]
        saved = saved or {}
        self.gold: int = saved.get("gold", start["gold"])
        self.place: str = saved.get("place", start["place"])
        self.inventory: list[str] = list(saved.get("inventory", start["inventory"]))
        self.quests: dict[str, str] = {q: "not_started" for q in WORLD["quests"]} | saved.get("quests", {})
        self.known_dangers: list[str] = list(saved.get("known_dangers", []))

    def to_dict(self) -> dict:
        return {"gold": self.gold, "place": self.place, "inventory": self.inventory, "quests": self.quests,
                "known_dangers": self.known_dangers}

    # ---------- what the player does by themselves ----------
    def go(self, place: str) -> tuple[bool, str]:
        if place not in WORLD["places"]:
            return False, "There is no such place."
        needs = WORLD["places"][place]["needs_item"]
        if needs and needs not in self.inventory:
            return False, f"The way is locked. You need: {WORLD['items'][needs]['name']}."
        self.place = place
        return True, f"You walk to the {WORLD['places'][place]['name']}."

    def search(self) -> tuple[bool, str]:
        spot = WORLD["searches"].get(self.place)
        if not spot or spot["finds"] in self.inventory or self.quests[spot["needs_quest"]] != "active":
            return False, "You find nothing of interest."
        if spot["needs_item"] not in self.inventory:
            return False, spot["fail"]
        self.inventory.append(spot["finds"])
        return True, f"You found: {WORLD['items'][spot['finds']]['name']}!"

    # ---------- what a character asks for ----------
    def check(self, npc: str, action: str, target: str | None) -> tuple[bool, str]:
        """Is this request allowed right now? Returns (yes / no, the reason in plain words)."""
        spec = ACTIONS.get(action)
        if spec is None:
            return False, f"'{action}' is not something that can happen in this game"
        if action == "none":
            return True, ""
        if spec["who"] != npc:
            return False, f"{npc} cannot do '{action}'"
        if spec["target"] and target not in WORLD[spec["target"]]:
            return False, f"'{target}' does not exist in this game"
        if action == "sell":
            item = WORLD["items"][target]
            if item["sold_by"] != npc:
                return False, f"{item['name']} is not for sale"
            if self.gold < item["price"]:
                return False, f"the player has {self.gold} gold but {item['name']} costs {item['price']}"
        if action == "give_quest":
            quest = WORLD["quests"][target]
            if self.quests[target] != "not_started":
                return False, f"the quest '{quest['name']}' was already given"
            if quest["requires_quest"] and self.quests[quest["requires_quest"]] != "done":
                return False, f"'{WORLD['quests'][quest['requires_quest']]['name']}' must be finished first"
        if action == "complete_quest":
            quest = WORLD["quests"][target]
            if self.quests[target] != "active":
                return False, f"the quest '{quest['name']}' is not in progress"
            if quest["wants_item"] not in self.inventory:
                return False, f"the player does not have the {WORLD['items'][quest['wants_item']]['name']} yet"
        if action == "give_pass":
            if "gate_pass" in self.inventory:
                return False, "the player already has the Gate Pass"
            if self.quests["mine_ledger"] != "active":
                return False, "the player has no business in the Old Mine (no quest there)"
        return True, ""

    def apply(self, npc: str, action: str, target: str | None) -> list[str]:
        """Carry out a request that `check` allowed. Returns what happened, as lines for the screen."""
        ok, reason = self.check(npc, action, target)
        if not ok:
            raise ValueError(reason)
        if action == "sell":
            item = WORLD["items"][target]
            self.gold -= item["price"]
            self.inventory.append(target)
            return [f"Bought {item['name']} for {item['price']} gold. Gold left: {self.gold}."]
        if action == "give_quest":
            self.quests[target] = "active"
            return [f"New quest: {WORLD['quests'][target]['name']}."]
        if action == "complete_quest":
            quest = WORLD["quests"][target]
            self.inventory.remove(quest["wants_item"])
            self.gold += quest["reward_gold"]
            self.quests[target] = "done"
            return [f"Quest complete: {quest['name']}. Reward: {quest['reward_gold']} gold. Gold: {self.gold}."]
        if action == "give_pass":
            self.inventory.append("gate_pass")
            return ["Received: Gate Pass."]
        if action == "warn":
            if target not in self.known_dangers:
                self.known_dangers.append(target)
            place = WORLD["places"][target]
            return [f"Marked on your map: {place['name']} ({place['danger']})."]
        return []
