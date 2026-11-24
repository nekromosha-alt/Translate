#!/usr/bin/env python3
"""
Generator for Live Screen Translator (Windows 11, PyQt6, Win32 API, EasyOCR).
Run: python generate_project.py
"""

import ast
from pathlib import Path
import sys


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


FILES: dict[str, str] = {}


FILES["src/__init__.py"] = r'''
"""Live Screen Translator package."""
'''


FILES["src/config.py"] = r'''
"""Управление конфигурацией, путями AppData и парсингом горячих клавиш Win32."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Optional, Tuple


APP_NAME = "LiveScreenTranslator"

DEFAULT_SYSTEM_PROMPT = (
    "You are an elite literary translator from English to Russian for games, "
    "visual novels, movies, and mature fiction. Translate the input into vivid, "
    "natural, idiomatic Russian that reads like native speech. Strictly preserve "
    "the original tone, slang, idioms, profanity, dark or adult themes, and "
    "emotional nuance without any censorship, softening, moralizing, or refusals. "
    "Never add notes, explanations, or quotes. Output ONLY the Russian translation."
)

# Win32 RegisterHotKey modifiers
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_SPECIAL_VK: dict[str, int] = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PGUP": 0x21,
    "PAGEDOWN": 0x22,
    "PGDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "PRINTSCREEN": 0x2C,
    "INSERT": 0x2D,
    "INS": 0x2D,
    "DELETE": 0x2E,
    "DEL": 0x2E,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "~": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
    "NUM0": 0x60,
    "NUM1": 0x61,
    "NUM2": 0x62,
    "NUM3": 0x63,
    "NUM4": 0x64,
    "NUM5": 0x65,
    "NUM6": 0x66,
    "NUM7": 0x67,
    "NUM8": 0x68,
    "NUM9": 0x69,
}


@dataclass
class AppConfig:
    start_hotkey: str = "Ctrl+Shift+Q"
    stop_hotkey: str = "Ctrl+Shift+X"
    engine: str = "free"  # "llm" or "free"
    free_provider: str = "google"  # "google", "mymemory", "deepl"
    deepl_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek/deepseek-chat"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    update_interval_ms: int = 700
    diff_threshold_pct: float = 1.5
    font_family: str = "Segoe UI"


def get_app_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / APP_NAME
    else:
        base = Path.home() / f".{APP_NAME}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_path() -> Path:
    return get_app_dir() / "config.json"


def get_models_dir() -> Path:
    models_dir = get_app_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def load_config() -> AppConfig:
    path = get_config_path()
    defaults = AppConfig()
    if not path.exists():
        save_config(defaults)
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return defaults
        valid_fields = asdict(defaults)
        merged = {k: raw.get(k, v) for k, v in valid_fields.items()}
        merged["update_interval_ms"] = max(200, min(10000, int(merged["update_interval_ms"])))
        merged["diff_threshold_pct"] = max(0.1, min(50.0, float(merged["diff_threshold_pct"])))
        if merged["engine"] not in ("llm", "free"):
            merged["engine"] = "free"
        if merged["free_provider"] not in ("google", "mymemory", "deepl"):
            merged["free_provider"] = "google"
        return AppConfig(**merged)
    except Exception:
        return defaults


def save_config(cfg: AppConfig) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def parse_hotkey_win32(hotkey_str: str) -> Optional[Tuple[int, int]]:
    """
    Преобразует строку вида 'Ctrl+Shift+Q' в (fsModifiers, vk) для Win32 RegisterHotKey.
    Возвращает None при некорректной комбинации.
    """
    if not hotkey_str or not hotkey_str.strip():
        return None

    parts = [p.strip() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return None

    modifiers = 0
    vk: Optional[int] = None

    for part in parts:
        upper = part.upper()
        if upper in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif upper == "SHIFT":
            modifiers |= MOD_SHIFT
        elif upper == "ALT":
            modifiers |= MOD_ALT
        elif upper in ("WIN", "META", "SUPER"):
            modifiers |= MOD_WIN
        else:
            if vk is not None:
                return None
            if len(upper) == 1 and ("A" <= upper <= "Z" or "0" <= upper <= "9"):
                vk = ord(upper)
            elif upper.startswith("F") and upper[1:].isdigit():
                f_num = int(upper[1:])
                if 1 <= f_num <= 24:
                    vk = 0x70 + (f_num - 1)
                else:
                    return None
            elif upper in _SPECIAL_VK:
                vk = _SPECIAL_VK[upper]
            else:
                return None

    if vk is None:
        return None

    return (modifiers | MOD_NOREPEAT, vk)
'''


FILES["src/translator.py"] = r'''
"""Движок перевода: LLM API (OpenAI-compatible) и Free Online (deep-translator) с LRU-кэшем."""

from __future__ import annotations

from collections import OrderedDict
import json
import logging
import re
import threading
from typing import List, Optional

import requests
from deep_translator import DeeplTranslator, GoogleTranslator, MyMemoryTranslator

from config import AppConfig


logger = logging.getLogger(__name__)
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LRUCache:
    """Потокобезопасный LRU-кэш для переведённых строк."""

    def __init__(self, maxsize: int = 2048) -> None:
        self._maxsize = max(64, maxsize)
        self._store: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            val = self._store.get(key)
            if val is not None:
                self._store.move_to_end(key)
            return val

    def put(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class TranslationEngine:
    """Унифицированный переводчик с поддержкой батчинга и кэширования."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._cache = LRUCache(maxsize=2048)
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._last_error: str = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config

    def _cache_signature(self, cfg: AppConfig) -> str:
        if cfg.engine == "llm":
            return f"llm|{cfg.llm_base_url}|{cfg.llm_model}|{hash(cfg.system_prompt)}"
        return f"free|{cfg.free_provider}"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _needs_translation(text: str) -> bool:
        cleaned = text.strip()
        if len(cleaned) < 2:
            return False
        return bool(_ASCII_LETTER_RE.search(cleaned))

    def translate_batch(self, texts: List[str]) -> List[str]:
        """Переводит список текстовых блоков с использованием LRU-кэша и батчинга."""
        if not texts:
            return []

        with self._lock:
            cfg = self._config

        sig = self._cache_signature(cfg)
        results: List[Optional[str]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for idx, raw in enumerate(texts):
            norm = self._normalize_text(raw)
            if not self._needs_translation(norm):
                results[idx] = norm
                continue
            cache_key = f"{sig}::{norm}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                results[idx] = cached
            else:
                uncached_indices.append(idx)
                uncached_texts.append(norm)

        if uncached_texts:
            try:
                if cfg.engine == "llm":
                    translated = self._translate_llm_batch(cfg, uncached_texts)
                else:
                    translated = self._translate_free_batch(cfg, uncached_texts)
                self._last_error = ""
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Translation failed: %s", exc)
                translated = list(uncached_texts)

            for idx, src_text, tr_text in zip(uncached_indices, uncached_texts, translated):
                final_tr = (tr_text or src_text).strip()
                results[idx] = final_tr
                if not self._last_error and final_tr:
                    self._cache.put(f"{sig}::{src_text}", final_tr)

        return [r if r is not None else t for r, t in zip(results, texts)]

    def _translate_free_batch(self, cfg: AppConfig, texts: List[str]) -> List[str]:
        provider = cfg.free_provider
        if provider == "deepl" and cfg.deepl_api_key.strip():
            try:
                translator = DeeplTranslator(
                    api_key=cfg.deepl_api_key.strip(),
                    source="en",
                    target="ru",
                    use_free_api=True,
                )
                return self._run_deep_translator(translator, texts)
            except Exception as exc:
                logger.warning("DeepL failed, falling back to Google: %s", exc)

        if provider == "mymemory":
            try:
                translator = MyMemoryTranslator(source="en-US", target="ru-RU")
                return self._run_deep_translator(translator, texts)
            except Exception as exc:
                logger.warning("MyMemory failed, falling back to Google: %s", exc)

        translator = GoogleTranslator(source="en", target="ru")
        return self._run_deep_translator(translator, texts)

    @staticmethod
    def _run_deep_translator(translator: object, texts: List[str]) -> List[str]:
        if len(texts) == 1:
            res = translator.translate(texts[0])  # type: ignore[attr-defined]
            return [res.strip() if isinstance(res, str) and res.strip() else texts[0]]

        try:
            batch_res = translator.translate_batch(texts)  # type: ignore[attr-defined]
            if isinstance(batch_res, list) and len(batch_res) == len(texts):
                return [
                    r.strip() if isinstance(r, str) and r.strip() else orig
                    for r, orig in zip(batch_res, texts)
                ]
        except Exception:
            pass

        output: List[str] = []
        for item in texts:
            try:
                res = translator.translate(item)  # type: ignore[attr-defined]
                output.append(res.strip() if isinstance(res, str) and res.strip() else item)
            except Exception:
                output.append(item)
        return output

    def _translate_llm_batch(self, cfg: AppConfig, texts: List[str]) -> List[str]:
        api_key = cfg.llm_api_key.strip()
        base_url = cfg.llm_base_url.strip().rstrip("/")
        model = cfg.llm_model.strip()

        if not base_url:
            raise ValueError("Base URL is empty.")
        if not model:
            raise ValueError("Model Name is empty.")

        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/live-screen-translator",
            "X-Title": "LiveScreenTranslator",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if len(texts) == 1:
            translated_one = self._call_llm_single(endpoint, headers, cfg, texts[0])
            return [translated_one]

        payload_items = [{"id": i, "text": t} for i, t in enumerate(texts)]
        batch_instruction = (
            f"{cfg.system_prompt}\n\n"
            "You will receive a JSON object with an array 'blocks' of English strings from the same screen. "
            "Translate EVERY item into Russian keeping cross-block context. "
            "Return STRICTLY a valid JSON object with the exact schema:\n"
            '{"translations": [{"id": 0, "text": "..."}]}\n'
            "Do not wrap in markdown, do not skip items, do not add extra text."
        )
        body = {
            "model": model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": batch_instruction},
                {"role": "user", "content": json.dumps({"blocks": payload_items}, ensure_ascii=False)},
            ],
        }

        resp = self._session.post(endpoint, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        content = self._extract_message_content(data)
        parsed = self._parse_batch_json(content, len(texts))

        if parsed is not None:
            return [parsed[i] if parsed[i] else texts[i] for i in range(len(texts))]

        return [self._call_llm_single(endpoint, headers, cfg, t) for t in texts]

    def _call_llm_single(
        self,
        endpoint: str,
        headers: dict[str, str],
        cfg: AppConfig,
        text: str,
    ) -> str:
        body = {
            "model": cfg.llm_model.strip(),
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": cfg.system_prompt},
                {"role": "user", "content": text},
            ],
        }
        resp = self._session.post(endpoint, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        content = self._extract_message_content(resp.json()).strip()
        return content if content else text

    @staticmethod
    def _extract_message_content(data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("LLM API returned empty choices.")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str):
            return ""
        return content.strip()

    @staticmethod
    def _parse_batch_json(content: str, expected_count: int) -> Optional[List[str]]:
        cleaned = _CODE_FENCE_RE.sub("", content.strip()).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            obj = json.loads(cleaned)
        except Exception:
            return None

        items = obj.get("translations") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            return None

        mapped: dict[int, str] = {}
        for item in items:
            if isinstance(item, dict) and "id" in item and "text" in item:
                try:
                    idx = int(item["id"])
                    mapped[idx] = str(item["text"]).strip()
                except Exception:
                    continue

        if not mapped:
            return None

        return [mapped.get(i, "") for i in range(expected_count)]
'''


