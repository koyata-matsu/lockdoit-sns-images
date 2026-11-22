"""台本 JSON から行ごとの音声（l01.wav ...）を作る
  python3 nv_style/voice.py <台本.json> <ja|en> <出力フォルダ>
日本語: VOICEVOX 青山龍星（style 13）速さ1.2 ／ 英語: Kokoro am_onyx 速さ1.05
道具は tools/setup_tts.sh で /home/claude/tts に入れておく。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from auto import build_lines  # noqa: E402

TTS = Path("/home/claude/tts")


def main(script_path, lang, out_dir):
    script = json.loads(Path(script_path).read_text())
    lines = build_lines(script, lang)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    if lang == "ja":
        from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
        ort = Onnxruntime.load_once(filename=str(TTS / "voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3"))
        syn = Synthesizer(ort, OpenJtalk(str(TTS / "open_jtalk_dic_utf_8-1.11")))
        with VoiceModelFile.open(str(TTS / "15.vvm")) as m:
            syn.load_voice_model(m)
        for i, ln in enumerate(lines, 1):
            q = syn.create_audio_query(ln["say"], 13)
            q.speed_scale = float(script.get("speed_ja", 1.2))
            q.pre_phoneme_length = 0.05; q.post_phoneme_length = 0.05
            (out / f"l{i:02d}.wav").write_bytes(syn.synthesis(q, 13))
    else:
        import soundfile as sf
        from kokoro_onnx import Kokoro
        k = Kokoro(str(TTS / "kokoro-v1.0.onnx"), str(TTS / "voices-v1.0.bin"))
        for i, ln in enumerate(lines, 1):
            s, sr = k.create(ln["say"], voice="am_onyx", speed=float(script.get("speed_en", 1.05)), lang="en-us")
            sf.write(str(out / f"l{i:02d}.wav"), s, sr, subtype="PCM_16")
    print(out, len(lines), "lines")


if __name__ == "__main__":
    main(*sys.argv[1:4])
