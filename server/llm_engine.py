import re
import requests
from openai import OpenAI
from server.config import (
    SYSTEM_PROMPT,
    IDENTITY_RESPONSE,
    GREETING_RESPONSE,
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
        Check if the user is saying hello or general greeting.
        """
        q = re.sub(r"[^\w\s]", "", query.lower()).strip()
        greetings = [
            "hello", "hi", "hey", "hello ivia", "hi ivia", "hey ivia",
            "hello there", "hi there", "good morning", "good afternoon", "good evening",
            "hey there", "greetings"
        ]
        return q in greetings or q.startswith("hello ") or q.startswith("hi ") or q.startswith("hey ")

    def _is_identity_query(self, query: str) -> bool:
        """
        Check if the user is asking about IVIA's identity, creators, or introduction.
        """
        q = query.lower().strip()
        patterns = [
            r"\bwho are you\b",
            r"\bintroduce yourself\b",
            r"\bintroduce\b",
            r"\bintroduction\b",
            r"\bwhat is your name\b",
            r"\bwho created you\b",
            r"\bwho made you\b",
            r"\bwho developed you\b",
            r"\btell me about yourself\b",
            r"\bwhat are you\b",
            r"\byour name\b"
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

    def generate_response(self, user_prompt: str, visual_context: str = None) -> str:
        """
        Generate answer for user prompt.
        Handles greeting, identity enforcement, real-time vision questions, general Q&A, and conversational flow.
        """
        prompt = user_prompt.strip()
        if not prompt:
            return ""

        # 1. Enforce Greeting query ("Hello" -> "I am IVIA, how can I assist you?")
        if self._is_greeting_query(prompt):
            print(f"[LLM] Triggered Greeting Response: '{GREETING_RESPONSE}'")
            return GREETING_RESPONSE

        # 2. Enforce strict identity response
        if self._is_identity_query(prompt):
            print(f"[LLM] Triggered Identity Response: '{IDENTITY_RESPONSE}'")
            return IDENTITY_RESPONSE

        # 3. Intercept isolated corporate tokens from noise hallucinations (prevent lecture responses)
        clean_p = re.sub(r"[^\w\s]", "", prompt.lower()).strip()
        if clean_p in ["edupark", "edupark private limited", "nextgenpro", "nextgenpro innovations", "ivia"]:
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
                    # Clean up formatting for spoken delivery
                    answer = self._clean_for_speech(answer)
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
                                answer = self._clean_for_speech(answer)
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
                answer = self._clean_for_speech(answer)
                self.conversation_history.append({"role": "assistant", "content": answer})
                return answer
            except Exception as e:
                print(f"[LLM - OpenAI] Request failed: {e}")

        # 7. Offline Fallback if API keys aren't added yet
        return self._offline_fallback(prompt, visual_context)

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
