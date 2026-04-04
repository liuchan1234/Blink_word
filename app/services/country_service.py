"""
Blink.World — Country Service
Handles free-text country input in any language, normalizes to a standard name,
and maps to the correct flag emoji.

Flow:
1. User types anything ("中国", "china", "deutschland", "日本", "brasil", "🇫🇷")
2. We try local lookup first (fast, covers 95% of cases)
3. If no match, fall back to AI detection
4. Return standardized {name_zh, name_en, flag_emoji, code}
"""

import logging
import re
from typing import NamedTuple

from app.ai_client import get_ai_client

logger = logging.getLogger(__name__)


class CountryInfo(NamedTuple):
    code: str       # ISO 3166-1 alpha-2, e.g. "CN"
    name_zh: str    # 中文名
    name_en: str    # English name
    flag: str       # Flag emoji


# ── Comprehensive country database ──
# ISO code → (name_zh, name_en, flag)
_COUNTRIES: dict[str, tuple[str, str, str]] = {
    "CN": ("中国", "China", "🇨🇳"),
    "US": ("美国", "United States", "🇺🇸"),
    "JP": ("日本", "Japan", "🇯🇵"),
    "KR": ("韩国", "South Korea", "🇰🇷"),
    "GB": ("英国", "United Kingdom", "🇬🇧"),
    "RU": ("俄罗斯", "Russia", "🇷🇺"),
    "DE": ("德国", "Germany", "🇩🇪"),
    "FR": ("法国", "France", "🇫🇷"),
    "BR": ("巴西", "Brazil", "🇧🇷"),
    "IN": ("印度", "India", "🇮🇳"),
    "SG": ("新加坡", "Singapore", "🇸🇬"),
    "MY": ("马来西亚", "Malaysia", "🇲🇾"),
    "TH": ("泰国", "Thailand", "🇹🇭"),
    "VN": ("越南", "Vietnam", "🇻🇳"),
    "PH": ("菲律宾", "Philippines", "🇵🇭"),
    "ID": ("印尼", "Indonesia", "🇮🇩"),
    "CA": ("加拿大", "Canada", "🇨🇦"),
    "AU": ("澳大利亚", "Australia", "🇦🇺"),
    "NZ": ("新西兰", "New Zealand", "🇳🇿"),
    "ES": ("西班牙", "Spain", "🇪🇸"),
    "IT": ("意大利", "Italy", "🇮🇹"),
    "NL": ("荷兰", "Netherlands", "🇳🇱"),
    "SE": ("瑞典", "Sweden", "🇸🇪"),
    "NO": ("挪威", "Norway", "🇳🇴"),
    "DK": ("丹麦", "Denmark", "🇩🇰"),
    "FI": ("芬兰", "Finland", "🇫🇮"),
    "CH": ("瑞士", "Switzerland", "🇨🇭"),
    "AT": ("奥地利", "Austria", "🇦🇹"),
    "BE": ("比利时", "Belgium", "🇧🇪"),
    "PT": ("葡萄牙", "Portugal", "🇵🇹"),
    "PL": ("波兰", "Poland", "🇵🇱"),
    "CZ": ("捷克", "Czech Republic", "🇨🇿"),
    "GR": ("希腊", "Greece", "🇬🇷"),
    "TR": ("土耳其", "Turkey", "🇹🇷"),
    "MX": ("墨西哥", "Mexico", "🇲🇽"),
    "AR": ("阿根廷", "Argentina", "🇦🇷"),
    "CL": ("智利", "Chile", "🇨🇱"),
    "CO": ("哥伦比亚", "Colombia", "🇨🇴"),
    "PE": ("秘鲁", "Peru", "🇵🇪"),
    "EG": ("埃及", "Egypt", "🇪🇬"),
    "ZA": ("南非", "South Africa", "🇿🇦"),
    "NG": ("尼日利亚", "Nigeria", "🇳🇬"),
    "KE": ("肯尼亚", "Kenya", "🇰🇪"),
    "SA": ("沙特阿拉伯", "Saudi Arabia", "🇸🇦"),
    "AE": ("阿联酋", "UAE", "🇦🇪"),
    "IL": ("以色列", "Israel", "🇮🇱"),
    "PK": ("巴基斯坦", "Pakistan", "🇵🇰"),
    "BD": ("孟加拉", "Bangladesh", "🇧🇩"),
    "UA": ("乌克兰", "Ukraine", "🇺🇦"),
    "RO": ("罗马尼亚", "Romania", "🇷🇴"),
    "HU": ("匈牙利", "Hungary", "🇭🇺"),
    "IE": ("爱尔兰", "Ireland", "🇮🇪"),
    "TW": ("台湾", "Taiwan", "🇹🇼"),
    "HK": ("香港", "Hong Kong", "🇭🇰"),
    "MO": ("澳门", "Macau", "🇲🇴"),
    "MM": ("缅甸", "Myanmar", "🇲🇲"),
    "KH": ("柬埔寨", "Cambodia", "🇰🇭"),
    "LA": ("老挝", "Laos", "🇱🇦"),
    "NP": ("尼泊尔", "Nepal", "🇳🇵"),
    "LK": ("斯里兰卡", "Sri Lanka", "🇱🇰"),
    "KZ": ("哈萨克斯坦", "Kazakhstan", "🇰🇿"),
    "UZ": ("乌兹别克斯坦", "Uzbekistan", "🇺🇿"),
    "IR": ("伊朗", "Iran", "🇮🇷"),
    "IQ": ("伊拉克", "Iraq", "🇮🇶"),
}

