import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import json
import time

# Page config
st.set_page_config(
    page_title="Should I Take Leave Tomorrow?",
    page_icon="🌅",
    layout="centered"
)

# Simple CSS with dark text on white background
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend+Deca:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background-color: white;
        font-family: 'Lexend Deca', sans-serif;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 600;
        text-align: center;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
        font-family: 'Lexend Deca', sans-serif;
    }
    
    .subtitle {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 3rem;
        font-family: 'Lexend Deca', sans-serif;
    }
    
    .decision-card {
        background: #007aff;
        border-radius: 16px;
        padding: 2rem;
        color: white;
        text-align: center;
        margin: 2rem 0;
        box-shadow: 0 4px 20px rgba(0, 122, 255, 0.15);
    }
    
    .recommendation {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #1a1a1a;
        border: 1px solid #dee2e6;
        font-weight: 500;
    }
    
    .do-item {
        background: #d4edda;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        color: #1a1a1a;
        font-weight: 500;
        border-left: 3px solid #28a745;
    }
    
    .dont-item {
        background: #f8d7da;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        color: #1a1a1a;
        font-weight: 500;
        border-left: 3px solid #dc3545;
    }
    
    .weather-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #1a1a1a;
        text-align: center;
        border: 1px solid #dee2e6;
    }
    
    .stButton > button {
        width: 100%;
        background: #007aff;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 1rem;
        font-weight: 600;
        font-size: 1rem;
        margin-top: 1.5rem;
        font-family: 'Lexend Deca', sans-serif;
    }
    
    /* Fix for input labels to be black */
    .stSelectbox label,
    .stSlider label,
    .stSelectbox > div > label,
    .stSlider > div > label,
    label[data-testid="stWidgetLabel"] {
        color: #1a1a1a !important;
        font-family: 'Lexend Deca', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Additional targeting for labels */
    .stSelectbox > label,
    .stSlider > label {
        color: #1a1a1a !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'assessments' not in st.session_state:
    st.session_state.assessments = []
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'generated_leave_mail' not in st.session_state:
    st.session_state.generated_leave_mail = None

# API Configuration
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    WEATHER_API_KEY = st.secrets.get("PIRATE_WEATHER_API_KEY", "")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.8-flash")
except:
    st.error("🔑 Please add GEMINI_API_KEY to Streamlit secrets")
    st.stop()

def get_weather_tomorrow():
    """Get tomorrow's weather forecast"""
    try:
        if WEATHER_API_KEY:
            url = f"https://api.pirateweather.net/forecast/{WEATHER_API_KEY}/49.2488,-122.9805"
            response = requests.get(url, timeout=3)
            data = response.json()
            tomorrow = data["daily"]["data"][1] if "daily" in data else data["currently"]
            return {
                "temp_high": round((tomorrow.get("temperatureHigh", 85) - 32) * 5/9),
                "temp_low": round((tomorrow.get("temperatureLow", 75) - 32) * 5/9),
                "condition": tomorrow.get("summary", "Partly cloudy"),
                "rain_chance": round(tomorrow.get("precipProbability", 0) * 100)
            }
    except:
        pass
    
    return {
        "temp_high": 30,
        "temp_low": 24,
        "condition": "Partly cloudy",
        "rain_chance": 20
    }

def generate_leave_mail():
    """Generate a concise, first-person leave mail with a personal or access-related reason."""

    # Personal medical reasons (first-person only)
    medical_reasons = [
        "acute dysentery",
        "severe migraine",
        "high fever",
        "acute food poisoning",
        "debilitating headache"
    ]

    # Non-medical personal access issues near home
    access_reasons = [
        "a blockade near my house due to a student movement",
        "a political demonstration blocking the roads in my neighborhood",
        "major road construction in front of my house causing access issues",
        "urgent utility maintenance in my building causing disruptions"
    ]

    # Pick one reason at random each time
    import random
    all_reasons = medical_reasons + access_reasons
    chosen_reason = random.choice(all_reasons)

    prompt = f"""
Generate a professional, concise leave application email for one day of leave tomorrow.
Use first-person and the following single reason: {chosen_reason}.

Requirements:
- 2–3 sentences max
- Subject line must be: "Subject: Leave Application for Tomorrow"
- Keep the tone polite and professional
- Do not mention family members; it is my personal situation
- Do not add any text outside the email
"""

    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        # Ensure 'Best regards' is present
        if text:
            if "best regards".lower() not in text.lower():
                # Add 'Best regards' before [Your Name] or at the end
                if "[Your Name]" in text:
                    text = text.replace("[Your Name]", "Best regards,\n[Your Name]")
                else:
                    text = text.strip() + "\n\nBest regards,\n[Your Name]"
            return text
        else:
            return f"Subject: Leave Application for Tomorrow\n\nDear Manager,\n\nI would like to request leave for tomorrow due to {chosen_reason}. I will ensure any urgent tasks are handed over and remain reachable for critical matters if needed.\n\nThank you for your understanding.\n\nBest regards,\n[Your Name]"
    except Exception:
        # Fallback email (deterministic, still varies via chosen_reason)
        return f"""Subject: Leave Application for Tomorrow

Dear Manager,

I would like to request leave for tomorrow due to {chosen_reason}. I will ensure urgent items are handed over today and remain reachable for any critical matters if needed.

Thank you for your understanding.

Best regards,
[Your Name]"""

def analyze_leave_decision(data, weather):
    """Enhanced AI analysis for leave recommendation"""
    
    prompt = f"""You are an intelligent work-life balance advisor. Analyze if this person should take leave tomorrow based on their mental state, workload, and external factors.

CURRENT STATE:
- Overall feeling: {data['mood']}
- Energy level: {data['energy']}/10
- Sleep quality: {data['sleep']}/10
- Work pressure: {data['work_pressure']}/10
- Personal life stress: {data['personal_stress']}/10
- Physical symptoms: {data['physical_symptoms']}
- Last break taken: {data['last_break']}
- Tomorrow's work importance: {data['tomorrow_importance']}
- Support system: {data['support']}
- Leave balance remaining: {data['leave_balance']}

WEATHER TOMORROW: {weather['temp_high']}°C/{weather['temp_low']}°C, {weather['condition']}, {weather['rain_chance']}% rain chance

DECISION FRAMEWORK:
- Full Day Leave: For burnout, severe stress, or mental health crisis
- Half Day/Early Leave: For moderate stress with manageable work
- Work Normally: For good mental state with support strategies
- Consider weather impact on mood and recovery opportunities
- Consider leave balance - if low, be more conservative

Respond in this EXACT JSON format (ensure valid JSON):
{{
    "wellness_score": 45,
    "leave_type": "full_day_leave",
    "confidence": 82,
    "main_reason": "Primary reason for recommendation",
    "decision_summary": "Brief 2-sentence explanation of the decision",
    "work_activities": ["3 things to do if working"],
    "work_avoid": ["3 things to avoid if working"],
    "leave_activities": ["4 recovery activities for leave day"],
    "leave_avoid": ["3 things to avoid during leave"],
    "warning_signs": ["signs requiring immediate attention"],
    "recovery_estimate": "Expected recovery timeframe"
}}

Leave types: "full_day_leave", "half_day_leave", "work_with_care", "work_normally"

SCORING GUIDE:
- 80-100: Excellent state, work normally
- 60-79: Good state, minor support needed
- 40-59: Moderate stress, consider half day
- 20-39: High stress, likely needs full day
- 0-19: Crisis level, definitely needs leave

Weather considerations:
- Rainy/gloomy: May worsen mood, indoor recovery activities
- Sunny/pleasant: Good for outdoor recovery, mood boost
- Extreme weather: Affects commute stress and recovery options

Leave balance considerations:
- High balance (>15 days): More flexible with recommendations
- Medium balance (5-15 days): Moderate recommendations
- Low balance (<5 days): Conservative recommendations"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up the response text
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(response_text)
        
        # Validate required fields
        required_fields = ['wellness_score', 'leave_type', 'confidence', 'main_reason', 'decision_summary']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        return result
        
    except Exception as e:
        error_text = str(e)
        if '429' in error_text or 'quota' in error_text.lower():
            st.info("Rate limit reached for AI analysis – using fallback recommendation. Please try again later.")
        else:
            st.warning(f"AI analysis failed, using fallback logic: {error_text}")
        
        # Enhanced fallback logic
        stress_factor = (data['work_pressure'] + data['personal_stress']) / 2
        energy_factor = data['energy']
        sleep_factor = data['sleep']
        
        # Parse leave balance
        leave_balance_text = data['leave_balance']
        if '20+' in leave_balance_text:
            leave_days = 20
        elif '15-20' in leave_balance_text:
            leave_days = 15
        elif '10-15' in leave_balance_text:
            leave_days = 10
        elif '5-10' in leave_balance_text:
            leave_days = 5
        else:
            leave_days = 2
        
        # Calculate wellness score with leave balance consideration
        wellness = 100 - (stress_factor * 10) - ((10 - energy_factor) * 8) - ((10 - sleep_factor) * 6)
        
        # Adjust based on leave balance
        if leave_days < 5:
            wellness += 10  # More conservative if low leave balance
        elif leave_days > 15:
            wellness -= 5   # More flexible if high leave balance
        
        wellness = max(5, min(100, int(wellness)))
        
        # Decision logic based on multiple factors
        if wellness < 25 or (stress_factor > 8 and energy_factor < 3):
            leave_type = "full_day_leave"
            decision = "Your stress levels are critically high and energy is depleted. A full day of rest is essential to prevent burnout."
        elif wellness < 45 or (stress_factor > 6 and sleep_factor < 5):
            leave_type = "half_day_leave"
            decision = "Moderate stress levels suggest you need some recovery time. Consider taking half day or leaving early."
        elif wellness < 65:
            leave_type = "work_with_care"
            decision = "You can work tomorrow but need to be very careful with your energy and stress management."
        else:
            leave_type = "work_normally"
            decision = "You're in good shape to work tomorrow. Focus on maintaining your current positive state."
        
        return {
            "wellness_score": wellness,
            "leave_type": leave_type,
            "confidence": 75,
            "main_reason": f"Stress level {stress_factor:.1f}/10, Energy {energy_factor}/10, Leave balance: {leave_days} days",
            "decision_summary": decision,
            "work_activities": ["Take regular breaks every hour", "Prioritize only essential tasks", "Stay hydrated and eat well"],
            "work_avoid": ["Overtime or extra commitments", "Perfectionism on minor tasks", "Skipping lunch break"],
            "leave_activities": ["Sleep until naturally awake", "Light exercise or walk", "Do something you enjoy", "Connect with supportive people"],
            "leave_avoid": ["Checking work emails", "Intensive physical activities", "Making major decisions"],
            "warning_signs": ["Panic attacks", "Complete inability to focus", "Persistent physical symptoms"],
            "recovery_estimate": "1-3 days with proper rest"
        }

def render_analysis_ui(analysis, leave_mail):
    # Display results
    leave_type_map = {
        "full_day_leave": ("Take Full Day Off", "#e74c3c"),
        "half_day_leave": ("Take Half Day / Leave Early", "#f39c12"),
        "work_with_care": ("Work With Extra Self-Care", "#f1c40f"),
        "work_normally": ("Work Normally", "#27ae60")
    }
    decision_text, decision_color = leave_type_map.get(analysis['leave_type'], ("Work With Care", "#007aff"))

    # Decision card with inline styles
    st.markdown(f"""
    <div style="background: #007aff; border-radius: 16px; padding: 2rem; color: white; text-align: center; margin: 2rem 0; box-shadow: 0 4px 20px rgba(0, 122, 255, 0.15); font-family: Lexend Deca, sans-serif;">
        <h2 style="margin: 0; font-weight: 600; color: white; font-family: Lexend Deca, sans-serif;">{decision_text}</h2>
        <p style="font-size: 1.1rem; opacity: 0.9; margin: 1rem 0; color: white; font-family: Lexend Deca, sans-serif;">{analysis['decision_summary']}</p>
        <p style="font-size: 0.9rem; opacity: 0.8; color: white; font-family: Lexend Deca, sans-serif;">Confidence: {analysis['confidence']}%</p>
    </div>
    """, unsafe_allow_html=True)

    # Recommendations based on decision
    col1, col2 = st.columns(2)
    if analysis['leave_type'] in ['full_day_leave', 'half_day_leave']:
        with col1:
            st.markdown('<p style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600;">Recovery Activities:</p>', unsafe_allow_html=True)
            for item in analysis.get('leave_activities', []):
                st.markdown(f'<div style="background: #d4edda; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; color: #1a1a1a; font-weight: 500; border-left: 3px solid #28a745; font-family: Lexend Deca, sans-serif;">{item}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<p style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600;">Avoid During Leave:</p>', unsafe_allow_html=True)
            for item in analysis.get('leave_avoid', []):
                st.markdown(f'<div style="background: #f8d7da; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; color: #1a1a1a; font-weight: 500; border-left: 3px solid #dc3545; font-family: Lexend Deca, sans-serif;">{item}</div>', unsafe_allow_html=True)
    else:
        with col1:
            st.markdown('<p style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600;">If You Work Tomorrow:</p>', unsafe_allow_html=True)
            for item in analysis.get('work_activities', []):
                st.markdown(f'<div style="background: #d4edda; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; color: #1a1a1a; font-weight: 500; border-left: 3px solid #28a745; font-family: Lexend Deca, sans-serif;">{item}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<p style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600;">Avoid While Working:</p>', unsafe_allow_html=True)
            for item in analysis.get('work_avoid', []):
                st.markdown(f'<div style="background: #f8d7da; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; color: #1a1a1a; font-weight: 500; border-left: 3px solid #dc3545; font-family: Lexend Deca, sans-serif;">{item}</div>', unsafe_allow_html=True)

    # Warning signs and recovery time
    if analysis.get('warning_signs'):
        st.markdown(f"""
        <div style="background: #f8f9fa; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; color: #1a1a1a; border: 1px solid #dee2e6; font-weight: 500; font-family: Lexend Deca, sans-serif;">
            <strong style="color: #1a1a1a; font-family: Lexend Deca, sans-serif;">Watch for these warning signs:</strong><br>
            {' • '.join(analysis['warning_signs'])}
        </div>
        """, unsafe_allow_html=True)

    if analysis.get('recovery_estimate'):
        st.markdown(f"""
        <div style="background: #f8f9fa; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; color: #1a1a1a; border: 1px solid #dee2e6; font-weight: 500; font-family: Lexend Deca, sans-serif;">
            <strong style="color: #1a1a1a; font-family: Lexend Deca, sans-serif;">Expected recovery time:</strong> {analysis['recovery_estimate']}
        </div>
        """, unsafe_allow_html=True)

    # AI Generated Leave Mail (use provided leave_mail)
    if analysis['leave_type'] in ['full_day_leave', 'half_day_leave'] and leave_mail:
        st.markdown('<h4 style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600; margin-top: 2rem;">📧 AI-Generated Leave Application</h4>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background: #f8f9fa; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; border: 1px solid #dee2e6; font-family: 'Courier New', monospace; font-size: 0.9rem; color: #1a1a1a; white-space: pre-line;">
{leave_mail}
        </div>
        """, unsafe_allow_html=True)
        render_copy_button(leave_mail)

def render_copy_button(text_to_copy: str) -> None:
    safe_text = json.dumps(text_to_copy)
    components.html(
        f"""
        <div>
          <button id=\"copyBtn\" style=\"background:#007aff;color:#fff;border:none;border-radius:8px;padding:8px 12px;font-weight:600;cursor:pointer;\">📋 Copy Email</button>
          <span id=\"copyStatus\" style=\"margin-left:8px;color:#1a1a1a;font-size:0.9rem;\"></span>
        </div>
        <script>
          const text = {safe_text};
          const btn = document.getElementById('copyBtn');
          const status = document.getElementById('copyStatus');
          btn.addEventListener('click', async () => {{
            try {{
              await navigator.clipboard.writeText(text);
              status.textContent = 'Copied!';
              setTimeout(() => status.textContent = '', 2000);
            }} catch (e) {{
              status.textContent = 'Copy failed. Please select and copy manually.';
            }}
          }});
        </script>
        """,
        height=60,
    )

def main():
    # Header with inline styles to ensure visibility
    st.markdown('<h1 style="font-size: 2.5rem; font-weight: 600; text-align: center; color: #1a1a1a; margin-bottom: 0.5rem; font-family: Lexend Deca, sans-serif;">Should I Take Leave Tomorrow?</h1>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 1.2rem; text-align: center; color: #666; margin-bottom: 3rem; font-family: Lexend Deca, sans-serif;">AI-powered decision making for your work-life balance</p>', unsafe_allow_html=True)
    
    # Get tomorrow's weather
    weather = get_weather_tomorrow()
    
    # Weather display with inline styles and animation
    # Determine weather icon and animation based on condition
    weather_condition_lower = weather['condition'].lower()
    if 'rain' in weather_condition_lower or 'shower' in weather_condition_lower:
        weather_icon = "🌧️"
        animation_class = "rain-animation"
    elif 'cloud' in weather_condition_lower:
        weather_icon = "☁️"
        animation_class = "cloud-animation"
    elif 'sun' in weather_condition_lower or 'clear' in weather_condition_lower:
        weather_icon = "☀️"
        animation_class = "sun-animation"
    else:
        weather_icon = "🌤️"
        animation_class = "default-animation"
    
    st.markdown(f'''
    <style>
        @keyframes rain-drop {{
            0% {{ transform: translateY(-5px); opacity: 0.7; }}
            50% {{ transform: translateY(2px); opacity: 1; }}
            100% {{ transform: translateY(-5px); opacity: 0.7; }}
        }}
        
        @keyframes cloud-drift {{
            0% {{ transform: translateX(-3px); }}
            50% {{ transform: translateX(3px); }}
            100% {{ transform: translateX(-3px); }}
        }}
        
        @keyframes sun-glow {{
            0% {{ transform: scale(1); opacity: 0.8; }}
            50% {{ transform: scale(1.05); opacity: 1; }}
            100% {{ transform: scale(1); opacity: 0.8; }}
        }}
        
        @keyframes gentle-float {{
            0% {{ transform: translateY(-2px); }}
            50% {{ transform: translateY(2px); }}
            100% {{ transform: translateY(-2px); }}
        }}
        
        .rain-animation {{
            animation: rain-drop 2s ease-in-out infinite;
        }}
        
        .cloud-animation {{
            animation: cloud-drift 4s ease-in-out infinite;
        }}
        
        .sun-animation {{
            animation: sun-glow 3s ease-in-out infinite;
        }}
        
        .default-animation {{
            animation: gentle-float 3s ease-in-out infinite;
        }}
    </style>
    <div style="background: #f8f9fa; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; color: #1a1a1a; text-align: center; border: 1px solid #dee2e6; font-family: Lexend Deca, sans-serif;">
        <h3 style="margin: 0; color: #1a1a1a; font-weight: 600; font-family: Lexend Deca, sans-serif;">Tomorrow's Weather in Burnaby</h3>
        <div style="font-size: 2rem; margin: 0.5rem 0;" class="{animation_class}">{weather_icon}</div>
        <p style="font-size: 1.1rem; margin: 0.5rem 0; color: #1a1a1a; font-family: Lexend Deca, sans-serif;">
            <strong style="color: #1a1a1a; font-family: Lexend Deca, sans-serif;">{weather['temp_high']}°C / {weather['temp_low']}°C</strong><br>
            {weather['condition']} • {weather['rain_chance']}% chance of rain
        </p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Input section header
    st.markdown('<h3 style="color: #1a1a1a; font-family: Lexend Deca, sans-serif; font-weight: 600;">How are you feeling today?</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        mood = st.selectbox(
            "Overall mood",
            ["Excellent", "Good", "Okay", "Struggling", "Overwhelmed", "Exhausted"],
            help="How would you describe your general state today?"
        )
        
        energy = st.slider("Energy level", 1, 10, 5, help="1 = Completely drained, 10 = Highly energized")
        sleep = st.slider("Last night's sleep quality", 1, 10, 6, help="1 = Terrible, 10 = Perfect rest")
        
        leave_balance = st.selectbox(
            "Leave balance remaining",
            ["20+ days", "15-20 days", "10-15 days", "5-10 days", "1-5 days", "No leave left"],
            help="How many days of leave do you have remaining?"
        )
        
    with col2:
        work_pressure = st.slider("Work pressure level", 1, 10, 5, help="1 = Very light, 10 = Overwhelming")
        personal_stress = st.slider("Personal life stress", 1, 10, 4, help="1 = Very peaceful, 10 = Major issues")
        
        physical_symptoms = st.selectbox(
            "Physical symptoms",
            ["None", "Mild tension/headache", "Moderate discomfort", "Severe symptoms"]
        )
        
        last_break = st.selectbox(
            "When did you last take a day off?",
            ["Never", "6+ months ago", "2-6 months ago", "1-2 months ago", "Within last month"]
        )
    
    tomorrow_importance = st.selectbox(
        "How critical is tomorrow's work?",
        ["Low priority - routine tasks", "Medium - some important items", "High - major deadlines", "Critical - cannot be postponed"]
    )
    
    support = st.selectbox(
        "Your support system",
        ["Strong - great family/friend support", "Good - some supportive people", "Limited - few people to talk to", "Weak - feeling quite isolated"]
    )
    
    # Analysis button
    if st.button("Get My Personalized Recommendation", type="primary"):
        data = {
            'mood': mood,
            'energy': energy,
            'sleep': sleep,
            'work_pressure': work_pressure,
            'personal_stress': personal_stress,
            'physical_symptoms': physical_symptoms,
            'last_break': last_break,
            'tomorrow_importance': tomorrow_importance,
            'support': support,
            'leave_balance': leave_balance
        }
        
        # Minimal loading animation
        loading_placeholder = st.empty()
        loading_placeholder.markdown("""
        <div style="text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 8px; margin: 1rem 0; border: 1px solid #dee2e6;">
            <div style="display: inline-block; width: 16px; height: 16px; border: 2px solid #007aff; border-radius: 50%; border-top-color: transparent; animation: spin 1s linear infinite; margin-right: 8px;"></div>
            <span style="color: #1a1a1a; font-family: 'Lexend Deca', sans-serif; font-size: 0.9rem;">Analyzing...</span>
        </div>
        <style>
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        </style>
        """, unsafe_allow_html=True)
        
        time.sleep(1.0)  # Reduced delay for better UX
        analysis = analyze_leave_decision(data, weather)
        
        # Clear loading animation
        loading_placeholder.empty()
        
        # Save assessment
        entry = {
            **data,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'wellness_score': analysis['wellness_score'],
            'recommendation': analysis['leave_type']
        }
        st.session_state.assessments.insert(0, entry)
        st.session_state.assessments = st.session_state.assessments[:30]
        
        # Persist analysis and mail in session, then render via a pure function so buttons don't collapse the UI
        st.session_state.analysis = analysis
        st.session_state.generated_leave_mail = generate_leave_mail() if analysis['leave_type'] in ['full_day_leave', 'half_day_leave'] else None
        render_analysis_ui(st.session_state.analysis, st.session_state.generated_leave_mail)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem; padding: 1.5rem; font-family: Lexend Deca, sans-serif;">
        <strong style="color: #666; font-family: Lexend Deca, sans-serif;">Your wellbeing matters.</strong> This tool provides guidance, not medical advice.<br>
        For serious mental health concerns, please consult a healthcare professional.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()




