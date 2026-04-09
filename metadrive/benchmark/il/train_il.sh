#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STREETWORLD_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

MODEL="${1:-uniad}"
if [[ $# -gt 0 ]]; then
  shift
fi

NPROC_PER_NODE="${NPROC_PER_NODE:-1}"
SCENE_CONFIG_DIR="${SCENE_CONFIG_DIR:-${STREETWORLD_ROOT}/scene_configs}"

case "${MODEL}" in
  uniad)
    AD_ROOT_DEFAULT="${STREETWORLD_ROOT}/UniAD_SIM"
    CONFIG_DEFAULT="${AD_ROOT_DEFAULT}/projects/configs/stage2_e2e/base_e2e.py"
    CHECKPOINT_DEFAULT="${AD_ROOT_DEFAULT}/ckpts/uniad_base_e2e.pth"
    ;;
  vad)
    AD_ROOT_DEFAULT="${STREETWORLD_ROOT}/VAD"
    CONFIG_DEFAULT="${AD_ROOT_DEFAULT}/projects/configs/VAD/VAD_base_e2e.py"
    CHECKPOINT_DEFAULT="${AD_ROOT_DEFAULT}/ckpts/VAD_base.pth"
    ;;
  *)
    echo "Unsupported model: ${MODEL}. Use 'uniad' or 'vad'." >&2
    exit 1
    ;;
esac

AD_ROOT="${AD_ROOT:-${AD_ROOT_DEFAULT}}"
CONFIG="${CONFIG:-${CONFIG_DEFAULT}}"
CHECKPOINT="${CHECKPOINT:-${CHECKPOINT_DEFAULT}}"
OUTPUT_DIR="${OUTPUT_DIR:-${SCRIPT_DIR}/outputs/${MODEL}_il}"

COMMON_ARGS=(
  --model "${MODEL}"
  --scene-config-dir "${SCENE_CONFIG_DIR}"
  --ad-root "${AD_ROOT}"
  --config "${CONFIG}"
  --checkpoint "${CHECKPOINT}"
  --output-dir "${OUTPUT_DIR}"
  --epochs 20
  --batch-size 16
  --debug-save-vis
  --debug-vis-dir /home/guojiarui/river/CarCrash/submodules/StreetWorld/metadrive/benchmark/il/vis
  --debug-bev-render output
  --debug-vis-steps 1
)

cd "${STREETWORLD_ROOT}"

if [[ "${NPROC_PER_NODE}" -gt 1 ]]; then
  exec torchrun --nproc_per_node="${NPROC_PER_NODE}" -m metadrive.benchmark.il.train "${COMMON_ARGS[@]}" "$@"
else
  exec python -m metadrive.benchmark.il.train "${COMMON_ARGS[@]}" "$@"
fi
