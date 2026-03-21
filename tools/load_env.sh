#!/usr/bin/env bash

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    [[ "$line" == *=* ]] || continue

    local name="${line%%=*}"
    local value="${line#*=}"
    name="${name//[[:space:]]/}"
    [[ -z "$name" ]] && continue

    if [[ -n "${!name+x}" ]]; then
      continue
    fi

    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$name=$value"
  done < "$file"
}

load_repo_env() {
  local repo_root="$1"
  load_env_file "$repo_root/.env"
  load_env_file "$repo_root/.env.local"
}

detect_openai_key_source() {
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    printf "env\n"
  else
    printf "missing\n"
  fi
}

load_repo_env_with_key_source() {
  local repo_root="$1"
  local key_source

  key_source="$(detect_openai_key_source)"
  load_repo_env "$repo_root"
  if [[ "$key_source" == "missing" && -n "${OPENAI_API_KEY:-}" ]]; then
    key_source="dotenv"
  fi

  printf "%s\n" "$key_source"
}