FILES["src/ocr_engine.py"] = r'''
"""Движок EasyOCR, группировка строк в абзацы, анализ цветов фона/текста и жирности."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image as _PILImage

from config import get_models_dir


# Патч совместимости EasyOCR с Pillow >= 10 (удалённый атрибут Image.ANTIALIAS)
if not hasattr(_PILImage, "ANTIALIAS") and hasattr(_PILImage, "Resampling"):
    _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

_EXPECTED_MODEL_FILES = ("craft_mlt_25k.pth", "english_g2.pth")
_HYPHEN_BREAK_RE = re.compile(r"(\w+)-\s+(\w+)")


@dataclass
class TextBlock:
    """Абзац / логический блок текста с визуальными атрибутами оригинала."""

    x1: int
    y1: int
    x2: int
    y2: int
    text: str
    line_height: float
    line_count: int
    bg_color: Tuple[int, int, int]
    fg_color: Tuple[int, int, int]
    font_weight: int  # 400=Normal, 600=DemiBold, 700=Bold


@dataclass
class _RawWord:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str
    conf: float

    @property
    def height(self) -> float:
        return float(max(1, self.y2 - self.y1))

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) * 0.5


@dataclass
class _TextLine:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str
    line_height: float
    bg_color: Tuple[int, int, int]


def models_exist() -> bool:
    """Проверяет, скачаны ли уже модели EasyOCR в AppData."""
    models_dir = get_models_dir()
    return all((models_dir / fname).exists() for fname in _EXPECTED_MODEL_FILES)


def compute_frame_diff_pct(prev_rgb: Optional[np.ndarray], curr_rgb: np.ndarray) -> float:
    """
    Быстрая оценка процента изменившихся пикселей между двумя кадрами через NumPy.
    Игнорирует мелкий шум (порог канала > 16 из 255).
    """
    if prev_rgb is None or prev_rgb.shape != curr_rgb.shape:
        return 100.0

    h, w = curr_rgb.shape[:2]
    step = 2 if (h * w) > 300_000 else 1
    a = prev_rgb[::step, ::step].astype(np.int16)
    b = curr_rgb[::step, ::step].astype(np.int16)

    diff = np.abs(a - b)
    changed_mask = np.max(diff, axis=2) > 16
    return float(np.count_nonzero(changed_mask)) * 100.0 / float(changed_mask.size)


def _quantized_dominant_color(pixels: np.ndarray) -> Tuple[int, int, int]:
    """Определяет доминантный RGB-цвет через квантование по корзинам."""
    if pixels.size == 0:
        return (20, 20, 24)
    flat = pixels.reshape(-1, 3)
    if flat.shape[0] < 4:
        med = np.median(flat, axis=0)
        return (int(med[0]), int(med[1]), int(med[2]))

    quant = (flat // 12).astype(np.int32)
    keys = quant[:, 0] * 10000 + quant[:, 1] * 100 + quant[:, 2]
    unique_keys, counts = np.unique(keys, return_counts=True)
    best_key = unique_keys[int(np.argmax(counts))]
    cluster = flat[keys == best_key]
    med = np.median(cluster, axis=0)
    return (int(med[0]), int(med[1]), int(med[2]))


def _extract_border_bg_color(img_rgb: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int]:
    """Считывает граничные пиксели вокруг bounding box для определения цвета фона."""
    h, w = img_rgb.shape[:2]
    pad = 4
    bx1 = max(0, x1 - pad)
    by1 = max(0, y1 - pad)
    bx2 = min(w, x2 + pad)
    by2 = min(h, y2 + pad)

    ix1 = max(0, min(w, x1))
    iy1 = max(0, min(h, y1))
    ix2 = max(0, min(w, x2))
    iy2 = max(0, min(h, y2))

    strips: List[np.ndarray] = []
    if by1 < iy1:
        strips.append(img_rgb[by1:iy1, bx1:bx2].reshape(-1, 3))
    if iy2 < by2:
        strips.append(img_rgb[iy2:by2, bx1:bx2].reshape(-1, 3))
    if bx1 < ix1:
        strips.append(img_rgb[iy1:iy2, bx1:ix1].reshape(-1, 3))
    if ix2 < bx2:
        strips.append(img_rgb[iy1:iy2, ix2:bx2].reshape(-1, 3))

    if strips:
        border_pixels = np.concatenate(strips, axis=0)
        if border_pixels.shape[0] > 0:
            return _quantized_dominant_color(border_pixels)

    crop = img_rgb[iy1:iy2, ix1:ix2]
    if crop.size == 0:
        return (20, 20, 24)
    return _quantized_dominant_color(crop)


def _perceived_luminance(rgb: Tuple[int, int, int]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    return float(((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5)


def _analyze_fg_and_weight(
    img_rgb: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    bg_color: Tuple[int, int, int],
) -> Tuple[Tuple[int, int, int], int]:
    """
    Определяет цвет оригинального текста (контрастного к фону) и оценивает жирность шрифта
    по плотности контрастных пикселей внутри bounding box.
    """
    h, w = img_rgb.shape[:2]
    cx1 = max(0, min(w - 1, x1))
    cy1 = max(0, min(h - 1, y1))
    cx2 = max(cx1 + 1, min(w, x2))
    cy2 = max(cy1 + 1, min(h, y2))

    crop = img_rgb[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return ((245, 245, 245) if _perceived_luminance(bg_color) < 128 else (20, 20, 24), 400)

    flat = crop.reshape(-1, 3).astype(np.float32)
    bg_vec = np.array(bg_color, dtype=np.float32)
    dists = np.linalg.norm(flat - bg_vec, axis=1)

    max_dist = float(np.max(dists)) if dists.size > 0 else 0.0
    if max_dist < 30.0:
        fg = (245, 245, 245) if _perceived_luminance(bg_color) < 128 else (20, 20, 24)
        return (fg, 400)

    high_thresh = max(35.0, float(np.percentile(dists, 82)))
    fg_pixels = flat[dists >= high_thresh]
    if fg_pixels.shape[0] == 0:
        fg_pixels = flat[dists >= max_dist * 0.5]

    med_fg = np.median(fg_pixels, axis=0)
    fg_color = (int(med_fg[0]), int(med_fg[1]), int(med_fg[2]))

    bg_lum = _perceived_luminance(bg_color)
    fg_lum = _perceived_luminance(fg_color)
    if abs(bg_lum - fg_lum) < 70.0:
        fg_color = (245, 245, 245) if bg_lum < 128.0 else (20, 20, 24)

    stroke_thresh = max(32.0, max_dist * 0.42)
    density = float(np.count_nonzero(dists >= stroke_thresh)) / float(dists.size)

    if density >= 0.30:
        font_weight = 700
    elif density >= 0.22:
        font_weight = 600
    else:
        font_weight = 400

    return (fg_color, font_weight)


class OCREngine:
    """Обёртка вокруг EasyOCR с хранением моделей в %APPDATA% и умной группировкой блоков."""

    def __init__(self) -> None:
        self._reader = None
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._reader is not None

    def initialize(self, status_callback: Optional[Callable[[str], None]] = None) -> None:
        """Загружает модели (при первом запуске скачивает в AppData) и инициализирует EasyOCR."""
        models_dir = str(get_models_dir())
        already_cached = models_exist()

        if status_callback:
            if already_cached:
                status_callback("Инициализация EasyOCR из локального кэша...")
            else:
                status_callback(
                    "Первый запуск: загрузка моделей EasyOCR (~100 МБ) в AppData... Подождите 1–2 мин."
                )

        import easyocr

        self._reader = easyocr.Reader(
            ["en"],
            gpu=False,
            model_storage_directory=models_dir,
            download_enabled=True,
            verbose=False,
        )
        self._ready = True
        if status_callback:
            status_callback("EasyOCR готов к работе")

    def extract_blocks(self, img_rgb: np.ndarray) -> List[TextBlock]:
        """Распознаёт текст на RGB-кадре, объединяет строки в абзацы и вычисляет стили."""
        if not self.is_ready or img_rgb is None or img_rgb.size == 0:
            return []

        h, w = img_rgb.shape[:2]
        if h < 12 or w < 12:
            return []

        raw_results = self._reader.readtext(img_rgb, detail=1, paragraph=False)
        if not raw_results:
            return []

        words: List[_RawWord] = []
        for bbox, text, conf in raw_results:
            cleaned = str(text).strip()
            if not cleaned or float(conf) < 0.25:
                continue
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            x1 = max(0, int(min(xs)))
            y1 = max(0, int(min(ys)))
            x2 = min(w, int(max(xs)))
            y2 = min(h, int(max(ys)))
            if (x2 - x1) < 4 or (y2 - y1) < 6:
                continue
            words.append(_RawWord(x1=x1, y1=y1, x2=x2, y2=y2, text=cleaned, conf=float(conf)))

        if not words:
            return []

        lines = self._group_words_into_lines(words, img_rgb)
        blocks = self._group_lines_into_blocks(lines, img_rgb)
        return blocks

    @staticmethod
    def _group_words_into_lines(words: List[_RawWord], img_rgb: np.ndarray) -> List[_TextLine]:
        """Объединяет фрагменты, стоящие на одной горизонтальной строке."""
        sorted_words = sorted(words, key=lambda item: (item.y1, item.x1))
        clusters: List[List[_RawWord]] = []

        for word in sorted_words:
            placed = False
            for cluster in clusters:
                ref_y1 = min(w.y1 for w in cluster)
                ref_y2 = max(w.y2 for w in cluster)
                ref_h = float(max(1, ref_y2 - ref_y1))
                overlap_y = min(ref_y2, word.y2) - max(ref_y1, word.y1)
                min_h = min(ref_h, word.height)
                max_h = max(ref_h, word.height)

                if overlap_y >= 0.45 * min_h and (max_h / max(1.0, min_h)) <= 1.65:
                    cluster.append(word)
                    placed = True
                    break
            if not placed:
                clusters.append([word])

        lines: List[_TextLine] = []
        for cluster in clusters:
            cluster.sort(key=lambda item: item.x1)
            sub_groups: List[List[_RawWord]] = [[cluster[0]]]
            for item in cluster[1:]:
                prev = sub_groups[-1][-1]
                avg_h = (prev.height + item.height) * 0.5
                gap_x = item.x1 - prev.x2
                if gap_x <= avg_h * 2.2:
                    sub_groups[-1].append(item)
                else:
                    sub_groups.append([item])

            for group in sub_groups:
                lx1 = min(w.x1 for w in group)
                ly1 = min(w.y1 for w in group)
                lx2 = max(w.x2 for w in group)
                ly2 = max(w.y2 for w in group)
                med_h = float(np.median([w.height for w in group]))
                text = " ".join(w.text for w in group)
                bg = _extract_border_bg_color(img_rgb, lx1, ly1, lx2, ly2)
                lines.append(
                    _TextLine(
                        x1=lx1,
                        y1=ly1,
                        x2=lx2,
                        y2=ly2,
                        text=text,
                        line_height=med_h,
                        bg_color=bg,
                    )
                )

        lines.sort(key=lambda ln: (ln.y1, ln.x1))
        return lines

    @staticmethod
    def _group_lines_into_blocks(lines: List[_TextLine], img_rgb: np.ndarray) -> List[TextBlock]:
        """Объединяет близкие по вертикали и горизонтали строки в цельные абзацы."""
        para_groups: List[List[_TextLine]] = []

        for line in lines:
            best_group: Optional[List[_TextLine]] = None
            best_gap = float("inf")

            for group in para_groups:
                last = group[-1]
                avg_h = (last.line_height + line.line_height) * 0.5
                h_ratio = max(last.line_height, line.line_height) / max(
                    1.0, min(last.line_height, line.line_height)
                )
                if h_ratio > 1.38:
                    continue

                v_gap = line.y1 - last.y2
                if v_gap < -0.35 * avg_h or v_gap > 0.90 * avg_h:
                    continue

                gx1 = min(g.x1 for g in group)
                gx2 = max(g.x2 for g in group)
                horiz_overlap = min(gx2, line.x2) - max(gx1, line.x1)
                left_close = abs(gx1 - line.x1) <= 2.2 * avg_h
                center_g = (gx1 + gx2) * 0.5
                center_l = (line.x1 + line.x2) * 0.5
                center_close = abs(center_g - center_l) <= 2.5 * avg_h

                if horiz_overlap <= 0 and not left_close and not center_close:
                    continue

                if _color_distance(last.bg_color, line.bg_color) > 60.0:
                    continue

                if v_gap < best_gap:
                    best_gap = v_gap
                    best_group = group

            if best_group is not None:
                best_group.append(line)
            else:
                para_groups.append([line])

        blocks: List[TextBlock] = []
        for group in para_groups:
            bx1 = min(ln.x1 for ln in group)
            by1 = min(ln.y1 for ln in group)
            bx2 = max(ln.x2 for ln in group)
            by2 = max(ln.y2 for ln in group)
            med_line_h = float(np.median([ln.line_height for ln in group]))

            joined = " ".join(ln.text for ln in group)
            joined = _HYPHEN_BREAK_RE.sub(r"\1\2", joined)

            bg_color = _extract_border_bg_color(img_rgb, bx1, by1, bx2, by2)
            fg_color, font_weight = _analyze_fg_and_weight(img_rgb, bx1, by1, bx2, by2, bg_color)

            blocks.append(
                TextBlock(
                    x1=bx1,
                    y1=by1,
                    x2=bx2,
                    y2=by2,
                    text=joined,
                    line_height=med_line_h,
                    line_count=len(group),
                    bg_color=bg_color,
                    fg_color=fg_color,
                    font_weight=font_weight,
                )
            )

        return blocks
'''


