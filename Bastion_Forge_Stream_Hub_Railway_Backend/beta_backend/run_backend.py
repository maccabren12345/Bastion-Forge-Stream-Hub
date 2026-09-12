import os
import uvicorn
from dotenv import load_dotenv
load_dotenv()
uvicorn.run(
    'beta_backend:app',
    host=os.getenv('HOST', '127.0.0.1'),
    port=int(os.getenv('PORT', '8792')),
    reload=False,
)
