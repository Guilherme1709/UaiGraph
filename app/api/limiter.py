"""
Configuração do Limitador de Taxa de Requisições (SlowAPI).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
