"""
Gerenciamento de provedores de IA (Groq e Gemini) com fallback unificado e tratamento de cotas.
"""

import time
import logging
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
import groq
from groq import Groq
from app.core.config import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    GROQ_CHAT_MODEL,
    GEMINI_MODEL
)

logger = logging.getLogger("graphpolitics.llm.providers")

T = TypeVar("T", bound=BaseModel)

class LLMProviderManager:
    """Gerencia clientes Groq e Gemini com chaveamento transparente e fallback sob rate-limit."""

    def __init__(self):
        self._groq_client: Optional[Groq] = None
        self._gemini_client = None
        self._gemini_available = False
        self._gemini_cooldown_until: float = 0.0

        self._init_groq()
        self._init_gemini()

    def _init_groq(self):
        if GROQ_API_KEY:
            try:
                self._groq_client = Groq(api_key=GROQ_API_KEY)
                logger.info("[LLMProvider] Cliente Groq inicializado.")
            except Exception as e:
                logger.error(f"[LLMProvider] Erro ao inicializar cliente Groq: {e}")

    def _init_gemini(self):
        if GEMINI_API_KEY:
            try:
                from google import genai
                from google.genai import types
                self._gemini_client = genai.Client(
                    api_key=GEMINI_API_KEY,
                    http_options=types.HttpOptions(
                        retry_options=types.HttpRetryOptions(attempts=0)
                    )
                )
                self._gemini_available = True
                logger.info("[LLMProvider] Cliente Gemini inicializado com sucesso.")
            except Exception as e:
                logger.warning(f"[LLMProvider] Falha ao inicializar Gemini: {e}. Usando Groq como principal.")
                self._gemini_available = False

    @property
    def groq_client(self) -> Optional[Groq]:
        return self._groq_client

    @property
    def is_gemini_available(self) -> bool:
        """Verifica se o Gemini está disponível e fora da janela de cooldown."""
        return (
            self._gemini_available
            and (self._gemini_client is not None)
            and (time.time() >= self._gemini_cooldown_until)
        )

    def set_gemini_cooldown(self, seconds: float = 60.0):
        """Ativa janela de cooldown temporária para o Gemini em caso de limite de cota (429)."""
        self._gemini_cooldown_until = time.time() + seconds
        logger.warning(f"[LLMProvider] Gemini em cooldown temporário por {seconds}s.")

    def generate_json_with_fallback(
        self,
        prompt: str,
        schema_cls: Type[T],
        groq_model: str = GROQ_CHAT_MODEL,
        max_retries: int = 3
    ) -> Optional[T]:
        """Gera resposta JSON estruturada validada pelo Pydantic, com fallback automático entre Gemini e Groq."""
        for attempt in range(max_retries):
            try:
                if self.is_gemini_available:
                    try:
                        from google.genai import types
                        resp = self._gemini_client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=schema_cls,
                            ),
                        )
                        return schema_cls.model_validate_json(resp.text)
                    except Exception as e:
                        logger.warning(f"[LLMProvider] Gemini falhou na extração JSON ({e}), acionando Groq...")
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            self.set_gemini_cooldown(60.0)
                        if self._groq_client:
                            completion = self._groq_client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model=groq_model,
                                response_format={"type": "json_object"},
                            )
                            return schema_cls.model_validate_json(completion.choices[0].message.content)
                        raise e
                elif self._groq_client:
                    completion = self._groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=groq_model,
                        response_format={"type": "json_object"},
                    )
                    return schema_cls.model_validate_json(completion.choices[0].message.content)
                else:
                    return None
            except groq.RateLimitError:
                logger.warning(f"[LLMProvider] Rate limit da Groq na tentativa {attempt + 1}. Aguardando...")
                if attempt < max_retries - 1:
                    time.sleep(3)
            except Exception as e:
                logger.error(f"[LLMProvider] Erro ao gerar JSON estruturado: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    break
        return None

    def generate_text_with_fallback(
        self,
        prompt: str,
        groq_model: str = GROQ_CHAT_MODEL,
        max_retries: int = 3
    ) -> str:
        """Gera texto natural usando Gemini com fallback transparente para Groq."""
        for attempt in range(max_retries):
            try:
                if self.is_gemini_available:
                    try:
                        resp = self._gemini_client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=prompt
                        )
                        return resp.text
                    except Exception as e:
                        logger.warning(f"[LLMProvider] Gemini falhou no chat ({e}), caindo para Groq...")
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            self.set_gemini_cooldown(60.0)
                        if self._groq_client:
                            completion = self._groq_client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model=groq_model,
                            )
                            return completion.choices[0].message.content
                        raise e
                elif self._groq_client:
                    completion = self._groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=groq_model,
                    )
                    return completion.choices[0].message.content
                else:
                    return "Nenhum provedor de IA (Groq ou Gemini) configurado ou disponível no momento."
            except groq.RateLimitError:
                if attempt < max_retries - 1:
                    logger.warning(f"[LLMProvider] Limite de taxa da Groq (tentativa {attempt + 1}). Aguardando 4s...")
                    time.sleep(4)
                else:
                    return "Limite temporário de requisições do provedor de IA atingido. Por favor, aguarde alguns instantes e tente novamente."
            except Exception as e:
                logger.error(f"[LLMProvider] Erro ao gerar texto: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return "Ocorreu uma instabilidade momentânea ao gerar a resposta política. Por favor, tente novamente em instantes."
        return "Não foi possível gerar a resposta no momento."

# Instância padrão singleton para uso da aplicação
llm_provider = LLMProviderManager()
