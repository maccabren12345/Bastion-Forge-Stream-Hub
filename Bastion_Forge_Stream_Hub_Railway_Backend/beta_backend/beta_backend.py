import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

load_dotenv()

BASE = Path(os.getenv('BASTION_DATA_DIR', str(Path(__file__).resolve().parent))).resolve()
RELEASES = BASE / 'releases'
FEEDBACK = BASE / 'feedback'
HISTORY = BASE / 'history'
for folder in (RELEASES, FEEDBACK, HISTORY):
    folder.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
DISCORD_FEEDBACK_WEBHOOK_URL = os.getenv('DISCORD_FEEDBACK_WEBHOOK_URL', '').strip()

app = FastAPI(title='Bastion Forge Stream Hub Beta Service', version='1.0')


def manifest_path(channel: str) -> Path:
    safe = 'stable' if channel == 'stable' else 'private-beta'
    return BASE / f'manifest-{safe}.json'


def safe_text(value: Any, limit: int = 1500) -> str:
    text = str(value or '').strip()
    return text[:limit]


@app.get('/health')
async def health() -> dict[str, Any]:
    return {
        'ok': True,
        'service': 'Bastion Forge Stream Hub Beta Service',
        'time': datetime.now(timezone.utc).isoformat(),
    }


@app.get('/streamhub/manifest.json')
async def manifest(channel: str = 'private-beta') -> dict[str, Any]:
    path = manifest_path(channel)
    if not path.exists():
        raise HTTPException(status_code=404, detail='No release is published on this channel yet.')
    data = json.loads(path.read_text(encoding='utf-8'))
    filename = data.get('installerFile', '')
    if filename and not data.get('installerUrl'):
        if not PUBLIC_BASE_URL:
            raise HTTPException(status_code=503, detail='PUBLIC_BASE_URL is not configured.')
        data['installerUrl'] = f'{PUBLIC_BASE_URL}/streamhub/releases/{filename}'
    return data


@app.get('/streamhub/releases/{filename}')
async def release_file(filename: str):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', filename):
        raise HTTPException(status_code=400, detail='Invalid filename.')
    path = RELEASES / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail='Release not found.')
    return FileResponse(path, filename=filename, media_type='application/octet-stream')


@app.post('/streamhub/feedback')
async def feedback(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Invalid JSON: {exc}')
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Feedback payload must be an object.')

    report_id = safe_text(payload.get('reportId'), 120)
    if not report_id:
        report_id = f'SH-{int(datetime.now(timezone.utc).timestamp())}'
    safe_id = re.sub(r'[^A-Za-z0-9._-]', '_', report_id)
    path = FEEDBACK / f'{safe_id}.json'
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')

    if DISCORD_FEEDBACK_WEBHOOK_URL:
        embed = {
            'title': f'Stream Hub Beta Report • {report_id}',
            'description': safe_text(payload.get('summary'), 1000) or 'No summary',
            'fields': [
                {'name': 'Type', 'value': safe_text(payload.get('category'), 100) or 'Unknown', 'inline': True},
                {'name': 'Severity', 'value': safe_text(payload.get('severity'), 100) or 'Unknown', 'inline': True},
                {'name': 'Version', 'value': safe_text(payload.get('version'), 100) or 'Unknown', 'inline': True},
                {'name': 'Tester', 'value': safe_text(payload.get('testerId'), 100) or 'Unknown', 'inline': True},
                {'name': 'Steps', 'value': safe_text(payload.get('steps'), 900) or 'Not supplied', 'inline': False},
                {'name': 'Actual', 'value': safe_text(payload.get('actual'), 900) or 'Not supplied', 'inline': False},
            ],
            'footer': {'text': 'Full JSON report saved on the Bastion beta server'},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(DISCORD_FEEDBACK_WEBHOOK_URL, json={'embeds': [embed]})
        except Exception:
            pass

    return {'ok': True, 'reportId': report_id}
