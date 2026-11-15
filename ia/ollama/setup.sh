#!/usr/bin/env bash
# Builds the three Ollama models behind IA_ENGINE=ollama from the repositories listed in ia/README.md.
#
#   kha-health      <- MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged (Hugging Face, ~6.4 GB download, quantized to q4_K_M)
#   kha-astronomy   <- llama3.2:3b + the LoRA adapter ojayy/llama32-3b-mmlu-astronomy-lora (Hugging Face, ~18 MB)
#   granite3.3:2b   <- IBM Granite 3.3 2B from the Ollama registry (the same model as ibm-granite/granite-3.3-2b-instruct)
#
# Needs: ollama running, uv, and about 12 GB of free disk. All three Hugging Face repositories are public; no token is used.
set -euo pipefail
cd "$(dirname "$0")"
MODELS="$PWD/models" # ignored by git
mkdir -p "$MODELS"

download() { # repo, destination
  REPO="$1" DEST="$2" uv run --no-project --with huggingface_hub python -c \
    "import os; from huggingface_hub import snapshot_download as s; s(os.environ['REPO'], local_dir=os.environ['DEST'])"
}

ollama pull llama3.2:3b
ollama pull granite3.3:2b

download ojayy/llama32-3b-mmlu-astronomy-lora "$MODELS/astronomy-lora"
# Ollama only recognises LoRA weights named model.safetensors or adapters.safetensors; Hugging Face
# ships adapter_model.safetensors, so the adapter is copied to a clean folder under the name Ollama expects.
rm -rf "$MODELS/astronomy-adapter" && mkdir -p "$MODELS/astronomy-adapter"
cp "$MODELS/astronomy-lora/adapter_config.json" "$MODELS/astronomy-adapter/"
cp "$MODELS/astronomy-lora/adapter_model.safetensors" "$MODELS/astronomy-adapter/model.safetensors"
cat > "$MODELS/Modelfile.astronomy" <<MODELFILE
FROM llama3.2:3b
ADAPTER $MODELS/astronomy-adapter
MODELFILE
ollama create kha-astronomy -f "$MODELS/Modelfile.astronomy"

download MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged "$MODELS/medical"
cat > "$MODELS/Modelfile.health" <<MODELFILE
FROM $MODELS/medical
TEMPLATE """{{- range .Messages }}<|start_header_id|>{{ .Role }}<|end_header_id|>

{{ .Content }}<|eot_id|>
{{- end }}<|start_header_id|>assistant<|end_header_id|>

"""
PARAMETER stop <|eot_id|>
PARAMETER stop <|end_of_text|>
MODELFILE
ollama create kha-health -f "$MODELS/Modelfile.health" --quantize q4_K_M

echo "Ready: kha-health, kha-astronomy, granite3.3:2b"
ollama list | grep -E "kha-|granite"
