"""Language-aware extraction of tracking calls.

The scanner tokenizes source so strings, comments, and nested calls stay intact,
then reads the event name and parameter map from the configured argument positions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Token:
    kind: str
    value: str
    line: int


def tokenize(code: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    line = 1
    length = len(code)
    while index < length:
        char = code[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in " \t\r":
            index += 1
            continue
        if char == "/" and index + 1 < length and code[index + 1] == "/":
            index += 2
            while index < length and code[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and code[index + 1] == "*":
            index += 2
            while index + 1 < length and not (code[index] == "*" and code[index + 1] == "/"):
                if code[index] == "\n":
                    line += 1
                index += 1
            index = min(length, index + 2)
            continue
        if char in "\"'`":
            quote = char
            index += 1
            value: list[str] = []
            while index < length and code[index] != quote:
                if code[index] == "\\" and index + 1 < length:
                    value.append(code[index + 1])
                    index += 2
                    continue
                if code[index] == "\n":
                    line += 1
                value.append(code[index])
                index += 1
            index = min(length, index + 1)
            tokens.append(Token("string", "".join(value), line))
            continue
        if char.isdigit() or (char == "-" and index + 1 < length and code[index + 1].isdigit()):
            start = index
            index += 1
            while index < length and (code[index].isdigit() or code[index] == "."):
                index += 1
            tokens.append(Token("number", code[start:index], line))
            continue
        if char.isalpha() or char == "_":
            start = index
            index += 1
            while index < length and (code[index].isalnum() or code[index] == "_"):
                index += 1
            word = code[start:index]
            kind = "keyword" if word in {"true", "false", "null", "to"} else "ident"
            tokens.append(Token(kind, word, line))
            continue
        tokens.append(Token(char, char, line))
        index += 1
    return tokens


def _matching(tokens: list[Token], start: int, open_kind: str, close_kind: str) -> int:
    depth = 0
    index = start
    while index < len(tokens):
        kind = tokens[index].kind
        if kind == open_kind:
            depth += 1
        elif kind == close_kind:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(tokens) - 1


def _split_args(tokens: list[Token], open_index: int) -> tuple[list[list[Token]], int]:
    close = _matching(tokens, open_index, "(", ")")
    args: list[list[Token]] = []
    current: list[Token] = []
    depth = 0
    for token in tokens[open_index + 1 : close]:
        if token.kind in "([{":
            depth += 1
            current.append(token)
        elif token.kind in ")]}":
            depth -= 1
            current.append(token)
        elif token.kind == "," and depth == 0:
            if current:
                args.append(current)
            current = []
        else:
            current.append(token)
    if current:
        args.append(current)
    return args, close + 1


def _literal(token: Token) -> tuple[Any, str]:
    if token.kind == "string":
        return token.value, "string"
    if token.kind == "number":
        return (float(token.value) if "." in token.value else int(token.value)), "number"
    if token.value == "true":
        return True, "boolean"
    if token.value == "false":
        return False, "boolean"
    if token.value == "null":
        return None, "null"
    return token.value, "unknown"


def _pairs(tokens: list[Token]) -> dict[str, tuple[Any, str]]:
    found: dict[str, tuple[Any, str]] = {}
    index = 0
    while index < len(tokens) - 2:
        key = tokens[index]
        sep = tokens[index + 1]
        value = tokens[index + 2]
        if key.kind in {"ident", "string"} and sep.kind in {":", "keyword"} and sep.value in {":", "to"}:
            found[key.value] = _literal(value)
            index += 3
            continue
        if key.kind == "string" and sep.kind == "," and value.kind in {"string", "number", "keyword"}:
            found[key.value] = _literal(value)
            index += 3
            continue
        index += 1
    return found


def _arg(args: list[list[Token]], position: int) -> list[Token]:
    if position < 0 or position >= len(args):
        return []
    return args[position]


def parse_language_calls(code: str, wrappers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not wrappers:
        return []
    by_name = {str(item["name"]).split(".")[-1]: item for item in wrappers if item.get("name")}
    tokens = tokenize(code)
    found: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        nxt = tokens[index + 1] if index + 1 < len(tokens) else None
        if token.kind == "ident" and token.value in by_name and nxt and nxt.kind == "(":
            wrapper = by_name[token.value]
            args, index = _split_args(tokens, index + 1)
            event_tokens = _arg(args, int(wrapper.get("event_arg", 0)))
            event_name = event_tokens[0].value if event_tokens and event_tokens[0].kind == "string" else None
            body = _arg(args, int(wrapper.get("params_arg", 1)))
            parameters: dict[str, Any] = {}
            param_types: dict[str, str] = {}
            dynamic = event_name is None
            for key, (value, typ) in _pairs(body).items():
                parameters[key] = value
                param_types[key] = typ
                if typ == "unknown":
                    dynamic = True
            found.append(
                {
                    "event_name": event_name,
                    "parameters": parameters,
                    "param_types": param_types,
                    "line": token.line,
                    "dynamic": dynamic,
                }
            )
            continue
        index += 1
    return found


def normalize_wrappers(functions: list[str] | None, wrappers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in wrappers or []:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(
            {
                "name": name,
                "event_arg": int(item.get("event_arg", 0)),
                "params_arg": int(item.get("params_arg", 1)),
                "style": item.get("style") or "auto",
            }
        )
    for name in functions or []:
        if name and name not in seen:
            seen.add(name)
            merged.append({"name": name, "event_arg": 0, "params_arg": 1, "style": "auto"})
    return merged


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