FILES["src/selector.py"] = r'''
"""Оверлей выбора прямоугольной области экрана с учётом Windows 11 Per-Monitor DPI."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional, Tuple

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget


_user32 = ctypes.windll.user32
_user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
_user32.GetCursorPos.restype = wintypes.BOOL


def get_cursor_pos_physical() -> Tuple[int, int]:
    """Возвращает точные физические координаты курсора Windows (под Per-Monitor V2 DPI)."""
    pt = wintypes.POINT()
    if _user32.GetCursorPos(ctypes.byref(pt)):
        return (int(pt.x), int(pt.y))
    return (0, 0)


class RegionSelector(QWidget):
    """
    Полноэкранное слегка затемнённое окно для выделения области мышкой.
    Возвращает логический QRect (для позиционирования Qt-оверлея) и физический кортеж (для mss).
    """

    region_selected = pyqtSignal(QRect, tuple)
    selection_cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        self._dragging = False
        self._start_local = QPoint()
        self._curr_local = QPoint()
        self._start_global = QPoint()
        self._start_phys: Tuple[int, int] = (0, 0)
        self._virtual_geo = QRect()

    def start_selection(self) -> None:
        """Разворачивает селектор на все подключённые мониторы."""
        screens = QGuiApplication.screens()
        geo = QRect()
        for scr in screens:
            geo = geo.united(scr.geometry())
        if geo.isNull():
            primary = QGuiApplication.primaryScreen()
            geo = primary.geometry() if primary else QRect(0, 0, 1920, 1080)

        self._virtual_geo = geo
        self._dragging = False
        self._start_local = QPoint()
        self._curr_local = QPoint()

        self.setGeometry(geo)
        self.show()
        self.raise_()
        self.activateWindow()
        self.update()

    def _current_selection_local(self) -> Optional[QRect]:
        if not self._dragging:
            return None
        return QRect(self._start_local, self._curr_local).normalized()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._dragging = False
            self.hide()
            self.selection_cancelled.emit()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_local = event.position().toPoint()
            self._curr_local = self._start_local
            self._start_global = event.globalPosition().toPoint()
            self._start_phys = get_cursor_pos_physical()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._curr_local = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return

        self._dragging = False
        end_global = event.globalPosition().toPoint()
        end_phys = get_cursor_pos_physical()

        logical_rect = QRect(self._start_global, end_global).normalized()
        px1 = min(self._start_phys[0], end_phys[0])
        py1 = min(self._start_phys[1], end_phys[1])
        px2 = max(self._start_phys[0], end_phys[0])
        py2 = max(self._start_phys[1], end_phys[1])
        phys_rect = (px1, py1, px2 - px1, py2 - py1)

        self.hide()

        if logical_rect.width() < 24 or logical_rect.height() < 16 or phys_rect[2] < 24 or phys_rect[3] < 16:
            self.selection_cancelled.emit()
            return

        self.region_selected.emit(logical_rect, phys_rect)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._dragging = False
            self.hide()
            self.selection_cancelled.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        full_rect = self.rect()
        dim_color = QColor(10, 14, 24, 115)
        sel = self._current_selection_local()

        if sel is None or sel.isEmpty():
            painter.fillRect(full_rect, dim_color)
        else:
            painter.fillRect(QRect(0, 0, full_rect.width(), sel.top()), dim_color)
            painter.fillRect(
                QRect(0, sel.bottom() + 1, full_rect.width(), full_rect.height() - sel.bottom() - 1),
                dim_color,
            )
            painter.fillRect(QRect(0, sel.top(), sel.left(), sel.height()), dim_color)
            painter.fillRect(
                QRect(sel.right() + 1, sel.top(), full_rect.width() - sel.right() - 1, sel.height()),
                dim_color,
            )
            # Невидимая заливка alpha=1 удерживает перехват мыши внутри выделения
            painter.fillRect(sel, QColor(0, 0, 0, 1))

            pen = QPen(QColor("#818CF8"), 2)
            painter.setPen(pen)
            painter.drawRect(sel)

            badge_text = f"{sel.width()} x {sel.height()}"
            badge_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
            painter.setFont(badge_font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(badge_text) + 16
            th = fm.height() + 8
            bx = sel.left()
            by = sel.top() - th - 6
            if by < 8:
                by = sel.top() + 6
            badge_rect = QRect(bx, by, tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(15, 18, 28, 225))
            painter.drawRoundedRect(badge_rect, 6, 6)
            painter.setPen(QColor("#E2E8F0"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        primary = QGuiApplication.primaryScreen()
        p_geo = primary.geometry() if primary else self._virtual_geo
        local_top_center_x = (p_geo.left() - self._virtual_geo.left()) + p_geo.width() // 2
        local_top_y = (p_geo.top() - self._virtual_geo.top()) + 28

        hint = "Выделите область мышкой для Live-перевода  |  ПКМ / Esc — отмена"
        hint_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(hint_font)
        hfm = painter.fontMetrics()
        hw = hfm.horizontalAdvance(hint) + 32
        hh = hfm.height() + 16
        hint_rect = QRect(local_top_center_x - hw // 2, local_top_y, hw, hh)

        painter.setPen(QPen(QColor("#4F46E5"), 1.5))
        painter.setBrush(QColor(15, 18, 28, 230))
        painter.drawRoundedRect(hint_rect, 10, 10)
        painter.setPen(QColor("#F8FAFC"))
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint)
'''


