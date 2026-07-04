#!/usr/bin/env bash
# Freeflow uninstaller — the mirror of install.sh. Removes exactly what install.sh created,
# nothing else. Your voice models and config are USER DATA: you're asked separately before
# those are touched. --dry-run prints what WOULD be removed and deletes nothing.
#
# It only ever touches paths under ~/.local/share/freeflow and ~/.config/freeflow (plus the
# freeflow systemd units). Unrelated older dictation daemons are left completely alone.
set -euo pipefail

FREEFLOW_HOME="${HOME}/.local/share/freeflow"      # data dir (whisper build, models, history)
FREEFLOW_CONFIG="${HOME}/.config/freeflow"         # config.toml, dictionary.txt, .onboarded
WHISPER_DIR="${FREEFLOW_HOME}/whisper.cpp"         # built from source by install.sh
MODELS_DIR="${FREEFLOW_HOME}/models"               # downloaded ggml models
USER_UNIT="${HOME}/.config/systemd/user/freeflow.service"
YDOTOOLD_UNIT="/etc/systemd/system/ydotoold.service"

DRY_RUN=0
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) echo "Usage: ./uninstall.sh [--dry-run]"; exit 0 ;;
    *) echo "Unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

HAS_SYSTEMD=0
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  HAS_SYSTEMD=1
fi

info() { echo "==> $*"; }
ok()   { echo "  ✅ $*"; }
note() { echo "  •  $*"; }

# rm_path PATH — remove a path, honoring --dry-run, always printing it first.
rm_path() {
  local p="$1"
  if [ ! -e "${p}" ]; then
    note "not present: ${p}"
    return
  fi
  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  [dry-run] would remove: ${p}"
  else
    rm -rf "${p}"
    ok "removed: ${p}"
  fi
}

# confirm PROMPT — y/N, defaults to No.
confirm() {
  local reply
  read -r -p "  $1 [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]]
}

info "Freeflow uninstaller"
[ "${DRY_RUN}" -eq 1 ] && echo "  (dry-run — nothing will be deleted)"
echo

# ---------------------------------------------------------------------------
# 1. systemd user unit (stop + disable + remove) — install.sh step 8
# ---------------------------------------------------------------------------
info "1. systemd user unit"
echo "  unit: ${USER_UNIT}"
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "  [dry-run] would stop + disable freeflow.service and remove ${USER_UNIT}"
else
  if [ "${HAS_SYSTEMD}" -eq 1 ]; then
    systemctl --user stop freeflow.service 2>/dev/null || true
    systemctl --user disable freeflow.service 2>/dev/null || true
  fi
  rm_path "${USER_UNIT}"
  [ "${HAS_SYSTEMD}" -eq 1 ] && systemctl --user daemon-reload 2>/dev/null || true
fi
echo

# ---------------------------------------------------------------------------
# 2. the freeflow program (venv/binary install.sh installed) — install.sh step 5
# ---------------------------------------------------------------------------
info "2. freeflow program"
if command -v uv >/dev/null 2>&1; then
  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  [dry-run] would run: uv tool uninstall freeflow"
  else
    if uv tool uninstall freeflow 2>/dev/null; then ok "uninstalled via uv tool"; else note "not installed via uv tool"; fi
  fi
else
  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  [dry-run] would run: python3 -m pip uninstall -y freeflow"
  else
    if python3 -m pip uninstall -y freeflow 2>/dev/null; then ok "uninstalled via pip"; else note "not installed via pip"; fi
  fi
fi
echo

# ---------------------------------------------------------------------------
# 3. whisper.cpp build (not user data — always removed) — install.sh step 3
# ---------------------------------------------------------------------------
info "3. whisper.cpp build"
rm_path "${WHISPER_DIR}"
echo

# ---------------------------------------------------------------------------
# 4. ydotoold system service (optional, needs sudo) — install.sh step 6
#    System-wide input-injection daemon. Only remove it if nothing else uses it.
# ---------------------------------------------------------------------------
info "4. ydotool system service (optional, system-wide)"
echo "  unit: ${YDOTOOLD_UNIT}"
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "  [dry-run] would ask before removing ${YDOTOOLD_UNIT} (needs sudo, system-wide)"
elif [ -f "${YDOTOOLD_UNIT}" ]; then
  echo "  Note: this is a system-wide daemon; skip if other tools rely on ydotool."
  if confirm "Stop + remove ${YDOTOOLD_UNIT} (sudo)?"; then
    sudo systemctl disable --now ydotoold.service 2>/dev/null || true
    sudo rm -f "${YDOTOOLD_UNIT}"
    sudo systemctl daemon-reload 2>/dev/null || true
    ok "removed: ${YDOTOOLD_UNIT}"
  else
    note "kept ydotoold system service"
  fi
else
  note "not present: ${YDOTOOLD_UNIT}"
fi
echo

# ---------------------------------------------------------------------------
# 5. downloaded whisper models (USER DATA — ask) — install.sh step 4
# ---------------------------------------------------------------------------
info "5. downloaded whisper models"
echo "  models dir: ${MODELS_DIR}"
if [ -d "${MODELS_DIR}" ]; then
  for f in "${MODELS_DIR}"/*; do
    [ -e "${f}" ] && echo "    - ${f}"
  done
fi
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "  [dry-run] would ask before removing ${MODELS_DIR}"
elif [ -d "${MODELS_DIR}" ]; then
  if confirm "Delete downloaded models in ${MODELS_DIR}? (re-downloadable)"; then
    rm_path "${MODELS_DIR}"
  else
    note "kept models"
  fi
else
  note "not present: ${MODELS_DIR}"
fi
echo

# ---------------------------------------------------------------------------
# 6. config + dictation history (USER DATA — ask separately) — install.sh step 8
# ---------------------------------------------------------------------------
info "6. config + history"
echo "  config: ${FREEFLOW_CONFIG}"
echo "  data:   ${FREEFLOW_HOME}"
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "  [dry-run] would ask before removing ${FREEFLOW_CONFIG} and ${FREEFLOW_HOME}"
else
  if [ -e "${FREEFLOW_CONFIG}" ]; then
    if confirm "Delete config + dictionary + history (${FREEFLOW_CONFIG})?"; then
      rm_path "${FREEFLOW_CONFIG}"
    else
      note "kept config"
    fi
  else
    note "not present: ${FREEFLOW_CONFIG}"
  fi
  # Data dir may still hold leftovers (e.g. history) after the build/models steps.
  if [ -d "${FREEFLOW_HOME}" ]; then
    if confirm "Delete remaining data dir (${FREEFLOW_HOME})?"; then
      rm_path "${FREEFLOW_HOME}"
    else
      note "kept data dir"
    fi
  fi
fi
echo

info "Done."
if [ "${DRY_RUN}" -eq 1 ]; then
  echo "  Nothing was deleted (dry-run). Re-run without --dry-run to uninstall."
else
  echo "  Freeflow removed. If you were added to the 'input' group and want that undone too:"
  echo "    sudo gpasswd -d \"\${USER}\" input   # then log out and back in"
fi
