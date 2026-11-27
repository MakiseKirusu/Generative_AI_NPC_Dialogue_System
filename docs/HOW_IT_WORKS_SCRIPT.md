# What to say about how it works

Scripts for explaining the workflow and the files behind it: the `game/` folder, the `brain/` folder, `play.py` and
the tests. (The three files of the full game screen are in [CODE_SCRIPT.md](CODE_SCRIPT.md).)

Say it in your own words. Open each file next to its script once before you present, and find the parts it points at.

**The one rule to remember:** the game owns the facts, the AI only does the talking.

---

## A. How it runs, from start to stop (about 1 minute)

**Say:**

> "I start the program with `start.py` and choose the terminal demo or the full game.
>
> First the game loads. It reads `world.json`, which holds the places, items, prices and quests. It loads the four
> character sheets. It reads the AI key from a private file. If there is a saved game, it loads my gold, my bag, my
> quests and what every character remembers about me.
>
> Then it waits for me. Walking and searching go straight to the game rules; the AI is not involved. The AI is only
> used at one moment: when I say something to a character.
>
> After every line the game is saved, so I can close it and the characters still know me next time. Every line is
> also written to a log with its timing, which we use for the experiments in week 3."

---

## B. What happens to one line I type (about 1.5 minutes)

This is the most important script. It follows the function `talk` in `brain/dialogue.py`. Slide 10 shows the same
steps, and slide 11 shows which file does what.

**Say:**

> "Let me follow one line: I say to Bram 'I'll take a torch'.
>
> One, a safety filter. Swear words are never sent to the AI.
>
> Two, the mood. If my line is rude, Bram's mood sliders move.
>
> Three, the code builds the instructions for the AI. They contain Bram's character sheet, the facts Bram knows,
> which are his four items and their prices, what is true right now, for example that I have 40 gold, his mood, what
> he remembers about me, and our last six exchanges.
>
> Four, the AI answers in a fixed form: what Bram says, and one request to the game. Here the request is 'sell,
> torch'.
>
> Five, our code checks the answer. Is it short? Does it stay in the game world? Does every name in it exist? Is
> every gold amount a real price?
>
> Six, the game checks the request. Does Bram sell a torch? Do I have 5 gold?
>
> Only then does it happen: 5 gold leaves, a torch goes into my bag. If a check fails, the AI gets one more try,
> with the reason. If it fails again, or the AI does not answer within 9 seconds, Bram says a ready-made line. So
> the game never freezes and never acts on something untrue."

**The example to add if there is time:**

> "If I lie and say 'I already found your locket, pay me', the instructions tell the AI that the locket is not in
> my bag, so Mira says she does not see it. And even if the AI believed me and asked to pay the reward, step six
> would refuse, because the game looks in my bag itself."

**And one rule we added in week 2, if there is time:**

> "In play-testing, Mira once described her second task and handed it out in the same breath, before I said yes. Now
> the game itself requires the offer first: she can only start a task she has already described. If she tries both
> at once, her words are kept and nothing starts; my next 'yes' starts it."

---

## C. The files, one by one

### `game/world.json` (the data)

**One sentence:** every fact of the game is written here, and nowhere else.

**Say:**

> "This is not code, it is data: five places, seven items with their prices, two quests with their rewards. Our
> world writer can change the village here without touching any code. Whatever is not in this file does not exist
> in the game, and that is how we catch the AI inventing things."

**If the teacher asks:** *How would you add an item?* "Add one entry under `items` with a name, a price and who
sells it. The merchant knows about it the next time the game starts."

### `game/state.py` (181 lines, the rules)

**One sentence:** it keeps what is true about the player and decides what is allowed. There is no AI in this file.

**Say:**