FILES["src/overlay.py"] = r'''
"""Прозрачный кликабельный насквозь Live-оверлей с защитой WDA_EXCLUDEFROMCAPTURE."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
from typing import List, Tuple

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QColor, QFont, QFontMetrics, QKeyEvent, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget


logger = logging.getLogger(__name__)

# Win32 константы
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

WDA_EXCLUDEFROMCAPTURE = 0x00000011

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = ctypes.c_void_p(-1)

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

_user32 = ctypes.windll.user32

_user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL

_user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = wintypes.LONG

_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
_user32.SetWindowLongW.restype = wintypes.LONG

_user32.SetWindowPos.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
_user32.SetWindowPos.restype = wintypes.BOOL

_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL


def enable_dpi_awareness() -> None:
    """Активирует Per-Monitor DPI Awareness V2 до создания QApplication."""
    try:
        ok = _user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        if not ok:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception as exc:
        logger.warning("Failed to set DPI awareness: %s", exc)


@dataclass
class RenderedBlock:
    """Переведённый блок для отрисовки на оверлее."""

    x1: int
    y1: int
    x2: int
    y2: int
    translated_text: str
    line_height: float
    bg_color: Tuple[int, int, int]
    fg_color: Tuple[int, int, int]
    font_weight: int


class OverlayWindow(QWidget):
    """
    Окно наложения перевода поверх оригинального текста.
    - Без рамки, прозрачное, всегда поверх окон (включая borderless игры).
    - Полностью кликабельно насквозь.
    - Исключено из захвата экрана (WDA_EXCLUDEFROMCAPTURE).
    - Закрывается ТОЛЬКО программно через force_close() (по глобальному хоткею остановки).
    """

    def __init__(self, font_family: str = "Segoe UI") -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._font_family = font_family or "Segoe UI"
        self._blocks: List[RenderedBlock] = []
        self._capture_w: int = 1
        self._capture_h: int = 1
        self._allow_close = False
        self._affinity_applied = False

        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(2000)
        self._topmost_timer.timeout.connect(self._assert_topmost)

    def set_font_family(self, font_family: str) -> None:
        self._font_family = font_family or "Segoe UI"

    def start_at(self, logical_rect: QRect) -> Tuple[int, int, int, int]:
        """
        Отображает оверлей в заданной логической области, применяет Win32-флаги
        и возвращает точный физический прямоугольник окна (left, top, width, height) для mss.
        """
        self._allow_close = False
        self._blocks = []
        self.setGeometry(logical_rect)
        self.show()
        self._apply_win32_flags()
        self._topmost_timer.start()
        self.update()
        return self.get_physical_rect()

    def _apply_win32_flags(self) -> None:
        hwnd = int(self.winId())
        if not hwnd:
            return

        ex_style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = (
            ex_style
            | WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOPMOST
            | WS_EX_NOACTIVATE
            | WS_EX_TOOLWINDOW
        )
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        # Защита от самоперевода и мерцания: оверлей невидим для mss
        ok = _user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        self._affinity_applied = bool(ok)
        if not ok:
            logger.error("SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) failed for hwnd=%s", hwnd)

        _user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )

    def _assert_topmost(self) -> None:
        if not self.isVisible():
            return
        hwnd = int(self.winId())
        if hwnd:
            _user32.SetWindowPos(
                ctypes.c_void_p(hwnd),
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )

    def get_physical_rect(self) -> Tuple[int, int, int, int]:
        """Считывает реальные физические координаты окна через Win32 GetWindowRect."""
        hwnd = int(self.winId())
        rect = wintypes.RECT()
        if hwnd and _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            w = max(1, int(rect.right - rect.left))
            h = max(1, int(rect.bottom - rect.top))
            return (int(rect.left), int(rect.top), w, h)
        geo = self.geometry()
        dpr = self.devicePixelRatioF()
        return (
            int(round(geo.x() * dpr)),
            int(round(geo.y() * dpr)),
            max(1, int(round(geo.width() * dpr))),
            max(1, int(round(geo.height() * dpr))),
        )

    def update_blocks(self, blocks: List[RenderedBlock], capture_w: int, capture_h: int) -> None:
        self._blocks = blocks
        self._capture_w = max(1, capture_w)
        self._capture_h = max(1, capture_h)
        self.update()

    def force_close(self) -> None:
        """Единственный разрешённый способ выключения Live-оверлея."""
        self._topmost_timer.stop()
        self._blocks = []
        self._allow_close = True
        self.hide()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close:
            event.ignore()
            return
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        event.ignore()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w_log = self.width()
        h_log = self.height()
        if w_log <= 0 or h_log <= 0:
            return

        self._draw_corner_markers(painter, w_log, h_log)

        if not self._blocks:
            return

        sx = float(w_log) / float(self._capture_w)
        sy = float(h_log) / float(self._capture_h)

        for blk in self._blocks:
            self._draw_block(painter, blk, sx, sy, w_log, h_log)

    @staticmethod
    def _draw_corner_markers(painter: QPainter, w: int, h: int) -> None:
        arm = min(14, max(6, min(w, h) // 10))
        pen = QPen(QColor(129, 140, 248, 150), 2)
        painter.setPen(pen)
        painter.drawLine(1, 1, arm, 1)
        painter.drawLine(1, 1, 1, arm)
        painter.drawLine(w - arm - 1, 1, w - 2, 1)
        painter.drawLine(w - 2, 1, w - 2, arm)
        painter.drawLine(1, h - 2, arm, h - 2)
        painter.drawLine(1, h - arm - 1, 1, h - 2)
        painter.drawLine(w - arm - 1, h - 2, w - 2, h - 2)
        painter.drawLine(w - 2, h - arm - 1, w - 2, h - 2)

    def _draw_block(
        self,
        painter: QPainter,
        blk: RenderedBlock,
        sx: float,
        sy: float,
        max_w: int,
        max_h: int,
    ) -> None:
        text = blk.translated_text.strip()
        if not text:
            return

        pad_x = 3
        pad_y = 2
        rx = max(0, int(round(blk.x1 * sx)) - pad_x)
        ry = max(0, int(round(blk.y1 * sy)) - pad_y)
        rx2 = min(max_w, int(round(blk.x2 * sx)) + pad_x)
        ry2 = min(max_h, int(round(blk.y2 * sy)) + pad_y)
        rw = max(16, rx2 - rx)
        rh = max(14, ry2 - ry)

        text_pad_x = 4
        text_pad_y = 2

        logical_line_h = max(10.0, blk.line_height * sy)
        start_px = max(9, min(68, int(round(logical_line_h * 0.86))))
        min_px = 8

        weight_enum = self._map_font_weight(blk.font_weight)
        flags = (
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap
        )

        font = QFont(self._font_family)
        font.setWeight(weight_enum)

        avail_w = max(12, rw - 2 * text_pad_x)
        avail_h = max(10, rh - 2 * text_pad_y)

        chosen_px = min_px
        measured = QRect()
        for px in range(start_px, min_px - 1, -1):
            font.setPixelSize(px)
            fm = QFontMetrics(font)
            measured = fm.boundingRect(QRect(0, 0, avail_w, 10000), flags, text)
            if measured.width() <= avail_w + 2 and measured.height() <= avail_h + 2:
                chosen_px = px
                break
        else:
            font.setPixelSize(min_px)
            fm = QFontMetrics(font)
            if measured.width() > avail_w:
                new_rw = min(max_w - rx, measured.width() + 2 * text_pad_x + 4)
                if new_rw > rw:
                    rw = new_rw
                    avail_w = max(12, rw - 2 * text_pad_x)
            measured = fm.boundingRect(QRect(0, 0, avail_w, 10000), flags, text)
            if measured.height() > avail_h:
                new_rh = min(max_h - ry, measured.height() + 2 * text_pad_y + 2)
                if new_rh > rh:
                    rh = new_rh
            chosen_px = min_px

        font.setPixelSize(chosen_px)
        bg_rect = QRect(rx, ry, rw, rh)

        radius = min(6.0, rh * 0.22)
        bg_qcolor = QColor(blk.bg_color[0], blk.bg_color[1], blk.bg_color[2], 248)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_qcolor)
        painter.drawRoundedRect(bg_rect, radius, radius)

        text_rect = bg_rect.adjusted(text_pad_x, text_pad_y, -text_pad_x, -text_pad_y)
        fg_qcolor = QColor(blk.fg_color[0], blk.fg_color[1], blk.fg_color[2], 255)
        painter.setFont(font)
        painter.setPen(fg_qcolor)
        painter.drawText(text_rect, flags, text)

    @staticmethod
    def _map_font_weight(weight: int) -> QFont.Weight:
        if weight >= 700:
            return QFont.Weight.Bold
        if weight >= 600:
            return QFont.Weight.DemiBold
        return QFont.Weight.Normal
'''


