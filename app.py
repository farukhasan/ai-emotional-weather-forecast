"""Should I take tomorrow off? (fast version, PhD student in Burnaby)."""
import html
import json

import requests
import streamlit as st
from google import genai
from google.genai import types

# Flash-Lite with thinking switched off is the fastest option on the free tier.
MODEL = "gemini-2.5-flash-lite"
LAT, LON, CITY = 49.2488, -122.9805, "Burnaby"

TYPES = {
    "full_day_leave": ("Take the day off", "#c0392b"),
    "half_day_leave": ("Take a half day / finish early", "#d68910"),
    "work_with_care": ("Work, but go easy on yourself", "#2e86c1"),
    "work_normally": ("Work as normal", "#1e8449"),
}
OFF = ("full_day_leave", "half_day_leave")
ICONS = {
    "rain": "🌧️", "snow": "❄️", "sleet": "🌨️", "wind": "💨", "fog": "🌫️",
    "cloudy": "☁️", "partly-cloudy-day": "⛅", "partly-cloudy-night": "⛅",
    "clear-day": "☀️", "clear-night": "🌙",
}
SYMPTOM_PENALTY = {
    "None": 0, "Mild tension/headache": 5,
    "Moderate discomfort": 12, "Severe symptoms": 25,
}

st.set_page_config(page_title="Should I Take Tomorrow Off?", page_icon="🌅", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend+Deca:wght@400;500;600&display=swap');
.stApp {background:white; font-family:'Lexend Deca',sans-serif;}
label, [data-testid="stWidgetLabel"] p {color:#1a1a1a !important; font-weight:500 !important;}
.ttl {font-size:2.2rem; font-weight:600; text-align:center; color:#1a1a1a; margin:0;}
.sub {text-align:center; color:#666; margin:.3rem 0 1.5rem;}
.card {background:#f8f9fa; border:1px solid #dee2e6; border-radius:12px; padding:1.1rem; margin:.8rem 0; color:#1a1a1a; text-align:center;}
.hero {border-radius:16px; padding:1.6rem; color:#fff; text-align:center; margin:1.2rem 0;}
.hero-t {font-size:1.6rem; font-weight:600; color:#fff;}
.hero-s {margin-top:.6rem; color:#fff; opacity:.92;}
.hero-c {margin-top:.6rem; color:#fff; opacity:.8; font-size:.85rem;}
.hd {color:#1a1a1a; font-weight:600; margin:.4rem 0 0;}
.do, .dont {border-radius:8px; padding:.8rem 1rem; margin:.4rem 0; color:#1a1a1a; font-weight:500;}
.do {background:#d4edda; border-left:3px solid #28a745;}
.dont {background:#f8d7da; border-left:3px solid #dc3545;}
.foot {text-align:center; color:#666; font-size:.85rem; padding:1rem;}
</style>
""", unsafe_allow_html=True)

esc = html.escape


# ---------- Gemini client (created once per server, not per rerun) ----------
@st.cache_resource
def get_client():
    try:
        return genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=20_000),  # ms; fail fast to fallback
        )
    except Exception:
        return None


# ---------- Weather (cached 30 min; failures are not cached) ----------
@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_weather(key):
    r = requests.get(
        f"https://api.pirateweather.net/forecast/{key}/{LAT},{LON}",
        params={"units": "si", "exclude": "minutely,hourly,alerts,currently"},
        timeout=(2, 3),
    )
    r.raise_for_status()
    d = r.json()["daily"]["data"][1]  # index 0 = today, 1 = tomorrow
    return {
        "high": round(d.get("temperatureHigh", d.get("temperatureMax", 0))),
        "low": round(d.get("temperatureLow", d.get("temperatureMin", 0))),
        "summary": d.get("summary", ""),
        "rain": round(d.get("precipProbability", 0) * 100),
        "icon": ICONS.get(d.get("icon"), "🌤️"),
    }


def get_weather():
    try:
        key = st.secrets.get("PIRATE_WEATHER_API_KEY", "")
        return _fetch_weather(key) if key else None
    except Exception:
        return None


# ---------- Analysis: ONE Gemini call returns the verdict and the email ----------
def build_prompt(d, w):
    wx = f"{w['high']}/{w['low']}°C, {w['summary']}, {w['rain']}% precipitation" if w else "unknown"
    name = d["name"] or "[Your Name]"
    return f"""Advise a PhD student on whether to take tomorrow off. Practical, kind, concise. Not medical advice.

State: mood={d['mood']}; energy={d['energy']}/10; sleep={d['sleep']}/10; workload pressure={d['work']}/10; personal stress={d['stress']}/10; symptoms={d['symptoms']}; last real day off={d['last_break']}; tomorrow={d['tomorrow']}; support={d['support']}; weather tomorrow in {CITY}: {wx}.

Score 0-100 (80+ work normally, 60-79 work with care, 40-59 half day, 20-39 full day, <20 needs real rest). Fixed deadlines or critical commitments tomorrow push toward working; a long gap since the last day off pushes toward resting.

Return ONLY JSON:
{{"wellness_score":int,"leave_type":"full_day_leave|half_day_leave|work_with_care|work_normally","confidence":int,"decision_summary":"2 sentences","do":["3 short items for the chosen path"],"avoid":["3 short items"],"warning_signs":["2 items"],"recovery_estimate":"short phrase","leave_mail":"..."}}

leave_mail: if leave_type is full_day_leave or half_day_leave, write a 2-3 sentence first-person email to my {d['recipient']}. First line 'Subject: Absence tomorrow'. Give only this reason: {d['reason']}. Offer to catch up on anything missed. End with 'Best regards,' and then {name} on the next line. Otherwise use an empty string."""


def ask_gemini(d, w):
    resp = get_client().models.generate_content(
        model=MODEL,
        contents=build_prompt(d, w),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=800,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return json.loads(resp.text)


def fallback_mail(d, half):
    when = "the rest of tomorrow" if half else "tomorrow"
    return (
        "Subject: Absence tomorrow\n\n"
        f"Hi,\n\nI need to take {when} off ({d['reason'].lower()}). "
        "I'll catch up on anything I miss and can be reached if something urgent comes up.\n\n"
        f"Best regards,\n{d['name'] or '[Your Name]'}"
    )


def fallback(d):
    score = (
        100
        - (d["work"] + d["stress"]) / 2 * 5
        - (10 - d["energy"]) * 4
        - (10 - d["sleep"]) * 3
        - SYMPTOM_PENALTY.get(d["symptoms"], 0)
    )
    if d["tomorrow"].startswith(("Fixed", "Critical")):
        score += 10
    score = max(5, min(100, int(score)))
    if score < 25:
        lt, why = "full_day_leave", "Stress is high and energy is low. A full rest day is the safer call."
    elif score < 45:
        lt, why = "half_day_leave", "You're running low. A half day or an early finish would help."
    elif score < 65:
        lt, why = "work_with_care", "You can work tomorrow, but protect your energy."
    else:
        lt, why = "work_normally", "You look in good shape to work tomorrow."
    return {
        "wellness_score": score, "leave_type": lt, "confidence": 70, "decision_summary": why,
        "do": ["Take a short break every hour", "Do the one or two essential tasks first", "Eat properly and stay hydrated"],
        "avoid": ["Extra commitments or overtime", "Perfectionism on minor tasks", "Skipping lunch"],
        "warning_signs": ["Can't focus at all", "Symptoms that keep getting worse"],
        "recovery_estimate": "1-3 days with proper rest",
    }


def normalise(r, d):
    lt = r.get("leave_type")
    lt = lt if lt in TYPES else "work_with_care"
    out = {
        "leave_type": lt,
        "wellness_score": max(0, min(100, int(r.get("wellness_score", 50)))),
        "confidence": max(0, min(100, int(r.get("confidence", 70)))),
        "decision_summary": str(r.get("decision_summary", "")),
        "recovery_estimate": str(r.get("recovery_estimate", "")),
    }
    for k in ("do", "avoid", "warning_signs"):
        out[k] = [str(x) for x in (r.get(k) or [])][:4]
    mail = str(r.get("leave_mail") or "").strip()
    if lt in OFF and not mail:
        mail = fallback_mail(d, half=(lt == "half_day_leave"))
    out["leave_mail"] = mail if lt in OFF else ""
    return out


def analyze(d, w):
    try:
        raw = ask_gemini(d, w)
    except Exception as e:
        msg = str(e)
        if "429" in msg or "quota" in msg.lower():
            st.info("Free-tier rate limit hit, so this is a quick offline estimate. Try again in a minute.")
        else:
            st.warning(f"AI call failed ({msg[:120]}). Showing an offline estimate.")
        raw = fallback(d)
    return normalise(raw, d)


# ---------- UI ----------
def render_weather(w):
    if w:
        body = (
            f'<div style="font-size:2rem">{w["icon"]}</div>'
            f'<b>{w["high"]}°C / {w["low"]}°C</b><br>{esc(w["summary"])} · {w["rain"]}% chance of precipitation'
        )
    else:
        body = "Forecast unavailable"
    st.markdown(f'<div class="card"><b>Tomorrow in {CITY}</b><br>{body}</div>', unsafe_allow_html=True)


def render_result(r):
    label, color = TYPES[r["leave_type"]]
    st.markdown(
        f'<div class="hero" style="background:{color}">'
        f'<div class="hero-t">{label}</div>'
        f'<div class="hero-s">{esc(r["decision_summary"])}</div>'
        f'<div class="hero-c">Wellness score {r["wellness_score"]}/100 · Confidence {r["confidence"]}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    off = r["leave_type"] in OFF
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="hd">{"Recovery activities" if off else "If you work tomorrow"}</div>', unsafe_allow_html=True)
        st.markdown("".join(f'<div class="do">{esc(x)}</div>' for x in r["do"]), unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="hd">{"Avoid during your day off" if off else "Avoid while working"}</div>', unsafe_allow_html=True)
        st.markdown("".join(f'<div class="dont">{esc(x)}</div>' for x in r["avoid"]), unsafe_allow_html=True)

    if r["warning_signs"]:
        st.markdown(
            f'<div class="card"><b>Watch for:</b> {esc(" • ".join(r["warning_signs"]))}</div>',
            unsafe_allow_html=True,
        )
    if r["recovery_estimate"]:
        st.markdown(
            f'<div class="card"><b>Expected recovery:</b> {esc(r["recovery_estimate"])}</div>',
            unsafe_allow_html=True,
        )
    if r["leave_mail"]:
        st.markdown('<div class="hd">📧 Draft email (use the copy icon on the box)</div>', unsafe_allow_html=True)
        st.code(r["leave_mail"], language=None)


def main():
    st.markdown('<div class="ttl">Should I Take Tomorrow Off?</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">A quick check-in for your work-life balance</div>', unsafe_allow_html=True)

    if get_client() is None:
        st.error("🔑 Please add GEMINI_API_KEY to Streamlit secrets")
        st.stop()

    weather = get_weather()
    render_weather(weather)

    # A form means moving a slider no longer reruns the whole script.
    with st.form("checkin"):
        st.markdown('<div class="hd">How are you feeling today?</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            mood = st.selectbox("Overall mood", ["Excellent", "Good", "Okay", "Struggling", "Overwhelmed", "Exhausted"])
            energy = st.slider("Energy level", 1, 10, 5, help="1 = drained, 10 = energized")
            sleep = st.slider("Last night's sleep", 1, 10, 6, help="1 = terrible, 10 = perfect")
            last_break = st.selectbox(
                "Last proper day off",
                ["Never", "6+ months ago", "2-6 months ago", "1-2 months ago", "Within last month"],
            )
        with c2:
            work = st.slider("Workload pressure (research, TA, courses)", 1, 10, 5, help="1 = light, 10 = overwhelming")
            stress = st.slider("Personal life stress", 1, 10, 4, help="1 = peaceful, 10 = major issues")
            symptoms = st.selectbox(
                "Physical symptoms",
                ["None", "Mild tension/headache", "Moderate discomfort", "Severe symptoms"],
            )
            tomorrow = st.selectbox(
                "Tomorrow's commitments",
                [
                    "Flexible: my own research time",
                    "Some meetings or TA hours",
                    "Fixed deadline (grading, assignment, submission)",
                    "Critical: exam, presentation or supervisor deadline",
                ],
            )
        support = st.selectbox(
            "Support around you (supervisor, lab, friends, family)",
            ["Strong", "Good", "Limited", "Weak, feeling isolated"],
        )
        with st.expander("Email settings (used only if time off is recommended)"):
            recipient = st.selectbox("Email to", ["supervisor", "course instructor", "TA coordinator", "research group"])
            reason = st.selectbox("Reason to give", ["Not feeling well", "Need a rest day", "Personal matter"])
            name = st.text_input("Your name (for the sign-off)")
        go = st.form_submit_button("Get my recommendation", type="primary", use_container_width=True)

    if go:
        data = {
            "mood": mood, "energy": energy, "sleep": sleep, "work": work, "stress": stress,
            "symptoms": symptoms, "last_break": last_break, "tomorrow": tomorrow, "support": support,
            "recipient": recipient, "reason": reason, "name": name.strip(),
        }
        with st.spinner("Thinking…"):
            st.session_state.result = analyze(data, weather)

    if st.session_state.get("result"):
        render_result(st.session_state.result)

    st.markdown("---")
    st.markdown(
        '<div class="foot"><b>Your wellbeing matters.</b> This is guidance, not medical advice.<br>'
        "If you're struggling, SFU Student Health &amp; Counselling can help, and in Canada you can call or text 9-8-8 any time.</div>",
        unsafe_allow_html=True,
    )


main()
