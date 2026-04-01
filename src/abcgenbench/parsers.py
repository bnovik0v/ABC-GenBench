from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from .canon import canonicalize_body, split_header_body, tokenize_body

try:
    from music21 import converter
except Exception:  # pragma: no cover - optional import guard
    converter = None


NOTE_BASE = {
    "C": 60,
    "D": 62,
    "E": 64,
    "F": 65,
    "G": 67,
    "A": 69,
    "B": 71,
}
VALID_METERS = {"2/4", "3/4", "4/4", "6/8", "9/8", "12/8", "C", "C|"}
VALID_KEYS = {
    "C", "G", "D", "A", "E", "B", "F", "Bb", "Eb", "Ab",
    "Am", "Em", "Bm", "Dm", "Gm", "Cm", "F#m", "C#m",
    "Ddor", "Gdor", "Ador", "Edor", "Amin", "Dmin", "Emin", "Gmaj",
}


@dataclass
class ParseResult:
    parse_success: bool
    errors: list[str]
    headers: dict[str, str]
    bar_count: int
    section_count: int
    note_pitches: list[int]
    invalid_token_count: int
    repeat_consistent: bool
    bar_duration_consistent: bool


class ABCParserAdapter:
    name = "base"

    def parse(self, abc: str) -> ParseResult:
        raise NotImplementedError


class LightweightABCParser(ABCParserAdapter):
    name = "lightweight"

    def parse(self, abc: str) -> ParseResult:
        headers, body_lines = split_header_body(abc)
        errors: list[str] = []
        header_map: dict[str, str] = {}
        for line in headers:
            key, value = line.split(":", 1)
            header_map[key] = value.strip()

        for required in ["X", "T", "M", "L", "K"]:
            if required not in header_map:
                errors.append(f"missing header {required}")

        meter = header_map.get("M")
        if meter and meter not in VALID_METERS:
            errors.append(f"unsupported meter {meter}")

        key = header_map.get("K")
        if key and key not in VALID_KEYS:
            errors.append(f"unsupported key {key}")

        body = canonicalize_body(body_lines)
        tokens = tokenize_body(body)
        invalid_token_count = 0
        body_without_known_tokens = body
        for token in tokens:
            body_without_known_tokens = body_without_known_tokens.replace(token, " ", 1)
        invalid_token_count += len(re.findall(r"[^\s]", body_without_known_tokens))

        bars = split_musical_bars(body)
        bar_count = len(bars)
        section_count = body_to_section_count(body)
        repeat_consistent = body.count("|:") == body.count(":|")

        note_pitches: list[int] = []
        for match in re.finditer(r"([=^_]?)([A-Ga-g])([,']*)", body):
            accidental, note, octave_mod = match.groups()
            pitch = NOTE_BASE[note.upper()]
            if note.islower():
                pitch += 12
            pitch += octave_mod.count("'") * 12
            pitch -= octave_mod.count(",") * 12
            if accidental == "^":
                pitch += 1
            elif accidental == "_":
                pitch -= 1
            note_pitches.append(pitch)

        bar_duration_consistent = True
        expected = None
        for segment in bars:
            duration = measure_bar_duration(segment)
            if expected is None:
                expected = duration
            elif duration != expected:
                bar_duration_consistent = False
                break

        if not body:
            errors.append("missing body")
        if invalid_token_count:
            errors.append(f"invalid token count {invalid_token_count}")
        if not repeat_consistent:
            errors.append("repeat markers are inconsistent")
        if not bar_duration_consistent:
            errors.append("bar durations are inconsistent")

        return ParseResult(
            parse_success=not errors,
            errors=errors,
            headers=header_map,
            bar_count=bar_count,
            section_count=section_count,
            note_pitches=note_pitches,
        invalid_token_count=invalid_token_count,
        repeat_consistent=repeat_consistent,
        bar_duration_consistent=bar_duration_consistent,
        )


class Music21ABCParser(ABCParserAdapter):
    name = "music21"

    def parse(self, abc: str) -> ParseResult:
        if converter is None:
            return ParseResult(
                parse_success=False,
                errors=["music21 is unavailable"],
                headers={},
                bar_count=0,
                section_count=0,
                note_pitches=[],
                invalid_token_count=0,
                repeat_consistent=False,
                bar_duration_consistent=False,
            )

        headers, body_lines = split_header_body(abc)
        header_map: dict[str, str] = {}
        for line in headers:
            key, value = line.split(":", 1)
            header_map[key] = value.strip()

        try:
            score = converter.parseData(abc, format="abc")
            notes = list(score.recurse().notes)
            measures = list(score.recurse().getElementsByClass("Measure"))
            note_pitches = [note.pitch.midi for note in notes if hasattr(note, "pitch")]
            return ParseResult(
                parse_success=True,
                errors=[],
                headers=header_map,
                bar_count=len(measures),
                section_count=max(1, body_to_section_count(canonicalize_body(body_lines))),
                note_pitches=note_pitches,
                invalid_token_count=0,
                repeat_consistent=True,
                bar_duration_consistent=True,
            )
        except Exception as exc:
            return ParseResult(
                parse_success=False,
                errors=[f"music21 parse failed: {exc}"],
                headers=header_map,
                bar_count=0,
                section_count=0,
                note_pitches=[],
                invalid_token_count=0,
                repeat_consistent=False,
                bar_duration_consistent=False,
            )


DEFAULT_PARSERS: list[ABCParserAdapter] = [LightweightABCParser()]
if converter is not None:
    DEFAULT_PARSERS.append(Music21ABCParser())


def measure_bar_duration(segment: str) -> Fraction:
    total = Fraction(0, 1)
    pattern = re.compile(r"([=^_]?[A-Ga-gzZ][,']*)(\d+)?(?:/(\d+))?")
    for match in pattern.finditer(segment):
        _, numerator, denominator = match.groups()
        value = Fraction(1, 1)
        if numerator:
            value *= int(numerator)
        if denominator:
            value /= int(denominator)
        total += value
    return total


def split_musical_bars(body: str) -> list[str]:
    normalized = body
    for token in ["|:", ":|", "[|", "|]"]:
        normalized = normalized.replace(token, "|")
    return [
        segment.strip()
        for segment in normalized.split("|")
        if re.search(r"[A-Ga-gzZ]", segment)
    ]


def body_to_section_count(body: str) -> int:
    return sum(token in {"|:", ":|", "[|"} for token in re.findall(r"\|:|:\||\[\|", body)) + 1
