"""Explicit provider settings; Windows user environment supports desktop launches."""
import os

USER_SETTINGS = {'GROQ_API_KEY', 'YOUAI_LLM_PROVIDER', 'YOUAI_SPEECH_PROVIDER', 'YOUAI_GROQ_MODEL'}

def setting(name, default=''):
    if name in os.environ:
        return os.environ[name]
    if os.name == 'nt' and name in USER_SETTINGS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                value, _ = winreg.QueryValueEx(key, name)
                return str(value)
        except OSError:
            pass
    return default
