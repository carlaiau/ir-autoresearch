#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_CACHE_DIR = ".cache/openai-query-rewrite"
DEFAULT_GROUND_DOCS = 0
DEFAULT_GROUND_DOC_WORDS = 90
DEFAULT_GROUND_TERMS = 12
DEFAULT_MAX_OUTPUT_TERMS = 8
DEFAULT_MAX_QUERY_TERMS = 3
DEFAULT_MODE = "off"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROMPT_VERSION = "openai-query-rewrite-v4"
DEFAULT_REWRITE_COUNT = 1
MAX_OPENAI_RETRIES = 5
OPENAI_API_URL = "https://api.openai.com/v1/responses"
RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
TRANSIENT_BAD_JSON_MARKER = "could not parse the json body"
VALID_MODES = {"off", "sparse"}
GROUND_STOPWORDS = {
    "also",
    "among",
    "been",
    "billion",
    "business",
    "companies",
    "company",
    "could",
    "from",
    "government",
    "inc",
    "including",
    "million",
    "more",
    "most",
    "new",
    "officials",
    "percent",
    "said",
    "some",
    "their",
    "them",
    "they",
    "this",
    "those",
    "under",
    "were",
    "when",
    "which",
    "would",
    "year",
    "years",
}


@dataclass
class Config:
    repo_root: Path
    workdir: Path
    mode: str
    model: str
    prompt_version: str
    cache_dir: Path
    cache_only: bool
    rewrite_count: int
    max_query_terms: int
    max_output_terms: int
    ground_docs: int
    ground_terms: int
    ground_doc_words: int
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
    grounded_queries: int = 0
    rewritten_queries: int = 0
    rewrite_lines: int = 0


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
    rewrite_count = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_COUNT", DEFAULT_REWRITE_COUNT)
    max_query_terms = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS", DEFAULT_MAX_QUERY_TERMS)
    max_output_terms = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS", DEFAULT_MAX_OUTPUT_TERMS)
    ground_docs = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOCS", DEFAULT_GROUND_DOCS)
    ground_terms = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_GROUND_TERMS", DEFAULT_GROUND_TERMS)
    ground_doc_words = int_from_env("JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOC_WORDS", DEFAULT_GROUND_DOC_WORDS)

    if mode not in VALID_MODES:
        raise SystemExit(f"JASSJR_OPENAI_QUERY_REWRITE_MODE must be one of: {', '.join(sorted(VALID_MODES))}")
    if rewrite_count <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_COUNT must be positive")
    if max_query_terms <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS must be positive")
    if max_output_terms <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS must be positive")
    if ground_docs < 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOCS must be non-negative")
    if ground_terms <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_GROUND_TERMS must be positive")
    if ground_doc_words <= 0:
        raise SystemExit("JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOC_WORDS must be positive")
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
        rewrite_count=rewrite_count,
        max_query_terms=max_query_terms,
        max_output_terms=max_output_terms,
        ground_docs=ground_docs,
        ground_terms=ground_terms,
        ground_doc_words=ground_doc_words,
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


