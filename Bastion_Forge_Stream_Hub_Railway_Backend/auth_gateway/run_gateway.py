import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

uvicorn.run(
    "auth_gateway:app",
    host=os.getenv("HOST", "127.0.0.1"),
    port=int(os.getenv("PORT", "8790")),
    reload=False,
)
