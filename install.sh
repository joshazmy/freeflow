#!/usr/bin/env bash
# Freeflow installer — one command, it just works.
# Read this before piping it to bash. Every step is idempotent: safe to re-run.
set -euo pipefail

FREEFLOW_HOME="${HOME}/.local/share/freeflow"
FREEFLOW_CONFIG="${HOME}/.config/freeflow"
WHISPER_DIR="${FREEFLOW_HOME}/whisper.cpp"
MODELS_DIR="${FREEFLOW_HOME}/models"
# Must run as a checked-out file, not piped (curl | bash): the installer installs freeflow
# FROM this repo checkout (pyproject.toml, systemd/freeflow.service) — a bare piped script has
# no such tree to install from. ${BASH_SOURCE[0]:-} is unset/empty when read from a stream.
if [ -z "${BASH_SOURCE[0]:-}" ] || [ ! -f "${BASH_SOURCE[0]}" ]; then
  echo "install.sh must be run from a real checkout, not piped (e.g. curl | bash)." >&2
  echo "Run instead:  git clone <this-repo> && cd freeflow && ./install.sh" >&2
  exit 1
fi
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBOOT_NEEDED=0
USER="${USER:-$(id -un)}"   # podman exec / minimal shells do not set USER; set -u would abort

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
# python3-devel: needed to build the evdev native extension (pip/uv has no prebuilt wheel for
# it). Fedora/Debian split headers from the interpreter; Arch's "python" package ships them
# together, so pacman just reinstalls "python" here (harmless, deduped by sort -u below).
declare -A DEPS_DNF=(
  [git]=git [cmake]=cmake [gcc-c++]=gcc-c++ [pw-record]=pipewire-utils
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [python3-devel]=python3-devel [curl]=curl
)
declare -A DEPS_APT=(
  [git]=git [cmake]=cmake [gcc-c++]=build-essential [pw-record]=pipewire-utils
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [python3-devel]=python3-dev [curl]=curl
)
declare -A DEPS_PACMAN=(
  [git]=git [cmake]=cmake [gcc-c++]=base-devel [pw-record]=pipewire
  [wl-copy]=wl-clipboard [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [python3-devel]=python [curl]=curl
)

declare -A DEPS_CHECK=(
  [git]=git [cmake]=cmake [gcc-c++]=g++ [pw-record]=pw-record
  [wl-copy]=wl-copy [ydotool]=ydotool [playerctl]=playerctl
  [python3]=python3 [python3-devel]="" [curl]=curl
)

# Python.h presence check (not a command, so it doesn't fit pkg_have's command -v model).
have_python_headers() {
  py_inc="$(python3 -c 'import sysconfig; print(sysconfig.get_path("include"))' 2>/dev/null || true)"
  [ -n "${py_inc}" ] && [ -f "${py_inc}/Python.h" ]
}

case "${PKG_MANAGER}" in
  dnf)    declare -n DEPS_MAP=DEPS_DNF ;;
  apt)    declare -n DEPS_MAP=DEPS_APT ;;
  pacman) declare -n DEPS_MAP=DEPS_PACMAN ;;
esac

missing_pkgs=()
for name in "${!DEPS_CHECK[@]}"; do
  check_bin="${DEPS_CHECK[$name]}"
  if [ "${name}" = "python3-devel" ]; then
    if have_python_headers; then
      skip "${name}"
    else
      missing_pkgs+=("${DEPS_MAP[$name]}")
    fi
  elif pkg_have "${check_bin}"; then
    skip "${name}"
  else
    missing_pkgs+=("${DEPS_MAP[$name]}")
  fi
done
# dedup, guarded: `printf '%s\n'` with zero args still emits one blank line, which would
# turn an empty missing_pkgs into a bogus single-element [""] array otherwise.
if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  mapfile -t missing_pkgs < <(printf '%s\n' "${missing_pkgs[@]}" | sort -u)
fi

# Optional: pill overlay deps (gtk4-layer-shell + python3-gobject). Best-effort only --
# folded into the SAME confirmed prompt as the required packages below, no second
# unprompted sudo install.
case "${PKG_MANAGER}" in
  dnf)    optional_pkgs=(gtk4-layer-shell python3-gobject) ;;
  apt)    optional_pkgs=(gir1.2-gtk-4.0 python3-gi) ;;
  pacman) optional_pkgs=(gtk4-layer-shell python-gobject) ;;
esac

