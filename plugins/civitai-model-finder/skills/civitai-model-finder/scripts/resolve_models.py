#!/usr/bin/env python3
"""Extract dependencies and optionally resolve hashes against Civitai. Python 3.10+."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from dependencies import extract_dependencies
from png_metadata import read_png_metadata

API_ROOT = 'https://civitai.com/api/v1/model-versions/by-hash/'
MAX_RESPONSE = 8 * 1024 * 1024
UPSCALER_URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'


def fetch_json(url):
    request = Request(url, headers={'User-Agent': 'CivitaiModelFinder/0.1', 'Accept': 'application/json'})
    with urlopen(request, timeout=12) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('API response too large')
    return json.loads(raw.decode('utf-8'))


def safe_download_url(url):
    if not isinstance(url, str):
        return None
    parsed = urlsplit(url)
    if (parsed.scheme == 'https' and parsed.hostname == 'civitai.com'
            and not parsed.username and not parsed.password
            and parsed.path.startswith('/api/download/models/')
            and 'token=' not in parsed.query.casefold()):
        return url
    return None


def matching_hash(hashes, requested):
    if not isinstance(hashes, dict):
        return None
    requested = requested.casefold()
    for algorithm, value in hashes.items():
        if not isinstance(value, str):
            continue
        if value.casefold() == requested:
            return {'algorithm': algorithm, 'value': value, 'comparison': 'exact'}
        # A1111 Model hash is usually the first 10 SHA256 hex digits.
        # Do not prefix-match 12-char LoRA hashes against unrelated hash types.
        if str(algorithm).upper() == 'SHA256' and len(requested) == 10 and len(value) == 64 and value.casefold().startswith(requested):
            return {'algorithm': 'SHA256', 'value': value, 'comparison': '10-character prefix'}
    return None


def resolve_resource(resource, fetch=fetch_json):
    result = dict(resource)
    name = str(resource.get('name', ''))
    hash_value = resource.get('hash')
    result['search_terms'] = [f'"{hash_value}"', f'"{name}"'] if hash_value else [f'"{name}"']
    if not hash_value:
        if resource.get('type') == 'upscaler' and name.casefold() in ('r-esrgan 4x+', 'realesrgan_x4plus', 'realesrgan_x4plus.pth'):
            result.update(status='official_name_match', download_url=UPSCALER_URL,
                          source_url='https://github.com/xinntao/Real-ESRGAN',
                          filename='RealESRGAN_x4plus.pth',
                          note='Official name alias, not a hash match or a live download/access check')
        else:
            result['status'] = 'name_search_required'
        return result
    if not isinstance(hash_value, str) or not re.fullmatch(r'[a-fA-F0-9]{8,64}', hash_value):
        result['status'] = 'invalid_hash'
        return result
    result['query_url'] = API_ROOT + quote(hash_value, safe='')
    try:
        data = fetch(result['query_url'])
        if not isinstance(data, dict) or type(data.get('id')) is not int or type(data.get('modelId')) is not int:
            raise ValueError('Expected model-version JSON')
        result['model_page'] = f"https://civitai.com/models/{data['modelId']}?modelVersionId={data['id']}"
        model = data.get('model') if isinstance(data.get('model'), dict) else {}
        result['api_resource_type'] = model.get('type')
        result.update(model_name=model.get('name'), version_name=data.get('name'),
                      base_model=data.get('baseModel'), availability=data.get('availability'),
                      model_mode=model.get('mode'), early_access_ends_at=data.get('earlyAccessEndsAt'))
        files = data.get('files') or []
        if not isinstance(files, list):
            raise ValueError('Invalid files collection')
        result['files'] = []
        for file in files:
            if not isinstance(file, dict):
                continue
            match = matching_hash(file.get('hashes'), hash_value)
            if match:
                result['files'].append({'name': file.get('name'), 'size_kb': file.get('sizeKB'),
                    'download_url': safe_download_url(file.get('downloadUrl')), 'matched_hash': match})
        result['status'] = 'hash_verified' if result['files'] else 'version_found_no_matching_file'
        known_types = {'checkpoint': {'checkpoint'}, 'lora': {'lora', 'locon', 'lycoris'},
                       'vae': {'vae'}, 'upscaler': {'upscaler'}, 'embedding': {'textualinversion', 'embedding'},
                       'controlnet': {'controlnet'}}
        api_type = str(model.get('type') or '').casefold()
        if api_type and resource.get('type') in known_types and api_type not in known_types[resource['type']]:
            result['status'] = 'resource_type_conflict'
            result['comfyui_directory'] = None
        result['note'] = 'File identity only; download permissions, price and image reproducibility are not verified'
    except HTTPError as exc:
        result['status'] = {404: 'not_found', 401: 'authentication_required', 403: 'access_denied', 429: 'rate_limited'}.get(exc.code, 'service_error')
        result['http_status'] = exc.code
    except (URLError, TimeoutError, socket.timeout, OSError):
        result['status'] = 'network_error'
    except (ValueError, TypeError, RecursionError, UnicodeError):
        result['status'] = 'invalid_response'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('png', type=Path)
    parser.add_argument('--lookup', action='store_true', help='Query Civitai using hashes only (no image upload)')
    parser.add_argument('--output', type=Path, help='Write JSON report to this NEW file; default stdout')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        metadata = read_png_metadata(args.png)
        report = extract_dependencies(metadata['text'])
        report['warnings'] = metadata['warnings'] + report['warnings']
        report['metadata'] = metadata['text']
        report['source_file'] = args.png.name
        report['generated_at'] = datetime.now(timezone.utc).isoformat()
        report['lookup_attempted'] = args.lookup
        if args.lookup:
            if len(report['resources']) > 64:
                report['warnings'].append('Only first 64 resources queried; remaining resources require follow-up')
            with ThreadPoolExecutor(max_workers=4) as executor:
                report['resources'] = list(executor.map(resolve_resource, report['resources'][:64])) + [
                    dict(r, status='not_queried_limit') for r in report['resources'][64:]]
        else:
            for resource in report['resources']:
                resource['status'] = 'not_queried'
        output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(output)
            print(f'Report written: {args.output.resolve()}')
        else:
            print(output)
        return 0
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
