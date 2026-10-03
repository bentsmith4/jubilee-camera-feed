"""Local telemetry only: no provider calls, request mutation or decision inputs."""
import base64
import hashlib
import json
import uuid
from datetime import datetime

UNKNOWN = 'UNKNOWN'
CACHE_SEMANTICS_SOURCE = 'https://developers.openai.com/api/docs/guides/prompt-caching#calculate-input-cost'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def field(obj, name):
    value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    return UNKNOWN if value is None else value


def capture_context(status_raw, burst_raw):
    status, burst = (json.loads(raw) for raw in (status_raw, burst_raw))
    capture = status.get('capture_time_ct')
    # This is the exact canonical identity used by observation-effort records.
    # No nearby-time join, current latest receipt, or archive seal is substituted.
    if not capture or burst.get('capture_time_ct') != capture:
        return {}
    if datetime.fromisoformat(capture).tzinfo is None:
        return {}
    return dict(capture_id=capture, capture_time_ct=capture,
                capture_identity_kind='canonical_capture_time_ct',
                capture_input_hashes={'status.json': sha(status_raw),
                                     'burst_status.json': sha(burst_raw)})


def request_evidence(kwargs):
    prefix = []
    images = []
    items = kwargs.get('input')
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            content = item.get('content', [])
            if item.get('role') == 'developer' and isinstance(content, list):
                # Fingerprint exact role/content including breakpoint configuration.
                prefix.append(item)
            if isinstance(content, list):
                for part in content:
                    if part.get('type') == 'input_image':
                        url = part.get('image_url', '')
                        if url.startswith('data:image/jpeg;base64,'):
                            images.append(sha(base64.b64decode(url.split(',', 1)[1], validate=True)))
                        else:
                            images.append(UNKNOWN)
    return dict(prompt_prefix_sha256=sha(encoded(prefix)) if prefix else UNKNOWN,
                prefix_fingerprint_kind='canonical_json_developer_items_v1',
                input_image_sha256=images,
                requested_service_tier=kwargs.get('service_tier', UNKNOWN),
                prompt_cache_key_sha256=sha(str(kwargs['prompt_cache_key']).encode()) if 'prompt_cache_key' in kwargs else UNKNOWN,
                prompt_cache_options=kwargs.get('prompt_cache_options', UNKNOWN),
                prompt_cache_retention=kwargs.get('prompt_cache_retention', UNKNOWN))


def attempt_fields(response, kwargs, runtime_version, context):
    usage = field(response, 'usage')
    details = field(usage, 'input_tokens_details')
    writes = field(details, 'cache_write_tokens')
    # Preserve count only if actually supplied. Never input-minus-cache-read.
    if type(writes) is not int or writes < 0:
        writes = UNKNOWN
    model = field(response, 'model')
    semantics = 'partition_of_input' if writes != UNKNOWN and model == 'gpt-5.6-luna' else UNKNOWN
    return dict(telemetry_schema_version=1, attempt_id=uuid.uuid4().hex,
                attempt_scope='responses_create_invocation_sdk_retries_not_exposed',
                runtime_version=runtime_version,
                capture_id=context.get('capture_id', UNKNOWN),
                capture_time_ct=context.get('capture_time_ct', UNKNOWN),
                capture_identity_kind=context.get('capture_identity_kind', UNKNOWN),
                capture_input_hashes=context.get('capture_input_hashes', UNKNOWN),
                canonical_integrity_receipt_sha256=UNKNOWN,
                camera_integrity=UNKNOWN,
                actual_service_tier=field(response, 'service_tier'),
                billed_service_tier=UNKNOWN, billing_context_class=UNKNOWN,
                billing_rules_provenance=UNKNOWN,
                cache_write_tokens=writes, cache_write_semantics=semantics,
                cache_write_semantics_source=CACHE_SEMANTICS_SOURCE if semantics != UNKNOWN else UNKNOWN,
                **request_evidence(kwargs))


def bind_integrity(row, snapshot, snapshot_raw):
    """Exact canonical receipt readback; no biological negative interpretation."""
    if json.loads(snapshot_raw) != snapshot:
        return dict(camera_integrity=UNKNOWN, canonical_integrity_receipt_sha256=UNKNOWN)
    hashes = row.get('capture_input_hashes')
    if (row.get('capture_id') == UNKNOWN or not isinstance(hashes, dict)
            or snapshot.get('generated_from_capture_time_ct') != row.get('capture_id')
            or any(snapshot.get('input_hashes', {}).get(k) != v for k, v in hashes.items())
            or set(hashes) != {'status.json', 'burst_status.json'}):
        return dict(camera_integrity=UNKNOWN, canonical_integrity_receipt_sha256=UNKNOWN)
    cameras = {}
    for cell in snapshot.get('cells', []):
        for camera in cell.get('camera_rows', []):
            cid = camera['camera_id']
            if cid in cameras and cameras[cid] != camera:
                return dict(camera_integrity=UNKNOWN, canonical_integrity_receipt_sha256=UNKNOWN)
            cameras[cid] = camera
    selected = (row['stage'].split(':', 1)[1],) if row['stage'].startswith('camera:') else (
        'montrose_pier_boat', 'montrose_pier_bird', 'montrose_shoreline',
        'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth')
    states = []
    for cid in selected:
        camera = cameras.get(cid, {})
        ok, issues = camera.get('capture_ok'), camera.get('integrity_issues')
        states.append(False if ok is False or isinstance(issues, list) and issues
                      else True if ok is True and issues == [] else UNKNOWN)
    return dict(camera_integrity=False if False in states else True if all(s is True for s in states) else UNKNOWN,
                canonical_integrity_receipt_sha256=sha(snapshot_raw))
