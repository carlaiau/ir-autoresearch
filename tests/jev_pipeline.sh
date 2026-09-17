#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
cat > "$fixture/jassjr-search" <<'SCRIPT'
#!/usr/bin/env bash
[[ "${JASSJR_RERANK_DOCS:-}" == 0 ]] || exit 91
cat >/dev/null
printf '1 Q0 A 1 2 old\n1 Q0 B 2 1 old\n'
SCRIPT
cat > "$fixture/python3" <<'SCRIPT'
#!/usr/bin/env bash
printf 'Unexpected legacy Python reranker invocation\n' >&2
exit 92
SCRIPT
cat > "$fixture/jev-python" <<'SCRIPT'
#!/usr/bin/env bash
[[ "$1" == */rerank_jev.py ]] || exit 93
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run) input="$2" ;;
    --output) output="$2" ;;
    --metadata) metadata="$2" ;;
    --mode) [[ "$2" == pointwise ]] || exit 94 ;;
  esac
  shift 2
done
cp "$input" "$output"
printf '{"status":"complete"}\n' > "$metadata"
SCRIPT
chmod +x "$fixture/jassjr-search" "$fixture/python3" "$fixture/jev-python"
printf '<DOC><DOCNO>A</DOCNO><TEXT>test</TEXT></DOC>\n' > "$fixture/collection"
printf '1 test\n' | env PATH="$fixture:$PATH" \
 JASSJR_JEV_RERANK=pointwise JASSJR_JEV_PYTHON="$fixture/jev-python" \
 JASSJR_JEV_COLLECTION="$fixture/collection" JASSJR_SEMANTIC_MODE=off \
 JASSJR_OPENAI_QUERY_REWRITE_MODE=off JASSJR_OPENAI_RERANK_MODE=mono \
 "$repo_root/tools/run_search_pipeline.sh" --workdir "$fixture" --metadata-file "$fixture/meta" > "$fixture/result"
cmp "$fixture/result" "$fixture/pre-jev.trec"
grep -q '^JASSJR_OPENAI_RERANK_MODE: off$' "$fixture/meta"
grep -q '^JASSJR_JEV_RERANK: pointwise$' "$fixture/meta"
printf 'JEV pipeline bypasses legacy reranking and preserves candidate input\n'
