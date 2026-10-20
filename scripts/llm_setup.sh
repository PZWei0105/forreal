#!/usr/bin/env bash
# 準備翻譯器：llama.cpp（CPU 版）＋ Qwen3 4B 開源模型。下載一次後由 GitHub 快取保存。
set -uo pipefail
D="$HOME/.cache/forreal-llm"
mkdir -p "$D"
LOG=/tmp/llm_setup.log
exec > >(tee -a "$LOG") 2>&1
echo "== setup $(date -u +%FT%TZ) cpu=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G disk=$(df -h ~ | awk 'NR==2{print $4}')"

if [ ! -x "$D/bin/llama-server" ]; then
  echo "llama.cpp assets:"; gh api repos/ggml-org/llama.cpp/releases/latest --jq '.tag_name, (.assets[].name)' 2>&1 | grep -i -E "ubuntu|b[0-9]+$|linux" | head -20
  url=$(gh api repos/ggml-org/llama.cpp/releases/latest \
        --jq '.assets[] | select(.name | test("bin-ubuntu-x64\\.(zip|tar\\.gz)$")) | .browser_download_url' | head -1)
  echo "llama.cpp: $url"
  if [ -n "$url" ]; then
    rm -rf /tmp/llama && mkdir -p /tmp/llama
    curl -fsSL --retry 3 "$url" -o /tmp/llama/pkg
    case "$url" in
      *.zip) unzip -q /tmp/llama/pkg -d /tmp/llama/x ;;
      *) mkdir -p /tmp/llama/x && tar -xzf /tmp/llama/pkg -C /tmp/llama/x ;;
    esac
    srv=$(find /tmp/llama/x -type f -name llama-server | head -1)
    echo "llama-server found at: $srv"; ls "$(dirname "$srv")" 2>/dev/null | head -30
    if [ -n "$srv" ]; then
      mkdir -p "$D/bin" && cp -a "$(dirname "$srv")"/. "$D/bin/" && chmod +x "$D/bin/llama-server"
    fi
  fi
fi

if [ ! -s "$D/model.gguf" ]; then
  for u in \
    "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
    "https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf"; do
    echo "model: trying $u"
    curl -fL --retry 3 --retry-delay 5 -sS "$u" -o "$D/model.gguf.part"; rc=$?
    echo "curl rc=$rc size=$(stat -c%s "$D/model.gguf.part" 2>/dev/null)"
    if [ $rc -eq 0 ] && [ "$(stat -c%s "$D/model.gguf.part")" -gt 1000000000 ]; then
      mv "$D/model.gguf.part" "$D/model.gguf"
      basename "$u" .gguf > "$D/model.txt"
      break
    fi
    rm -f "$D/model.gguf.part"
  done
fi

ls -la "$D" "$D/bin" 2>/dev/null | head -30
if [ -x "$D/bin/llama-server" ] && [ -s "$D/model.gguf" ]; then
  echo "ready=true" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "translator files ready: $(cat "$D/model.txt" 2>/dev/null)"
else
  echo "ready=false" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "translator files missing"
fi
