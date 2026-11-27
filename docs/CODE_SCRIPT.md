# What to say about the code of the full game

Three files make the full game: `start.py`, `run_game.py` and `web/game.js`. For each one there is a sentence to
remember, a script to say out loud (about a minute), the parts to point at on screen, and questions a teacher may ask.

Say it in your own words. The scripts are a guide, not a text to read out.

**The one idea behind all three:** the screen never decides anything. It shows the village and passes on what the
player does. The game rules (`game/state.py`) and the dialogue pipeline (`brain/dialogue.py`) decide, exactly like
in the terminal version.

```
start.py ── choice 1 ──> play.py ─────────────────────────────┐
         └─ choice 2 ──> run_game.py <── web/game.js (browser) ├──> brain/ (the characters) ──> game/ (the rules)
                                                               ┘
```

---

## 1. `start.py` (39 lines)

**One sentence:** it is the menu: it asks which way you want to play and starts that one.

**Say:**

> "This is the smallest file. It prints a menu with two choices: the terminal demo or the full game. The function
> `ask` keeps asking until I type one of the allowed answers, so a typing mistake does not crash it. Then it asks
> whether I want a new game. In the end it does one of two things: it starts `play.py`, the text version, or
> `run_game.py`, the full game. Both use the same characters and the same saved game, so I can play in one and
> continue in the other."

**Point at:**

- `ask(...)`: the loop that repeats the question until the answer is valid.
- The `--new` line: starting over is the same switch both versions already understand.
- `import play` / `import run_game`: the file itself contains no game logic.

**If the teacher asks:**

- *Why a separate file?* "So there is one command to remember, and so the two versions stay independent. Either one
  can also be started directly."
- *What does `--new` do?* "It deletes `save.json`, the saved game, before starting."

---

## 2. `run_game.py` (154 lines)

**One sentence:** it is a small web server on my own computer that connects the game screen in the browser to the
Python brain.

**Say:**

> "The game screen runs in the browser and is written in JavaScript. The characters and the rules are in Python. This
> file is the bridge between them. It is a small web server that only my own computer can reach, built with what
> Python already includes, so there is nothing extra to install.
>
> The browser can ask it for six things. Two only read: `world` gives the names of the places, items and characters,
> and `state` gives the game right now, like gold, bag, quests, the next step and the signs over heads. Four do
> something: `talk`, `go`, `search` and `reset`.
>
> The important part is the function `act`. When the browser sends 'talk to Bram: hello', `act` calls `Brain.talk`,
> the same function the terminal version calls. When the player walks to another place it calls `Game.go`, and the
> game may refuse. So the server adds no rules of its own. After every action it sends back the new state, and the
> screen shows that."

**Point at:**

- The list of addresses in the comment at the top of the file.
- `act(...)`: four short `if` blocks, each calling one function of the brain or the game.
- `state()`: everything the screen is allowed to know, in one place.
- `FILES`: the only three files the server hands out (the page, its style, its script).
- `LOCK`: only one request is handled at a time.

**If the teacher asks:**

- *Why a server? Why not put everything in the browser?* "Our dialogue system is in Python, and the API key must stay
  secret. Code in a browser is visible to anyone. This way the key never leaves the Python side."
- *Can someone else on the network play or break my game?* "No. It listens on `127.0.0.1`, which means this computer
  only."
- *Could the browser get the `.env` file with the key?* "No. The server only hands out the three files in `FILES`.
  Everything else gets 'not found'."
- *What is the `Content-Type` check for?* "Only our own page sends JSON. It stops other websites that are open in
  the browser from sending commands to the game."
- *What is the lock for?* "All requests share one game. The lock makes them wait for each other, so two actions
  cannot change the game at the same moment."
- *What happens if the AI is slow?* "Nothing special here. `Brain.talk` already gives up after 9 seconds and
  returns a ready-made line; the server just passes it on."
- *Where does the 'Next' box come from?* "From `state()`: it calls `Game.next_step`, which works out the goal from
  the game's facts. The screen only prints it, and the AI is not involved."

---

## 3. `web/game.js` (457 lines)

**One sentence:** it draws the village and passes on what the player does; it cannot change gold, items or quests by
itself.

This is the longest file. It is split into sections by lines of `─────`, with a title in each. Explain it in the
seven steps below (the short "keys and buttons" section belongs to steps four and five).

**Say:**

