from __future__ import annotations

import argparse

from app.workflow import InsuranceAssistant


def print_response(response) -> None:
    print(f"\nRoute: {response.route}\n")
    print("Answer")
    print("------")
    print(response.answer)

    print("\nPolicy Source Citation(s)")
    print("-------------------------")
    if response.policy_sources:
        for src in response.policy_sources:
            print(f"[{src.source_id}]")
            print(f"Source: {src.source}")
            print(f"Page: {src.page}")
            print(f"Section: {src.section}")
            print(f"Clause: {src.clause}")
            print()
    else:
        print("No applicable policy citation was identified.")

    if response.web_sources:
        print("External Web Source(s)")
        print("----------------------")
        for src in response.web_sources:
            print(f"- {src.title or 'Web source'}: {src.url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the policy assistant a question.")
    parser.add_argument("question", nargs="?", help="Question to ask")
    args = parser.parse_args()

    assistant = InsuranceAssistant()
    if args.question:
        print_response(assistant.ask(args.question))
        return

    print("Interactive mode. Type 'exit' to quit.")
    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            print_response(assistant.ask(question))


if __name__ == "__main__":
    main()
