#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_CACHE_DIR = ".cache/openai-query-rewrite"
DEFAULT_MAX_OUTPUT_TERMS = 8
DEFAULT_MAX_QUERY_TERMS = 3
DEFAULT_MODE = "off"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROMPT_VERSION = "openai-query-rewrite-v3"
MAX_OPENAI_RETRIES = 5
OPENAI_API_URL = "https://api.openai.com/v1/responses"
RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
TRANSIENT_BAD_JSON_MARKER = "could not parse the json body"
VALID_MODES = {"off", "sparse"}


@dataclass
class Config:
    repo_root: Path
    workdir: Path
    mode: str
    model: str
    prompt_version: str
    cache_dir: Path
    cache_only: bool
    max_query_terms: int
    max_output_terms: int
    api_key: str
    key_source: str


@dataclass
class UsageTotals:
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    calls: int = 0
    eligible_queries: int = 0
    rewritten_queries: int = 0


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or name in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[name] = value


def load_repo_env(repo_root: Path) -> str:
    key_source = "env" if os.getenv("OPENAI_API_KEY") else "missing"
    load_env_file(repo_root / ".env")
    load_env_file(repo_root / ".env.local")
    if key_source == "missing" and os.getenv("OPENAI_API_KEY"):
        return "dotenv"
    return key_source


def int_from_env(name: str, fallback: int) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return fallback
    return int(raw)


def build_config(repo_root: Path, workdir: Path) -> Config:
    key_source = load_repo_env(repo_root)
    mode = os.getenv("JASSJR_OPENAI_QUERY_REWRITE_MODE", DEFAULT_MODE).strip() or DEFAULT_MODE
    model = os.getenv("JASSJR_OPENAI_QUERY_REWRITE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt_version = os.getenv("JASSJR_OPENAI_QUERY_REWRITE_PROMPT_VERSION", DEFAULT_PROMPT_VERSION).strip() or DEFAULT_PROMPT_VERSION
    cache_dir_raw = os.getenv("JASSJR_OPENAI_QUERY_REWRITE_CACHE_DIR", DEFAULT_CACHE_DIR).strip() or DEFAULT_CACHE_DIR
    cache_dir = Path(cache_dir_raw).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = (repo_root / cache_dir).resolve()
    cache_only = os.getenv("JASSJR_OPENAI_QUERY_REWRITE_CACHE_ONLY", "") == "1"
    max_query_terms = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS", DEFAULT_MAX_QUERY_TERMS)
    max_output_terms = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS", DEFAULT_MAX_OUTPUT_TERMS)

    if mode not in VALID_MODES:
        raise SystemExit(f"JASSJR_OPENAI_QUERY_REWRITE_MODE must be one of: {', '.join(sorted(VALID_MODES))}")
    if max_query_terms <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS must be positive")
    if max_output_terms <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS must be positive")
    if mode != "off" and key_source == "missing" and not cache_only:
        raise SystemExit("OPENAI_API_KEY is required for uncached OpenAI query rewriting")

    return Config(
        repo_root=repo_root,
        workdir=workdir,
        mode=mode,
        model=model,
        prompt_version=prompt_version,
        cache_dir=cache_dir,
        cache_only=cache_only,
        max_query_terms=max_query_terms,
        max_output_terms=max_output_terms,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        key_source=key_source,
    )


def parse_topics(path: Path) -> List[Tuple[str, str]]:
    queries: List[Tuple[str, str]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split()
        if not parts:
            continue
        if parts[0].isdigit():
            query_id = parts[0]
            query_text = " ".join(parts[1:])
        else:
            query_id = str(index)
            query_text = line.strip()
        queries.append((query_id, query_text))
    return queries


def normalize_terms(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def normalize_rewrite(query_text: str, rewrite_text: str, max_output_terms: int) -> str:
    original_terms = normalize_terms(query_text)
    original_set = set(original_terms)
    rewrite_terms = normalize_terms(rewrite_text)
    if not rewrite_terms:
        return ""

    deduped: List[str] = []
    seen = set()
    for token in rewrite_terms:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= max_output_terms:
            break

    max_novel_terms = 3 if len(original_terms) <= 1 else 1
    filtered: List[str] = []
    novel_terms = 0
    for token in deduped:
        if token in original_set:
            filtered.append(token)
            continue
        if novel_terms >= max_novel_terms:
            continue
        filtered.append(token)
        novel_terms += 1

    if not filtered or filtered == original_terms:
        return ""
    return " ".join(filtered)


def should_rewrite(config: Config, query_text: str) -> bool:
    terms = normalize_terms(query_text)
    return bool(terms) and len(terms) <= config.max_query_terms


def cache_path(cache_dir: Path, payload: Dict[str, str]) -> Path:
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.json"


def ensure_cache_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def estimated_tokens(text: str) -> int:
    return len(text.split())


def extract_text(response_json: Dict) -> str:
    if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
        return response_json["output_text"].strip()

    texts: List[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                texts.append(content["text"])
    if texts:
        return "\n".join(texts).strip()

    if response_json.get("status") == "incomplete":
        detail = response_json.get("incomplete_details") or {}
        raise RuntimeError(f"incomplete OpenAI response: {detail}")

    raise RuntimeError("could not extract text output from OpenAI response")


def rewrite_text_format() -> Dict:
    return {
        "type": "json_schema",
        "name": "query_rewrite",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "rewrite_query": {
                    "type": "string",
                }
            },
            "required": ["rewrite_query"],
            "additionalProperties": False,
        },
    }


def post_openai(config: Config, system_prompt: str, user_prompt: str) -> Dict:
    payload = {
        "model": config.model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "max_output_tokens": 64,
        "reasoning": {"effort": "minimal"},
        "text": {
            "format": rewrite_text_format(),
            "verbosity": "low",
        },
        "store": False,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(1, MAX_OPENAI_RETRIES + 1):
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            normalized_detail = detail.lower()
            retryable_bad_json = exc.code == 400 and TRANSIENT_BAD_JSON_MARKER in normalized_detail
            if (exc.code in RETRYABLE_HTTP_CODES or retryable_bad_json) and attempt < MAX_OPENAI_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 16))
                continue
            raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_OPENAI_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 16))
                continue
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
    raise RuntimeError("OpenAI request failed after retries")


