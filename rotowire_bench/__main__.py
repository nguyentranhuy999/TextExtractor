import argparse
import json
import os
import sys


def main():
    # Upstream GLiNER2 1.2.4 constructs fields through a set; fix its order across processes.
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.execve(sys.executable,[sys.executable,"-m","rotowire_bench",*sys.argv[1:]],{**os.environ,"PYTHONHASHSEED":"0"})
    parser=argparse.ArgumentParser(description="Khảo sát RotoWire GLiNER2 / GPT 5.5")
    commands=parser.add_subparsers(dest="command",required=True)
    for name in ("prepare","validate","preflight","pilot","run"):
        p=commands.add_parser(name)
        p.add_argument("--config",default="configs/main.yaml")
        if name in ("preflight","pilot","run"):
            p.add_argument("--local-files-only",action="store_true")
        if name in ("pilot","run"):
            p.add_argument("--run-id")
            p.add_argument("--resume",action="store_true")
            p.add_argument("--max-requests","--max-tasks",dest="max_requests",type=int)
            p.add_argument("--max-seconds",type=float)
        if name == "pilot":
            p.add_argument("--split",choices=["validation"],default="validation")
            p.add_argument("--limit",type=int,default=3)
        if name == "run":
            p.add_argument("--dry-run",action="store_true")
    for name in ("evaluate","report"):
        p=commands.add_parser(name);p.add_argument("--run-dir",required=True)
    p=commands.add_parser("export-tasks")
    p.add_argument("--config",default="configs/main.yaml")
    p.add_argument("--out",required=True)
    p=commands.add_parser("import-results")
    p.add_argument("--run-dir",required=True)
    p.add_argument("--from-dir",required=True)
    p.add_argument("--local-files-only",action="store_true")
    p=commands.add_parser("gliner-validation")
    p.add_argument("--config",default="configs/main.yaml")
    p.add_argument("--out",required=True)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--report-only",action="store_true")
    p=commands.add_parser("hybrid-validation")
    p.add_argument("--config",default="configs/main.yaml")
    p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,choices=[3,30],default=30)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--report-only",action="store_true")
    p=commands.add_parser("snippet-comparison")
    p.add_argument("--config",default="configs/main.yaml")
    p.add_argument("--out",required=True)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--max-pairs",type=int,default=30)
    p.add_argument("--report-only",action="store_true")
    p=commands.add_parser("hybrid-test")
    p.add_argument("--config",default="configs/main.yaml")
    p.add_argument("--out",required=True)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--max-tasks",type=int,help="Maximum new sample tasks this invocation; keep all 200 IDs in the campaign")
    p.add_argument("--report-only",action="store_true")
    args=parser.parse_args()
    try:
        if args.command == "hybrid-test":
            from .config import load_config
            from .hybrid_validation import run_test,report_hybrid
            result=report_hybrid(args.out) if args.report_only else run_test(load_config(args.config),args.out,resume=args.resume,max_tasks=args.max_tasks)
        elif args.command == "snippet-comparison":
            from .config import load_config
            from .snippet_comparison import run_comparison,report_comparison
            result=report_comparison(args.out) if args.report_only else run_comparison(load_config(args.config),args.out,resume=args.resume,max_pairs=args.max_pairs)
        elif args.command == "hybrid-validation":
            from .config import load_config
            from .hybrid_validation import run_validation,report_validation
            result=report_validation(args.out) if args.report_only else run_validation(load_config(args.config),args.out,limit=args.limit,resume=args.resume)
        elif args.command == "gliner-validation":
            from .config import load_config
            from .gliner_validation import run_validation,report_validation
            result=report_validation(args.out) if args.report_only else run_validation(load_config(args.config),args.out,resume=args.resume)
        elif args.command == "export-tasks":
            from .config import load_config
            from .external_tasks import export_tasks
            result=export_tasks(load_config(args.config),args.out)
        elif args.command == "import-results":
            from .external_tasks import import_results
            result=import_results(args.run_dir,args.from_dir,local_files_only=args.local_files_only)
        elif args.command in ("evaluate","report"):
            from .reporting import evaluate,report
            result=(evaluate if args.command == "evaluate" else report)(args.run_dir)
        else:
            from .config import load_config
            from .data import prepare,prepared
            from .runner import dry_run,preflight,run
            from pathlib import Path
            config=load_config(args.config)
            if args.command == "prepare":
                manifest=prepare(config)
                result=dict(n_test=manifest["n_test"],selected_test=len(manifest["samples"]),selected_validation=len(manifest["validation_samples"]))
            elif args.command == "validate":
                inputs,_,manifest=prepared(config)
                validation,_,_=prepared(config,"validation")
                report,_,_=preflight(config,Path(config["dataset"]["prepared_dir"])/"preflight.json")
                result=dict(status="valid",n_test=len(inputs),n_validation=len(validation),overlap=manifest["overlap_check"],preflight=report)
            elif args.command == "preflight":
                result,_,_=preflight(config,Path(config["dataset"]["prepared_dir"])/"preflight.json",load_models=True,local_files_only=args.local_files_only)
            elif args.command == "run" and args.dry_run:
                result=dry_run(config)
            else:
                if args.max_requests is not None and args.max_requests < 0:
                    raise ValueError("max-requests must be nonnegative")
                if args.max_seconds is not None and args.max_seconds <= 0:
                    raise ValueError("max-seconds must be positive")
                result=run(config,run_id=args.run_id,resume=args.resume,split="validation" if args.command == "pilot" else "test",limit=args.limit if args.command == "pilot" else None,max_requests=args.max_requests,local_files_only=args.local_files_only,max_seconds=args.max_seconds)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as exc:
        print(f"Lỗi: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
