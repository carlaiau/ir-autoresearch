#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
fixture="$repo_root/tests/fixtures/test_documents.xml"
topics="$repo_root/tests/fixtures/smoke_topics.txt"
qrels="$repo_root/tests/fixtures/smoke_qrels.txt"
workdir="$repo_root/smoke-eval"
index_cmd="go run $repo_root/index/JASSjr_index.go"
search_cmd="go run $repo_root/search/JASSjr_search.go"

usage() {
  cat <<EOF
Usage: $0 [-i "index command"] [-s "search command"] [-w workdir]

Run a lightweight end-to-end smoke evaluation on the toy fixture using trec_eval.

Options:
  -i <cmd>  Index command. The fixture path is appended as the final argument.
            Default: $index_cmd
  -s <cmd>  Search command. The smoke topics are piped to stdin.
            Default: $search_cmd
  -w <dir>  Working directory for temporary index and run files.
            Default: $workdir
  -h        Show this help text.
EOF
}

while getopts ":i:s:w:h" opt; do
  case "$opt" in
    i)
      index_cmd="$OPTARG"
      ;;
    s)
      search_cmd="$OPTARG"
      ;;
    w)
      workdir="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    :)
      printf "Missing value for -%s\n\n" "$OPTARG" >&2
      usage >&2
      exit 1
      ;;
    \?)
      printf "Unknown option: -%s\n\n" "$OPTARG" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v trec_eval >/dev/null 2>&1; then
  printf "trec_eval is required but was not found on PATH\n" >&2
  exit 1
fi

mkdir -p "$workdir"
workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"

cp "$fixture" "$workdir/test_documents.xml"
cp "$topics" "$workdir/smoke_topics.txt"
cp "$qrels" "$workdir/smoke_qrels.txt"

rm -f \
  "$workdir/docids.bin" \
  "$workdir/lengths.bin" \
  "$workdir/postings.bin" \
  "$workdir/results.trec" \
  "$workdir/vocab.bin"

printf "Indexing toy fixture in %s\n" "$workdir"
(
  cd "$workdir" || exit 1
  bash -lc "$index_cmd test_documents.xml"
)

printf "Running smoke topics\n"
(
  cd "$workdir" || exit 1
  bash -lc "$search_cmd" < smoke_topics.txt > results.trec
)

printf "Evaluating smoke run with trec_eval\n"
summary="$(
  cd "$workdir" &&
    trec_eval -m map -m recip_rank -m P.5 -c -M1000 smoke_qrels.txt results.trec
)"
printf "%s\n" "$summary"

grep -Eq '^map[[:space:]]+all[[:space:]]+1\.0000$' <<<"$summary" || {
  printf "Smoke eval failed: expected map=1.0000\n" >&2
  exit 1
}

grep -Eq '^recip_rank[[:space:]]+all[[:space:]]+1\.0000$' <<<"$summary" || {
  printf "Smoke eval failed: expected recip_rank=1.0000\n" >&2
  exit 1
}

printf "Smoke evaluation passed\n"
