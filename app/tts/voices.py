"""Voice catalog — REAL Piper Vietnamese voices only.

Verified against rhasspy/piper-voices ONNX configs (2026-09):

    vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json
        -> "num_speakers": 1, sample_rate 22050, female speaker (Vais-1000 dataset)
    vi/vi_VN/25hours_single/low/vi_VN-25hours_single-low.onnx.json
        -> "num_speakers": 1, sample_rate 16000, male speaker (25hours dataset)
    vi/vi_VN/vivos/x_low/vi_VN-vivos-x_low.onnx.json
        -> "num_speakers": 65 with a real speaker_id_map (VIVOSSPK*, VIVOSDEV*),
           sample_rate 16000. The VIVOS dataset does NOT publish per-speaker
           gender metadata, so those voices are labelled neutrally.

Limitations (honest, per spec §8 — we do NOT fake unavailable voices):
- No "Nam 2" / "Nữ 2" / child / deep-elderly checkpoint exists for vi_VN.
- Speed / pitch / volume controls are NOT exposed: Piper SynthesisConfig
  supports length_scale, but reliable pitch shifting would require extra DSP;
  we keep the UX honest and stable instead.
"""
from __future__ import annotations

from dataclasses import dataclass

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN"


@dataclass(frozen=True)
class VoiceOption:
    key: str
    label: str
    model: str
    sample_rate: int
    gender: str | None  # only set when the dataset actually documents it
    speaker_id: int | None = None
    description: str = ""

    @property
    def onnx_url(self) -> str:
        # vi_VN-<dataset>-<quality>.onnx  lives at vi/vi_VN/<dataset>/<quality>/
        stem = self.model[len("vi_VN-"):]
        dataset, quality = stem.rsplit("-", 1)
        return f"{HF_BASE}/{dataset}/{quality}/{self.model}.onnx"

    @property
    def config_url(self) -> str:
        return f"{self.onnx_url}.json"


VOICES: dict[str, VoiceOption] = {
    v.key: v
    for v in [
        VoiceOption(
            key="NU_1",
            label="👩 Nữ 1",
            model="vi_VN-vais1000-medium",
            sample_rate=22050,
            gender="female",
            description="Giọng nữ, chất lượng medium (22.05 kHz) — dataset Vais-1000",
        ),
        VoiceOption(
            key="NAM_1",
            label="👨 Nam 1",
            model="vi_VN-25hours_single-low",
            sample_rate=16000,
            gender="male",
            description="Giọng nam, chất lượng low (16 kHz) — dataset 25hours",
        ),
        VoiceOption(
            key="VIVOS_A",
            label="🗣️ VIVOS #13",
            model="vi_VN-vivos-x_low",
            sample_rate=16000,
            gender=None,
            speaker_id=0,  # VIVOSSPK13
            description="Speaker VIVOSSPK13 — giới tính chưa được ghi nhận trong dataset",
        ),
        VoiceOption(
            key="VIVOS_B",
            label="🗣️ VIVOS #01",
            model="vi_VN-vivos-x_low",
            sample_rate=16000,
            gender=None,
            speaker_id=22,  # VIVOSSPK01
            description="Speaker VIVOSSPK01 — giới tính chưa được ghi nhận trong dataset",
        ),
        VoiceOption(
            key="VIVOS_C",
            label="🗣️ VIVOS #25",
            model="vi_VN-vivos-x_low",
            sample_rate=16000,
            gender=None,
            speaker_id=40,  # VIVOSSPK25
            description="Speaker VIVOSSPK25 — giới tính chưa được ghi nhận trong dataset",
        ),
        VoiceOption(
            key="VIVOS_D",
            label="🗣️ VIVOS DEV#5",
            model="vi_VN-vivos-x_low",
            sample_rate=16000,
            gender=None,
            speaker_id=50,  # VIVOSDEV05
            description="Speaker VIVOSDEV05 — giới tính chưa được ghi nhận trong dataset",
        ),
    ]
}

ALL_MODELS: tuple[str, ...] = tuple(sorted({v.model for v in VOICES.values()}))


def get_voice(key: str) -> VoiceOption | None:
    return VOICES.get(key)
