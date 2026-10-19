"""Run an explicit verification contract and emit a local execution receipt."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.execution_evidence import ExecutionEvidenceStore, EvidenceError, normalize_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True)
    parser.add_argument('--contract', required=True, help='JSON command contract')
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    try:
        command = normalize_command(json.loads(Path(args.contract).read_text(encoding='utf-8')))
        receipt = ExecutionEvidenceStore(args.store).run(args.task_id,args.actor,args.spec_sha256,args.manifest_sha256,
            command['argv'],command['cwd'],command['ac_ids'],command['timeout'],command['id'],command['report'],command['browser'])
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0 if receipt['status'] == 'PASS' else 1
    except (EvidenceError,OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