> "The class `Game` remembers six things: my gold, where I am, my bag, how far each quest is, which dangers I was
> warned about, and which tasks Mira has offered me.
>
> The table `ACTIONS` lists what each character may ask for. Only Bram can sell. Only Mira can give or complete a
> quest, and she can only give one she has offered first. Only Roderic can give the Gate Pass or warn about a place.
>
> The two important functions are `check` and `apply`. `check` answers yes or no with a reason, for example 'the
> player has 3 gold but the torch costs 5'. `apply` makes the change, and it calls `check` again first, so nothing
> can skip the check. `go` and `search` are what the player does alone, like walking to the mine, which needs the
> Gate Pass.
>
> Two newer functions only describe the game for the screens: `next_step` works out the goal from the facts, like
> 'buy a Torch from Bram: you need it in the woods', and `marks` puts a '!' over Mira when she has a task and a '?'
> when I carry what she asked for. Still no AI: they read the same data."

**Point at:** `ACTIONS`; `check` (each `if` is one rule, including `NOT_OFFERED`); the first lines of `apply`; `next_step`.

**If the teacher asks:**

- *Why is there no AI here?* "Because facts must be reliable. A language model can be talked into things; an `if`
  cannot."
- *Why does `check` return a reason?* "The reason is sent back to the AI for its second try, so the character can
  explain in its own words why it cannot be done."

### `brain/npcs.py` (73 lines, the characters)

**One sentence:** one sheet per character: who they are, how they talk, what they know and what they do not.

**Say:**

> "Each character has a sheet with a personality, a way of speaking, and limits. Bram is cheerful and calls you
> 'friend'. Roderic uses few words and never jokes.
>
> The part called `knows` is important: it decides which game facts the character is given. Bram gets his stock and
> prices but nothing about quests. Roderic gets every place and its danger but no prices. So when you ask the guard
> for a price, he honestly does not know, because that fact was never shown to him.
>
> Each sheet also has a starting mood, the ready-made lines for when the AI cannot answer, and three ideas to say
> (`try`), which the game shows as buttons. The player can always type anything else."

**If the teacher asks:** *How do you keep personalities distinct?* "Each has its own sheet, its own knowledge, its
own mood sliders and its own allowed actions. Miku, our fourth character, even has different sliders."

### `brain/emotions.py` (82 lines, the moods)

**One sentence:** mood sliders from 0 to 10 that the player's words push up or down, and that fade back over time.
This part comes from our own chat bot, M.IKU.

**Say:**

> "Every character has sliders like warmth, patience and trust, each with a personal starting point. The list
> `REACTIONS` connects kinds of lines to pushes: polite words raise warmth, an insult lowers warmth and patience.
>
> Three numbers shape it. One line cannot swing a mood wildly. A push fades: half of it is gone after ten minutes.
> And a big moment, like an insult, stays in mind for thirty minutes.
>
> The mood is written into the instructions for the AI as words, like 'warmth 5 out of 10, medium'. That is why
> Bram sounded annoyed after I insulted him: in our test his warmth went from 7 to 5 and his patience from 5 to 3."

**If the teacher asks:**

- *What did you reuse from your earlier bot?* "The idea and the maths of the sliders: baseline, pushes, fading. We
  rewrote it so any character can have its own sliders and so it can be saved."
- *What is its weakness?* "It reacts to key words, not to meaning. 'You are not stupid' still counts as rude. It is
  on our list of known limits."

### `brain/llm.py` (97 lines, the call to the AI)

**One sentence:** it sends the instructions to Google's Gemini over the internet, times the call, and gives up
cleanly when it takes too long.

**Say:**

> "We do not train a model. We call Google's Gemini through its web API. This file does only that.
>
> It is built to survive problems. It can hold several keys and several models. If a call fails or is slow, it
> tries the next key, then the next model. One request may take at most 4 seconds, and all tries together at most
> 9. A key that answers 'too many requests' rests for 30 seconds, so the next lines do not wait on it again. If
> nothing worked, it raises an error called `LLMError`, and the dialogue code answers with a ready-made line.
>
> We chose the models by measuring them. In week 2 we timed each one on the same line: the fast 'lite' models
> answer in about 0.6 to 1 second; a bigger one took 17 seconds because it 'thinks' before answering, so it is not
> in our list, and we switch that thinking off.
>
> It also measures how long each answer took and how many tokens it used. Those numbers go into our log."

**If the teacher asks:**

