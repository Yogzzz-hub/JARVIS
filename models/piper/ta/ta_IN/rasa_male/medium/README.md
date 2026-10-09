---
license: cc-by-4.0
language:
- ta
library_name: piper
pipeline_tag: text-to-speech
tags:
- piper
- tts
- text-to-speech
- tamil
- ta_IN
- rasa
- expressive
datasets:
- ai4bharat/Rasa
---

# Piper Tamil — Rasa Male (medium)

A [Piper](https://github.com/rhasspy/piper) text-to-speech voice for **Tamil (ta_IN)**, trained on the **male speaker** of the [AI4Bharat Rasa](https://huggingface.co/datasets/ai4bharat/Rasa) expressive speech dataset.

- **Language:** Tamil (ta_IN)
- **Sample rate:** 22050 Hz
- **Quality:** medium
- **Phoneme backend:** eSpeak (`voice: ta`)
- **Framework:** Piper (ONNX)

## Files

| File | Purpose |
|---|---|
| `ta_IN-rasa_male-medium.onnx` | Voice model weights |
| `ta_IN-rasa_male-medium.onnx.json` | Voice config (phoneme map, inference params) |
| `sample.wav` | Demo synthesis (see "Sample sentence" below) |

## Usage

Install Piper:

```bash
pip install piper-tts
```

Synthesize:

```bash
echo "வணக்கம், இது தமிழ் குரல் மாதிரி." \
  | piper -m ta_IN-rasa_male-medium.onnx -f out.wav
```

Or from Python:

```python
from piper import PiperVoice
import wave

voice = PiperVoice.load("ta_IN-rasa_male-medium.onnx")
with wave.open("out.wav", "wb") as wav:
    voice.synthesize("வணக்கம், இது தமிழ் குரல் மாதிரி.", wav)
```

## Sample sentence

> வணக்கம், இது பைப்பர் தமிழ் மாதிரிகளின் ஒப்பீட்டு சோதனை. இந்த வாக்கியம் ஒவ்வொரு குரல் மாதிரியிலும் ஒரே மாதிரியாக உருவாக்கப்படுகிறது.

## License

Released under **CC-BY-4.0**, matching the license of the underlying Rasa dataset.

## Attribution

This model is trained on the AI4Bharat Rasa dataset. If you use this voice, please cite:

```bibtex
@inproceedings{ai4bharat2024rasa,
  author    = {Praveen Srinivasa Varadhan and Ashwin Sankar and Giri Raju and Mitesh M. Khapra},
  title     = {{Rasa: Building Expressive Speech Synthesis Systems for Indian Languages in Low-resource Settings}},
  booktitle = {Proc. INTERSPEECH 2024},
  year      = {2024}
}
```

Dataset: [ai4bharat/Rasa](https://huggingface.co/datasets/ai4bharat/Rasa) · Paper: [arXiv 2407.14056](https://arxiv.org/abs/2407.14056)
