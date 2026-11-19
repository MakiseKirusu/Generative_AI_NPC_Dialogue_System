"""Start Maple Hollow and choose how to play. Both ways use the same characters, rules and saved game.

    python start.py
"""
import sys


def ask(question: str, answers: tuple[str, ...]) -> str:
    while True:
        answer = input(question).strip().lower()
        if answer in answers:
            return answer
        print("Please type one of: " + ", ".join(a for a in answers if a))


def main() -> None:
    print("\n=== Maple Hollow ===\n\n"
          "  1  Terminal demo   text only, in this window\n"
          "  2  Full game       a village you walk around in, in your web browser\n"
          "  q  Quit\n")
    choice = ask("Your choice (1, 2 or q): ", ("1", "2", "q"))
    if choice == "q":
        return
    fresh = ask("Start a new game? Type  y  for new, or just press Enter to continue the saved one: ", ("y", "n", "")) == "y"
    sys.argv = [sys.argv[0]] + (["--new"] if fresh else [])
    print()
    if choice == "1":
        import play
        play.main()
    else:
        import run_game
        run_game.main()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
