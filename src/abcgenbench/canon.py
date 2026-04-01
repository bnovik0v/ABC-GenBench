from __future__ import annotations

import re

HEADER_ORDER = ["X", "T", "M", "L", "Q", "R", "K"]
TOKEN_PATTERN = re.compile(r"[A-Ga-gzZ][,']*\d*/*\d*|[|:\[\]]+|\(\d+|[<>-]|[=^_][A-Ga-g]")


def strip_comments(abc: str) -> str:
    return "\n".join(line.split("%", 1)[0].rstrip() for line in abc.splitlines())


def split_header_body(abc: str) -> tuple[list[str], list[str]]:
    headers: list[str] = []
    body: list[str] = []
    in_body = False
    for raw_line in strip_comments(abc).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not in_body and re.match(r"^[A-Z]:", line):
            headers.append(line)
            if line.startswith("K:"):
                in_body = True
            continue
        in_body = True
        body.append(line)
    return headers, body


def canonicalize_headers(headers: list[str]) -> list[str]:
    parsed: dict[str, list[str]] = {}
    for line in headers:
        key, value = line.split(":", 1)
        parsed.setdefault(key, []).append(value.strip())

    ordered: list[str] = []
    for key in HEADER_ORDER:
        for value in parsed.pop(key, []):
            ordered.append(f"{key}:{value}")
    for key in sorted(parsed):
        for value in parsed[key]:
            ordered.append(f"{key}:{value}")
    return ordered


def canonicalize_body(body_lines: list[str]) -> str:
    body = " ".join(body_lines)
    body = re.sub(r"\s+", " ", body).strip()
    body = re.sub(r"\s*\|\s*", " | ", body)
    body = re.sub(r"\s*\|\]\s*", " |] ", body)
    body = re.sub(r"\s*\[\|\s*", " [| ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body


def canonicalize_abc(abc: str) -> str:
    headers, body = split_header_body(abc)
    normalized_headers = canonicalize_headers(headers)
    normalized_body = canonicalize_body(body)
    if normalized_body:
        return "\n".join([*normalized_headers, normalized_body]).strip()
    return "\n".join(normalized_headers).strip()


def tokenize_body(body: str) -> list[str]:
    return TOKEN_PATTERN.findall(body)


def normalized_levenshtein(left: str, right: str) -> float:
    if left == right:
        return 0.0
    if not left and not right:
        return 0.0
    if not left or not right:
        return 1.0

    rows = len(left) + 1
    cols = len(right) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[-1][-1] / max(len(left), len(right))
