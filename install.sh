#!/usr/bin/env bash
# Freeflow installer — one command, it just works.
# Read this before piping it to bash. Every step is idempotent: safe to re-run.
set -euo pipefail

FREEFLOW_HOME="${HOME}/.local/share/freeflow"
FREEFLOW_CONFIG="${HOME}/.config/freeflow"
WHISPER_DIR="${FREEFLOW_HOME}/whisper.cpp"
MODELS_DIR="${FREEFLOW_HOME}/models"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBOOT_NEEDED=0

ok()   { echo "  ✅ $*"; }
skip() { echo "  ⏭  $* (already done)"; }
info() { echo "==> $*"; }
warn() { echo "  ⚠️  $*" >&2; }

# ---------------------------------------------------------------------------
# 0. Detect package manager
# ---------------------------------------------------------------------------
PKG_MANAGER=""
if command -v dnf >/dev/null 2>&1; then
  PKG_MANAGER="dnf"
elif command -v apt >/dev/null 2>&1; then
  PKG_MANAGER="apt"
elif command -v pacman >/dev/null 2>&1; then
  PKG_MANAGER="pacman"
else
  echo "No supported package manager found (dnf/apt/pacman). Install dependencies manually." >&2
  exit 1
fi
info "Detected package manager: ${PKG_MANAGER}"

pkg_install() {
  # $@ = list of package names FOR THE DETECTED MANAGER (caller maps names per-manager)
  case "${PKG_MANAGER}" in
    dnf)    sudo dnf install -y "$@" ;;
    apt)    sudo apt-get install -y "$@" ;;
    pacman) sudo pacman -S --needed --noconfirm "$@" ;;
  esac
}

pkg_have() {
  # $1 = command to check for presence (proxy for "package already installed")
  command -v "$1" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------
info "Step 1/9: system dependencies"

# name -> (dnf apt pacman) package names, and a command to check it's present
declare -A DEPS_DNF=(
  [git]=git [cmake]=cmake [gcc-c++]=gcc-c++ [pw-record]=pipewire-utils
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [curl]=curl
)
declare -A DEPS_APT=(
  [git]=git [cmake]=cmake [gcc-c++]=build-essential [pw-record]=pipewire-utils
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [curl]=curl
)
declare -A DEPS_PACMAN=(
  [git]=git [cmake]=cmake [gcc-c++]=base-devel [pw-record]=pipewire
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [curl]=curl
)

declare -A DEPS_CHECK=(
  [git]=git [cmake]=cmake [gcc-c++]=g++ [pw-record]=pw-record
  [wl-copy]=wl-copy [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [curl]=curl
)

case "${PKG_MANAGER}" in
  dnf)    declare -n DEPS_MAP=DEPS_DNF ;;
  apt)    declare -n DEPS_MAP=DEPS_APT ;;
  pacman) declare -n DEPS_MAP=DEPS_PACMAN ;;
esac

missing_pkgs=()
for name in "${!DEPS_CHECK[@]}"; do
  check_bin="${DEPS_CHECK[$name]}"
  if pkg_have "${check_bin}"; then
    skip "${name}"
  else
    missing_pkgs+=("${DEPS_MAP[$name]}")
  fi
done

if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  # de-duplicate (gcc-c++/build-essential and cmake can repeat across dnf/apt aliasing)
  mapfile -t missing_pkgs < <(printf '%s\n' "${missing_pkgs[@]}" | sort -u)
  echo "About to install (${PKG_MANAGER}): ${missing_pkgs[*]}"
  read -r -p "Proceed with sudo install? [y/N] " reply
  if [[ "${reply}" =~ ^[Yy]$ ]]; then
    pkg_install "${missing_pkgs[@]}"
    ok "installed: ${missing_pkgs[*]}"
  else
    echo "Cannot continue without required dependencies." >&2
    exit 1
  fi
fi

# Optional: pill overlay deps (gtk4-layer-shell + python3-gobject). Best-effort only.
info "Optional pill-overlay dependencies (skipped gracefully if unavailable)"
case "${PKG_MANAGER}" in
  dnf)    optional_pkgs=(gtk4-layer-shell python3-gobject) ;;
  apt)    optional_pkgs=(gir1.2-gtk-4.0 python3-gi) ;;
  pacman) optional_pkgs=(gtk4-layer-shell python-gobject) ;;
esac
if pkg_install "${optional_pkgs[@]}" 2>/dev/null; then
  ok "pill overlay dependencies installed"
else
  warn "pill overlay dependencies not available — will fall back to notify-send overlay"
fi

# ---------------------------------------------------------------------------
# 2. GPU probe
# ---------------------------------------------------------------------------
info "Step 2/9: GPU probe"
GPU_BACKEND="cpu"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  GPU_BACKEND="cuda"
elif command -v vulkaninfo >/dev/null 2>&1 && vulkaninfo --summary >/dev/null 2>&1; then
  GPU_BACKEND="vulkan"
fi
ok "GPU backend selected: ${GPU_BACKEND}"

# ---------------------------------------------------------------------------
# 3. Build whisper.cpp
# ---------------------------------------------------------------------------
info "Step 3/9: whisper.cpp"
WHISPER_CLI="${WHISPER_DIR}/build/bin/whisper-cli"
if [ -x "${WHISPER_CLI}" ]; then
  skip "whisper.cpp already built"