def rewrite_prompt(query_text: str, max_output_terms: int) -> Tuple[str, str]:
    system_prompt = (
        "You rewrite short Wall Street Journal archive search queries to improve document recall. "
        "Return one alternate lexical query only. "
        "Prefer acronym expansions, entity aliases, alternate spellings, and close business or policy synonyms. "
        "The corpus covers Wall Street Journal articles from 1987 to 1992. "
        "Stay specific to the original intent. Prefer direct aliases over background concepts. "
        "Do not add related people, related organizations, later parent companies, successor companies, locations, years, or speculative facts. "
        "Do not explain your answer."
    )
    user_prompt = (
        f"Original query: {query_text}\n"
        f"Return a concise alternate query with at most {max_output_terms} lowercase content terms. "
        "If no high-confidence alternate query is obvious, return an empty string."
    )
    return system_prompt, user_prompt


def parse_rewrite(text: str) -> str:
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("rewrite_query"), str):
        raise RuntimeError(f"expected JSON object with rewrite_query, got: {text!r}")
    return payload["rewrite_query"]


def cached_or_live_json(
    *,
    config: Config,
    cache_payload: Dict[str, str],
    system_prompt: str,
    user_prompt: str,
    usage: UsageTotals,
) -> Dict:
    ensure_cache_dir(config.cache_dir)
    path = cache_path(config.cache_dir, cache_payload)
    if path.is_file():
        usage.cache_hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    usage.cache_misses += 1
    if config.cache_only:
        raise RuntimeError(f"cache miss while JASSJR_OPENAI_QUERY_REWRITE_CACHE_ONLY=1: {path.name}")
    if not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is required for cache misses")

    response_json = post_openai(config, system_prompt, user_prompt)
    path.write_text(json.dumps(response_json, sort_keys=True), encoding="utf-8")
    usage.calls += 1
    return response_json