FILES["src/ui_window.py"] = r'''
"""Стартовое окно управления (PyQt6, современная тёмная тема)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig, DEFAULT_SYSTEM_PROMPT, parse_hotkey_win32


DARK_QSS = """
QMainWindow, QWidget#CentralRoot, QWidget#ScrollContent {
    background-color: #0F1117;
    color: #E2E8F0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QScrollArea {
    border: none;
    background-color: #0F1117;
}
QFrame[card="true"] {
    background-color: #171B26;
    border: 1px solid #252B3B;
    border-radius: 10px;
}
QLabel#TitleLabel {
    font-size: 18px;
    font-weight: 700;
    color: #F8FAFC;
}
QLabel#SubtitleLabel {
    font-size: 12px;
    color: #94A3B8;
}
QLabel[role="section"] {
    font-size: 13px;
    font-weight: 700;
    color: #C7D2FE;
}
QLabel[role="hint"] {
    font-size: 11px;
    color: #94A3B8;
}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0D1017;
    color: #F1F5F9;
    border: 1px solid #2D3548;
    border-radius: 6px;
    padding: 6px 9px;
    selection-background-color: #4F46E5;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6366F1;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #171B26;
    color: #F1F5F9;
    border: 1px solid #2D3548;
    selection-background-color: #4F46E5;
}
QRadioButton {
    spacing: 8px;
    color: #E2E8F0;
    font-weight: 600;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #475569;
    background-color: #0D1017;
}
QRadioButton::indicator:checked {
    border: 2px solid #818CF8;
    background-color: #6366F1;
}
QPushButton {
    background-color: #23293A;
    color: #F1F5F9;
    border: 1px solid #333C52;
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2C344A;
    border-color: #4F46E5;
}
QPushButton:pressed {
    background-color: #1E2433;
}
QPushButton#PrimaryBtn {
    background-color: #4F46E5;
    border: 1px solid #6366F1;
    color: #FFFFFF;
    padding: 10px 18px;
    font-size: 13px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #6366F1;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #2A2F42;
    border-color: #32384D;
    color: #64748B;
}
QPushButton#SmallBtn {
    padding: 5px 10px;
    font-size: 11px;
}
QProgressBar {
    background-color: #0D1017;
    border: 1px solid #252B3B;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #6366F1;
    border-radius: 3px;
}
"""

_QT_KEY_NAMES = {
    Qt.Key.Key_Space: "Space",
    Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Return: "Enter",
    Qt.Key.Key_Enter: "Enter",
    Qt.Key.Key_Backspace: "Backspace",
    Qt.Key.Key_Insert: "Insert",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End",
    Qt.Key.Key_PageUp: "PageUp",
    Qt.Key.Key_PageDown: "PageDown",
    Qt.Key.Key_Left: "Left",
    Qt.Key.Key_Right: "Right",
    Qt.Key.Key_Up: "Up",
    Qt.Key.Key_Down: "Down",
    Qt.Key.Key_QuoteLeft: "`",
    Qt.Key.Key_Minus: "-",
    Qt.Key.Key_Equal: "=",
    Qt.Key.Key_BracketLeft: "[",
    Qt.Key.Key_BracketRight: "]",
    Qt.Key.Key_Semicolon: ";",
    Qt.Key.Key_Apostrophe: "'",
    Qt.Key.Key_Comma: ",",
    Qt.Key.Key_Period: ".",
    Qt.Key.Key_Slash: "/",
    Qt.Key.Key_Backslash: "\\",
}


class HotkeyEdit(QLineEdit):
    """Поле записи комбинации клавиш (кликните и нажмите нужное сочетание)."""

    def __init__(self, initial: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(initial, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Нажмите комбинацию клавиш...")
        self.setToolTip("Кликните в поле и нажмите желаемую комбинацию (например, Ctrl+Shift+Q)")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = int(event.key())
        ignored = {
            int(Qt.Key.Key_Control.value),
            int(Qt.Key.Key_Shift.value),
            int(Qt.Key.Key_Alt.value),
            int(Qt.Key.Key_Meta.value),
            int(Qt.Key.Key_unknown.value),
        }
        if key in ignored:
            return

        if key == int(Qt.Key.Key_Escape.value):
            self.clearFocus()
            return

        mods = event.modifiers()
        parts: list[str] = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")

        key_name = self._qt_key_to_name(key)
        if not key_name:
            return

        parts.append(key_name)
        candidate = "+".join(parts)
        if parse_hotkey_win32(candidate) is not None:
            self.setText(candidate)

    @staticmethod
    def _qt_key_to_name(key: int) -> Optional[str]:
        key_a = int(Qt.Key.Key_A.value)
        key_z = int(Qt.Key.Key_Z.value)
        key_0 = int(Qt.Key.Key_0.value)
        key_9 = int(Qt.Key.Key_9.value)
        key_f1 = int(Qt.Key.Key_F1.value)
        key_f24 = int(Qt.Key.Key_F24.value)

        if key_a <= key <= key_z:
            return chr(ord("A") + (key - key_a))
        if key_0 <= key <= key_9:
            return chr(ord("0") + (key - key_0))
        if key_f1 <= key <= key_f24:
            return f"F{key - key_f1 + 1}"
        try:
            return _QT_KEY_NAMES.get(Qt.Key(key))
        except ValueError:
            return None


class MainWindow(QMainWindow):
    """Компактное стартовое окно настроек и запуска Live-переводчика."""

    config_saved = pyqtSignal(AppConfig)
    start_live_requested = pyqtSignal()

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._ocr_ready = False

        self.setWindowTitle("Live Screen Translator (EN -> RU)")
        self.setMinimumSize(510, 620)
        self.resize(540, 690)
        self.setStyleSheet(DARK_QSS)

        self._build_ui()
        self._load_values(config)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("CentralRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Live Screen Translator")
        title_lbl.setObjectName("TitleLabel")
        sub_lbl = QLabel("Мгновенный перевод EN -> RU поверх оригинального текста (Windows 11)")
        sub_lbl.setObjectName("SubtitleLabel")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        header_row.addLayout(title_col)
        root_layout.addLayout(header_row)

        status_card = QFrame()
        status_card.setProperty("card", "true")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(6)

        self.status_label = QLabel("Подготовка EasyOCR...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #FBBF24; font-weight: 600; font-size: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        root_layout.addWidget(status_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 2, 4, 2)
        content_layout.setSpacing(10)

        # Карточка 1: Горячие клавиши и интервал
        hk_card = QFrame()
        hk_card.setProperty("card", "true")
        hk_layout = QVBoxLayout(hk_card)
        hk_layout.setContentsMargins(12, 10, 12, 12)
        hk_layout.setSpacing(8)

        hk_title = QLabel("Управление и Live-режим")
        hk_title.setProperty("role", "section")
        hk_layout.addWidget(hk_title)

        hk_form = QFormLayout()
        hk_form.setSpacing(8)
        hk_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.start_hk_edit = HotkeyEdit()
        self.stop_hk_edit = HotkeyEdit()

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(200, 10000)
        self.interval_spin.setSingleStep(50)
        self.interval_spin.setSuffix(" мс")

        self.diff_spin = QDoubleSpinBox()
        self.diff_spin.setRange(0.2, 25.0)
        self.diff_spin.setSingleStep(0.5)
        self.diff_spin.setDecimals(1)
        self.diff_spin.setSuffix(" %")
        self.diff_spin.setToolTip("Если кадр изменился меньше порога, OCR пропускается для экономии CPU")

        hk_form.addRow("Старт / выбор области:", self.start_hk_edit)
        hk_form.addRow("Остановка Live-режима:", self.stop_hk_edit)
        hk_form.addRow("Интервал обновления:", self.interval_spin)
        hk_form.addRow("Порог изменения кадра:", self.diff_spin)
        hk_layout.addLayout(hk_form)

        strict_hint = QLabel(
            "Важно: Live-режим не закрывается по Esc или клику — выход только по комбинации остановки."
        )
        strict_hint.setProperty("role", "hint")
        strict_hint.setWordWrap(True)
        hk_layout.addWidget(strict_hint)
        content_layout.addWidget(hk_card)

        # Карточка 2: Движок перевода
        eng_card = QFrame()
        eng_card.setProperty("card", "true")
        eng_layout = QVBoxLayout(eng_card)
        eng_layout.setContentsMargins(12, 10, 12, 12)
        eng_layout.setSpacing(10)

        eng_title = QLabel("Движок перевода")
        eng_title.setProperty("role", "section")
        eng_layout.addWidget(eng_title)

        radio_row = QHBoxLayout()
        self.rb_llm = QRadioButton("LLM API (Креативный, без цензуры)")
        self.rb_free = QRadioButton("Free Online (Google / DeepL)")
        self.rb_llm.toggled.connect(self._on_engine_toggled)
        radio_row.addWidget(self.rb_llm)
        radio_row.addWidget(self.rb_free)
        eng_layout.addLayout(radio_row)

        self.engine_stack = QStackedWidget()

        # Страница 0: LLM API
        llm_page = QWidget()
        llm_layout = QVBoxLayout(llm_page)
        llm_layout.setContentsMargins(0, 4, 0, 0)
        llm_layout.setSpacing(8)

        llm_form = QFormLayout()
        llm_form.setSpacing(7)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://openrouter.ai/api/v1")

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-or-v1-...")
        self.toggle_key_btn = QPushButton("Показать")
        self.toggle_key_btn.setObjectName("SmallBtn")
        self.toggle_key_btn.setCheckable(True)
        self.toggle_key_btn.toggled.connect(self._toggle_api_key_visibility)
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.toggle_key_btn)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("deepseek/deepseek-chat")

        llm_form.addRow("Base URL:", self.base_url_edit)
        llm_form.addRow("API Key:", key_row)
        llm_form.addRow("Model Name:", self.model_edit)
        llm_layout.addLayout(llm_form)

        prompt_header = QHBoxLayout()
        prompt_lbl = QLabel("System Prompt (литературный перевод без цензуры):")
        prompt_lbl.setProperty("role", "hint")
        reset_prompt_btn = QPushButton("Сбросить промт")
        reset_prompt_btn.setObjectName("SmallBtn")
        reset_prompt_btn.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT))
        prompt_header.addWidget(prompt_lbl)
        prompt_header.addStretch()
        prompt_header.addWidget(reset_prompt_btn)
        llm_layout.addLayout(prompt_header)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setMinimumHeight(96)
        self.prompt_edit.setMaximumHeight(130)
        llm_layout.addWidget(self.prompt_edit)

        # Страница 1: Free Online (deep-translator)
        free_page = QWidget()
        free_layout = QVBoxLayout(free_page)
        free_layout.setContentsMargins(0, 4, 0, 0)
        free_layout.setSpacing(8)

        free_form = QFormLayout()
        free_form.setSpacing(7)
        self.free_provider_combo = QComboBox()
        self.free_provider_combo.addItem("Google Translate (сразу без API-ключа)", "google")
        self.free_provider_combo.addItem("MyMemory (сразу без API-ключа)", "mymemory")
        self.free_provider_combo.addItem("DeepL Free API (нужен бесплатный ключ DeepL)", "deepl")
        self.free_provider_combo.currentIndexChanged.connect(self._on_free_provider_changed)

        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key_edit.setPlaceholderText("Опционально — только для DeepL (иначе используется Google)")

        free_form.addRow("Провайдер:", self.free_provider_combo)
        free_form.addRow("DeepL API Key:", self.deepl_key_edit)
        free_layout.addLayout(free_form)

        free_hint = QLabel(
            "Google Translate через deep-translator работает сразу из коробки без регистрации и ключей. "
            "Для максимально живого и художественного перевода выберите LLM API."
        )
        free_hint.setProperty("role", "hint")
        free_hint.setWordWrap(True)
        free_layout.addWidget(free_hint)
        free_layout.addStretch()

        self.engine_stack.addWidget(llm_page)
        self.engine_stack.addWidget(free_page)
        eng_layout.addWidget(self.engine_stack)
        content_layout.addWidget(eng_card)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, 1)

        self.feedback_label = QLabel("")
        self.feedback_label.setProperty("role", "hint")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.feedback_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.clicked.connect(self._on_save_clicked)

        self.start_btn = QPushButton("Выбрать область и запустить")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start_clicked)

        btn_row.addWidget(self.save_btn, 1)
        btn_row.addWidget(self.start_btn, 2)
        root_layout.addLayout(btn_row)

        self.setCentralWidget(root)

    def _load_values(self, cfg: AppConfig) -> None:
        self.start_hk_edit.setText(cfg.start_hotkey)
        self.stop_hk_edit.setText(cfg.stop_hotkey)
        self.interval_spin.setValue(cfg.update_interval_ms)
        self.diff_spin.setValue(cfg.diff_threshold_pct)

        if cfg.engine == "llm":
            self.rb_llm.setChecked(True)
            self.engine_stack.setCurrentIndex(0)
        else:
            self.rb_free.setChecked(True)
            self.engine_stack.setCurrentIndex(1)

        self.base_url_edit.setText(cfg.llm_base_url)
        self.api_key_edit.setText(cfg.llm_api_key)
        self.model_edit.setText(cfg.llm_model)
        self.prompt_edit.setPlainText(cfg.system_prompt)

        idx = self.free_provider_combo.findData(cfg.free_provider)
        self.free_provider_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.deepl_key_edit.setText(cfg.deepl_api_key)
        self._on_free_provider_changed()
        self._refresh_start_button_text()

    def _on_engine_toggled(self) -> None:
        self.engine_stack.setCurrentIndex(0 if self.rb_llm.isChecked() else 1)

    def _on_free_provider_changed(self) -> None:
        is_deepl = self.free_provider_combo.currentData() == "deepl"
        self.deepl_key_edit.setEnabled(is_deepl)

    def _toggle_api_key_visibility(self, checked: bool) -> None:
        self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.toggle_key_btn.setText("Скрыть" if checked else "Показать")

    def _refresh_start_button_text(self) -> None:
        hk = self.start_hk_edit.text().strip() or "Ctrl+Shift+Q"
        self.start_btn.setText(f"Выбрать область и запустить ({hk})")

    def collect_config(self) -> AppConfig:
        start_hk = self.start_hk_edit.text().strip() or "Ctrl+Shift+Q"
        stop_hk = self.stop_hk_edit.text().strip() or "Ctrl+Shift+X"
        return AppConfig(
            start_hotkey=start_hk,
            stop_hotkey=stop_hk,
            engine="llm" if self.rb_llm.isChecked() else "free",
            free_provider=str(self.free_provider_combo.currentData() or "google"),
            deepl_api_key=self.deepl_key_edit.text().strip(),
            llm_base_url=self.base_url_edit.text().strip() or "https://openrouter.ai/api/v1",
            llm_api_key=self.api_key_edit.text().strip(),
            llm_model=self.model_edit.text().strip() or "deepseek/deepseek-chat",
            system_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_SYSTEM_PROMPT,
            update_interval_ms=int(self.interval_spin.value()),
            diff_threshold_pct=float(self.diff_spin.value()),
            font_family=self._config.font_family,
        )

    def _on_save_clicked(self) -> None:
        cfg = self.collect_config()
        if cfg.start_hotkey.upper() == cfg.stop_hotkey.upper():
            self.set_feedback("Ошибка: хоткеи старта и остановки должны различаться.", error=True)
            return
        self._config = cfg
        self._refresh_start_button_text()
        self.config_saved.emit(cfg)

    def _on_start_clicked(self) -> None:
        cfg = self.collect_config()
        if cfg.start_hotkey.upper() == cfg.stop_hotkey.upper():
            self.set_feedback("Ошибка: хоткеи старта и остановки должны различаться.", error=True)
            return
        self._config = cfg
        self._refresh_start_button_text()
        self.config_saved.emit(cfg)
        self.start_live_requested.emit()

    def set_ocr_status(self, message: str, ready: bool = False, error: bool = False) -> None:
        self._ocr_ready = ready
        self.status_label.setText(message)
        if error:
            self.status_label.setStyleSheet("color: #F87171; font-weight: 600; font-size: 12px;")
            self.progress_bar.setVisible(False)
            self.start_btn.setEnabled(False)
        elif ready:
            self.status_label.setStyleSheet("color: #34D399; font-weight: 600; font-size: 12px;")
            self.progress_bar.setVisible(False)
            self.start_btn.setEnabled(True)
        else:
            self.status_label.setStyleSheet("color: #FBBF24; font-weight: 600; font-size: 12px;")
            self.progress_bar.setVisible(True)
            self.start_btn.setEnabled(False)

    def set_feedback(self, message: str, error: bool = False) -> None:
        color = "#F87171" if error else "#34D399"
        self.feedback_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.feedback_label.setText(message)
'''


