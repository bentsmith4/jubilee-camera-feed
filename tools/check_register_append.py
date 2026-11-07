"""Verify that a routine register update preserves the complete base blob."""
import subprocess
import sys

REGISTER = "model_data/MODEL_WORK_REGISTER.md"


def read_register(revision):
    return subprocess.check_output(["git", "show", f"{revision}:{REGISTER}"])


def verify(base, proposed):
    if not base or not proposed.startswith(base):
        raise ValueError("Historical register bytes changed or were removed")
    proposed.decode("utf-8")
    if b"\x00" in proposed:
        raise ValueError("Register contains a NUL byte")
    if len(proposed) > len(base) and not (
        base.endswith(b"\n") or proposed[len(base):].startswith(b"\n")
    ):
        raise ValueError("Append must start on a new line")


if __name__ == "__main__":
    verify(*(read_register(revision) for revision in sys.argv[1:]))