def rewrite_query(config: Config, query_id: str, query_text: str, usage: UsageTotals) -> str:
    usage.eligible_queries += 1
    system_prompt, user_prompt = rewrite_prompt(query_text, config.max_output_terms)
    usage.estimated_input_tokens += estimated_tokens(system_prompt) + estimated_tokens(user_prompt)
    usage.estimated_output_tokens += 12
    response_json = cached_or_live_json(
        config=config,
        cache_payload={
            "kind": "query_rewrite",
            "mode": config.mode,
            "model": config.model,
            "prompt_version": config.prompt_version,
            "query_id": query_id,
            "query_text": query_text,
            "max_query_terms": str(config.max_query_terms),
            "max_output_terms": str(config.max_output_terms),
        },
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        usage=usage,
    )
    response_text = extract_text(response_json)
    response_usage = response_json.get("usage", {})
    usage.actual_input_tokens += int(response_usage.get("input_tokens", 0))
    usage.actual_output_tokens += int(response_usage.get("output_tokens", 0))
    normalized = normalize_rewrite(query_text, parse_rewrite(response_text), config.max_output_terms)
    if normalized:
        usage.rewritten_queries += 1
    return normalized


def metadata_lines(config: Config, output_file: Path, queries_total: int, usage: UsageTotals) -> List[str]:
    return [
        f"JASSJR_OPENAI_QUERY_REWRITE_MODE: {config.mode}",
        f"JASSJR_OPENAI_QUERY_REWRITE_KEY_SOURCE: {config.key_source}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MODEL: {config.model}",
        f"JASSJR_OPENAI_QUERY_REWRITE_PROMPT_VERSION: {config.prompt_version}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS: {config.max_query_terms}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS: {config.max_output_terms}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_DIR: {config.cache_dir}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_ONLY: {1 if config.cache_only else 0}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_TOTAL: {queries_total}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_ELIGIBLE: {usage.eligible_queries}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_REWRITTEN: {usage.rewritten_queries}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_HITS: {usage.cache_hits}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_MISSES: {usage.cache_misses}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CALLS: {usage.calls}",
        f"JASSJR_OPENAI_QUERY_REWRITE_EST_INPUT_TOKENS: {usage.estimated_input_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_EST_OUTPUT_TOKENS: {usage.estimated_output_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_ACTUAL_INPUT_TOKENS: {usage.actual_input_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_ACTUAL_OUTPUT_TOKENS: {usage.actual_output_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_OUTPUT_FILE: {output_file}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sparse-query OpenAI rewrite sidecars for WSJ title queries.")
    parser.add_argument("--repo-root", default="", help="Repository root for .env loading")
    parser.add_argument("--workdir", default="", help="Search workdir")
    parser.add_argument("--topics-file", required=True, help="Input topics file")
    parser.add_argument("--output-file", required=True, help="Where to write rewritten sparse topics")
    parser.add_argument("--metadata-file", default="", help="Optional output path for metadata lines")
    parser.add_argument("--check-config", action="store_true", help="Validate config and exit")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser() if args.repo_root else Path(__file__).resolve().parent.parent
    if not repo_root.is_absolute():
        repo_root = (Path.cwd() / repo_root).resolve()
    workdir = Path(args.workdir).expanduser() if args.workdir else repo_root
    if not workdir.is_absolute():
        workdir = (Path.cwd() / workdir).resolve()

    config = build_config(repo_root, workdir)
    topics_path = Path(args.topics_file).expanduser()
    if not topics_path.is_absolute():
        topics_path = (Path.cwd() / topics_path).resolve()
    output_file = Path(args.output_file).expanduser()
    if not output_file.is_absolute():
        output_file = (Path.cwd() / output_file).resolve()

    queries = parse_topics(topics_path)
    usage = UsageTotals()

    if args.check_config:
        for line in metadata_lines(config, output_file, len(queries), usage):
            print(line)
        return 0

    if config.mode == "off":
        output_file.write_text("", encoding="utf-8")
        if args.metadata_file:
            Path(args.metadata_file).write_text(
                "\n".join(metadata_lines(config, output_file, len(queries), usage)) + "\n",
                encoding="utf-8",
            )
        return 0

    rewritten_lines: List[str] = []
    for query_id, query_text in queries:
        if not should_rewrite(config, query_text):
            continue
        rewritten_query = rewrite_query(config, query_id, query_text, usage)
        if rewritten_query:
            rewritten_lines.append(f"{query_id} {rewritten_query}")

    output_file.write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")
    if args.metadata_file:
        Path(args.metadata_file).write_text(
            "\n".join(metadata_lines(config, output_file, len(queries), usage)) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
