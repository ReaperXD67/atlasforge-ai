"""Mix the voice-anchored audio plan into one measured HyperFrames master."""
import argparse
import json
from pathlib import Path

from daily_video_factory.cinematic_audio import mix_project_audio

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    result = mix_project_audio(args.project)
    print(json.dumps({"master": str(args.project / "assets/audio/master.wav"),
                      "seconds": result["duration_seconds"],
                      "loudness": result["normalization"]["output_i"],
                      "true_peak": result["normalization"]["output_tp"]}, indent=2))
