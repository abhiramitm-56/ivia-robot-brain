import re
import requests
from openai import OpenAI
from server.config import (
    SYSTEM_PROMPT,
    IDENTITY_RESPONSE,
    IDENTITY_RESPONSE_ML,
    IDENTITY_RESPONSE_HI,
    GREETING_RESPONSE,
    GREETING_RESPONSE_ML,
    GREETING_RESPONSE_HI,
    NEXTGENPRO_RESPONSE,
    NEXTGENPRO_RESPONSE_ML,
    NEXTGENPRO_RESPONSE_HI,
    NEXTGENPRO_LOCATION_RESPONSE,
    NEXTGENPRO_LOCATION_RESPONSE_ML,
    NEXTGENPRO_LOCATION_RESPONSE_HI,
    KERALA_CM_RESPONSE,
    KERALA_CM_RESPONSE_ML,
    KERALA_CM_RESPONSE_HI,
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

    def _detect_lang(self, text: str) -> str:
        """
        Detects whether the prompt is Malayalam, Hindi, or English.
        """
        if any('\u0D00' <= c <= '\u0D7F' for c in text):
            return "ml"
        elif any('\u0900' <= c <= '\u097F' for c in text):
            return "hi"
        return "en"

    def _is_greeting_query(self, query: str) -> bool:
        """
        Check if the user is saying hello or general greeting in English, Malayalam, or Hindi.
        """
        q = query.lower().strip()
        patterns = [
            r"^hello\b", r"^hi\b", r"^hey\b", r"^greetings\b", r"^good\s+morning\b",
            r"^good\s+afternoon\b", r"^good\s+evening\b",
            r"നമസ്കാരം", r"ഹലോ", r"ഹായ്", r"സുഖമാണോ",
            r"नमस्ते", r"नमस्कार", r"प्रणाम", r"हेलो"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_identity_query(self, query: str) -> bool:
        """
        Check if the user is asking about IVIA's identity, creators, or introduction.
        """
        q = query.lower().strip()
        patterns = [
            r"\bwho are you\b", r"\bintroduce yourself\b", r"\bintroduce\b", r"\bintroduction\b",
            r"\bwhat is your name\b", r"\bwho created you\b", r"\bwho made you\b",
            r"\bwho developed you\b", r"\btell me about yourself\b", r"\bwhat are you\b",
            r"\byour name\b",
            r"ആരാണ്\s*നീ", r"നീ\s*ആരാണ്", r"ആരാണ്\s*നിങ്ങൾ", r"പേരെന്താണ്", r"പേര്\s*എന്താണ്",
            r"तुम\s*कौन\s*हो", r"आप\s*कौन\s*हैं", r"तुम्हारा\s*नाम\s*क्या\s*है"
        ]
        return any(re.search(pat, q) for pat in patterns)

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
        Check if user asked a question starting with or containing 'do you know' / 'അറിയാമോ' / 'क्या आप जानते हैं'.
        """
        q = query.lower().strip()
        patterns = [
            r"^do\s+you\s+know\b", r"^do\s+u\s+know\b", r"\bdo\s+you\s+know\b", r"\bdo\s+u\s+know\b",
            r"^can\s+you\s+tell\s+me\s+if\s+you\s+know\b",
            r"അറിയാമോ", r"നിനക്കറിയാമോ", r"നിങ്ങൾക്ക്\s*അറിയാമോ",
            r"क्या\s*आप\s*जानते\s*हैं", r"क्या\s*तुम\s*जानते\s*हो", r"जानते\s*हो"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_nextgenpro_location_query(self, query: str) -> bool:
        """
        Check if the user is asking about NextGenPro's location, address, or where it is.
        """
        q = query.lower().strip()
        has_ngp = "nextgenpro" in q or "next gen pro" in q or "nextgen" in q or "നെക്സ്റ്റ്ജെൻപ്രോ" in q or "നെക്സ്റ്റ്" in q or "नेक्स्टजेनप्रो" in q
        loc_words = ["location", "where is", "where are", "address", "situated", "place", "office", "headquarter", "station", "complex", "located", "എവിടെയാണ്", "എവിടെ", "സ്ഥലം", "ഓഫീസ്", "कहाँ", "पता", "कार्यालय"]
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
            r"\bnext gen pro\b",
            r"നെക്സ്റ്റ്ജെൻപ്രോ", r"നെക്സ്റ്റ്\s*ജെൻ\s*പ്രോ", r"നെക്സ്റ്റ്ജെൻ",
            r"नेक्स्टजेनप्रो"
        ]
        return any(re.search(pat, q) for pat in patterns)

    def _is_kerala_cm_query(self, query: str) -> bool:
        """
        Check if user asked about the Chief Minister of Kerala.
        """
        q = query.lower().strip()
        has_kerala = "kerala" in q or "കേരള" in q or "केरल" in q
        has_cm = "cm" in q or "chief minister" in q or "chiefminister" in q or "മുഖ്യമന്ത്രി" in q or "मुख्यमंत्री" in q
        return (has_kerala and has_cm) or "മുഖ്യമന്ത്രി" in q

    def generate_response(self, user_prompt: str, visual_context: str = None) -> str:
        """
        Generate answer for user prompt with multilingual intelligence.
        """
        prompt = user_prompt.strip()
        if not prompt:
            return ""

        lang = self._detect_lang(prompt)
        is_know_q = self._is_do_you_know_query(prompt)

        know_prefix = ""
        if is_know_q:
            if lang == "ml":
                know_prefix = "അതെ, എനിക്കറിയാം. "
            elif lang == "hi":
                know_prefix = "हाँ, मुझे पता है। "
            else:
                know_prefix = "Yes, I know. "

        # 1. Enforce Greeting query
        if self._is_greeting_query(prompt):
            resp = GREETING_RESPONSE_ML if lang == "ml" else (GREETING_RESPONSE_HI if lang == "hi" else GREETING_RESPONSE)
            print(f"[LLM] Triggered Greeting Response ({lang}): '{resp}'")
            return resp

        # 2. Enforce strict identity response
        if self._is_identity_query(prompt):
            resp = IDENTITY_RESPONSE_ML if lang == "ml" else (IDENTITY_RESPONSE_HI if lang == "hi" else IDENTITY_RESPONSE)
            print(f"[LLM] Triggered Identity Response ({lang}): '{resp}'")
            return resp

        # 3. Kerala CM query
        if self._is_kerala_cm_query(prompt):
            base = KERALA_CM_RESPONSE_ML if lang == "ml" else (KERALA_CM_RESPONSE_HI if lang == "hi" else KERALA_CM_RESPONSE)
            resp = f"{know_prefix}{base}"
            print(f"[LLM] Triggered Kerala CM Response ({lang}): '{resp}'")
            return resp

        # 4. NextGenPro location query
        if self._is_nextgenpro_location_query(prompt):
            base = NEXTGENPRO_LOCATION_RESPONSE_ML if lang == "ml" else (NEXTGENPRO_LOCATION_RESPONSE_HI if lang == "hi" else NEXTGENPRO_LOCATION_RESPONSE)
            resp = f"{know_prefix}{base}"
            print(f"[LLM] Triggered NextGenPro Location Response ({lang}): '{resp}'")
            return resp

        # 5. NextGenPro general query
        if self._is_nextgenpro_query(prompt):
            base = NEXTGENPRO_RESPONSE_ML if lang == "ml" else (NEXTGENPRO_RESPONSE_HI if lang == "hi" else NEXTGENPRO_RESPONSE)
            resp = f"{know_prefix}{base}"
            print(f"[LLM] Triggered NextGenPro Response ({lang}): '{resp}'")
            return resp

        # 6. Intercept isolated corporate tokens from noise hallucinations
        clean_p = re.sub(r"[^\w\s]", "", prompt.lower()).strip()
        if clean_p in ["edupark", "edupark private limited", "ivia"]:
            print(f"[LLM] Suppressed unprompted corporate hallucination: '{prompt}'")
            return GREETING_RESPONSE

        # 4. Add user prompt to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        if len(self.conversation_history) > 8:
            self.conversation_history = self.conversation_history[-8:]

        # Augment system prompt with live vision context
        system_content = SYSTEM_PROMPT
        if visual_context:
            system_content += f"\n\n[LIVE ROBOT VISION TELEMETRY]:\n{visual_context}\nCRITICAL: You have a live camera sensor attached. When the user asks what you see, who is in front of you, what they are holding, or about their hand gesture, answer directly based on this live telemetry!"

        history_messages = list(self.conversation_history)
        if self._is_vision_query(prompt) and visual_context:
            # Explicitly tie visual observation to the question
            history_messages[-1] = {
                "role": "user",
                "content": f"{prompt}\n[Robot Vision Sensor reports: {visual_context}]"
            }

        messages = [{"role": "system", "content": system_content}] + history_messages

        # 4. Query Groq (Ultra-fast LLM response < 500ms)
        if self.groq_client:
            candidate_models = [GROQ_MODEL] + [m for m in ["qwen/qwen3.8-27b", "allam-2-7b", "openai/gpt-oss-120b"] if m != GROQ_MODEL]
            for model_candidate in candidate_models:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model_candidate,
                        messages=messages,
                        max_tokens=100,
                        temperature=0.6
                    )
                    answer = response.choices[0].message.content.strip()
                    # Clean up formatting for spoken delivery and ensure 'Yes, I know' prefix if asked
                    answer = self._finalize_answer(answer, is_know_q, lang)
                    self.conversation_history.append({"role": "assistant", "content": answer})
                    return answer
                except Exception as e:
                    print(f"[LLM - Groq] Model '{model_candidate}' failed: {e}")

        # 5. Query Gemini / Google AI (Fallback)
        if GEMINI_API_KEY:
            for gemini_cand in [GEMINI_MODEL, "gemma-4-26b-a4b-it", "gemma-4-31b-it"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_cand}:generateContent?key={GEMINI_API_KEY}"
                    payload = {
                        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser Question: {prompt}"}]}],
                        "generationConfig": {"maxOutputTokens": 200, "temperature": 0.7}
                    }
                    resp = requests.post(url, json=payload, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get('candidates', [])
                        if candidates and 'content' in candidates[0]:
                            parts = candidates[0]['content'].get('parts', [])
                            if parts:
                                answer = parts[0].get('text', '').strip()
                                answer = self._finalize_answer(answer, is_know_q, lang)
                                self.conversation_history.append({"role": "assistant", "content": answer})
                                return answer
                    else:
                        print(f"[LLM - Gemini] Model '{gemini_cand}' status {resp.status_code}")
                except Exception as e:
                    print(f"[LLM - Gemini] Request failed: {e}")

        # 6. Query OpenAI (Fallback)
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    max_tokens=200,
                    temperature=0.7
                )
                answer = response.choices[0].message.content.strip()
                answer = self._finalize_answer(answer, is_know_q, lang)
                self.conversation_history.append({"role": "assistant", "content": answer})
                return answer
            except Exception as e:
                print(f"[LLM - OpenAI] Request failed: {e}")

        # 7. Offline Fallback if API keys aren't added yet
        offline_resp = self._offline_fallback(prompt, visual_context)
        return self._finalize_answer(offline_resp, is_know_q, lang)

    def _finalize_answer(self, text: str, is_know_q: bool, lang: str = "en") -> str:
        clean = self._clean_for_speech(text)
        if is_know_q:
            if lang == "ml":
                if not clean.startswith("അതെ") and "എനിക്കറിയാം" not in clean[:30]:
                    clean = f"അതെ, എനിക്കറിയാം. {clean}"
            elif lang == "hi":
                if not clean.startswith("हाँ") and "मुझे पता है" not in clean[:30]:
                    clean = f"हाँ, मुझे पता है। {clean}"
            else:
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
        # Strip trailing "thank you" / "thanks" if appended at the end
        text = re.sub(r"([?.!])?\s*(?:thank\s+you|thanks)(?:\s+(?:very\s+much|so\s+much))?[\.\!\?]*$", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r",\s*$", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _offline_fallback(self, prompt: str, visual_context: str = None) -> str:
        """
        Convenient offline responses when testing without an API key.
        """
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
            return "I am functioning at peak efficiency and ready to assist you! What would you like to explore?"
        if "time" in p:
            return "Time is a fascinating concept. In my digital world, every moment is an opportunity to learn something new!"
        
        return f"I heard your question about '{prompt}'. Please configure your GROQ or OpenAI API key in the environment file so I can answer all questions about the world."
