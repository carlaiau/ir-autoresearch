#!/usr/bin/env python3

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_MODE = "off"
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 512
DEFAULT_DOC_WORDS = 220
DEFAULT_BATCH_SIZE = 64
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
RETRYABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_OPENAI_RETRIES = 5
VECTOR_FILE_NAME = "dense-docs.f32"
VECTOR_FILE_PART_NAME = "dense-docs.f32.part"
META_FILE_NAME = "dense-docs.meta.json"
META_FILE_PART_NAME = "dense-docs.meta.part.json"


@dataclass
class Config:
    repo_root: Path
    workdir: Path
    mode: str
    model: str
    dimensions: int
    doc_words: int
    batch_size: int
    api_key: str
    key_source: str


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
    mode = os.getenv("JASSJR_SEMANTIC_MODE", DEFAULT_MODE).strip() or DEFAULT_MODE
    model = os.getenv("JASSJR_SEMANTIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    dimensions = int_from_env("JASSJR_SEMANTIC_DIMENSIONS", DEFAULT_DIMENSIONS)
    doc_words = int_from_env("JASSJR_SEMANTIC_DOC_WORDS", DEFAULT_DOC_WORDS)
    batch_size = int_from_env("JASSJR_SEMANTIC_BATCH_SIZE", DEFAULT_BATCH_SIZE)

    if mode not in {"off", "openai"}:
        raise SystemExit("JASSJR_SEMANTIC_MODE must be one of: off, openai")
    if dimensions <= 0:
        raise SystemExit("JASSJR_SEMANTIC_DIMENSIONS must be positive")
    if doc_words <= 0:
        raise SystemExit("JASSJR_SEMANTIC_DOC_WORDS must be positive")
    if batch_size <= 0:
        raise SystemExit("JASSJR_SEMANTIC_BATCH_SIZE must be positive")
    if mode == "openai" and key_source == "missing":
        raise SystemExit("OPENAI_API_KEY is required when JASSJR_SEMANTIC_MODE=openai")

    return Config(
        repo_root=repo_root,
        workdir=workdir,
        mode=mode,
        model=model,
        dimensions=dimensions,
        doc_words=doc_words,
        batch_size=batch_size,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        key_source=key_source,
    )


def load_doc_index(workdir: Path) -> Tuple[List[str], List[int], object]:
    docids = [line for line in (workdir / "docids.bin").read_text(encoding="utf-8").splitlines() if line]
    offsets_raw = (workdir / "forward_offsets.bin").read_bytes()
    offsets = [
        int.from_bytes(offsets_raw[i : i + 8], byteorder=sys.byteorder, signed=True)
        for i in range(0, len(offsets_raw), 8)
    ]
    if len(offsets) != len(docids) * 2:
        raise SystemExit("forward_offsets.bin must contain offset/size pairs for every document")
    forward_file = (workdir / "forward.bin").open("rb")
    return docids, offsets, forward_file


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


def normalize_embedding(values: List[float]) -> List[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return [0.0] * len(values)
    return [float(value / magnitude) for value in values]


def post_embeddings(config: Config, texts: List[str]) -> Dict:
    payload = {
        "input": texts,
        "model": config.model,
        "dimensions": config.dimensions,
        "encoding_format": "float",
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_EMBEDDINGS_URL,
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
            raise RuntimeError(f"OpenAI embeddings request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_OPENAI_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 16))
                continue
            raise RuntimeError(f"OpenAI embeddings request failed: {exc}") from exc
    raise RuntimeError("OpenAI embeddings request failed after retries")


def create_embeddings(config: Config, texts: List[str]) -> List[List[float]]:
    response_json = post_embeddings(config, texts)
    data = response_json.get("data", [])
    if len(data) != len(texts):
        raise RuntimeError(f"expected {len(texts)} embeddings, got {len(data)}")
    ordered = sorted(data, key=lambda item: item.get("index", 0))
    embeddings: List[List[float]] = []
    for item in ordered:
        values = item.get("embedding")
        if not isinstance(values, list):
            raise RuntimeError("embedding response did not include a float vector")
        embeddings.append(normalize_embedding([float(value) for value in values]))
    return embeddings


def metadata_payload(config: Config, documents: int, completed_documents: int, status: str, vector_file: Path) -> Dict:
    return {
        "mode": config.mode,
        "model": config.model,
        "dimensions": config.dimensions,
        "doc_words": config.doc_words,
        "batch_size": config.batch_size,
        "documents": documents,
        "completed_documents": completed_documents,
        "status": status,
        "key_source": config.key_source,
        "byte_order": sys.byteorder,
        "vector_file": str(vector_file),
    }


def write_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Optional[Dict]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def metadata_lines(config: Config, documents: int, vector_file: Path, meta_file: Path) -> List[str]:
    return [
        f"JASSJR_SEMANTIC_MODE: {config.mode}",
        f"JASSJR_SEMANTIC_KEY_SOURCE: {config.key_source}",
        f"JASSJR_SEMANTIC_MODEL: {config.model}",
        f"JASSJR_SEMANTIC_DIMENSIONS: {config.dimensions}",
        f"JASSJR_SEMANTIC_DOC_WORDS: {config.doc_words}",
        f"JASSJR_SEMANTIC_BATCH_SIZE: {config.batch_size}",
        f"JASSJR_SEMANTIC_DOCUMENTS: {documents}",
        f"JASSJR_SEMANTIC_DOC_VECTOR_FILE: {vector_file}",
        f"JASSJR_SEMANTIC_DOC_VECTOR_META: {meta_file}",
    ]


def matching_metadata(config: Config, payload: Dict, documents: int) -> bool:
    return (
        payload.get("mode") == config.mode
        and payload.get("model") == config.model
        and int(payload.get("dimensions", -1)) == config.dimensions
        and int(payload.get("doc_words", -1)) == config.doc_words
        and int(payload.get("batch_size", -1)) == config.batch_size
        and int(payload.get("documents", -1)) == documents
    )


def expected_vector_size(documents: int, dimensions: int) -> int:
    return documents * dimensions * 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Build resumable file-backed dense document vectors aligned to docids.bin.")
    parser.add_argument("--repo-root", default="", help="Repository root for .env loading")
    parser.add_argument("--workdir", required=False, default="", help="Index workdir containing docids.bin and forward.bin")
    parser.add_argument("--metadata-file", default="", help="Optional output path for human-readable metadata lines")
    parser.add_argument("--check-config", action="store_true", help="Validate config and exit without building vectors")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser() if args.repo_root else Path(__file__).resolve().parent.parent
    if not repo_root.is_absolute():
        repo_root = (Path.cwd() / repo_root).resolve()
    workdir = Path(args.workdir).expanduser() if args.workdir else repo_root
    if not workdir.is_absolute():
        workdir = (Path.cwd() / workdir).resolve()

    config = build_config(repo_root, workdir)

    docids_path = workdir / "docids.bin"
    if not docids_path.is_file():
        raise SystemExit(f"docids.bin not found in workdir: {workdir}")

    docids = [line for line in docids_path.read_text(encoding="utf-8").splitlines() if line]
    documents = len(docids)
    vector_file = workdir / VECTOR_FILE_NAME
    meta_file = workdir / META_FILE_NAME

    if args.check_config:
        lines = metadata_lines(config, documents, vector_file, meta_file)
        for line in lines:
            print(line)
        return 0

    if config.mode == "off":
        raise SystemExit("JASSJR_SEMANTIC_MODE is off; nothing to build")

    final_meta = read_json(meta_file)
    if final_meta and matching_metadata(config, final_meta, documents):
        if vector_file.is_file() and vector_file.stat().st_size == expected_vector_size(documents, config.dimensions):
            print(f"Using existing dense vectors in {vector_file}")
            if args.metadata_file:
                Path(args.metadata_file).write_text(
                    "\n".join(metadata_lines(config, documents, vector_file, meta_file)) + "\n",
                    encoding="utf-8",
                )
            return 0

    part_file = workdir / VECTOR_FILE_PART_NAME
    part_meta_file = workdir / META_FILE_PART_NAME
    part_meta = read_json(part_meta_file)
    completed_documents = 0
    row_size = config.dimensions * 4

    if part_meta and matching_metadata(config, part_meta, documents) and part_file.is_file():
        completed_documents = part_file.stat().st_size // row_size
        if completed_documents > documents:
            completed_documents = 0
    else:
        if part_file.exists():
            part_file.unlink()
        if part_meta_file.exists():
            part_meta_file.unlink()

    _, offsets, forward_file = load_doc_index(workdir)
    zero_bytes = array("f", [0.0] * config.dimensions).tobytes()

    try:
        with part_file.open("ab") as output:
            for batch_start in range(completed_documents, documents, config.batch_size):
                batch_end = min(batch_start + config.batch_size, documents)
                texts: List[str] = []
                text_doc_indexes: List[int] = []
                for doc_index in range(batch_start, batch_end):
                    text = read_doc_terms(forward_file, offsets, doc_index, config.doc_words)
                    if text:
                        texts.append(text)
                        text_doc_indexes.append(doc_index)

                embeddings_by_doc: Dict[int, List[float]] = {}
                if texts:
                    embeddings = create_embeddings(config, texts)
                    for doc_index, embedding in zip(text_doc_indexes, embeddings):
                        embeddings_by_doc[doc_index] = embedding

                for doc_index in range(batch_start, batch_end):
                    values = embeddings_by_doc.get(doc_index)
                    if values is None:
                        output.write(zero_bytes)
                        continue
                    array("f", values).tofile(output)

                completed_documents = batch_end
                write_json(
                    part_meta_file,
                    metadata_payload(config, documents, completed_documents, "partial", part_file),
                )
                print(f"Embedded {completed_documents}/{documents} documents")
    finally:
        forward_file.close()

    part_file.replace(vector_file)
    write_json(meta_file, metadata_payload(config, documents, documents, "complete", vector_file))
    if part_meta_file.exists():
        part_meta_file.unlink()

    print(f"Wrote dense vectors to {vector_file}")
    if args.metadata_file:
        Path(args.metadata_file).write_text(
            "\n".join(metadata_lines(config, documents, vector_file, meta_file)) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
