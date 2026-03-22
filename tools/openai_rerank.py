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


DEFAULT_MONO_MODEL = "gpt-5-mini"
DEFAULT_DUO_MODEL = "gpt-5-mini"
DEFAULT_MODE = "off"
DEFAULT_MONO_DOCS = 85
DEFAULT_DUO_DOCS = 10
DEFAULT_DOC_WORDS = 220
DEFAULT_PROMPT_VERSION = "openai-rerank-v2"
DEFAULT_CACHE_DIR = ".cache/openai-rerank"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_OPENAI_RETRIES = 5
SCORE_RE = re.compile(r"-?\d+")
VALID_MODES = {"off", "mono", "mono_duo"}
MODEL_PRICING = {
    "gpt-5-mini": (0.25, 2.0),
    "gpt-5.1": (1.25, 10.0),
}


@dataclass
class Config:
    repo_root: Path
    workdir: Path
    mode: str
    mono_model: str
    duo_model: str
    mono_docs: int
    duo_docs: int
    doc_words: int
    prompt_version: str
    cache_dir: Path
    cache_only: bool
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
    mono_calls: int = 0
    duo_calls: int = 0


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
    mode = os.getenv("JASSJR_OPENAI_RERANK_MODE", DEFAULT_MODE).strip() or DEFAULT_MODE
    mono_model = os.getenv("JASSJR_OPENAI_MONO_MODEL", DEFAULT_MONO_MODEL).strip() or DEFAULT_MONO_MODEL
    duo_model = os.getenv("JASSJR_OPENAI_DUO_MODEL", DEFAULT_DUO_MODEL).strip() or DEFAULT_DUO_MODEL
    mono_docs = int_from_env("JASSJR_OPENAI_MONO_DOCS", DEFAULT_MONO_DOCS)
    duo_docs = int_from_env("JASSJR_OPENAI_DUO_DOCS", DEFAULT_DUO_DOCS)
    doc_words = int_from_env("JASSJR_OPENAI_DOC_WORDS", DEFAULT_DOC_WORDS)
    prompt_version = os.getenv("JASSJR_OPENAI_PROMPT_VERSION", DEFAULT_PROMPT_VERSION).strip() or DEFAULT_PROMPT_VERSION
    cache_dir_raw = os.getenv("JASSJR_OPENAI_CACHE_DIR", DEFAULT_CACHE_DIR).strip() or DEFAULT_CACHE_DIR
    cache_dir = Path(cache_dir_raw).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = (repo_root / cache_dir).resolve()
    cache_only = os.getenv("JASSJR_OPENAI_CACHE_ONLY", "") == "1"

    if mode not in VALID_MODES:
        raise SystemExit(f"JASSJR_OPENAI_RERANK_MODE must be one of: {', '.join(sorted(VALID_MODES))}")
    if mono_docs <= 0:
        raise SystemExit("JASSJR_OPENAI_MONO_DOCS must be positive")
    if duo_docs <= 1:
        raise SystemExit("JASSJR_OPENAI_DUO_DOCS must be greater than 1")
    if doc_words <= 0:
        raise SystemExit("JASSJR_OPENAI_DOC_WORDS must be positive")
    if mode == "mono_duo" and duo_model == "gpt-5.1":
        raise SystemExit("gpt-5.1 is only supported as a mono-stage comparison model in v1; duo must use gpt-5-mini")
    if mode != "off" and key_source == "missing" and not cache_only:
        raise SystemExit("OPENAI_API_KEY is required for uncached OpenAI-backed reranking")

    return Config(
        repo_root=repo_root,
        workdir=workdir,
        mode=mode,
        mono_model=mono_model,
        duo_model=duo_model,
        mono_docs=mono_docs,
        duo_docs=duo_docs,
        doc_words=doc_words,
        prompt_version=prompt_version,
        cache_dir=cache_dir,
        cache_only=cache_only,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        key_source=key_source,
    )


def parse_topics(path: Path) -> Dict[str, str]:
    queries: Dict[str, str] = {}
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
        queries[query_id] = query_text
    return queries


def parse_run(path: Path) -> Dict[str, List[Dict[str, str]]]:
    runs: Dict[str, List[Dict[str, str]]] = {}
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
        entries.sort(key=lambda entry: entry["rank"])
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


def read_doc_terms(forward_file, offsets: List[int], doc_index: int, limit_words: int) -> str:
    offset = offsets[doc_index * 2]
    size = offsets[doc_index * 2 + 1]
    if size <= 0:
        return ""
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
    return " ".join(terms)