FILES["src/main.py"] = r'''
"""Точка входа Live Screen Translator: DPI, глобальные хоткеи Win32, фоновые потоки OCR и перевода."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
import sys
import threading
import time
from typing import List, Optional, Tuple


_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class _SafeLogStream:
    """Предотвращает падение EasyOCR (print/flush) при сборке PyInstaller с --noconsole."""

    encoding = "utf-8"

    def write(self, data: str) -> int:
        return len(data) if data else 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


if sys.stdout is None:
    sys.stdout = _SafeLogStream()  # type: ignore[assignment]
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = _SafeLogStream()  # type: ignore[assignment]
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# 1. Включаем Per-Monitor DPI Awareness V2 строго ДО создания QApplication
from overlay import OverlayWindow, RenderedBlock, enable_dpi_awareness

enable_dpi_awareness()

import mss
import numpy as np
from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from config import AppConfig, get_app_dir, load_config, parse_hotkey_win32, save_config
from ocr_engine import OCREngine, compute_frame_diff_pct
from selector import RegionSelector
from translator import TranslationEngine
from ui_window import MainWindow


WM_HOTKEY = 0x0312
HOTKEY_ID_START = 1001
HOTKEY_ID_STOP = 1002

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL


def _setup_logging() -> None:
    log_path = get_app_dir() / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )


logger = logging.getLogger(__name__)


class WinHotkeyFilter(QAbstractNativeEventFilter):
    """Перехватывает системные WM_HOTKEY поверх любых окон и borderless-игр."""

    def __init__(self, on_start, on_stop) -> None:
        super().__init__()
        self._on_start = on_start
        self._on_stop = on_stop

    def nativeEventFilter(self, eventType, message):  # type: ignore[override]
        try:
            ev = bytes(eventType)
        except Exception:
            ev = b""

        if ev in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    if hk_id == HOTKEY_ID_START:
                        QTimer.singleShot(0, self._on_start)
                        return True, 0
                    if hk_id == HOTKEY_ID_STOP:
                        QTimer.singleShot(0, self._on_stop)
                        return True, 0
            except Exception as exc:
                logger.debug("nativeEventFilter error: %s", exc)
        return False, 0


class OCRInitThread(QThread):
    """Фоновая загрузка/инициализация моделей EasyOCR без зависания UI."""

    status_changed = pyqtSignal(str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, ocr_engine: OCREngine) -> None:
        super().__init__()
        self._ocr = ocr_engine

    def run(self) -> None:
        try:
            self._ocr.initialize(status_callback=lambda msg: self.status_changed.emit(msg))
            self.finished_ok.emit()
        except Exception as exc:
            logger.exception("EasyOCR initialization failed")
            self.failed.emit(f"Ошибка инициализации EasyOCR: {exc}")


class LiveWorker(QThread):
    """Фоновый цикл захвата (mss), детекции изменений (NumPy), OCR и перевода."""

    blocks_ready = pyqtSignal(list, int, int)
    worker_error = pyqtSignal(str)

    def __init__(
        self,
        phys_rect: Tuple[int, int, int, int],
        ocr_engine: OCREngine,
        translator: TranslationEngine,
        interval_ms: int,
        diff_threshold_pct: float,
    ) -> None:
        super().__init__()
        self._phys_rect = phys_rect
        self._ocr = ocr_engine
        self._translator = translator
        self._interval_sec = max(0.2, interval_ms / 1000.0)
        self._diff_threshold = max(0.1, diff_threshold_pct)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        left, top, width, height = self._phys_rect
        monitor = {"left": left, "top": top, "width": width, "height": height}

        prev_rgb: Optional[np.ndarray] = None
        last_rendered_signature: Optional[Tuple[Tuple[str, int, int], ...]] = None

        if self._sleep_interruptible(0.08):
            return

        try:
            with mss.mss() as sct:
                while not self._stop_event.is_set():
                    tick_start = time.monotonic()

                    try:
                        shot = sct.grab(monitor)
                        img_rgb = np.ascontiguousarray(np.asarray(shot)[:, :, 2::-1])
                    except Exception as exc:
                        logger.warning("Screen grab failed: %s", exc)
                        if self._sleep_interruptible(self._interval_sec):
                            break
                        continue

                    diff_pct = compute_frame_diff_pct(prev_rgb, img_rgb)
                    if prev_rgb is not None and diff_pct < self._diff_threshold:
                        elapsed = time.monotonic() - tick_start
                        if self._sleep_interruptible(max(0.05, self._interval_sec - elapsed)):
                            break
                        continue

                    prev_rgb = img_rgb

                    if self._stop_event.is_set():
                        break

                    try:
                        blocks = self._ocr.extract_blocks(img_rgb)
                    except Exception as exc:
                        logger.warning("OCR pass failed: %s", exc)
                        if self._sleep_interruptible(self._interval_sec):
                            break
                        continue

                    if self._stop_event.is_set():
                        break

                    if not blocks:
                        if last_rendered_signature != ():
                            last_rendered_signature = ()
                            self.blocks_ready.emit([], width, height)
                    else:
                        sig = tuple((b.text, b.x1 // 4, b.y1 // 4) for b in blocks)
                        texts = [b.text for b in blocks]
                        translated_texts = self._translator.translate_batch(texts)

                        if self._stop_event.is_set():
                            break

                        rendered: List[RenderedBlock] = [
                            RenderedBlock(
                                x1=b.x1,
                                y1=b.y1,
                                x2=b.x2,
                                y2=b.y2,
                                translated_text=tr,
                                line_height=b.line_height,
                                bg_color=b.bg_color,
                                fg_color=b.fg_color,
                                font_weight=b.font_weight,
                            )
                            for b, tr in zip(blocks, translated_texts)
                        ]

                        last_rendered_signature = sig
                        self.blocks_ready.emit(rendered, width, height)

                    elapsed = time.monotonic() - tick_start
                    if self._sleep_interruptible(max(0.05, self._interval_sec - elapsed)):
                        break
        except Exception as exc:
            logger.exception("LiveWorker crashed")
            self.worker_error.emit(str(exc))

    def _sleep_interruptible(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))
        return True


class AppController(QObject):
    """Координирует стартовое окно, глобальные хоткеи, выбор области и Live-перевод."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._config: AppConfig = load_config()
        self._ocr = OCREngine()
        self._translator = TranslationEngine(self._config)

        self._main_window = MainWindow(self._config)
        self._selector = RegionSelector()
        self._overlay = OverlayWindow(font_family=self._config.font_family)

        self._worker: Optional[LiveWorker] = None
        self._ocr_init_thread: Optional[OCRInitThread] = None
        self._live_active = False
        self._selecting = False
        self._is_shutdown = False
        self._registered_hwnd: int = 0

        self._hotkey_filter = WinHotkeyFilter(
            on_start=self.trigger_start_selection,
            on_stop=self.stop_live_mode,
        )
        self._app.installNativeEventFilter(self._hotkey_filter)

        self._main_window.config_saved.connect(self._on_config_saved)
        self._main_window.start_live_requested.connect(self.trigger_start_selection)
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.selection_cancelled.connect(self._on_selection_cancelled)
        self._app.aboutToQuit.connect(self.shutdown)

    def start(self) -> None:
        self._main_window.show()
        self._register_hotkeys()
        self._start_ocr_init()

    def _start_ocr_init(self) -> None:
        self._main_window.set_ocr_status("Проверка моделей EasyOCR...", ready=False)
        self._ocr_init_thread = OCRInitThread(self._ocr)
        self._ocr_init_thread.status_changed.connect(
            lambda msg: self._main_window.set_ocr_status(msg, ready=False)
        )
        self._ocr_init_thread.finished_ok.connect(
            lambda: self._main_window.set_ocr_status(
                f"EasyOCR готов к работе  |  Старт: {self._config.start_hotkey}  |  Стоп: {self._config.stop_hotkey}",
                ready=True,
            )
        )
        self._ocr_init_thread.failed.connect(
            lambda err: self._main_window.set_ocr_status(err, ready=False, error=True)
        )
        self._ocr_init_thread.start()

    def _unregister_hotkeys(self) -> None:
        if self._registered_hwnd:
            _user32.UnregisterHotKey(self._registered_hwnd, HOTKEY_ID_START)
            _user32.UnregisterHotKey(self._registered_hwnd, HOTKEY_ID_STOP)
            self._registered_hwnd = 0

    def _register_hotkeys(self) -> None:
        self._unregister_hotkeys()
        hwnd = int(self._main_window.winId())
        self._registered_hwnd = hwnd

        errors: List[str] = []

        start_parsed = parse_hotkey_win32(self._config.start_hotkey)
        if not start_parsed:
            errors.append(f"некорректный хоткей старта ({self._config.start_hotkey})")
        elif not _user32.RegisterHotKey(hwnd, HOTKEY_ID_START, start_parsed[0], start_parsed[1]):
            errors.append(f"хоткей {self._config.start_hotkey} занят другой программой")

        stop_parsed = parse_hotkey_win32(self._config.stop_hotkey)
        if not stop_parsed:
            errors.append(f"некорректный хоткей остановки ({self._config.stop_hotkey})")
        elif not _user32.RegisterHotKey(hwnd, HOTKEY_ID_STOP, stop_parsed[0], stop_parsed[1]):
            errors.append(f"хоткей {self._config.stop_hotkey} занят другой программой")

        if errors:
            msg = "Внимание: " + "; ".join(errors)
            logger.warning(msg)
            self._main_window.set_feedback(msg, error=True)
        else:
            self._main_window.set_feedback(
                f"Хоткеи активны: Старт ({self._config.start_hotkey}) / Стоп ({self._config.stop_hotkey})",
                error=False,
            )

    def _on_config_saved(self, new_cfg: AppConfig) -> None:
        self._config = new_cfg
        save_config(new_cfg)
        self._translator.update_config(new_cfg)
        self._overlay.set_font_family(new_cfg.font_family)
        self._register_hotkeys()
        if self._ocr.is_ready:
            self._main_window.set_ocr_status(
                f"EasyOCR готов к работе  |  Старт: {self._config.start_hotkey}  |  Стоп: {self._config.stop_hotkey}",
                ready=True,
            )

    def trigger_start_selection(self) -> None:
        if not self._ocr.is_ready:
            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()
            self._main_window.set_feedback("Дождитесь завершения загрузки моделей EasyOCR.", error=True)
            return

        if self._selecting:
            return

        if self._live_active:
            self._stop_worker_and_overlay()

        self._selecting = True
        self._main_window.hide()
        self._selector.start_selection()

    def _on_selection_cancelled(self) -> None:
        self._selecting = False
        self._show_main_window()

    def _on_region_selected(self, logical_rect: QRect, fallback_phys_rect: tuple) -> None:
        self._selecting = False
        self._main_window.hide()

        phys_rect = self._overlay.start_at(logical_rect)
        if phys_rect[2] < 16 or phys_rect[3] < 16:
            phys_rect = fallback_phys_rect

        self._live_active = True
        self._worker = LiveWorker(
            phys_rect=phys_rect,
            ocr_engine=self._ocr,
            translator=self._translator,
            interval_ms=self._config.update_interval_ms,
            diff_threshold_pct=self._config.diff_threshold_pct,
        )
        self._worker.blocks_ready.connect(self._overlay.update_blocks)
        self._worker.worker_error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_error(self, err: str) -> None:
        logger.error("LiveWorker reported error: %s", err)

    def _stop_worker_and_overlay(self) -> None:
        self._live_active = False
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(2500)
            self._worker = None
        self._overlay.force_close()

    def stop_live_mode(self) -> None:
        if self._selecting:
            self._selecting = False
            self._selector.hide()
            self._show_main_window()
            return

        if not self._live_active:
            self._show_main_window()
            return

        self._stop_worker_and_overlay()
        self._show_main_window()

    def _show_main_window(self) -> None:
        self._main_window.showNormal()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def shutdown(self) -> None:
        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._stop_worker_and_overlay()
        self._unregister_hotkeys()
        if self._ocr_init_thread is not None and self._ocr_init_thread.isRunning():
            self._ocr_init_thread.wait(1500)


def main() -> int:
    _setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LiveScreenTranslator")
    app.setQuitOnLastWindowClosed(False)

    controller = AppController(app)

    original_close = controller._main_window.closeEvent

    def _on_main_close(event) -> None:
        controller.shutdown()
        original_close(event)
        app.quit()

    controller._main_window.closeEvent = _on_main_close  # type: ignore[method-assign]
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
'''


