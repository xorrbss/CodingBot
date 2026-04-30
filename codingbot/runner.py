"""Shell-loop wrapper. Claude Code를 자식 프로세스로 띄우고 사이클을 돌린다."""
import os
import signal
import subprocess
import sys

from codingbot import handoff, logger, paths, state


FINAL_CHECK_PROMPT = (
    "지금 코드 상태를 다시 한번 살펴봐 주세요. 추가로 가능한 작업이 있나요? "
    "— 개선/리팩터링, 테스트 추가, 문서화, 미발견 버그, 일관성 안 맞는 패턴 등.\n\n"
    "있다면 평소처럼 `~/.codingbot/handoff.md`에 작성하고 종료하세요. "
    "정말 없다면 핸드오프 만들지 말고 그렇게 알려 주고 종료하세요."
)


class RunnerLockError(Exception):
    pass


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_INFORMATION = 0x0400
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _acquire_lock() -> None:
    paths.ensure_home()
    lf = paths.lock_file()
    if lf.exists():
        try:
            existing_pid = int(lf.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            existing_pid = -1
        if existing_pid != os.getpid() and _is_pid_alive(existing_pid):
            raise RunnerLockError(
                f"another codingbot run is in progress (pid={existing_pid}). "
                "Use `codingbot stop` or wait."
            )
        try:
            lf.unlink()
        except FileNotFoundError:
            pass
    lf.write_text(str(os.getpid()), encoding="utf-8")


def _release_lock() -> None:
    try:
        paths.lock_file().unlink()
    except FileNotFoundError:
        pass


def run(initial_prompt: str) -> int:
    """자동화 루프 실행.

    Returns: 종료 코드 (0=정상, 1=락 충돌, 2=Claude Code 연속 비정상 종료).
    """
    try:
        _acquire_lock()
    except RunnerLockError as e:
        logger.error("lock_conflict", error=str(e))
        print(f"[codingbot] {e}", file=sys.stderr)
        return 1

    state.clear_stop_signal()
    handoff.clear()
    state.start_cycle()
    logger.info("run_start", initial_prompt=initial_prompt[:200])

    final_check_pending = False
    abnormal_exits = 0
    interrupted = False
    exit_status = 0

    def _on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        logger.info("user_sigint")
    prev_handler = signal.signal(signal.SIGINT, _on_sigint)

    try:
        while True:
            if interrupted:
                logger.info("run_end", reason="user_sigint")
                break
            if state.should_stop():
                logger.info("run_end", reason="stop_signal_or_limit")
                break

            if final_check_pending:
                msg = FINAL_CHECK_PROMPT
                logger.info("final_check_started")
            else:
                msg = handoff.read() or initial_prompt
            handoff.clear()

            logger.info("cycle_start", msg_preview=msg[:200])
            result = subprocess.run(["claude", msg])
            state.record_cycle()
            exit_code = result.returncode
            logger.info("cycle_end", exit_code=exit_code)

            if exit_code != 0:
                abnormal_exits += 1
                logger.warn("claude_abnormal_exit", code=exit_code, count=abnormal_exits)
                if abnormal_exits >= 2:
                    print(
                        "[codingbot] Claude Code 연속 비정상 종료. 자동화를 중단합니다.",
                        file=sys.stderr,
                    )
                    logger.error("run_end", reason="repeated_abnormal_exit")
                    exit_status = 2
                    break
                continue
            abnormal_exits = 0

            if handoff.exists():
                final_check_pending = False
            else:
                if final_check_pending:
                    logger.info("run_end", reason="final_check_returned_done")
                    break
                final_check_pending = True
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        _release_lock()
    return exit_status
