"""Server-only Groq adapter. No secrets, provider error bodies or reasoning are returned."""
import json
import time
import httpx
from app.config import setting

BASE = 'https://api.groq.com/openai/v1'
SPEECH_MODEL = 'whisper-large-v3-turbo'

class ProviderError(ValueError):
    pass

def headers():
    key = setting('GROQ_API_KEY').strip()
    if not key:
        raise ProviderError('Groq is selected but GROQ_API_KEY is missing. Configure it on the backend.')
    return {'Authorization': 'Bearer ' + key}

def check(response):
    if response.status_code in (401, 403):
        raise ProviderError('Groq rejected the API key or model permission. Check the backend key and account permissions.')
    if response.status_code == 429:
        raise ProviderError('Groq usage limit reached. Wait before trying again; check your account quota.')
    if response.status_code in (400, 404):
        raise ProviderError('Groq could not accept this request. Check the selected model and input format.')
    if response.is_error:
        raise ProviderError('Groq is temporarily unavailable. Try again later.')

def payload(model, messages, stream):
    body = {'model': model, 'messages': messages, 'stream': stream,
            'max_completion_tokens': 1024, 'temperature': 0.4}
    if model == 'qwen/qwen3.8-27b':
        body['reasoning_effort'] = 'none'
        body['reasoning_format'] = 'hidden'
    return body

class GroqProvider:
    def __init__(self, model):
        self.model = model
        self._status = None
        self._checked_at = 0

    async def status(self):
        if self._status is not None and time.monotonic() - self._checked_at < 60:
            return self._status
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(BASE + '/models', headers=headers())
                check(response)
                names = {m['id'] for m in response.json()['data']}
                result = {'ready': self.model in names, 'speech_ready': SPEECH_MODEL in names,
                          'error': None if self.model in names else 'Selected Groq model is unavailable for this account.'}
        except ProviderError as error:
            result = {'ready': False, 'speech_ready': False, 'error': str(error)}
        except (httpx.HTTPError, ValueError, KeyError):
            result = {'ready': False, 'speech_ready': False, 'error': 'Cannot reach Groq. Check your internet connection.'}
        self._status, self._checked_at = result, time.monotonic()
        return result

    async def answer(self, messages):
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post(BASE + '/chat/completions', headers=headers(),
                                             json=payload(self.model, messages, False))
                check(response)
                choice = response.json()['choices'][0]
                if choice.get('finish_reason') != 'stop':
                    raise ProviderError('Groq did not finish the answer. Try a shorter request.')
                result = (choice['message'].get('content') or '').strip()
                if not result:
                    raise ProviderError('Groq returned an empty answer. Please retry.')
                return result
        except httpx.HTTPError:
            raise ProviderError('Groq connection failed or timed out. Check your internet and retry.') from None
        except (KeyError, IndexError, json.JSONDecodeError):
            raise ProviderError('Groq returned an invalid answer. Please retry.') from None

    async def stream(self, messages):
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                async with client.stream('POST', BASE + '/chat/completions', headers=headers(),
                                         json=payload(self.model, messages, True)) as response:
                    check(response)
                    done, finished = False, False
                    async for line in response.aiter_lines():
                        if not line.startswith('data:'):
                            continue
                        data = line[5:].strip()
                        if data == '[DONE]':
                            done = True
                            break
                        event = json.loads(data)
                        if event.get('error'):
                            raise ProviderError('Groq interrupted the answer. Please retry.')
                        for choice in event.get('choices', []):
                            reason = choice.get('finish_reason')
                            if reason and reason != 'stop':
                                raise ProviderError('Groq did not finish the answer. Try a shorter request.')
                            finished = finished or reason == 'stop'
                            # Ignore reasoning and tool calls. Only ordinary answer text is spoken.
                            if text := choice.get('delta', {}).get('content'):
                                yield text
                    if not done or not finished:
                        raise ProviderError('Groq connection ended before the answer finished. Please retry.')
        except httpx.HTTPError:
            raise ProviderError('Groq connection failed or timed out. Check your internet and retry.') from None
        except (KeyError, IndexError, json.JSONDecodeError):
            raise ProviderError('Groq returned an invalid answer stream. Please retry.') from None

    async def transcribe(self, audio, language=None):
        fields = {'model': SPEECH_MODEL, 'response_format': 'verbose_json', 'temperature': '0'}
        if language:
            fields['language'] = language
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post(BASE + '/audio/transcriptions', headers=headers(),
                    data=fields, files={'file': ('voice.wav', audio, 'audio/wav')})
                check(response)
                result = response.json()
                return {'text': result['text'].strip(), 'language': result.get('language', language or 'auto')}
        except httpx.HTTPError:
            raise ProviderError('Groq transcription failed or timed out. Check your internet and retry.') from None
        except (KeyError, json.JSONDecodeError):
            raise ProviderError('Groq returned an invalid transcription. Please retry.') from None