if [ "${#missing_pkgs[@]}" -gt 0 ] || [ "${#optional_pkgs[@]}" -gt 0 ]; then
  echo "About to install (${PKG_MANAGER}):"
  [ "${#missing_pkgs[@]}" -gt 0 ] && echo "  required: ${missing_pkgs[*]}"
  [ "${#optional_pkgs[@]}" -gt 0 ] && echo "  optional (pill overlay): ${optional_pkgs[*]}"
  read -r -p "Proceed with sudo install? [y/N] " reply
  if [[ "${reply}" =~ ^[Yy]$ ]]; then
    if [ "${#missing_pkgs[@]}" -gt 0 ]; then
      pkg_install "${missing_pkgs[@]}"
      ok "installed: ${missing_pkgs[*]}"
    fi
    if [ "${#optional_pkgs[@]}" -gt 0 ]; then
      if pkg_install "${optional_pkgs[@]}" 2>/dev/null; then
        ok "pill overlay dependencies installed"
      else
        warn "pill overlay dependencies not available — will fall back to notify-send overlay"
      fi
    fi
  elif [ "${#missing_pkgs[@]}" -gt 0 ]; then
    echo "Cannot continue without required dependencies." >&2
    exit 1
  else
    warn "skipped optional pill overlay dependencies — will fall back to notify-send overlay"
  fi
fi

# ---------------------------------------------------------------------------
# 1b. Require Python 3.11+ (checked AFTER step 1 installs python3 on a fresh box)
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1 || \
   [ "$(python3 -c 'import sys; print(sys.version_info >= (3, 11))' 2>/dev/null)" != "True" ]; then
  echo "Freeflow requires Python 3.11 or newer. Install/upgrade python3 and re-run." >&2
  exit 1
fi
ok "python3 >= 3.11"

# systemd as PID 1 (not just the systemctl binary) — containers/chroots/WSL often have the
# binary but no running instance, and `systemctl` there just errors out.
HAS_SYSTEMD=0
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  HAS_SYSTEMD=1
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
    git clone --depth 1 --branch v1.7.6 https://github.com/ggerganov/whisper.cpp "${WHISPER_DIR}"
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
  if ! python3 -m pip --version >/dev/null 2>&1; then
    case "${PKG_MANAGER}" in
      dnf)    pip_pkg="python3-pip" ;;
      apt)    pip_pkg="python3-pip" ;;
      pacman) pip_pkg="python-pip" ;;
    esac
    echo "pip not found; about to install (${PKG_MANAGER}): ${pip_pkg}"
    read -r -p "Proceed with sudo install? [y/N] " reply
    if [[ "${reply}" =~ ^[Yy]$ ]]; then
      pkg_install "${pip_pkg}"
      ok "installed: ${pip_pkg}"
    else
      echo "Cannot continue without pip (or install 'uv' instead)." >&2
      exit 1
    fi
  fi
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
    INPUT_GID="$(getent group input | cut -d: -f3)"
    if [ -z "${INPUT_GID}" ]; then
      sudo groupadd -r input
      INPUT_GID="$(getent group input | cut -d: -f3)"
    fi
    # socket-perm=0666 would let ANY local user inject keystrokes into your session.
    # Restrict to the 'input' group (the installer adds you to it below) instead.
    sudo tee /etc/systemd/system/ydotoold.service >/dev/null <<EOF
[Unit]
Description=ydotool daemon (uinput-based input injection for Freeflow)
After=local-fs.target

[Service]
ExecStart=${YDOTOOLD_BIN} --socket-path=/run/ydotoold.socket --socket-own=0:${INPUT_GID} --socket-perm=0660
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    if [ "${HAS_SYSTEMD}" -eq 1 ]; then
      sudo systemctl daemon-reload
      sudo systemctl enable --now ydotoold.service
      ok "installed + started ydotoold system service"
    else
      warn "skipped: no running systemd — unit file written to /etc/systemd/system/ydotoold.service, enable it manually with 'sudo systemctl enable --now ydotoold.service' once systemd is available"
    fi
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
  # config --init leaves whisper_bin/model_path blank; point them at what we just built/
  # downloaded so freeflow works out of the box instead of needing manual editing.
  CONFIG_FILE="${FREEFLOW_CONFIG}/config.toml"
  if [ -f "${CONFIG_FILE}" ]; then
    sed -i "s|^whisper_bin = \"\"|whisper_bin = \"${WHISPER_CLI}\"|" "${CONFIG_FILE}"
    sed -i "s|^model_path = \"\"|model_path = \"${MODEL_PATH}\"|" "${CONFIG_FILE}"
    ok "wired whisper_bin/model_path into config.toml"
  fi
else
  warn "freeflow binary not found at ${FREEFLOW_BIN} yet — skipping config --init, run it manually after re-login"
fi

mkdir -p "${HOME}/.config/systemd/user"
cp "${REPO_DIR}/systemd/freeflow.service" "${HOME}/.config/systemd/user/freeflow.service"
# headless/no-systemd (container, chroot, no user D-Bus session): copy the unit file for later,
# don't hard-fail the rest of the install trying to reach a session bus that isn't there.
if [ "${HAS_SYSTEMD}" -eq 1 ] && systemctl --user daemon-reload 2>/dev/null; then
  systemctl --user enable freeflow.service
  ok "installed + enabled freeflow.service (user unit)"
else
  warn "skipped: no user systemd session available — unit copied to ~/.config/systemd/user/freeflow.service, run 'systemctl --user enable --now freeflow.service' after logging into a real desktop session"
fi

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