def cache_path(cache_dir: Path, payload: Dict[str, str]) -> Path:
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.json"


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

    if "choices" in response_json:
        for choice in response_json.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content)
        if texts:
            return "\n".join(texts).strip()

    if response_json.get("status") == "incomplete":
        detail = response_json.get("incomplete_details") or {}
        raise RuntimeError(f"incomplete OpenAI response: {detail}")

    raise RuntimeError("could not extract text output from OpenAI response")


def parse_score(text: str) -> int:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict) and "score" in payload:
            value = int(payload["score"])
            return max(0, min(100, value))
    except Exception:
        pass

    match = SCORE_RE.search(stripped)
    if not match:
        raise RuntimeError(f"expected a numeric relevance score, got: {text!r}")
    value = int(match.group(0))
    return max(0, min(100, value))


def parse_winner(text: str) -> str:
    stripped = text.strip().upper()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get("winner") in {"A", "B"}:
            return payload["winner"]
    except Exception:
        pass
    if stripped.startswith("A"):
        return "A"
    if stripped.startswith("B"):
        return "B"
    raise RuntimeError(f"expected pairwise winner A or B, got: {text!r}")


def mono_text_format() -> Dict:
    return {
        "type": "json_schema",
        "name": "mono_score",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                }
            },
            "required": ["score"],
            "additionalProperties": False,
        },
    }


def duo_text_format() -> Dict:
    return {
        "type": "json_schema",
        "name": "duo_choice",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "winner": {
                    "type": "string",
                    "enum": ["A", "B"],
                }
            },
            "required": ["winner"],
            "additionalProperties": False,
        },
    }


def post_openai(config: Config, model: str, system_prompt: str, user_prompt: str, text_format: Dict) -> Dict:
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "max_output_tokens": 64,
        "reasoning": {"effort": "minimal"},
        "text": {
            "format": text_format,
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
            if exc.code in RETRYABLE_HTTP_CODES and attempt < MAX_OPENAI_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 16))
                continue
            raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_OPENAI_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 16))
                continue
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
    raise RuntimeError("OpenAI request failed after retries")


def estimated_tokens(text: str) -> int:
    return len(text.split())


def pricing_for(model: str) -> Optional[Tuple[float, float]]:
    return MODEL_PRICING.get(model)


def add_cost(metadata: UsageTotals, model: str, input_tokens: int, output_tokens: int) -> float:
    rates = pricing_for(model)
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def ensure_cache_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def mono_prompt(query_text: str, doc_text: str) -> Tuple[str, str]:
    system = (
        "You rerank Wall Street Journal search results. "
        "Score how relevant the document is to the query on a scale from 0 to 100. "
        "Higher means more relevant."
    )
    user = f"Query: {query_text}\n\nDocument:\n{doc_text}"
    return system, user


def duo_prompt(query_text: str, doc_a: str, doc_b: str) -> Tuple[str, str]:
    system = (
        "You compare two Wall Street Journal documents for a search query. "
        "Choose the more relevant document."
    )
    user = f"Query: {query_text}\n\nDocument A:\n{doc_a}\n\nDocument B:\n{doc_b}"
    return system, user


def cached_or_live_json(
    *,
    config: Config,
    stage: str,
    model: str,
    cache_payload: Dict[str, str],
    system_prompt: str,
    user_prompt: str,
    text_format: Dict,
    usage: UsageTotals,
) -> Dict:
    ensure_cache_dir(config.cache_dir)
    path = cache_path(config.cache_dir, cache_payload)
    if path.is_file():
        usage.cache_hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    usage.cache_misses += 1
    if config.cache_only:
        raise RuntimeError(f"cache miss while JASSJR_OPENAI_CACHE_ONLY=1: {path.name}")
    if not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is required for cache misses")

    response_json = post_openai(config, model, system_prompt, user_prompt, text_format)
    path.write_text(json.dumps(response_json, sort_keys=True), encoding="utf-8")
    if stage == "mono":
        usage.mono_calls += 1
    elif stage == "duo":
        usage.duo_calls += 1
    return response_json


def score_document(
    *,
    config: Config,
    query_id: str,
    query_text: str,
    doc_id: str,
    doc_text: str,
    usage: UsageTotals,
) -> int:
    system_prompt, user_prompt = mono_prompt(query_text, doc_text)
    usage.estimated_input_tokens += estimated_tokens(system_prompt) + estimated_tokens(user_prompt)
    usage.estimated_output_tokens += 8
    response_json = cached_or_live_json(
        config=config,
        stage="mono",
        model=config.mono_model,
        cache_payload={
            "kind": "mono",
            "model": config.mono_model,
            "prompt_version": config.prompt_version,
            "query_id": query_id,
            "doc_id": doc_id,
            "query_text": query_text,
            "doc_text": doc_text,
        },
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        text_format=mono_text_format(),
        usage=usage,
    )
    response_text = extract_text(response_json)
    response_usage = response_json.get("usage", {})
    usage.actual_input_tokens += int(response_usage.get("input_tokens", 0))
    usage.actual_output_tokens += int(response_usage.get("output_tokens", 0))
    return parse_score(response_text)


