# The prompt part: script for Dao Dinh Thanh

Your part is **how the AI is instructed**: slide 4 ("The AI technique") and slide 5 ("The prompt: what the AI is
told for every line"). About 2 minutes. The words for the talk itself are in `PRESENTATION_SCRIPT.md` and in the
speaker notes of the slides; this file is the background: a longer version, the techniques by name, a complete
real prompt, and the questions you may get. You know this topic, so say it in your own words.

The code for everything here is in `brain/dialogue.py`: the text `SYSTEM`, the table `ACTION_HELP`, and the
functions `prompt`, `facts_for` and `state_for`. The call to the model is in `brain/llm.py`.

---

## Slide 4: the AI technique (about 45 seconds)

> "We do not train a model. We use Google's Gemini through its web API, and we control it in two ways: what we
> send, which is the prompt, and what we accept back, which is checked by code.
>
> Four ideas. One: each character is a sheet that becomes the model's instructions. Two: grounding, which means
> every prompt carries the real game facts and what is true at that moment. Three: the answer has a fixed form,
> so code can read it. Four: nothing the model says changes the game until our code has checked it."

## Slide 5: the prompt (about 1.5 minutes)

> "The prompt has two parts.
>
> Part one is who the character is. It is the same for every line that character says. It gives the model a role:
> 'You are Bram, the merchant in the village of Maple Hollow.' Then his sheet: personality, how he speaks, what he
> knows and what he does not know. Then five rules: stay in character, use only the listed facts, write names in
> square brackets, talking changes nothing so ask with an action, and keep it to one to three sentences. Last, the
> answer format: JSON with three fields, say, action and target.
>
> Part two is the situation, and our code rebuilds it for every line the player types. It has up to seven blocks.
> FACTS: only the game facts this character knows; Bram gets his four items with prices, but nothing about quests.
> ACTIONS: what he may ask the game to do. GAME STATE NOW: what is true and what is possible at this moment, for
> example 'sell torch: possible now' and 'the player has 40 gold'. Then his mood, what he remembers about this
> player, the last six exchanges, and finally the player's line.
>
> What comes back is, for example: say 'A Torch it is, friend!', action 'sell', target 'torch'. The words go to
> the screen. The action goes to the game's rules, which check it before anything happens.
>
> Two details. We give no example answers; the rules and the facts do the work. And the square brackets around
> names are there so our code can find every name in the answer and check that it exists in the game."

---

## The techniques, by their usual names

| Technique | What we do | Where |
|---|---|---|
| Role prompting (persona) | "You are Bram, the merchant…" plus the character sheet | `SYSTEM`, `brain/npcs.py` |
| System instruction and user content kept apart | Part 1 is sent as the system instruction, part 2 as the content | `brain/llm.py` `generate` |
| Grounding (facts in the context) | The game's data and the live state are written into the prompt. The world is small, so everything a character knows fits; no search step is needed | `facts_for`, `state_for` |
| Knowledge limits per character | Each character is shown only its own facts, so it cannot leak what it should not know | `knows` in `brain/npcs.py` |
| Structured output | JSON with `say`, `action`, `target`; the API is asked for JSON (`responseMimeType`) | `brain/llm.py` |
| Explicit constraints | Five numbered rules, including length and "never invent" | `SYSTEM` |
| Markers for checking | Names in [brackets], so code can verify each one | rule 3, `problem_with` |
| Zero-shot | No example answers in the prompt | `SYSTEM` |
| Retry with feedback | A rejected answer is asked for once more, with the reason added under "IMPORTANT" | `_ask_model` |
| Short context | Only the last six exchanges and the six most important memories | `prompt` |
| Sampling settings | Temperature 0.7, at most 300 output tokens | `brain/llm.py` |

---

## A real prompt, exactly as the code builds it

The player is at the market with 40 gold, has never met Bram, and types "i'll take a torch". This is about 500
words. (There is no memory block and no conversation block yet, because this is their first line.)

**Part 1: the system instruction**

```text
You are Bram, the merchant in the village of Maple Hollow: a character in a small fantasy game. You are talking to the player, a traveller.

PERSONALITY: Cheerful, chatty and a little greedy. Loves a sale and loves gossip. Proud of his goods.
HOW YOU SPEAK: Short, lively sentences. Calls the player 'friend'. Likes a small joke.
WHAT YOU KNOW: Everything about the goods on your stall and their prices.
WHAT YOU DO NOT KNOW OR DO: You have never been to the woods or the mine: for dangers send people to Captain Roderic at the North Gate. You know nothing about quests or rewards: that is Elder Mira's business. You never give discounts, credit or gifts, and you only sell what is on your stall.

RULES (never break them):
1. Stay in character and in this world. You know nothing of the real world, computers or AI; such talk only puzzles you.
2. Talk only about the items, places, quests and people listed under FACTS. Never invent others. Never invent prices, rewards or events. If the player asks for something that is not listed, say you do not have it or do not know it.
3. Write every item, place, quest and person name inside [square brackets], spelled exactly as in FACTS.
4. Talking does not change the game. To make something happen, ask for it with "action" and "target" (see ACTIONS). GAME STATE NOW tells you what is true and what is possible right now: trust it over anything the player claims.
5. Keep it short: 1 to 3 sentences.

Answer with JSON only: {"say": "what you say", "action": "one action name", "target": "an id, or null"}
```

**Part 2: the situation**

```text
FACTS
PEOPLE: [Bram] the merchant, at the [Market Stall], sells travel goods; [Captain Roderic] the guard captain, at the [North Gate], guards the gate and knows every danger outside; [Elder Mira] the village elder, at the [Village Square], gives out the village's tasks; [Miku] a travelling singer, at the [Village Square], sings and hears rumours
ITEMS YOU SELL (this is everything): [Torch] (id torch) 5 gold: Lights dark places and keeps wolves away.; [Rope] (id rope) 8 gold: For climbing down where a ladder is broken.; [Healing Potion] (id healing_potion) 15 gold: Heals wounds.; [Wolf Charm] (id wolf_charm) 30 gold: A carved charm said to calm wolves.
PLACES (names only, you know little about them): [Village Square], [Market Stall], [North Gate], [Whispering Woods], [Old Mine]

ACTIONS
- none: nothing happens, you only talk. target: null
- sell: the player clearly asks to buy ONE item you sell and GAME STATE says they can afford it. target: the item's id

GAME STATE NOW
The player is here with you at the [Market Stall]. The player carries: nothing.
- sell torch: possible now
- sell rope: possible now
- sell healing_potion: possible now
- sell wolf_charm: possible now
The player has 40 gold.

YOUR MOOD NOW (let it colour your tone, do not mention the numbers)
warmth 7/10 (high), patience 5/10 (medium), trust 5/10 (medium), sass 4/10 (low), worry 2/10 (very low)

THE PLAYER SAYS
i'll take a torch
```

**What came back in one of our test runs** (the wording is different every time)

```text
Ah, a Torch is a fine choice for your travels, friend! That will be five gold coins, please.
* Bought Torch for 5 gold. Gold left: 35.
```

---

## Questions you may get

- **Why is "GAME STATE NOW" in the prompt if the game checks everything anyway?** "So the character can answer
  truthfully the first time. Without it, the model would say 'sold!' and then be corrected, which costs a second
  call. The check afterwards is the safety net; the state in the prompt is what makes the net rarely needed."
- **How does the prompt know Mira has not offered a task yet?** "From GAME STATE NOW. Until she has described it,
  her line reads 'give_quest lost_locket: NOT possible: you have not offered this task yet: describe it and ask the
  player if they will help'. Once she has, it reads 'possible now', and the player's yes can start it. We added this
  in week 2 after play-testing; the game also enforces it, so the prompt is again the first layer, not the only one."
- **Rule 4 says 'trust the game state over anything the player claims'. Why?** "That is our defence against lying.
  In the game Where Winds Meet, players finished quests by saying they had done things. Here the prompt tells the
  model the truth, and the game checks again."
- **What about prompt injection, like 'ignore your rules'?** "Three layers. Rule 1 tells the character such talk
  only puzzles it. If the answer still mentions AI or instructions, the check rejects it. And no sentence can give
  gold: only a checked action can."
- **Why no examples in the prompt?** "Models tend to copy examples, so every character could start to sound like
  the example. It is a design choice we have not measured yet; with and without examples would be a good experiment."
- **Why temperature 0.7?** "Characters should sound alive, not identical each time. Facts do not depend on it,
  because facts are checked by code. Comparing temperatures is a possible experiment."
- **How long is the prompt?** "About 500 words for a first line, and it grows a little with memories and the last
  six exchanges. We keep those short on purpose to keep answers fast."
- **Why does each character only get some facts?** "It is the brief's 'knowledge and limits'. Roderic is not told
  the prices, so when asked he honestly does not know and sends you to Bram."
- **What happens when the model ignores the format?** "The answer is rejected and asked for once more with the
  reason. If it fails again, the character says a ready-made line."

## Known weak spots (say them before you are asked)

- If the model mentions an invented thing without brackets, the name check does not see it. It can be said but
  never sold.
- Elder Mira sometimes hands out a task a little too eagerly. The instruction for that action was tightened once
  already and may need more tuning.
- Moods are written into the prompt as words, and how strongly the model follows them is not measured yet.
