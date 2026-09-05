# Provider list prices checked on 2026-09-03. Free-tier spend can be zero; these
# rates estimate an equivalent paid production turn. USD/INR uses the 2026-08-25
# FBIL reference rate of 95.4254, rounded to 95.43.
USD_TO_INR = 95.43
MODEL_RATES_USD_PER_MILLION = {
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "qwen/qwen3.6-27b": (0.60, 3.00),
    "qwen/qwen3.8-27b": (0.80, 4.00),
}
STT_USD_PER_HOUR = {"whisper-large-v3-turbo": 0.04}
TTS_USD_PER_MILLION_CHARACTERS = {"canopylabs/orpheus-v1-english": 22.0}


def llm_list_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    rates = MODEL_RATES_USD_PER_MILLION.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def voice_list_cost_usd(
    audio_seconds: float | None, characters: int, *, stt_model: str, tts_model: str
) -> float | None:
    stt_rate = STT_USD_PER_HOUR.get(stt_model)
    tts_rate = TTS_USD_PER_MILLION_CHARACTERS.get(tts_model)
    if audio_seconds is None or stt_rate is None or tts_rate is None:
        return None
    return audio_seconds / 3600 * stt_rate + characters / 1_000_000 * tts_rate