def compare_documents(
    *,
    config: Config,
    query_id: str,
    query_text: str,
    doc_a_id: str,
    doc_a_text: str,
    doc_b_id: str,
    doc_b_text: str,
    usage: UsageTotals,
) -> str:
    system_prompt, user_prompt = duo_prompt(query_text, doc_a_text, doc_b_text)
    usage.estimated_input_tokens += estimated_tokens(system_prompt) + estimated_tokens(user_prompt)
    usage.estimated_output_tokens += 8
    response_json = cached_or_live_json(
        config=config,
        stage="duo",
        model=config.duo_model,
        cache_payload={
            "kind": "duo",
            "model": config.duo_model,
            "prompt_version": config.prompt_version,
            "query_id": query_id,
            "doc_a_id": doc_a_id,
            "doc_b_id": doc_b_id,
            "query_text": query_text,
            "doc_a_text": doc_a_text,
            "doc_b_text": doc_b_text,
        },
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        text_format=duo_text_format(),
        usage=usage,
    )
    response_text = extract_text(response_json)
    response_usage = response_json.get("usage", {})
    usage.actual_input_tokens += int(response_usage.get("input_tokens", 0))
    usage.actual_output_tokens += int(response_usage.get("output_tokens", 0))
    return parse_winner(response_text)


def rerank_query(
    *,
    config: Config,
    query_id: str,
    query_text: str,
    entries: List[Dict[str, str]],
    doc_lookup: Dict[str, int],
    offsets: List[int],
    forward_file,
    usage: UsageTotals,
) -> List[Dict[str, str]]:
    rerank_limit = min(config.mono_docs, len(entries))
    prefix = []
    for entry in entries[:rerank_limit]:
        doc_index = doc_lookup.get(entry["doc_id"])
        if doc_index is None:
            doc_text = ""
        else:
            doc_text = read_doc_terms(forward_file, offsets, doc_index, config.doc_words)
        score = score_document(
            config=config,
            query_id=query_id,
            query_text=query_text,
            doc_id=entry["doc_id"],
            doc_text=doc_text,
            usage=usage,
        )
        enriched = dict(entry)
        enriched["llm_score"] = score
        enriched["doc_text"] = doc_text
        prefix.append(enriched)

    prefix.sort(key=lambda item: (-item["llm_score"], -item["score"], item["rank"]))

    if config.mode == "mono_duo":
        duo_limit = min(config.duo_docs, len(prefix))
        wins = {item["doc_id"]: 0 for item in prefix[:duo_limit]}
        duo_prefix = prefix[:duo_limit]
        for left_index in range(len(duo_prefix)):
            for right_index in range(left_index + 1, len(duo_prefix)):
                left = duo_prefix[left_index]
                right = duo_prefix[right_index]
                winner = compare_documents(
                    config=config,
                    query_id=query_id,
                    query_text=query_text,
                    doc_a_id=left["doc_id"],
                    doc_a_text=left["doc_text"],
                    doc_b_id=right["doc_id"],
                    doc_b_text=right["doc_text"],
                    usage=usage,
                )
                wins[left["doc_id"] if winner == "A" else right["doc_id"]] += 1
        duo_prefix.sort(
            key=lambda item: (
                -wins[item["doc_id"]],
                -item["llm_score"],
                -item["score"],
                item["rank"],
            )
        )
        prefix = duo_prefix + prefix[duo_limit:]

    for item in prefix:
        item.pop("doc_text", None)

    return prefix + entries[rerank_limit:]


def write_results(runs: Dict[str, List[Dict[str, str]]], output_path: Optional[Path]) -> None:
    lines: List[str] = []
    for query_id in sorted(runs, key=lambda item: int(item) if item.isdigit() else item):
        entries = runs[query_id]
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            synthetic_score = float(total - index + 1)
            lines.append(f"{query_id} Q0 {entry['doc_id']} {index} {synthetic_score:.4f} JASSjr")
    content = "\n".join(lines) + ("\n" if lines else "")
    if output_path is None:
        sys.stdout.write(content)
    else:
        output_path.write_text(content, encoding="utf-8")