> "This file is the game screen. It has seven parts.
>
> **One: talking to the server.** The function `api` sends a request to `run_game.py` and gets the answer. Every
> fact on the screen arrives through it.
>
> **Two: the map.** The map is data, not code. `ZONES` are rectangles that say which place of our world you are
> standing in. `SOLID` are the things you cannot walk through, like the wall and Bram's counter. `STAND` is where
> each character stands.
>
> **Three: what the screen remembers.** `S` is the game state, and it always comes from the server: gold, bag,
> quests, the next step and the signs. The screen only remembers small things of its own, like where the player is
> standing and which keys are held down.
>
> **Four: walking.** `update` runs many times a second. It moves the player a little in the direction of the keys,
> unless something solid is in the way. When the next step would cross into another place, it does not just walk
> in. It calls `enter`, which asks the game first. That is how the mine gate works: the game answers 'the way is
> locked, you need the Gate Pass', and the player stays where they are.
>
> **Five: talking.** Pressing E next to a character opens the dialogue box, with their face drawn by the same code
> as on the map, and three ideas to say as buttons; I can still type anything. When I send a line, '…is thinking'
> shows while the AI works. The answer appears letter by letter, then a star line for anything the game did, like a
> purchase, and a small grey line that says whether the AI answered and how fast, or whether it was a ready-made line
> and why.
>
> **Six: the side panel.** `renderSide` writes the next step, the gold, the bag with what each item is for, the
> quests and the mood bars. It copies them from the state; it calculates nothing.
>
> **Seven: drawing.** `draw` paints the picture from simple shapes: rectangles, circles and lines. There are no
> image files. Everything that stands on the ground is sorted from back to front, so the player can walk behind a
> tree or a house. On top come the helpers from the game's facts: a gold ring or arrow for the next step, '!' and '?'
> over a character, and a place's danger written next to its name once someone has warned me. There is also a story
> card when the game opens, and a 'thank you' card the moment the game says every task is done."

**Point at:**

- `ZONES`, `SOLID`, `STAND`: the whole map in about 20 lines.
- `update` and `enter`: the place where the screen asks the game for permission.
- `if (!has('gate_pass'))` in `draw`: the gate is drawn shut until the game says the pass is in the bag.
- `sayLine`: names the character wrote in [brackets] are shown in blue. They are the names that were checked against
  the game's facts.
- The woods at the end of `draw`: a dark layer, with a hole of light around the player when the bag has a Torch.
- The goal marker in `draw` (`S.next`): a ring for a place, an arrow over a character.
- `typeLine` and `portrait`: the dialogue box's typing effect and the face drawn from `person`.

**If the teacher asks:**

- *How does the screen know the player has 35 gold?* "It does not know by itself. After every action the server
  sends the whole state, and `setState` stores it and redraws the panel."
- *Could a player cheat by changing the JavaScript?* "They could change what is drawn on their own screen, but not
  the game. Gold, items and quests live on the Python side, and every action is checked there."
- *How does walking into things work?* "`blocked` tests the player's feet, a small box of 16 by 8 pixels, against
  every rectangle in `SOLID`. Left-right and up-down are tested separately, so you slide along a wall instead of
  sticking to it."
- *How does it know who I can talk to?* "`nearby` looks for a character in the same place and closer than 78
  pixels."
- *Why is there a short pause after the locked gate refuses?* "So that holding the key down does not ask the game
  the same question sixty times a second. It waits one and a half seconds."
- *Why no pictures or a game engine?* "To keep it small enough to explain. The project is about the dialogue
  system; the screen only has to show it. In week 2 we polished it with what the game knows: the next-step marker,
  the signs over heads, the danger labels, the portrait and the story and ending cards."
- *Is the 'Next' box an AI hint?* "No. It comes from `Game.next_step`, plain code that reads the quests, the bag and
  `world.json`. The AI never decides what the goal is."
- *Aren't the idea buttons a dialogue tree again?* "They are only examples for people who do not know what to say.
  Pressing one just types that line; the AI answers it like anything else, and any other line works too."
- *Did you write the drawing code yourself?* Answer this one honestly, in your own words: say what you wrote, what
  you had help with, and that you can explain each part.

---

## A 30-second version, if there is no time

> "The full game has three small pieces. `start.py` is a menu. `web/game.js` draws the village in the browser and
> sends what the player does. `run_game.py` is a small server on my computer that hands those actions to the same
> Python code the terminal version uses. The screen decides nothing: if I walk into the locked mine or ask for free
> gold, it is the game rules that refuse."
