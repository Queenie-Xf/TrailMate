import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from thefuzz import process
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# ✅ 修正 1: 引用新的数据库工具
from app.core.database import execute
# ✅ 修正 2: 引用新的模型文件
from app.models.sql_models import Trail
# ✅ 修正 3: 引用 wta_service (现在它在 app.services 里了)
from app.services.wta_service import search_wta_trail, get_recent_trip_reports, check_hazards

logger = logging.getLogger(__name__)

# ==========================================
# 1. Mock Data & Schema
# ==========================================
MOCK_TRAILS_DB = [
    {
        "name": "Mailbox Peak",
        "location": "North Bend, WA",
        "length_km": 15.1,
        "elevation_gain_m": 1219,
        "difficulty_rating": 5.0,
        "latitude": 47.4665,
        "longitude": -121.6749,
        "features": "steep,mailbox_at_top,views"
    },
    {
        "name": "Rattlesnake Ledge",
        "location": "North Bend, WA",
        "length_km": 6.4,
        "elevation_gain_m": 353,
        "difficulty_rating": 2.5,
        "latitude": 47.4326,
        "longitude": -121.7679,
        "features": "lake_view,crowded,easy"
    },
]

class ExtractionSchema(BaseModel):
    is_planning_trip: bool = Field(description="True only if users are actively proposing a plan.")
    trail_name_raw: Optional[str] = None
    target_date_str: Optional[str] = None

# ==========================================
# 2. Main Service Class
# ==========================================
class AutoPlannerService:
    def __init__(self, db: Session):
        self.db = db
        # 确保 Docker 内部能访问 Ollama
        self.client = AsyncOpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama",
        )
        self.model_name = "llama3.2" 

    async def run_pipeline(self, chat_id: str, user_message: str):
        triggers = ["go to", "hike", "trail", "plan", "weekend", "trip", "join", "去", "爬山", "路线"]
        if not any(k in user_message.lower() for k in triggers):
            return

        extraction = await self._extract_intent(user_message)
        if not extraction.is_planning_trip or not extraction.trail_name_raw:
            return

        logger.info(f"🚀 Intent detected: '{extraction.trail_name_raw}'")

        trail_record = self._fuzzy_match_trail(extraction.trail_name_raw)
        if not trail_record:
            return

        # --- WTA Integration ---
        logger.info(f"🔎 Checking WTA reports for {trail_record.name}...")
        wta_context = ""
        wta_hazards = []
        
        try:
            url = search_wta_trail(trail_record.name)
            if url:
                reports = get_recent_trip_reports(url)
                wta_hazards = check_hazards(reports)
                if reports:
                    wta_context = "Recent User Reports:\n- " + "\n- ".join(reports[:3])
                else:
                    wta_context = "No recent trip reports found."
            else:
                wta_context = "Trail not found on WTA."
        except Exception as e:
            logger.error(f"WTA lookup failed: {e}")
            wta_context = "WTA data unavailable."

        weather_info = "Sunny, 20°C (Mock)" 

        announcement_json = await self._generate_final_json(
            trail_record, 
            extraction.target_date_str, 
            weather_info,
            wta_context,
            wta_hazards
        )

        self._post_announcement_to_db(chat_id, announcement_json)
        
    async def _extract_intent(self, message: str) -> ExtractionSchema:
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
        You are a JSON extractor. Current Date: {current_date}.
        Check if user is planning a hike.
        Return ONLY a JSON object: {{"is_planning_trip": true, "trail_name_raw": "...", "target_date_str": "..."}}
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
                response_format={"type": "json_object"}, 
                temperature=0.0
            )
            return ExtractionSchema(**json.loads(response.choices[0].message.content))
        except Exception:
            return ExtractionSchema(is_planning_trip=False)

    def _fuzzy_match_trail(self, raw_name: str):
        # 1. Try DB
        try:
            all_trails = self.db.query(Trail).all()
            if all_trails:
                choices = {t.name: t for t in all_trails}
                best, score = process.extractOne(raw_name, list(choices.keys()))
                if score > 70: return choices[best]
        except: pass
        
        # 2. Try Mock
        mock_choices = {t['name']: t for t in MOCK_TRAILS_DB}
        best, score = process.extractOne(raw_name, list(mock_choices.keys()))
        if score > 50:
            t_data = mock_choices[best]
            # Create a fake object to mimic SQLAlchemy model
            class MockTrailObj: pass
            obj = MockTrailObj()
            for k, v in t_data.items(): setattr(obj, k, v)
            return obj
        return None

    async def _generate_final_json(self, trail, date_str, weather, wta_context, wta_hazards) -> Dict:
        system_prompt = f"""
        You are an expert hiking guide. Generate a JSON trip card.
        Trail: {trail.name} | Length: {trail.length_km}km
        Conditions: {wta_context}
        Hazards: {', '.join(wta_hazards)}
        
        Return JSON:
        {{"title": "Trip Plan: {trail.name}", "summary": "...", "stats": {{"dist": "{trail.length_km}km", "elev": "{trail.elevation_gain_m}m"}}, "weather_warning": "...", "gear_required": ["Item1", "Item2"], "fun_fact": "..."}}
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Generate plan"}],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"title": "Error", "stats": {}}

    def _post_announcement_to_db(self, chat_id: str, content_json: Dict):
        content_str = json.dumps(content_json)
        try:
            execute(
                "INSERT INTO group_messages (group_id, sender_display, role, content, created_at) VALUES (%(gid)s, 'HikeBot', 'assistant', %(c)s, NOW())",
                {"gid": chat_id, "c": content_str}
            )
        except Exception as e:
            logger.error(f"DB Write failed: {e}")