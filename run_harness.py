import argparse
from harness.orchestrator import ChiefOrchestrator

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--branch", choices=["app", "marketing", "auto"], default=None, help="Branch")
    args = parser.parse_args()
    
    orchestrator = ChiefOrchestrator()
    context, verdict = orchestrator.process_task(args.task, args.branch)
    print(f"Task processing finished. Status: {context.state}, Verdict: {verdict}")

if __name__ == "__main__":
    main()
