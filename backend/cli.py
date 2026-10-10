"""Command-line demo of the PetCare AI agent graph (the equivalent of your Trip Concierge main.py).

    python cli.py                 # runs sample requests for Bruno the Labrador
    python cli.py --interactive   # chat with the agents yourself
    python cli.py --rules-only    # skip Ollama and use the built-in rules
Nothing is saved except the JSON reports in reports/.
"""
import argparse
import os
import sys

SAMPLE_PET = {"id": "demo", "name": "Bruno", "species": "dog", "breed": "Labrador", "age": 3,
              "weight_kg": 24, "activity_level": "moderate"}
SAMPLE_REQUESTS = [
    "Create a weekly care plan for Bruno.",
    "I won't be home on Wednesday. Change Bruno's exercise plan.",
    "Next vet appointment 20 October, grooming every 4 weeks.",
    "What should I prepare before his vet appointment?",
    "Bruno keeps vomiting and won't eat.",
]


def run(graph, message, pet, plan):
    result = graph.invoke({"user_message": message, "pet_id": pet["id"], "pet": pet, "previous_plan": plan, "trace": []})
    print(f"\n> {message}")
    print(f"  Intent: {result['intent']}")
    print("  Agent path:")
    for step in result["trace"]:
        print(f"    - {step['agent']}: {step['summary']}")
    print("\n" + result["reply"])
    print(f"\n  Report saved: reports/{result['report']['id']}.json")
    return result.get("care_plan") or plan


def main():
    parser = argparse.ArgumentParser(description="PetCare AI agent demo")
    parser.add_argument("--interactive", action="store_true", help="type your own requests")
    parser.add_argument("--rules-only", action="store_true", help="run without Ollama")
    args = parser.parse_args()
    if args.rules_only:
        os.environ["PETCARE_USE_LLM"] = "0"

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from graph.petcare_graph import GRAPH  # imported after the env var is set

    plan = None
    if args.interactive:
        print("Pet: Bruno, 3-year-old Labrador. Blank line to quit.")
        while True:
            try:
                msg = input("\n> ").strip()
            except EOFError:
                break
            if not msg:
                break
            plan = run(GRAPH, msg, SAMPLE_PET, plan)
    else:
        for msg in SAMPLE_REQUESTS:
            plan = run(GRAPH, msg, SAMPLE_PET, plan)


if __name__ == "__main__":
    main()
