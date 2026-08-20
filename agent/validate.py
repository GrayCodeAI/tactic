from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import lean

_AXIOM_RE = re.compile(r"\baxiom\b", re.IGNORECASE)
_SORRY_RE = re.compile(r"\bsorry\b", re.IGNORECASE)
_CONCAT_AXIOM_RE = re.compile(r'"\s*ax\s*"\s*\+\+\s*"\s*iom\s*"', re.IGNORECASE)
_ELAB_BYPASS_RE = re.compile(r"\b(elab|elabCommand|runParserCategory)\b")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    reason: str
    output: str
    axioms_found: list[str]


def _find_axiom_injections(text: str) -> list[str]:
    hits: list[str] = []
    if _AXIOM_RE.search(text):
        hits.append("axiom")
    if _SORRY_RE.search(text):
        hits.append("sorry")
    if _CONCAT_AXIOM_RE.search(text):
        hits.append("concat-axiom")
    if _ELAB_BYPASS_RE.search(text) and "axiom" in text.lower():
        hits.append("elab-axiom")
    return hits


def validate_file(lean_file: Path, lean_dir: Path, expected_signature: str | None = None, timeout: int = 60) -> ValidationResult:
    text = lean_file.read_text(errors="replace") if lean_file.exists() else ""
    injections = _find_axiom_injections(text)
    if injections:
        return ValidationResult(ok=False, reason=f"illegal axiom injection: {','.join(injections)}", output=text[:4000], axioms_found=injections)
    proved, output = lean.check_file(lean_file, lean_dir, timeout=timeout)
    if not proved:
        return ValidationResult(ok=False, reason="lean check failed", output=output, axioms_found=[])
    if expected_signature:
        # Last `:= by`: statements with scaffolding declarations before the
        # target theorem (Putnam `_solution` abbrevs, FormalQualBench defs)
        # carry several; the theorem is always the final declaration.
        sig = expected_signature.strip().rsplit(":= by", 1)[0].strip()
        name_m = re.search(r"theorem\s+(\w+)", sig)
        if name_m:
            name = name_m.group(1)
            if name not in text:
                return ValidationResult(ok=False, reason=f"theorem {name} not found — statement mismatch", output=output, axioms_found=[])
    if "axiom" in output.lower():
        return ValidationResult(ok=False, reason="axiom in lean output", output=output, axioms_found=["axiom-output"])
    return ValidationResult(ok=True, reason="comparator pass", output=output, axioms_found=[])


def validate_text(text: str, lean_dir: Path, expected_signature: str | None = None, timeout: int = 60) -> ValidationResult:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".lean", mode="w", delete=False, dir=str(lean_dir / "tmp")) as f:
        f.write(text)
        tmp_path = Path(f.name)
    try:
        return validate_file(tmp_path, lean_dir, expected_signature, timeout)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
