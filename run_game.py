"""The full game: a little village you walk around in, in your web browser. Same brain and same saved game as the
terminal version (play.py); only the screen is different.

    python run_game.py            start the game and open it in the browser
    python run_game.py --new      start over
    python run_game.py --port 9000 --no-browser

This file is a small web server on your own computer (nobody else can reach it). The page in web/ draws the
village and calls these addresses:
    GET  /api/world    the map's names (places, items with what they are, quests, characters and ideas to say); never changes
    GET  /api/state    the game right now (gold, bag, quests, the next step, signs over heads, moods, recent chat)
    POST /api/talk     {"npc": "bram", "text": "hello"}   → the character's answer + the new state
    POST /api/go       {"place": "market"}                 → move to a place (the game may refuse)
    POST /api/search   {}                                  → search where you stand
    POST /api/reset    {}                                  → new game
"""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brain.dialogue import Brain
from brain.llm import GeminiLLM
from brain.npcs import NPCS
from game.state import WORLD

HERE = Path(__file__).parent
WEB = HERE / "web"
SAVE = HERE / "save.json"
FILES = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/game.js": ("game.js", "text/javascript")}
LOCK = threading.Lock()  # one thing at a time: the brain is shared by every request
LLM = GeminiLLM()


def new_brain() -> Brain:
    return Brain(LLM, save_path=SAVE, log_path=HERE / "logs" / "turns.jsonl")


BRAIN = new_brain()
PEOPLE = {k: {"name": n["name"], "place": n["place"]} for k, n in NPCS.items()}


def world() -> dict:
    return {"village": WORLD["village"],
            "places": {k: {"name": p["name"], "danger": p["danger"]} for k, p in WORLD["places"].items()},
            "items": {k: {"name": i["name"], "about": i["about"], "price": i["price"]} for k, i in WORLD["items"].items()},
            "quests": {k: {"name": q["name"], "summary": q["summary"], "reward": q["reward_gold"]} for k, q in WORLD["quests"].items()},
            "npcs": {k: {"name": n["name"], "role": n["role"], "place": n["place"], "try": n.get("try", [])} for k, n in NPCS.items()}}


def state() -> dict:
    """Everything here comes from the game's facts; the screen only draws it."""
    return {"game": BRAIN.game.to_dict(), "has_key": bool(LLM.keys),
            "next": BRAIN.game.next_step(PEOPLE), "marks": BRAIN.game.marks(),
            "moods": {n: BRAIN.emotions[n].sliders() for n in NPCS},
            "history": {n: BRAIN.history[n][-3:] for n in NPCS}}


def act(path: str, body: dict) -> dict:
    """One request from the game screen. Everything goes through the same rules as the terminal version."""
    global BRAIN
    if path == "/api/talk":
        npc = str(body.get("npc"))
        if npc not in NPCS:
            return {"error": "no such character"}
        return {"reply": BRAIN.talk(npc, str(body.get("text", ""))), **state()}
    if path == "/api/go":
        ok, message = BRAIN.game.go(str(body.get("place")))
        BRAIN.save()
        return {"ok": ok, "message": message, **state()}
    if path == "/api/search":
        ok, message = BRAIN.game.search()
        BRAIN.save()
        return {"ok": ok, "message": message, **state()}
    if path == "/api/reset":
        SAVE.unlink(missing_ok=True)
        BRAIN = new_brain()
        return state()
    return {"error": "unknown address"}


class Handler(BaseHTTPRequestHandler):
    def send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, data: dict, code: int = 200) -> None:
        self.send(code, json.dumps(data).encode(), "application/json")

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in FILES:
            name, kind = FILES[path]
            self.send(200, (WEB / name).read_bytes(), kind)
        elif path == "/api/world":
            self.json(world())
        elif path == "/api/state":
            with LOCK:
                self.json(state())
        elif path == "/favicon.ico":
            self.send(204, b"", "image/x-icon")  # no icon: say so without an error in the browser's console
        else:
            self.send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        # only our own page sends JSON; this stops other websites from poking the game
        if self.headers.get("Content-Type") != "application/json":
            self.json({"error": "bad request"}, 400)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            self.json({"error": "bad request"}, 400)
            return
        with LOCK:
            result = act(self.path, body if isinstance(body, dict) else {})
        self.json(result, 400 if "error" in result else 200)

    def log_message(self, *_) -> None:  # keep the terminal quiet
        pass


def main() -> None:
    global BRAIN
    args = sys.argv[1:]
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8765
    if "--new" in args:
        SAVE.unlink(missing_ok=True)
        BRAIN = new_brain()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"Port {port} is already in use. Is the game already running in another window? "
                 f"Close it, or start with:  python run_game.py --port {port + 1}")
    url = f"http://127.0.0.1:{port}/"
    print(f"Maple Hollow is running at {url}\nKeep this window open while you play. Press Ctrl+C here to stop.")
    if not LLM.keys:
        print("!! No AI key found (.env): the characters can only say their ready-made lines.")
    if "--no-browser" not in args:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSaved. See you next time!")


if __name__ == "__main__":
    main()
