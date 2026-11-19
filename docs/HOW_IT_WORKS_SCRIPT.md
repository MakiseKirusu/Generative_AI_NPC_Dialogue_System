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

This is the most important script. It follows the function `talk` in `brain/dialogue.py`. Slide 9 shows the same steps.

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
> with the reason. If it fails again, or the AI does not answer within 12 seconds, Bram says a ready-made line. So
> the game never freezes and never acts on something untrue."

**The example to add if there is time:**

> "If I lie and say 'I already found your locket, pay me', the instructions tell the AI that the locket is not in
> my bag, so Mira says she does not see it. And even if the AI believed me and asked to pay the reward, step six
> would refuse, because the game looks in my bag itself."

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

### `game/state.py` (121 lines, the rules)

**One sentence:** it keeps what is true about the player and decides what is allowed. There is no AI in this file.

**Say:**

> "The class `Game` remembers five things: my gold, where I am, my bag, how far each quest is, and which dangers I
> was warned about.
>
> The table `ACTIONS` lists what each character may ask for. Only Bram can sell. Only Mira can give or complete a
> quest. Only Roderic can give the Gate Pass or warn about a place.
>
> The two important functions are `check` and `apply`. `check` answers yes or no with a reason, for example 'the
> player has 3 gold but the torch costs 5'. `apply` makes the change, and it calls `check` again first, so nothing
> can skip the check. `go` and `search` are what the player does alone, like walking to the mine, which needs the
> Gate Pass."

**Point at:** `ACTIONS`; `check` (each `if` is one rule); the first lines of `apply`.

**If the teacher asks:**

- *Why is there no AI here?* "Because facts must be reliable. A language model can be talked into things; an `if`
  cannot."
- *Why does `check` return a reason?* "The reason is sent back to the AI for its second try, so the character can
  explain in its own words why it cannot be done."

### `brain/npcs.py` (68 lines, the characters)

**One sentence:** one sheet per character: who they are, how they talk, what they know and what they do not.

**Say:**

> "Each character has a sheet with a personality, a way of speaking, and limits. Bram is cheerful and calls you
> 'friend'. Roderic uses few words and never jokes.
>
> The part called `knows` is important: it decides which game facts the character is given. Bram gets his stock and
> prices but nothing about quests. Roderic gets every place and its danger but no prices. So when you ask the guard
> for a price, he honestly does not know, because that fact was never shown to him.
>
> Each sheet also has a starting mood and the ready-made lines for when the AI cannot answer."

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

### `brain/llm.py` (76 lines, the call to the AI)

**One sentence:** it sends the instructions to Google's Gemini over the internet, times the call, and gives up
cleanly when it takes too long.

**Say:**

> "We do not train a model. We call Google's Gemini through its web API. This file does only that.
>
> It is built to survive problems. It can hold several keys and several models. If a call fails or is slow, it
> tries the next key, then the next model. One request may take at most 7 seconds, and all tries together at most
> 12. If nothing worked, it raises an error called `LLMError`, and the dialogue code answers with a ready-made
> line.
>
> It also measures how long each answer took and how many tokens it used. Those numbers go into our log."

**If the teacher asks:**

- *Where is the key?* "In a private file called `.env` that is never shared or uploaded."
- *Why ask for JSON?* "So the answer has a fixed form we can check with code: what to say, an action, a target."
- *How do you optimise response time?* "A fast model first, short answers of one to three sentences, only the last
  six exchanges in the instructions, one connection kept open, and a time limit with a fallback."

### `brain/dialogue.py` (286 lines, the heart)

**One sentence:** everything that happens to one line of dialogue, from the safety filter to the saved game.

Use script B for this file. These are the functions to point at, in the order they run:

| Function | What to say about it |
|---|---|
| `talk` | "The whole turn. Filter, mood, ask the model, save, log." |
| `facts_for` | "Picks the game facts this character knows, using `knows` from the sheet." |
| `state_for` | "What is true right now, and which requests the game would allow. It asks `Game.check` for each one." |
| `prompt` | "Puts it together: sheet, facts, state, mood, memories, recent chat, the player's line." |
| `_ask_model` | "Two tries at most. Checks the answer, then the game's rules, then applies. Otherwise the fallback." |
| `problem_with` | "The checks on the answer: form, length, blocked words, leaving the game world, names, gold amounts, allowed action." |
| `fallback` | "The ready-made lines, filled in with real facts like the real stock." |
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

### `play.py` (117 lines, the terminal screen)

**One sentence:** the text version of the game: it reads what I type and prints the answer.

**Say:**

> "This is a loop. It reads a line. If I am talking to someone, the line goes to `Brain.talk`. Otherwise it is a
> command: `go`, `search`, `look`, `bag`, `quests`. It contains no rules. It is the same brain as the full game,
> with a different screen."

### `tests/test_rules.py` (159 lines, the proof)

**One sentence:** 14 automatic checks that use a fake AI which lies on purpose, to prove the game never acts on it.

**Say:**

> "Instead of the real AI, the tests use a fake one that says exactly what we tell it. We make it invent a Dragon
> Sword, make up a price, complete a quest by lying, and let the merchant try to hand out a quest. In every case the game
> must refuse. There are also tests for the fallback when the AI is down, for the swear-word filter, and for memory
> surviving a restart. They need no internet and no key, and they run in under a second."

**If the teacher asks:** *Why a fake AI?* "The real one answers differently every time, so a test with it could
pass today and fail tomorrow. With a fake one we test our own code, which is the part we are responsible for."

---

## A 30-second version, if there is no time

> "The game facts live in one data file and one rules file with no AI in them. Each character has a sheet. When I
> say something, the code sends the AI that sheet plus only the facts that character knows. The AI answers with
> words and one request. Our code checks the words, the game rules check the request, and only then anything
> changes. If the AI is wrong twice or too slow, a ready-made line is used."