# ── Build reverse lookup index (lowercase aliases → ISO code) ──
_ALIAS_INDEX: dict[str, str] = {}


def _build_index():
    """Build a comprehensive alias → ISO code lookup."""
    for code, (zh, en, flag) in _COUNTRIES.items():
        # Standard names
        _ALIAS_INDEX[zh.lower()] = code
        _ALIAS_INDEX[en.lower()] = code
        _ALIAS_INDEX[code.lower()] = code

        # Flag emoji → code
        _ALIAS_INDEX[flag] = code

    # ── Extra aliases (common names in various languages) ──
    extras = {
        # Chinese variants
        "美国": "US", "美利坚": "US", "英国": "GB", "英格兰": "GB",
        "韩国": "KR", "南韩": "KR", "朝鲜": "KP",
        "日本": "JP", "法国": "FR", "德国": "DE",
        "俄罗斯": "RU", "俄国": "RU",
        "新加坡": "SG", "狮城": "SG",
        "马来西亚": "MY", "大马": "MY",
        "印度尼西亚": "ID", "印尼": "ID",
        "澳洲": "AU", "澳大利亚": "AU",
        "纽西兰": "NZ", "新西兰": "NZ",
        "阿联酋": "AE", "迪拜": "AE",
        "中国大陆": "CN", "大陆": "CN", "内地": "CN",
        "台灣": "TW", "台湾": "TW",

        # English variants
        "usa": "US", "u.s.": "US", "u.s.a.": "US", "america": "US",
        "united states": "US", "united states of america": "US",
        "uk": "GB", "england": "GB", "britain": "GB", "great britain": "GB",
        "united kingdom": "GB",
        "south korea": "KR", "korea": "KR", "rok": "KR",
        "uae": "AE", "dubai": "AE",
        "russia": "RU",
        "czech republic": "CZ", "czechia": "CZ",

        # Native language names
        "deutschland": "DE", "allemagne": "DE",
        "france": "FR", "frankreich": "FR",
        "italia": "IT", "italien": "IT",
        "espana": "ES", "españa": "ES", "spanien": "ES",
        "brasil": "BR", "brasilien": "BR",
        "portugal": "PT",
        "nederland": "NL", "niederlande": "NL", "holland": "NL",
        "sverige": "SE", "schweden": "SE",
        "norge": "NO", "norwegen": "NO",
        "danmark": "DK", "danemark": "DK",
        "suomi": "FI", "finnland": "FI",
        "schweiz": "CH", "suisse": "CH", "svizzera": "CH",
        "osterreich": "AT", "österreich": "AT", "autriche": "AT",
        "belgique": "BE", "belgien": "BE",
        "polska": "PL", "polen": "PL", "pologne": "PL",
        "turkiye": "TR", "turquie": "TR", "turkei": "TR", "türkei": "TR",
        "mexico": "MX", "mexiko": "MX", "mexique": "MX",
        "россия": "RU", "росія": "UA",
        "україна": "UA", "украина": "UA",
        "ایران": "IR",
        "مصر": "EG",
        "السعودية": "SA",
        "الإمارات": "AE",
        "ไทย": "TH",
        "việt nam": "VN",
        "philippines": "PH", "pilipinas": "PH",
        "indonesia": "ID",
        "malaysia": "MY",
        "singapore": "SG",
        "대한민국": "KR", "한국": "KR",
        "日本国": "JP", "にほん": "JP", "にっぽん": "JP",
        "中华人民共和国": "CN", "中國": "CN",
    }
    for alias, code in extras.items():
        _ALIAS_INDEX[alias.lower()] = code


