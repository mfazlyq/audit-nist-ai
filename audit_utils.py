"""Small, dependency-free helpers for parsing generated NIST CSF findings."""
import re
from typing import List

NIST_FUNCTIONS = ("GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER")

VALID_CONTROL_PATTERN = re.compile(
    r"^(?:GV\.OC|GV\.RM|GV\.RR|GV\.PO|GV\.OV|GV\.SC|"
    r"ID\.AM|ID\.RA|ID\.IM|"
    r"PR\.AA|PR\.AT|PR\.DS|PR\.PS|PR\.IR|"
    r"DE\.AE|DE\.CM|"
    r"RS\.CO|RS\.AN|RS\.MI|RS\.MA|"
    r"RC\.RP|RC\.CO)-\d{2}$"
)


def parse_nist_findings(response: str, limit: int = 12) -> List[List[str]]:
    """Parse pipe-delimited model output into validated NIST CSF findings.

    Expected columns: pillar | control ID | current situation | recommendation.
    Invalid/header rows are ignored. At most the requested limit is returned.
    """
    if not isinstance(response, str):
        raise TypeError("response must be a string")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    findings: List[List[str]] = []
    for line in response.splitlines():
        if "|" not in line:
            continue

        columns = [column.strip() for column in line.split("|", maxsplit=3)]
        if len(columns) < 4:
            continue

        pillar_text = columns[0].upper()
        matched_pillar = next(
            (name for name in NIST_FUNCTIONS if name in pillar_text),
            None,
        )
        control_id = re.sub(r"\s+", "", columns[1].upper())

        if not matched_pillar or not VALID_CONTROL_PATTERN.fullmatch(control_id):
            continue

        findings.append([matched_pillar, control_id, columns[2], columns[3]])
        if len(findings) >= limit:
            break

    return findings
