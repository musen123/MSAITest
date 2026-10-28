# @Author  : 木森
# @weixin: python771

import os
from pathlib import Path

import dotenv

_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
dotenv.load_dotenv(_dotenv_path)