_build_index()


# ══════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════

def lookup_country(text: str) -> CountryInfo | None:
    """
    Try to match user input to a known country. Fast local lookup.
    Returns CountryInfo or None if no match.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        return None

    # Direct lookup
    code = _ALIAS_INDEX.get(cleaned)
    if code and code in _COUNTRIES:
        zh, en, flag = _COUNTRIES[code]
        return CountryInfo(code=code, name_zh=zh, name_en=en, flag=flag)

    # Try stripping common prefixes/suffixes
    for prefix in ["the ", "republic of ", "kingdom of "]:
        if cleaned.startswith(prefix):
            code = _ALIAS_INDEX.get(cleaned[len(prefix):])
            if code and code in _COUNTRIES:
                zh, en, flag = _COUNTRIES[code]
                return CountryInfo(code=code, name_zh=zh, name_en=en, flag=flag)

    # Try fuzzy: check if input is a substring of any alias
    for alias, code in _ALIAS_INDEX.items():
        if len(cleaned) >= 3 and (cleaned in alias or alias in cleaned):
            if code in _COUNTRIES:
                zh, en, flag = _COUNTRIES[code]
                return CountryInfo(code=code, name_zh=zh, name_en=en, flag=flag)

    return None


async def detect_country(text: str) -> CountryInfo:
    """
    Detect country from free-text input. Tries local lookup first, then AI.
    Always returns a result (fallback to storing raw text with globe emoji).
    """
    # 1. Local fast lookup
    result = lookup_country(text)
    if result:
        return result

    # 2. AI detection
    result = await _ai_detect_country(text)
    if result:
        return result

    # 3. Fallback: store as-is with globe emoji
    cleaned = text.strip()[:64]
    return CountryInfo(code="XX", name_zh=cleaned, name_en=cleaned, flag="🌍")


async def _ai_detect_country(text: str) -> CountryInfo | None:
    """Use AI to detect country from ambiguous text."""
    from pydantic import BaseModel

    class CountryDetection(BaseModel):
        country_code: str
        name_zh: str
        name_en: str

    ai = get_ai_client()
    result = await ai.generate_json(
        system=(
            "You are a country name detector. The user has typed a country name in any language. "
            "Identify the country and return its ISO 3166-1 alpha-2 code, Chinese name, and English name. "
            'Return JSON: {"country_code": "XX", "name_zh": "...", "name_en": "..."}'
        ),
        prompt=f'What country is this: "{text}"',
        schema=CountryDetection,
        max_tokens=128,
        timeout_s=10.0,
        temperature=0.1,
    )

    if not result:
        return None

    code = result["country_code"].upper()

    # Check if we have this code in our database
    if code in _COUNTRIES:
        zh, en, flag = _COUNTRIES[code]
        return CountryInfo(code=code, name_zh=zh, name_en=en, flag=flag)

    # AI found a country we don't have in our list — use AI names + generate flag
    flag = _code_to_flag(code)
    return CountryInfo(
        code=code,
        name_zh=result["name_zh"],
        name_en=result["name_en"],
        flag=flag,
    )


def get_flag(country_name: str) -> str:
    """Get flag emoji for a country name. Returns 🌍 if not found."""
    result = lookup_country(country_name)
    return result.flag if result else "🌍"


def get_country_display(country_name: str, lang: str = "zh") -> str:
    """Get display string with flag for a country. e.g. '🇨🇳 中国'"""
    if not country_name:
        return ""
    result = lookup_country(country_name)
    if result:
        name = result.name_zh if lang == "zh" else result.name_en
        return f"{result.flag} {name}"
    return f"🌍 {country_name}"


def _code_to_flag(code: str) -> str:
    """Convert ISO 3166-1 alpha-2 code to flag emoji."""
    if len(code) != 2:
        return "🌍"
    try:
        return chr(0x1F1E6 + ord(code[0]) - ord("A")) + chr(0x1F1E6 + ord(code[1]) - ord("A"))
    except (ValueError, TypeError):
        return "🌍"