def metadata_lines(config: Config, usage: UsageTotals) -> List[str]:
    est_cost = add_cost(usage, config.mono_model, usage.estimated_input_tokens, usage.estimated_output_tokens)
    actual_cost = add_cost(usage, config.mono_model, usage.actual_input_tokens, usage.actual_output_tokens)
    if config.mode == "mono_duo" and config.duo_model != config.mono_model:
        # If models diverge later, keep the current estimate conservative by logging only aggregate values.
        actual_cost = 0.0
        est_cost = 0.0

    lines = [
        f"JASSJR_OPENAI_RERANK_MODE: {config.mode}",
        f"JASSJR_OPENAI_KEY_SOURCE: {config.key_source}",
        f"JASSJR_OPENAI_MONO_MODEL: {config.mono_model}",
        f"JASSJR_OPENAI_DUO_MODEL: {config.duo_model}",
        f"JASSJR_OPENAI_PROMPT_VERSION: {config.prompt_version}",
        f"JASSJR_OPENAI_MONO_DOCS: {config.mono_docs}",
        f"JASSJR_OPENAI_DUO_DOCS: {config.duo_docs}",
        f"JASSJR_OPENAI_DOC_WORDS: {config.doc_words}",
        f"JASSJR_OPENAI_CACHE_DIR: {config.cache_dir}",
        f"JASSJR_OPENAI_CACHE_HITS: {usage.cache_hits}",
        f"JASSJR_OPENAI_CACHE_MISSES: {usage.cache_misses}",
        f"JASSJR_OPENAI_MONO_CALLS: {usage.mono_calls}",
        f"JASSJR_OPENAI_DUO_CALLS: {usage.duo_calls}",
        f"JASSJR_OPENAI_EST_INPUT_TOKENS: {usage.estimated_input_tokens}",
        f"JASSJR_OPENAI_EST_OUTPUT_TOKENS: {usage.estimated_output_tokens}",
        f"JASSJR_OPENAI_ACTUAL_INPUT_TOKENS: {usage.actual_input_tokens}",
        f"JASSJR_OPENAI_ACTUAL_OUTPUT_TOKENS: {usage.actual_output_tokens}",
        f"JASSJR_OPENAI_EST_COST_USD: {est_cost:.6f}",
        f"JASSJR_OPENAI_ACTUAL_COST_USD: {actual_cost:.6f}",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI-backed reranker for WSJ/TREC runs.")
    parser.add_argument("--repo-root", default="", help="Repository root for .env loading and cache resolution")
    parser.add_argument("--workdir", required=False, default="", help="Index workdir containing docids.bin and forward.bin")
    parser.add_argument("--topics-file", default="", help="Topics file used to generate the run")
    parser.add_argument("--run-file", default="", help="Input TREC run file to rerank")
    parser.add_argument("--output-file", default="", help="Where to write the reranked TREC run")
    parser.add_argument("--metadata-file", default="", help="Where to write reranker metadata lines")
    parser.add_argument("--check-config", action="store_true", help="Validate config and exit without reranking")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser() if args.repo_root else Path(__file__).resolve().parent.parent
    if not repo_root.is_absolute():
        repo_root = (Path.cwd() / repo_root).resolve()
    workdir = Path(args.workdir).expanduser() if args.workdir else repo_root
    if not workdir.is_absolute():
        workdir = (Path.cwd() / workdir).resolve()

    config = build_config(repo_root, workdir)

    if args.check_config:
        for line in metadata_lines(config, UsageTotals()):
            print(line)
        return 0

    if config.mode == "off":
        raise SystemExit("JASSJR_OPENAI_RERANK_MODE is off; nothing to rerank")
    if not args.topics_file or not args.run_file:
        raise SystemExit("--topics-file and --run-file are required unless --check-config is used")

    topics_file = Path(args.topics_file).expanduser()
    run_file = Path(args.run_file).expanduser()
    output_file = Path(args.output_file).expanduser() if args.output_file else None
    metadata_file = Path(args.metadata_file).expanduser() if args.metadata_file else None
    if not topics_file.is_absolute():
        topics_file = (Path.cwd() / topics_file).resolve()
    if not run_file.is_absolute():
        run_file = (Path.cwd() / run_file).resolve()
    if output_file is not None and not output_file.is_absolute():
        output_file = (Path.cwd() / output_file).resolve()
    if metadata_file is not None and not metadata_file.is_absolute():
        metadata_file = (Path.cwd() / metadata_file).resolve()

    queries = parse_topics(topics_file)
    runs = parse_run(run_file)
    doc_lookup, offsets, forward_file = load_doc_index(workdir)
    usage = UsageTotals()

    try:
        reranked: Dict[str, List[Dict[str, str]]] = {}
        for query_id, entries in runs.items():
            query_text = queries.get(query_id, query_id)
            reranked[query_id] = rerank_query(
                config=config,
                query_id=query_id,
                query_text=query_text,
                entries=entries,
                doc_lookup=doc_lookup,
                offsets=offsets,
                forward_file=forward_file,
                usage=usage,
            )
    finally:
        forward_file.close()

    write_results(reranked, output_file)
    if metadata_file is not None:
        metadata_file.write_text("\n".join(metadata_lines(config, usage)) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
