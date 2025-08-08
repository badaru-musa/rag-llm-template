from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.enums import LLMProvider
from app.exceptions import LLMServiceError, ConfigurationError
from config import Settings


class BaseLLMService(ABC):
    """Abstract base class for LLM services"""
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate a streaming response from the LLM"""
        pass


class AzureOpenAIService(BaseLLMService):
    """Azure OpenAI LLM service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate Azure OpenAI configuration"""
        if not self.config.azure_openai_api_key:
            raise ConfigurationError("Azure OpenAI API key is required")
        if not self.config.azure_openai_endpoint:
            raise ConfigurationError("Azure OpenAI endpoint is required")
        if not self.config.azure_openai_deployment_name:
            raise ConfigurationError("Azure OpenAI deployment name is required")
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client"""
        try:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=self.config.azure_openai_api_key,
                api_version=self.config.azure_openai_api_version,
                azure_endpoint=self.config.azure_openai_endpoint,
            )
        except ImportError:
            raise ConfigurationError("OpenAI library not installed")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using Azure OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.azure_openai_deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMServiceError(f"Azure OpenAI API error: {str(e)}")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate streaming response using Azure OpenAI"""
        try:
            stream = self.client.chat.completions.create(
                model=self.config.azure_openai_deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise LLMServiceError(f"Azure OpenAI streaming error: {str(e)}")


class OpenAIService(BaseLLMService):
    """OpenAI LLM service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate OpenAI configuration"""
        if not self.config.openai_api_key:
            raise ConfigurationError("OpenAI API key is required")
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.config.openai_api_key)
        except ImportError:
            raise ConfigurationError("OpenAI library not installed")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMServiceError(f"OpenAI API error: {str(e)}")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate streaming response using OpenAI"""
        try:
            stream = self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise LLMServiceError(f"OpenAI streaming error: {str(e)}")


class AnthropicService(BaseLLMService):
    """Anthropic Claude LLM service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate Anthropic configuration"""
        if not self.config.anthropic_api_key:
            raise ConfigurationError("Anthropic API key is required")
    
    def _initialize_client(self):
        """Initialize Anthropic client"""
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.config.anthropic_api_key)
        except ImportError:
            raise ConfigurationError("Anthropic library not installed")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using Anthropic Claude"""
        try:
            response = self.client.messages.create(
                model=self.config.anthropic_model,
                messages=messages,
                max_tokens=max_tokens or 1000,
                temperature=temperature,
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            raise LLMServiceError(f"Anthropic API error: {str(e)}")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate streaming response using Anthropic Claude"""
        try:
            stream = self.client.messages.create(
                model=self.config.anthropic_model,
                messages=messages,
                max_tokens=max_tokens or 1000,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            for chunk in stream:
                if chunk.type == "content_block_delta" and chunk.delta.text:
                    yield chunk.delta.text
        except Exception as e:
            raise LLMServiceError(f"Anthropic streaming error: {str(e)}")


class GeminiService(BaseLLMService):
    """Google Gemini LLM service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate Gemini configuration"""
        if not self.config.google_api_key:
            raise ConfigurationError("Google API key is required")
    
    def _initialize_client(self):
        """Initialize Gemini client"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.google_api_key)
            self.client = genai.GenerativeModel(self.config.gemini_model)
        except ImportError:
            raise ConfigurationError("Google Generative AI library not installed")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using Google Gemini"""
        try:
            # Convert messages to Gemini format
            prompt = self._convert_messages_to_prompt(messages)
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )
            return response.text
        except Exception as e:
            raise LLMServiceError(f"Gemini API error: {str(e)}")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate streaming response using Google Gemini"""
        try:
            prompt = self._convert_messages_to_prompt(messages)
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
                stream=True
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMServiceError(f"Gemini streaming error: {str(e)}")
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to Gemini prompt format"""
        prompt_parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        return "\n".join(prompt_parts)


class LocalLLMService(BaseLLMService):
    """Local LLM service (placeholder for local models)"""
    
    def __init__(self, config: Settings):
        self.config = config
        # TODO: Implement local model loading
        raise NotImplementedError("Local LLM service not yet implemented")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using local LLM"""
        # TODO: Implement local model inference
        raise NotImplementedError("Local LLM generation not yet implemented")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """Generate streaming response using local LLM"""
        # TODO: Implement local model streaming
        raise NotImplementedError("Local LLM streaming not yet implemented")


class LLMFactory:
    """Factory for creating LLM services"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._services = {
            LLMProvider.AZURE_OPENAI: AzureOpenAIService,
            LLMProvider.OPENAI: OpenAIService,
            LLMProvider.ANTHROPIC: AnthropicService,
            LLMProvider.GEMINI: GeminiService,
            LLMProvider.LOCAL: LocalLLMService,
        }
    
    def create_llm(self, provider: str) -> BaseLLMService:
        """Create LLM service based on provider"""
        try:
            provider_enum = LLMProvider(provider)
        except ValueError:
            raise ConfigurationError(f"Unsupported LLM provider: {provider}")
        
        service_class = self._services.get(provider_enum)
        if not service_class:
            raise ConfigurationError(f"LLM service not found for provider: {provider}")
        
        return service_class(self.config)