def parse_run(path: Path) -> Dict[str, List[Dict[str, object]]]:
    runs: Dict[str, List[Dict[str, object]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 6:
            continue
        query_id, _, doc_id, rank, score, run_name = parts
        runs.setdefault(query_id, []).append(
            {
                "doc_id": doc_id,
                "rank": int(rank),
                "score": float(score),
                "run_name": run_name,
            }
        )
    for entries in runs.values():
        entries.sort(key=lambda entry: int(entry["rank"]))
    return runs


def load_doc_index(workdir: Path) -> Tuple[Dict[str, int], List[int], object]:
    docids = [line for line in (workdir / "docids.bin").read_text(encoding="utf-8").splitlines() if line]
    offsets_raw = (workdir / "forward_offsets.bin").read_bytes()
    offsets = [
        int.from_bytes(offsets_raw[i : i + 8], byteorder=sys.byteorder, signed=True)
        for i in range(0, len(offsets_raw), 8)
    ]
    forward_file = (workdir / "forward.bin").open("rb")
    lookup = {doc_id: index for index, doc_id in enumerate(docids)}
    return lookup, offsets, forward_file


def read_doc_terms(forward_file, offsets: List[int], doc_index: int, limit_words: int) -> List[str]:
    offset = offsets[doc_index * 2]
    size = offsets[doc_index * 2 + 1]
    if size <= 0:
        return []
    forward_file.seek(offset)
    buffer = forward_file.read(size)
    terms: List[str] = []
    cursor = 0
    while cursor < len(buffer) and len(terms) < limit_words:
        length = buffer[cursor]
        cursor += 1
        term = buffer[cursor : cursor + length].decode("utf-8", errors="ignore")
        cursor += length
        terms.append(term)
    return terms


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

    max_novel_terms = 3 if len(original_terms) <= 1 else 2
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


def slot_output_path(output_file: Path, slot_index: int) -> Path:
    suffix = output_file.suffix or ".txt"
    return output_file.with_name(f"{output_file.stem}-{slot_index}{suffix}")


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


def rewrite_text_format(rewrite_count: int) -> Dict:
    return {
        "type": "json_schema",
        "name": "query_rewrites",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "rewrites": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": rewrite_count,
                }
            },
            "required": ["rewrites"],
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
        "max_output_tokens": 128,
        "reasoning": {"effort": "minimal"},
        "text": {
            "format": rewrite_text_format(config.rewrite_count),
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


def extract_grounding_terms(
    *,
    config: Config,
    query_id: str,
    query_text: str,
    run_entries: Dict[str, List[Dict[str, object]]],
    doc_lookup: Dict[str, int],
    offsets: List[int],
    forward_file,
) -> List[str]:
    if config.ground_docs == 0 or query_id not in run_entries:
        return []

    query_terms = set(normalize_terms(query_text))
    scores: Dict[str, float] = {}
    for entry in run_entries[query_id][: config.ground_docs]:
        doc_id = str(entry["doc_id"])
        doc_index = doc_lookup.get(doc_id)
        if doc_index is None:
            continue
        doc_terms = read_doc_terms(forward_file, offsets, doc_index, config.ground_doc_words)
        if not doc_terms:
            continue
        doc_rank = max(1, int(entry["rank"]))
        doc_weight = 1.0 / float(doc_rank)
        seen_in_doc = set()
        for position, token in enumerate(doc_terms):
            if token in seen_in_doc:
                continue
            seen_in_doc.add(token)
            if token in query_terms or token in GROUND_STOPWORDS:
                continue
            if len(token) < 3 or token.isdigit():
                continue
            scores[token] = scores.get(token, 0.0) + doc_weight / (1.0 + float(position) / 20.0)

    ranked_terms = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked_terms[: config.ground_terms]]


def rewrite_prompt(query_text: str, grounding_terms: List[str], rewrite_count: int, max_output_terms: int) -> Tuple[str, str]:
    system_prompt = (
        "You rewrite short Wall Street Journal archive search queries to improve document recall. "
        f"Return up to {rewrite_count} distinct alternate lexical queries as a JSON array. "
        "Prefer acronym expansions, formal entity names, alternate spellings, and narrow paraphrases. "
        "The corpus covers Wall Street Journal articles from 1987 to 1992. "
        "When grounding terms are provided, use them only as evidence to clarify the original query. "
        "Do not add related people, later parent companies, successor companies, locations, years, or speculative facts. "
        "Keep each rewrite concise and lowercase."
    )

    grounding_text = " ".join(grounding_terms) if grounding_terms else "(none)"
    user_prompt = (
        f"Original query: {query_text}\n"
        f"Grounding terms from top feedback documents: {grounding_text}\n"
        f"Return up to {rewrite_count} distinct alternate queries with at most {max_output_terms} lowercase content terms each. "
        "Each rewrite must stay faithful to the original query. "
        "If no high-confidence grounded rewrite is obvious, return an empty list."
    )
    return system_prompt, user_prompt


def parse_rewrites(text: str) -> List[str]:
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("rewrites"), list):
        raise RuntimeError(f"expected JSON object with rewrites array, got: {text!r}")
    rewrites: List[str] = []
    for item in payload["rewrites"]:
        if isinstance(item, str):
            rewrites.append(item)
    return rewrites


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