else
  mkdir -p "${FREEFLOW_HOME}"
  if [ -d "${WHISPER_DIR}/.git" ]; then
    skip "whisper.cpp clone"
  else
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp "${WHISPER_DIR}"
    ok "cloned whisper.cpp"
  fi

  cmake_flags=()
  case "${GPU_BACKEND}" in
    cuda)   cmake_flags+=("-DGGML_CUDA=1") ;;
    vulkan) cmake_flags+=("-DGGML_VULKAN=1") ;;
  esac

  cmake -S "${WHISPER_DIR}" -B "${WHISPER_DIR}/build" "${cmake_flags[@]}"
  cmake --build "${WHISPER_DIR}/build" -j"$(nproc)" --config Release
  ok "built whisper.cpp (${GPU_BACKEND})"
fi

# ---------------------------------------------------------------------------
# 4. Model auto-pick + download
# ---------------------------------------------------------------------------
info "Step 4/9: whisper model"
mkdir -p "${MODELS_DIR}"
if [ "${GPU_BACKEND}" = "cpu" ]; then
  MODEL_FILE="ggml-small.bin"
else
  MODEL_FILE="ggml-large-v3-turbo.bin"
fi
MODEL_PATH="${MODELS_DIR}/${MODEL_FILE}"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODEL_FILE}"

if [ -f "${MODEL_PATH}" ]; then
  skip "model ${MODEL_FILE}"
else
  echo "Downloading ${MODEL_FILE} (this can take a while)..."
  curl -L --continue-at - -o "${MODEL_PATH}" "${MODEL_URL}"
  ok "downloaded ${MODEL_FILE}"
fi
echo "  (override the model later in ~/.config/freeflow/config.toml)"

# ---------------------------------------------------------------------------
# 5. Install freeflow
# ---------------------------------------------------------------------------
info "Step 5/9: install freeflow"
if command -v uv >/dev/null 2>&1; then
  uv tool install --force "${REPO_DIR}"
  ok "installed via uv tool"
else
  python3 -m pip install --user "${REPO_DIR}"
  ok "installed via pip --user"
fi

# ---------------------------------------------------------------------------
# 6. ydotool daemon + permissions
# ---------------------------------------------------------------------------
info "Step 6/9: ydotool daemon"
if [ -S /run/ydotoold.socket ]; then
  skip "ydotoold already running"
else
  YDOTOOLD_BIN="$(command -v ydotoold || true)"
  if [ -z "${YDOTOOLD_BIN}" ]; then
    warn "ydotoold binary not found — ydotool package should provide it, check install"
  else
    sudo tee /etc/systemd/system/ydotoold.service >/dev/null <<EOF
[Unit]
Description=ydotool daemon (uinput-based input injection for Freeflow)
After=local-fs.target

[Service]
ExecStart=${YDOTOOLD_BIN} --socket-path=/run/ydotoold.socket --socket-perm=0666
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now ydotoold.service
    ok "installed + started ydotoold system service"
  fi
fi

if ! groups "${USER}" | grep -qw input; then
  sudo usermod -aG input "${USER}"
  REBOOT_NEEDED=1
  ok "added ${USER} to 'input' group (needs re-login)"
else
  skip "user already in 'input' group"
fi
if [ ! -e /dev/uinput ]; then
  warn "/dev/uinput missing — ydotool needs the uinput kernel module (modprobe uinput)"
fi

# ---------------------------------------------------------------------------
# 7. Ollama (optional, for AI cleanup)
# ---------------------------------------------------------------------------
info "Step 7/9: Ollama (optional AI cleanup)"
if command -v ollama >/dev/null 2>&1; then
  ollama pull qwen3:1.7b
  ok "ollama model qwen3:1.7b ready"
else
  warn "ollama not found — AI cleanup will be skipped until installed"
  echo "  Install it yourself from https://ollama.com/download (one command on their site)."
  echo "  Freeflow works without it — dictation still lands, just without AI cleanup."
fi

# ---------------------------------------------------------------------------
# 8. Config + systemd user unit
# ---------------------------------------------------------------------------
info "Step 8/9: config + systemd user unit"
FREEFLOW_BIN="${HOME}/.local/bin/freeflow"
if [ -x "${FREEFLOW_BIN}" ]; then
  "${FREEFLOW_BIN}" config --init
  ok "wrote default config (or confirmed it exists)"
else
  warn "freeflow binary not found at ${FREEFLOW_BIN} yet — skipping config --init, run it manually after re-login"
fi

mkdir -p "${HOME}/.config/systemd/user"
cp "${REPO_DIR}/systemd/freeflow.service" "${HOME}/.config/systemd/user/freeflow.service"
systemctl --user daemon-reload
systemctl --user enable freeflow.service
ok "installed + enabled freeflow.service (user unit)"

# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------
info "Step 9/9: done"
echo
echo "Freeflow is installed."
echo "  GPU backend:   ${GPU_BACKEND}"
echo "  Whisper model: ${MODEL_PATH}"
echo "  Hotkey:        hold Left Ctrl + Left Alt + Left Shift, speak, release"
echo "  Verify:        freeflow status"
echo "  Start now:     systemctl --user start freeflow"
echo
if [ "${REBOOT_NEEDED}" -eq 1 ]; then
  echo -e "\033[0;31m⚠️  You were added to the 'input' group — log out and back in before using Freeflow.\033[0m"
fi
