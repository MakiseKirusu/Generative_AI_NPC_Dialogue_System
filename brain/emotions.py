"""Moods for the characters. Adapted from M.IKU's emotion engine (our Discord bot: amora_bot/engine/emotions.py).

Kept from M.IKU: every character has "sliders" from 0 to 10 with a personal baseline; what the player says pushes
them up or down; a single line cannot swing a mood wildly (inertia); pushes fade back to the baseline (half of
it every 10 minutes); a big moment ("the player insulted you") lingers for 30 minutes.
Changed for the game: any set of sliders (each character brings its own), no database, and it can be saved and
loaded, so a guard you insulted yesterday has cooled down by today.
"""
from __future__ import annotations

import time

HALF_LIFE = 600.0   # seconds until half of a push has faded
LINGER = 1800.0     # seconds a big moment stays in mind
INERTIA = 0.75      # how strongly the current mood resists one new push

# What the player says → pushes. A character only feels the sliders it has (Miku's are different from the villagers').
REACTIONS = [
    ("polite", ("please", "thank", "sorry", "appreciate", "kind of you"),
     {"warmth": 1.5, "trust": 1, "patience": 1, "cuteness": 2, "empathy": 2}, ""),
    ("praise", ("amazing", "wonderful", "great", "beautiful", "love your", "the best", "hero"),
     {"warmth": 2, "sass": -1, "cuteness": 2, "shyness": 1}, ""),
    ("rude", ("stupid", "idiot", "dumb", "shut up", "useless", "ugly", "hate you", "liar", "old fool"),
     {"warmth": -3, "patience": -3, "sass": 2, "sadness": 2, "chaos": 1}, "The player insulted you a moment ago."),
    ("threat", ("kill you", "rob you", "steal", "attack you", "burn", "or else", "hurt you"),
     {"trust": -4, "worry": 3, "warmth": -2, "sadness": 2, "shyness": 2}, "The player threatened you a moment ago."),
    ("haggle", ("discount", "cheaper", "too expensive", "lower the price", "for free", "half price"),
     {"patience": -1.5, "sass": 1}, ""),
]


class Emotions:
    def __init__(self, baseline: dict[str, int], saved: dict | None = None):
        self.baseline = dict(baseline)
        saved = saved or {}
        self.offsets = {k: float(saved.get("offsets", {}).get(k, 0.0)) for k in baseline}
        self.updated = float(saved.get("updated", time.time()))
        self.event = str(saved.get("event", ""))
        self.event_at = float(saved.get("event_at", 0.0))

    def to_dict(self) -> dict:
        return {"offsets": self.offsets, "updated": self.updated, "event": self.event, "event_at": self.event_at}

    def _decay(self) -> None:
        now = time.time()
        factor = 0.5 ** (max(0.0, now - self.updated) / HALF_LIFE)
        self.offsets = {k: v * factor for k, v in self.offsets.items()}
        self.updated = now

    def sliders(self) -> dict[str, int]:
        """The mood right now: baseline + what is left of the pushes, kept between 0 and 10."""
        self._decay()
        return {k: max(0, min(10, round(self.baseline[k] + self.offsets[k]))) for k in self.baseline}

    def lingering(self) -> str:
        return self.event if time.time() - self.event_at < LINGER else ""

    def push(self, delta: dict[str, float], event: str = "") -> None:
        self._decay()
        for k, v in delta.items():
            if k in self.offsets:
                dampened = self.offsets[k] * INERTIA + v * (1.0 - INERTIA * 0.5)
                self.offsets[k] = max(-5.0, min(5.0, dampened))
        if event:
            self.event, self.event_at = event, time.time()

    def react(self, player_text: str) -> list[str]:
        """Read the player's line and push the mood. Returns what was noticed ("rude", "polite"…)."""
        text = player_text.lower()
        noticed = []
        for name, words, delta, event in REACTIONS:
            if any(w in text for w in words):
                self.push(delta, event)
                noticed.append(name)
        return noticed

    def describe(self) -> str:
        """For the prompt: the sliders as text, plus the lingering moment."""
        words = {0: "none", 1: "very low", 2: "very low", 3: "low", 4: "low", 5: "medium", 6: "medium", 7: "high", 8: "high",
                 9: "very high", 10: "very high"}
        line = ", ".join(f"{k} {v}/10 ({words[v]})" for k, v in self.sliders().items())
        return line + (f". {self.lingering()}" if self.lingering() else "")
