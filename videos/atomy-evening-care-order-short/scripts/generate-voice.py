from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro


MODEL = Path.home() / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"
VOICES = Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"
LINES = [
    "Pause. Are you using Atomy Evening Care in the right order?",
    "Step one: Deep Cleanser. Step two: Foam Cleanser.",
    "Step three: Peeling Gel. Step four: Peel-Off Mask.",
    "Cleanse, foam, exfoliate, then mask. Save this order for tonight.",
]


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "assets/voice"
    output.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(MODEL), str(VOICES))
    for index, text in enumerate(LINES, 1):
        samples, sample_rate = kokoro.create(
            text,
            voice="af_heart",
            speed=1.03,
            lang="en-us",
            sentence_pause=0.18,
            clause_pause=0.08,
        )
        target = output / f"{index:02d}.wav"
        sf.write(target, samples, sample_rate)
        print(f"{target.name}\t{len(samples) / sample_rate:.3f}s")


if __name__ == "__main__":
    main()
