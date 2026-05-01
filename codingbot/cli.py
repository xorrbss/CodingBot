"""argparse 기반 codingbot CLI."""
import argparse
import sys
from typing import List, Optional

from codingbot import config, install_hooks, paths, runner, state


def _cmd_run(args: argparse.Namespace) -> int:
    return runner.run(args.prompt)


def _cmd_stop(args: argparse.Namespace) -> int:
    paths.ensure_home()
    paths.stop_signal_file().touch()
    print("[codingbot] stop signal set. Active runs will exit at next safe point.")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    state.clear_stop_signal()
    print("[codingbot] stop signal cleared.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    s = state.read()
    cfg = config.load()
    print("=== CodingBot Status ===")
    print(f"home: {paths.codingbot_home()}")
    print(f"stop signal: {'YES' if paths.stop_signal_file().exists() else 'no'}")
    print(f"runner lock: {'YES' if paths.lock_file().exists() else 'no'}")

    print("\n=== Cycle ===")
    print(f"cycle_started_at: {s.get('cycle_started_at', 'n/a')}")
    print(f"cycles_this_run: {s.get('cycles_this_run', 0)}")
    print(f"auto_approve_count: {s.get('auto_approve_count', 0)}")
    print(f"auto_continue_count: {s.get('auto_continue_count', 0)}")

    print("\n=== Decisions (PreToolUse) ===")
    print(f"auto_approve_by_heuristic: {s.get('auto_approve_by_heuristic', 0)}")
    print(f"auto_approve_by_llm: {s.get('auto_approve_by_llm', 0)}")
    print(f"auto_defer_by_rule: {s.get('auto_defer_by_rule', 0)}")
    print(f"auto_defer_by_heuristic: {s.get('auto_defer_by_heuristic', 0)}")
    print(f"auto_defer_by_llm: {s.get('auto_defer_by_llm', 0)}")

    print("\n=== Decisions (Stop) ===")
    print(f"stop_block_continue: {s.get('stop_block_continue', 0)}")
    print(f"stop_block_handoff: {s.get('stop_block_handoff', 0)}")
    print(f"stop_block_unstuck: {s.get('stop_block_unstuck', 0)}")
    print(f"stop_allow: {s.get('stop_allow', 0)}")

    print("\n=== Judge ===")
    print(f"judge_call_total: {s.get('judge_call_total', 0)}")
    print(f"judge_timeout_total: {s.get('judge_timeout_total', 0)}")
    print(f"judge_error_total: {s.get('judge_error_total', 0)}")

    print("\n=== Config ===")
    print(f"time_limit_minutes: {cfg.time_limit_minutes}")
    print(f"max_cycles_per_run: {cfg.max_cycles_per_run}")
    return 0


def _cmd_tail_log(args: argparse.Namespace) -> int:
    p = paths.log_file()
    if not p.exists():
        print("[codingbot] no log yet")
        return 0
    lines = p.read_text(encoding="utf-8").splitlines()
    for line in lines[-args.n:]:
        print(line)
    return 0


def _cmd_install_hooks(args: argparse.Namespace) -> int:
    install_hooks.install()
    return 0


def _cmd_uninstall_hooks(args: argparse.Namespace) -> int:
    install_hooks.uninstall()
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    import yaml
    cfg = config.load()
    print(yaml.safe_dump(cfg.__dict__, allow_unicode=True, sort_keys=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="codingbot")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    r = sub.add_parser("run", help="자동화 시작")
    r.add_argument("prompt", help="초기 작업 프롬프트")
    r.set_defaults(func=_cmd_run)

    s = sub.add_parser("stop", help="자동화 정지 신호")
    s.set_defaults(func=_cmd_stop)

    st = sub.add_parser("start", help="정지 신호 해제")
    st.set_defaults(func=_cmd_start)

    status = sub.add_parser("status", help="현재 상태 표시")
    status.set_defaults(func=_cmd_status)

    tail = sub.add_parser("tail-log", help="최근 로그 표시")
    tail.add_argument("-n", type=int, default=20, help="표시할 줄 수")
    tail.set_defaults(func=_cmd_tail_log)

    install = sub.add_parser("install-hooks", help="Claude Code에 hook 등록")
    install.set_defaults(func=_cmd_install_hooks)

    uninstall = sub.add_parser("uninstall-hooks", help="hook 등록 해제")
    uninstall.set_defaults(func=_cmd_uninstall_hooks)

    cfg = sub.add_parser("config", help="현재 적용 중인 설정 표시")
    cfg.set_defaults(func=_cmd_config)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