def rewrite_query(
    *,
    config: Config,
    query_id: str,
    query_text: str,
    run_entries: Dict[str, List[Dict[str, object]]],
    doc_lookup: Dict[str, int],
    offsets: List[int],
    forward_file,
    usage: UsageTotals,
) -> List[str]:
    usage.eligible_queries += 1
    grounding_terms = extract_grounding_terms(
        config=config,
        query_id=query_id,
        query_text=query_text,
        run_entries=run_entries,
        doc_lookup=doc_lookup,
        offsets=offsets,
        forward_file=forward_file,
    )
    if grounding_terms:
        usage.grounded_queries += 1

    system_prompt, user_prompt = rewrite_prompt(query_text, grounding_terms, config.rewrite_count, config.max_output_terms)
    usage.estimated_input_tokens += estimated_tokens(system_prompt) + estimated_tokens(user_prompt)
    usage.estimated_output_tokens += 16 * config.rewrite_count
    response_json = cached_or_live_json(
        config=config,
        cache_payload={
            "kind": "query_rewrite",
            "mode": config.mode,
            "model": config.model,
            "prompt_version": config.prompt_version,
            "query_id": query_id,
            "query_text": query_text,
            "rewrite_count": str(config.rewrite_count),
            "max_query_terms": str(config.max_query_terms),
            "max_output_terms": str(config.max_output_terms),
            "ground_docs": str(config.ground_docs),
            "ground_terms": str(config.ground_terms),
            "ground_doc_words": str(config.ground_doc_words),
            "grounding_terms": " ".join(grounding_terms),
        },
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        usage=usage,
    )
    response_text = extract_text(response_json)
    response_usage = response_json.get("usage", {})
    usage.actual_input_tokens += int(response_usage.get("input_tokens", 0))
    usage.actual_output_tokens += int(response_usage.get("output_tokens", 0))

    normalized_rewrites: List[str] = []
    seen = set()
    for raw_rewrite in parse_rewrites(response_text):
        normalized = normalize_rewrite(query_text, raw_rewrite, config.max_output_terms)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_rewrites.append(normalized)
        if len(normalized_rewrites) >= config.rewrite_count:
            break

    if normalized_rewrites:
        usage.rewritten_queries += 1
        usage.rewrite_lines += len(normalized_rewrites)
    return normalized_rewrites


