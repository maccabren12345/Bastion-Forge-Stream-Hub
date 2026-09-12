import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

load_dotenv(Path(__file__).with_name('.env'))
host = os.getenv('BASTION_BRIDGE_HOST', '0.0.0.0')
port = int(os.getenv('BASTION_BRIDGE_PORT', '8788'))
uvicorn.run('kick_bridge:app', host=host, port=port, reload=False)
