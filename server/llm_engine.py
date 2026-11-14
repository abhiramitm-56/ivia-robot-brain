import re
import requests
from openai import OpenAI
from server.config import (
    SYSTEM_PROMPT,
    IDENTITY_RESPONSE,
    GREETING_RESPONSE,
    NEXTGENPRO_RESPONSE,
    NEXTGENPRO_LOCATION_RESPONSE,
    KERALA_CM_RESPONSE,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    GROQ_MODEL,
    OPENAI_MODEL,
    GEMINI_MODEL,
)

class LLMEngine:
    def __init__(self):
        self.groq_client = None
        self.openai_client = None
        self.conversation_history = []

        if GROQ_API_KEY:
            try:
                self.groq_client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=GROQ_API_KEY
                )
            except Exception as e:
                print(f"[LLM] Groq init error: {e}")

        if OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as e:
                print(f"[LLM] OpenAI init error: {e}")

    def _is_greeting_query(self, query: str) -> bool:
        """
        Check if the user is saying a standalone hello or general greeting.
        Anchored to full phrase so questions starting with 'Hello, what is...' do not get hijacked.
        """
        q_clean = re.sub(r"[.,!?;:\-–—\(\)\[\]\"']+", " ", query.lower()).strip()
        patterns = [
            r"^(?:hello|hi|hey|greetings)(?:\s+ivia)?$",
            r"^(?:good\s+morning|good\s+afternoon|good\s+evening)(?:\s+ivia)?$",
            r"^(?:how\s+are\s+you|how\s+do\s+you\s+do)(?:\s+ivia)?$",
            r"^(?:ivia)$"
        ]
        return any(re.match(pat, q_clean, flags=re.IGNORECASE) for pat in patterns)

    def _is_identity_query(self, query: str) -> bool:
        """
        Check if the user is specifically asking about IVIA's identity, creators, or introduction.
        Requires explicit self-referential targets (you/your/self).
        """
        q = query.lower().strip()
        patterns = [
            r"\bwho\s+are\s+you\b",
            r"\bwhat\s+is\s+your\s+name\b",
            r"\bintroduce\s+yourself\b",
            r"\btell\s+me\s+about\s+yourself\b",
            r"\bwho\s+created\s+you\b",
            r"\bwho\s+made\s+you\b",
            r"\bwho\s+developed\s+you\b",
            r"\bwhat\s+are\s+you\b",
            r"\byour\s+name\b"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _strip_leading_address(self, text: str) -> str:
        """
        If user starts with an address like 'Hello IVIA, ...' or 'Hi, ...' or 'IVIA, ...'
        and follows with an actual question/query, strip the address so the real question
        can be properly answered by the LLM.
        """
        t = text.strip()
        m = re.match(
            r"^(?:(?:hello|hi|hey|greetings)(?:\s+(?:ivia|robot))?|(?:ivia|robot))[\s,:\-]+(.+)$",
            t,
            flags=re.IGNORECASE
        )
        if m:
            rem = m.group(1).strip()
            if len(rem) >= 3 and not re.match(r"^(?:ivia|robot)$", rem, re.IGNORECASE):
                return rem
        return t

    def _is_vision_query(self, query: str) -> bool:
        """
        Check if the user is asking about what IVIA sees, objects, persons, or hand gestures.
        """
        q = query.lower().strip()
        patterns = [
            r"\bwhat do you see\b",
            r"\bwhat are you seeing\b",
            r"\bwho is in front of you\b",
            r"\bwho do you see\b",
            r"\bcan you see me\b",
            r"\bdo you see me\b",
            r"\bwhat am i holding\b",
            r"\bwhat is in my hand\b",
            r"\bwhat am i doing\b",
            r"\bwhat am i showing\b",
            r"\bwhat gesture\b",
            r"\bwhat hand gesture\b",
            r"\blook at me\b",
            r"\blook at this\b",
            r"\bwhat is this\b",
            r"\bdescribe what you see\b",
            r"\bvision report\b"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_do_you_know_query(self, query: str) -> bool:
        """
        Check if user asked a question starting with or containing 'do you know'.
        """
        q = query.lower().strip()
        patterns = [
            r"^do\s+you\s+know\b", r"^do\s+u\s+know\b", r"\bdo\s+you\s+know\b", r"\bdo\s+u\s+know\b",
            r"^can\s+you\s+tell\s+me\s+if\s+you\s+know\b"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_nextgenpro_location_query(self, query: str) -> bool:
        """
        Check if the user is asking about NextGenPro's location or address.
        """
        q = query.lower().strip()
        has_ngp = "nextgenpro" in q or "next gen pro" in q or "nextgen" in q
        loc_words = ["location", "where is", "where are", "address", "situated", "place", "office", "headquarter", "station", "complex", "located"]
        return has_ngp and any(w in q for w in loc_words)

    def _is_nextgenpro_query(self, query: str) -> bool:
        """
        Check if the user is asking about NextGenPro.
        """
        q = query.lower().strip()
        patterns = [
            r"\bwhat is nextgenpro\b", r"\bwhat is next gen pro\b", r"\btell me about nextgenpro\b",
            r"\btell me about next gen pro\b", r"\babout nextgenpro\b", r"\babout next gen pro\b",
            r"\bwho is nextgenpro\b", r"\bwho is next gen pro\b", r"\bnextgenpro innovations\b",
            r"\bwhat does nextgenpro do\b", r"\bwhat does next gen pro do\b", r"\bnextgenpro\b",
            r"\bnext gen pro\b"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_kerala_cm_query(self, query: str) -> bool:
        """
        Check if user asked about the Chief Minister of Kerala.
        """
        q = query.lower().strip()
        has_kerala = "kerala" in q
        has_cm = "cm" in q or "chief minister" in q or "chiefminister" in q
        return has_kerala and has_cm

    def generate_response(self, user_prompt: str, visual_context: str = None, forced_lang: str = None) -> str:
        """
        Generate answer for user prompt strictly in English.
        """
        prompt = user_prompt.strip()
        if not prompt:
            return ""

        # 1. Enforce Greeting query ONLY IF it is a standalone greeting (e.g. "Hello", "Hi IVIA")
        if self._is_greeting_query(prompt):
            print(f"[LLM] Triggered Greeting Response: '{GREETING_RESPONSE}'")
            return GREETING_RESPONSE

        # Strip polite robot address prefix if present (e.g. "Hello IVIA, what is...", "Hi, tell me...", "IVIA, who is...")
        active_query = self._strip_leading_address(prompt)
        is_know_q = self._is_do_you_know_query(active_query)

        know_prefix = "Yes, I know. " if is_know_q else ""

        # 2. Enforce strict identity response ONLY when asking about IVIA itself
        if self._is_identity_query(active_query):
            print(f"[LLM] Triggered Identity Response: '{IDENTITY_RESPONSE}'")
            return IDENTITY_RESPONSE

        # 3. Kerala CM query
        if self._is_kerala_cm_query(active_query):
            resp = f"{know_prefix}{KERALA_CM_RESPONSE}"
            print(f"[LLM] Triggered Kerala CM Response: '{resp}'")
            return resp

        # 4. NextGenPro location query
        if self._is_nextgenpro_location_query(active_query):
            resp = f"{know_prefix}{NEXTGENPRO_LOCATION_RESPONSE}"
            print(f"[LLM] Triggered NextGenPro Location Response: '{resp}'")
            return resp

        # 5. NextGenPro general query
        if self._is_nextgenpro_query(active_query):
            resp = f"{know_prefix}{NEXTGENPRO_RESPONSE}"
            print(f"[LLM] Triggered NextGenPro Response: '{resp}'")
            return resp

        # 6. Intercept isolated corporate tokens from noise hallucinations
        clean_p = re.sub(r"[^\w\s]", "", active_query.lower()).strip()
        if clean_p in ["edupark", "edupark private limited", "ivia"]:
            print(f"[LLM] Suppressed unprompted corporate hallucination: '{active_query}'")
            return GREETING_RESPONSE

        # Add active user prompt to conversation history
        self.conversation_history.append({"role": "user", "content": active_query})
        if len(self.conversation_history) > 6:
            self.conversation_history = self.conversation_history[-6:]

        system_content = f"{SYSTEM_PROMPT}\n\nMANDATORY: Reply strictly in natural, fluent English. Keep your answer strictly to 1 crisp sentence."
        if visual_context:
            system_content += f"\n\n[LIVE ROBOT VISION TELEMETRY]:\n{visual_context}"

        history_messages = list(self.conversation_history)
        if self._is_vision_query(active_query) and visual_context:
            history_messages[-1] = {
                "role": "user",
                "content": f"{active_query}\n[Robot Vision Sensor reports: {visual_context}]"
            }

        messages = [{"role": "system", "content": system_content}] + history_messages

        # Query Groq (Ultra-fast LLM response < 200ms)
        if self.groq_client:
            candidate_models = [GROQ_MODEL] + [m for m in ["allam-2-7b"] if m != GROQ_MODEL]
            for model_candidate in candidate_models:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model_candidate,
                        messages=messages,
                        max_tokens=45,
                        temperature=0.4
                    )
                    answer = response.choices[0].message.content.strip()
                    answer = self._finalize_answer(answer, is_know_q)
                    self.conversation_history.append({"role": "assistant", "content": answer})
                    return answer
                except Exception as e:
                    print(f"[LLM - Groq] Model '{model_candidate}' failed: {e}")

        # Query OpenAI (Fallback)
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    max_tokens=45,
                    temperature=0.4
                )
                answer = response.choices[0].message.content.strip()
                answer = self._finalize_answer(answer, is_know_q)
                self.conversation_history.append({"role": "assistant", "content": answer})
                return answer
            except Exception as e:
                print(f"[LLM - OpenAI] Request failed: {e}")

        # Offline Fallback if APIs are unreachable
        offline_resp = self._offline_fallback(active_query, visual_context)
        return self._finalize_answer(offline_resp, is_know_q)

    def _finalize_answer(self, text: str, is_know_q: bool) -> str:
        clean = self._clean_for_speech(text)
        if is_know_q:
            low = clean.lower()
            if not low.startswith("yes, i know") and not low.startswith("yes i know"):
                clean = f"Yes, I know. {clean}"
        return clean

    def _clean_for_speech(self, text: str) -> str:
        text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2026", "...")
        text = re.sub(r"[\*\_#`]", "", text)
        text = re.sub(r"([?.!])?\s*(?:thank\s+you|thanks)(?:\s+(?:very\s+much|so\s+much))?[\.\!\?]*$", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r",\s*$", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _offline_fallback(self, prompt: str, visual_context: str = None) -> str:
        p = prompt.lower()
        if self._is_vision_query(prompt):
            if visual_context:
                return f"Looking through my camera: {visual_context}"
            return "My camera sensor is currently idle. Activate the camera feed to see in real-time."

        if self._is_identity_query(prompt):
            return IDENTITY_RESPONSE
        if "hello" in p or "hi" in p or "hey" in p:
            return GREETING_RESPONSE
        if "how are you" in p:
            return "I am functioning at peak efficiency and ready to assist you!"
        if "time" in p:
            return "Time is a fascinating concept. In my digital world, every moment is an opportunity to learn something new!"
        
        return f"I heard your question about '{prompt}'. Please check your network and API keys to connect to my full intelligence."
