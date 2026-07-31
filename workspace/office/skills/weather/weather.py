"""
MyClaw Weather Skill — 天气查询
数据源: Open-Meteo (免费，无需 API Key)
用法: python weather.py <城市名> [--days N] [--json]
"""
import sys, os, json
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import quote

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 天气代码 → emoji ────────────────────────────────────

WMO_CODES = {
    0:  ("晴天", "☀️"),
    1:  ("大部晴", "🌤️"),
    2:  ("多云", "⛅"),
    3:  ("阴天", "☁️"),
    45: ("雾", "🌫️"),
    48: ("霜雾", "🌫️"),
    51: ("小毛毛雨", "🌦️"),
    53: ("毛毛雨", "🌦️"),
    55: ("大毛毛雨", "🌧️"),
    56: ("冻毛毛雨", "🌨️"),
    57: ("大冻毛毛雨", "🌨️"),
    61: ("小雨", "🌧️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("冻雨", "🌨️"),
    67: ("大冻雨", "🌨️"),
    71: ("小雪", "❄️"),
    73: ("中雪", "❄️"),
    75: ("大雪", "❄️"),
    77: ("雪粒", "❄️"),
    80: ("阵雨", "⛈️"),
    81: ("大阵雨", "⛈️"),
    82: ("暴阵雨", "⛈️"),
    85: ("小阵雪", "🌨️"),
    86: ("大阵雪", "🌨️"),
    95: ("雷暴", "⚡"),
    96: ("雷暴+小冰雹", "⚡"),
    99: ("雷暴+大冰雹", "⚡"),
}


def geocode(city: str) -> dict:
    """城市名 → 坐标 (Open-Meteo Geocoding API)"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote(city)}&count=1&language=zh&format=json"
    req = Request(url, headers={"User-Agent": "MyClaw-Weather/1.0"})

    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = data.get("results")
    if not results:
        raise RuntimeError(f"未找到城市: {city}（请确认城市名拼写，支持中英文）")

    r = results[0]
    return {
        "name": r.get("name", city),
        "country": r.get("country", ""),
        "lat": r["latitude"],
        "lon": r["longitude"],
        "timezone": r.get("timezone", "UTC"),
    }


def get_weather(lat: float, lon: float, timezone: str, days: int = 3) -> dict:
    """获取天气数据 (Open-Meteo Weather API)"""
    params = (
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,cloud_cover,wind_speed_10m"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"precipitation_probability_max"
        f"&timezone={quote(timezone)}"
        f"&forecast_days={days}"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = Request(url, headers={"User-Agent": "MyClaw-Weather/1.0"})

    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_current(data: dict, city_info: dict) -> str:
    """格式化当前天气"""
    c = data.get("current", {})
    wmo = c.get("weather_code", 0)
    desc, emoji = WMO_CODES.get(wmo, ("未知", "❓"))

    lines = [
        f"{emoji} {city_info['name']} 当前天气",
        "━" * 40,
        f"  🌡️ 温度: {c.get('temperature_2m', '?')}°C (体感 {c.get('apparent_temperature', '?')}°C)",
        f"  💧 湿度: {c.get('relative_humidity_2m', '?')}%",
        f"  🌬️ 风速: {c.get('wind_speed_10m', '?')} km/h",
        f"  ☁️ 云量: {c.get('cloud_cover', '?')}%",
        f"  📊 天气: {desc}",
    ]
    return "\n".join(lines)


def format_daily(data: dict, days: int) -> str:
    """格式化天气预报"""
    daily = data.get("daily", {})
    if not daily:
        return ""

    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_probability_max", [])

    lines = [f"\n📅 未来 {min(days, len(dates))} 天预报"]

    for i in range(min(days, len(dates))):
        date = dates[i]
        wmo = codes[i] if i < len(codes) else 0
        desc, emoji = WMO_CODES.get(wmo, ("?", "❓"))
        hi = tmax[i] if i < len(tmax) else "?"
        lo = tmin[i] if i < len(tmin) else "?"
        rain = precip[i] if i < len(precip) else 0

        lines.append(f"  {date}: {emoji} {lo}~{hi}°C  降水 {rain}%")

    return "\n".join(lines)


def format_full(data: dict, city_info: dict, days: int) -> str:
    """完整输出"""
    parts = [
        format_current(data, city_info),
        format_daily(data, days),
        "",
        "━" * 40,
        f"📍 坐标: {city_info['lat']:.2f}°N, {city_info['lon']:.2f}°E"
        f" | 时区: {city_info['timezone']}",
        "数据来源: Open-Meteo (免费 API)",
    ]
    return "\n".join(parts)


# ── CLI ────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python weather.py <城市名> [--days N] [--json]")
        print("示例: python weather.py 杭州")
        print("      python weather.py Tokyo --days 5")
        print("      python weather.py London --json")
        sys.exit(1)

    city = args[0]
    days = 3
    output_json = False

    i = 1
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = min(max(int(args[i + 1]), 1), 7)
            i += 2
        elif args[i] == "--json":
            output_json = True
            i += 1
        else:
            i += 1

    try:
        city_info = geocode(city)
        data = get_weather(city_info["lat"], city_info["lon"],
                          city_info["timezone"], days)
    except URLError as e:
        print(f"❌ 网络错误: {e.reason}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        sys.exit(1)

    if output_json:
        output = {
            "city": city_info,
            "current": data.get("current", {}),
            "daily": data.get("daily", {}),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_full(data, city_info, days))


if __name__ == "__main__":
    main()
