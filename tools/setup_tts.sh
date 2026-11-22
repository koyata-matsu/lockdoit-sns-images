#!/bin/bash
# 音声づくりの道具をクラウドの作業場所 /home/claude/tts に入れる（毎回の定期作業の最初に1回）
set -e
T=/home/claude/tts; mkdir -p $T; cd $T
WHL=voicevox_core-0.17.1-cp310-abi3-manylinux_2_34_x86_64.whl
get() { [ -s "$2" ] || curl -sfL -o "$2" "$1"; }
get https://github.com/VOICEVOX/voicevox_core/releases/download/0.17.1/$WHL $WHL
get https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.17.3/voicevox_onnxruntime-linux-x64-1.17.3.tgz ort.tgz
get https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz dic.tgz
get https://github.com/VOICEVOX/voicevox_vvm/releases/download/0.16.1/15.vvm 15.vvm
get https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx kokoro-v1.0.onnx
get https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin voices-v1.0.bin
[ -d voicevox_onnxruntime-linux-x64-1.17.3 ] || tar xzf ort.tgz
[ -d open_jtalk_dic_utf_8-1.11 ] || tar xzf dic.tgz
python3 -c "import voicevox_core, kokoro_onnx, soundfile, cairo" 2>/dev/null || \
  pip install --break-system-packages -q ./$WHL kokoro-onnx soundfile pycairo
command -v espeak-ng >/dev/null || (apt-get install -y -q espeak-ng >/dev/null 2>&1 || true)
echo "tts ready"