FILES["requirements.txt"] = r'''
PyQt6>=6.6.0
easyocr>=1.7.1
mss>=9.0.1
numpy>=1.24.0,<2.0.0
opencv-python-headless>=4.8.0
Pillow>=10.0.0
requests>=2.31.0
deep-translator>=1.11.4
'''


FILES["README.md"] = "\n".join([
    "# Live Screen Translator (Windows 11, EN -> RU)",
    "",
    "Настольное приложение для Windows 11, выполняющее Live-перевод английского текста",
    "с выбранной области экрана на русский язык прямо поверх оригинала.",
    "",
    "## Основные функции",
    "- Прозрачный кликабельный оверлей с защитой от самоперевода (WDA_EXCLUDEFROMCAPTURE).",
    "- Поддержка Per-Monitor DPI V2 (масштабирование Windows 125% / 150%).",
    "- Два движка перевода: LLM API (OpenRouter/DeepSeek) и Free Online (Google/MyMemory/DeepL).",
    "- Строгий выход из Live-режима только по заданному хоткею (по умолчанию Ctrl+Shift+X).",
    "- Модели EasyOCR хранятся в %APPDATA%\\LiveScreenTranslator\\models.",
    "",
    "## Локальный запуск (Python 3.11)",
    "1. pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu",
    "2. pip install -r requirements.txt",
    "3. python src/main.py",
]) + "\n"


def main() -> int:
    root = Path.cwd()
    created: list[str] = []

    for rel_path, content in FILES.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized = content.lstrip("\n")
        if rel_path.endswith(".py"):
            ast.parse(normalized, filename=rel_path)
        target.write_text(normalized, encoding="utf-8", newline="\n")
        created.append(rel_path)

    print("Live Screen Translator project generated successfully:")
    for item in created:
        print(f"  + {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