def metadata_lines(config: Config, output_file: Path, slot_files: List[Path], queries_total: int, usage: UsageTotals) -> List[str]:
    lines = [
        f"JASSJR_OPENAI_QUERY_REWRITE_MODE: {config.mode}",
        f"JASSJR_OPENAI_QUERY_REWRITE_KEY_SOURCE: {config.key_source}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MODEL: {config.model}",
        f"JASSJR_OPENAI_QUERY_REWRITE_PROMPT_VERSION: {config.prompt_version}",
        f"JASSJR_OPENAI_QUERY_REWRITE_COUNT: {config.rewrite_count}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MAX_QUERY_TERMS: {config.max_query_terms}",
        f"JASSJR_OPENAI_QUERY_REWRITE_MAX_OUTPUT_TERMS: {config.max_output_terms}",
        f"JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOCS: {config.ground_docs}",
        f"JASSJR_OPENAI_QUERY_REWRITE_GROUND_TERMS: {config.ground_terms}",
        f"JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOC_WORDS: {config.ground_doc_words}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_DIR: {config.cache_dir}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_ONLY: {1 if config.cache_only else 0}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_TOTAL: {queries_total}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_ELIGIBLE: {usage.eligible_queries}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_GROUNDED: {usage.grounded_queries}",
        f"JASSJR_OPENAI_QUERY_REWRITE_QUERIES_REWRITTEN: {usage.rewritten_queries}",
        f"JASSJR_OPENAI_QUERY_REWRITE_TOTAL_REWRITES: {usage.rewrite_lines}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_HITS: {usage.cache_hits}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CACHE_MISSES: {usage.cache_misses}",
        f"JASSJR_OPENAI_QUERY_REWRITE_CALLS: {usage.calls}",
        f"JASSJR_OPENAI_QUERY_REWRITE_EST_INPUT_TOKENS: {usage.estimated_input_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_EST_OUTPUT_TOKENS: {usage.estimated_output_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_ACTUAL_INPUT_TOKENS: {usage.actual_input_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_ACTUAL_OUTPUT_TOKENS: {usage.actual_output_tokens}",
        f"JASSJR_OPENAI_QUERY_REWRITE_OUTPUT_FILE: {output_file}",
    ]
    for slot_index, slot_file in enumerate(slot_files, start=1):
        lines.append(f"JASSJR_OPENAI_QUERY_REWRITE_SLOT_{slot_index}_FILE: {slot_file}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sparse-query OpenAI rewrite sidecars for WSJ title queries.")
    parser.add_argument("--repo-root", default="", help="Repository root for .env loading")
    parser.add_argument("--workdir", default="", help="Search workdir")
    parser.add_argument("--topics-file", required=True, help="Input topics file")
    parser.add_argument("--output-file", required=True, help="Where to write aggregate rewritten sparse topics")
    parser.add_argument("--ground-run-file", default="", help="Optional TREC run whose top documents ground rewrites")
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
    slot_files = [slot_output_path(output_file, slot_index) for slot_index in range(1, config.rewrite_count + 1)]

    queries = parse_topics(topics_path)
    usage = UsageTotals()

    if args.check_config:
        for line in metadata_lines(config, output_file, slot_files, len(queries), usage):
            print(line)
        return 0

    if config.mode == "off":
        output_file.write_text("", encoding="utf-8")
        for slot_file in slot_files:
            slot_file.write_text("", encoding="utf-8")
        if args.metadata_file:
            Path(args.metadata_file).write_text(
                "\n".join(metadata_lines(config, output_file, slot_files, len(queries), usage)) + "\n",
                encoding="utf-8",
            )
        return 0

    run_entries: Dict[str, List[Dict[str, object]]] = {}
    doc_lookup: Dict[str, int] = {}
    offsets: List[int] = []
    forward_file = None
    if config.ground_docs > 0:
        if not args.ground_run_file:
            raise SystemExit("--ground-run-file is required when JASSJR_OPENAI_QUERY_REWRITE_GROUND_DOCS > 0")
        ground_run_path = Path(args.ground_run_file).expanduser()
        if not ground_run_path.is_absolute():
            ground_run_path = (Path.cwd() / ground_run_path).resolve()
        if not ground_run_path.is_file():
            raise SystemExit(f"ground run not found: {ground_run_path}")
        run_entries = parse_run(ground_run_path)
        doc_lookup, offsets, forward_file = load_doc_index(workdir)

    aggregate_lines: List[str] = []
    slot_lines: List[List[str]] = [[] for _ in slot_files]

    try:
        for query_id, query_text in queries:
            if not should_rewrite(config, query_text):
                continue
            rewrites = rewrite_query(
                config=config,
                query_id=query_id,
                query_text=query_text,
                run_entries=run_entries,
                doc_lookup=doc_lookup,
                offsets=offsets,
                forward_file=forward_file,
                usage=usage,
            )
            for slot_index, rewrite in enumerate(rewrites):
                line = f"{query_id} {rewrite}"
                aggregate_lines.append(line)
                slot_lines[slot_index].append(line)
    finally:
        if forward_file is not None:
            forward_file.close()

    output_file.write_text("\n".join(aggregate_lines) + ("\n" if aggregate_lines else ""), encoding="utf-8")
    for slot_file, lines in zip(slot_files, slot_lines):
        slot_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if args.metadata_file:
        Path(args.metadata_file).write_text(
            "\n".join(metadata_lines(config, output_file, slot_files, len(queries), usage)) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
