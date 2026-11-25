"""Month-end financial packet reconciliation checks (deterministic, no LLM)."""

from pathlib import Path
from typing import BinaryIO

from .checks import CheckResult, Status, run_checks
from .extract import Packet, extract_packet
from .pdf import load_pages


def check_packet(source: str | Path | BinaryIO) -> tuple[Packet, list[CheckResult]]:
    packet = extract_packet(load_pages(source))
    return packet, run_checks(packet)


__all__ = ["CheckResult", "Packet", "Status", "check_packet", "extract_packet", "run_checks"]