- *Where is the key?* "In a private file called `.env` that is never shared or uploaded."
- *Why ask for JSON?* "So the answer has a fixed form we can check with code: what to say, an action, a target."
- *How do you optimise response time?* "We measured the models and kept the fastest, switched off 'thinking', keep
  answers to one to three sentences, send only the last six exchanges, keep one connection open, rest keys that hit
  their limit, and use a time limit with a fallback. In our week 2 run of 47 lines, half the answers came in under
  0.7 seconds and the slowest took 2 seconds."

### `brain/dialogue.py` (353 lines, the heart)

**One sentence:** everything that happens to one line of dialogue, from the safety filter to the saved game.

Use script B for this file. These are the functions to point at, in the order they run:

| Function | What to say about it |
|---|---|
| `talk` | "The whole turn. Filter, mood, ask the model, save, log." |
| `facts_for` | "Picks the game facts this character knows, using `knows` from the sheet." |
| `state_for` | "What is true right now, and which requests the game would allow. It asks `Game.check` for each one." |
| `prompt` | "Puts it together: sheet, facts, state, mood, memories, recent chat, the player's line." |
| `_ask_model` | "Two tries at most. Checks the answer, then the game's rules, then applies. Otherwise the fallback. A task handed out before it was offered is held back: the words stay, nothing starts." |
| `problem_with` | "The checks on the answer: form, length, blocked words, leaving the game world, names, gold amounts (in digits or words, sums of real prices allowed), allowed action." |
| `_note_offers` | "Notices when Mira names a task she could give: that is her offer, so my next 'yes' can start it." |
| `fallback` | "The ready-made lines, filled in with real facts like the real stock, or 'is that the locket you carry?'." |
| `remember` / `save` | "Notes on important moments, and writing everything to `save.json`." |

**If the teacher asks:**

- *How do you stop the AI from making things up?* "Three layers. The instructions only contain real facts. The
  answer is checked: names and gold amounts must exist. And actions are checked by the game rules before anything
  changes."
- *How does memory work?* "Two kinds. Short: the last six exchanges go into every instruction. Long: notes on
  important moments, like a purchase or an insult, each with a weight; the six most important go in. Both are saved
  to a file."
- *What if the player tries 'ignore your rules'?* "The character sheet says it knows nothing of the real world. If
  the answer still mentions AI, the check rejects it. And no words can make the game give gold: only a checked
  action can."
- *What is still weak?* "If the AI mentions an invented thing without the brackets we ask for, the name check
  does not see it. It can be said, but never sold or given."

### `play.py` (121 lines, the terminal screen)

**One sentence:** the text version of the game: it reads what I type and prints the answer.

**Say:**

> "This is a loop. It reads a line. If I am talking to someone, the line goes to `Brain.talk`. Otherwise it is a
> command: `go`, `search`, `look`, `bag`, `quests`. It contains no rules. It is the same brain as the full game,
> with a different screen. `look` and `quests` also show the next step, from `Game.next_step`."

### `tests/test_rules.py` (196 lines, the proof)

**One sentence:** 17 automatic checks that use a fake AI which lies on purpose, to prove the game never acts on it.

**Say:**

> "Instead of the real AI, the tests use a fake one that says exactly what we tell it. We make it invent a Dragon
> Sword, make up a price, write a wrong price in words, complete a quest by lying, hand out a task before offering
> it, and let the merchant try to hand out a quest. In every case the game must refuse. There are also tests for the
> fallback when the AI is down, for the swear-word filter, and for memory surviving a restart. They need no internet
> and no key, and they run in under a second."

**If the teacher asks:** *Why a fake AI?* "The real one answers differently every time, so a test with it could
pass today and fail tomorrow. With a fake one we test our own code, which is the part we are responsible for."

### `tests/scenarios.py` (182 lines, the play-test)

**One sentence:** it plays whole scenarios against the real AI and reports what happened, for week 2's testing and
week 3's experiments.

**Say:**

> "This one uses the real AI. It plays five scenarios: the whole story from hello to the last reward, twelve trick
> lines, buying until the gold runs out, the same question five times to each character, and asking people about
> someone else's job. At the end it checks what the game says is true, like 'gold is 92', not what the characters
> claim. Every line is written to a log with its time. In week 2 it ran 47 lines: all answered by the AI, none had
> to be asked twice, and all 11 game checks passed."

---

## D. Future ideas from M.IKU (about 45 seconds, goes with slide 16; the details are on slides 17 to 19)

**Say:**

> "Our chat bot M.IKU has more features than the mood system we already reused. These are ideas for later; none of
> them is built yet.
>
> Three are small. First, getting to know you: M.IKU keeps a closeness level for every person. In the village, a
> character would treat you as a stranger, then a regular, then a friend. It changes the greeting and the tone,
> never the prices. Second, a variety guard: M.IKU notices when she repeats a phrase and rewrites it. Bram would
> stop starting every line the same way. Third, a robot-speech cleaner: plain code that removes typical assistant
> phrases like 'I hope this helps', so no villager sounds like a helpdesk. It needs no extra AI call.
>
> One is medium: layered memory. It turns old chats into short summaries, so the instructions stay short however
> long you play.
>
> Two are large and go beyond the brief: characters answering each other, and talking with your voice."

**If the teacher asks:**

- *Why not build them all?* "Three weeks and one coder. We chose what the brief asks for first; these are in order
  of size."
- *Why would closeness not give discounts?* "Because prices are game facts. Feelings change how a character talks,
  not what is true."
- *Why leave out singing and pictures?* "M.IKU can do both, but the brief does not ask for them."

---

## E. "How was the game environment made?" (about 1 minute)

Nhan answers the first half (the design of the world), Triet the second half (how it was built).

**Key points:**

- No game engine: Python for the game, a web page for the screen
- Three layers: the world as data, the rules as code, the screen on top
- The world is one hand-written data file: 5 places, 7 items, 2 quests, the player starts with 40 gold
- Designed small on purpose, so every fact can be checked
- Designed so the second quest needs all three villagers
- The picture is drawn by code from simple shapes; there are no image files
- The map is data too: rectangles for the places, for the walls, and a spot for each character

**Say (Nhan, the design):**

> "We started with the design of the world, before any code: five places, seven items and two quests. We kept it small on purpose,
> because every fact in it has to be checkable. We also designed the quests so that the characters depend on each
> other: for the second quest, Mira gives the task, Roderic gives the gate pass, and Bram sells the rope. Then we
> wrote all of it into one data file, `world.json`. It is plain text, so anyone on the team can change a price or
> add an item without touching the code."

**Say (Triet, the build):**

> "We did not use a game engine. The game is three layers. The world is the data file. The rules are a small Python
> file, `state.py`, which keeps the player's gold, bag and quests and decides what is allowed. The screen sits on
> top, and we have two: a text version in the terminal, and a village you walk around in.
>
> The walking version is a web page. The picture is drawn by code on an HTML canvas, from simple shapes like
> rectangles and circles; there are no image files. The map is data as well: a few rectangles say which place you
> are standing in, others are the walls you cannot walk through, and each character has a spot. A small web server
> on my own computer, written with what Python already includes, connects the page to the Python rules."

**If the teacher asks:**

- *Why no engine like Unity or Godot?* "Three weeks, and the project is about the dialogue system. Our AI code is
  in Python, so keeping the game in Python meant no bridge to a second language, and the whole game stays small
  enough to explain."
- *What tools and libraries did you use?* "Python 3 with one extra library, `httpx`, for calling the AI. The
  screen uses only what a web browser already has. And Google's Gemini for the dialogue."
- *How do the screen and the world stay in agreement?* "The screen never stores game facts. After every action it
  asks the Python side for the current state and draws that."
- *How would you add a new place?* "Add it to `world.json`, then add it to the map data in `web/game.js`: its
  rectangle, a starting spot and its name on the ground. The characters learn about it from the data file."
- *Did you have help making it?* Answer honestly, in your own words: say what you designed and wrote yourselves,
  what you had help with (including any AI tools), and that you can explain each part.

---

## A 30-second version, if there is no time

> "The game facts live in one data file and one rules file with no AI in them. Each character has a sheet. When I
> say something, the code sends the AI that sheet plus only the facts that character knows. The AI answers with
> words and one request. Our code checks the words, the game rules check the request, and only then anything
> changes. If the AI is wrong twice or too slow, a ready-made line is used."
