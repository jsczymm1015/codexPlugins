"""Extract recorded model dependencies; never execute metadata or infer from pixels."""
import json
import re

FOLDERS = {'checkpoint': 'models/checkpoints/', 'lora': 'models/loras/',
           'vae': 'models/vae/', 'upscaler': 'models/upscale_models/',
           'embedding': 'models/embeddings/', 'controlnet': 'models/controlnet/',
           'diffusion_model': 'models/diffusion_models/', 'text_encoder': 'models/text_encoders/',
           'clip_vision': 'models/clip_vision/', 'detector': 'depends on detector node/plugin'}
# Only documented/common built-in widget layouts; custom nodes require investigation.
NODES = {
    'CheckpointLoaderSimple': [('ckpt_name', 'checkpoint', 0)],
    'CheckpointLoader': [('config_name', None, 0), ('ckpt_name', 'checkpoint', 1)],
    'LoraLoader': [('lora_name', 'lora', 0)],
    'LoraLoaderModelOnly': [('lora_name', 'lora', 0)],
    'VAELoader': [('vae_name', 'vae', 0)],
    'UpscaleModelLoader': [('model_name', 'upscaler', 0)],
    'ControlNetLoader': [('control_net_name', 'controlnet', 0)],
    'DiffControlNetLoader': [('control_net_name', 'controlnet', 0)],
    'UNETLoader': [('unet_name', 'diffusion_model', 0)],
    'CLIPLoader': [('clip_name', 'text_encoder', 0)],
    'DualCLIPLoader': [('clip_name1', 'text_encoder', 0), ('clip_name2', 'text_encoder', 1)],
    'TripleCLIPLoader': [('clip_name1', 'text_encoder', 0), ('clip_name2', 'text_encoder', 1), ('clip_name3', 'text_encoder', 2)],
    'CLIPVisionLoader': [('clip_name', 'clip_vision', 0)],
}


def split_fields(text):
    """Commas within quoted hash maps must not split metadata fields."""
    return [part.strip() for part in re.split(r',\s*(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', text)]


def hash_map(value):
    result = {}
    for item in value.strip('"').split(','):
        if ':' in item:
            name, hash_value = item.rsplit(':', 1)
            result[name.strip()] = hash_value.strip()
    return result


def extract_dependencies(text):
    resources, warnings, settings = [], [], {}
    formats = []

    def add(kind, name, source, hash_value=None, weight=None):
        if not isinstance(name, str) or not name.strip() or name.casefold() in ('none', 'automatic', 'baked vae', 'undefined'):
            return
        name = name.strip()
        if kind == 'upscaler' and name.casefold().startswith(('latent', 'nearest', 'bilinear', 'bicubic', 'lanczos')):
            return
        if kind == 'vae' and name.casefold() == 'pixel_space':
            return
        existing = next((r for r in resources if r['type'] == kind and r['name'].casefold() == name.casefold()), None)
        if existing:
            if hash_value and not existing.get('hash'):
                existing['hash'] = hash_value
            if source not in existing['sources']:
                existing['sources'].append(source)
            return
        resource = {'type': kind, 'name': name, 'sources': [source], 'comfyui_directory': FOLDERS.get(kind)}
        if hash_value:
            resource['hash'] = hash_value
        if weight is not None:
            resource['weight'] = str(weight)
        resources.append(resource)

    parameters = text.get('parameters', '')
    if parameters:
        formats.append('a1111_parameters')
        matches = list(re.finditer(r'(?:^|\n)Steps:\s*\d+', parameters))
        if matches:
            split = matches[-1].start()
            body, tail = parameters[:split], parameters[split:].strip()
            for field in split_fields(tail):
                if ':' in field:
                    key, value = field.split(':', 1)
                    settings[key.strip()] = value.strip()
        else:
            body = parameters
            warnings.append('A1111 parameters lack a Steps settings line; only explicit dependencies extracted')
        prompt, separator, negative = body.partition('\nNegative prompt:')
        settings['positive_prompt'] = prompt.strip()
        settings['negative_prompt'] = negative.strip() if separator else ''
        add('checkpoint', settings.get('Model'), 'parameters.Model', settings.get('Model hash'))
        add('vae', settings.get('VAE'), 'parameters.VAE', settings.get('VAE hash'))
        add('upscaler', settings.get('Hires upscaler'), 'parameters.Hires upscaler')
        for key, value in settings.items():
            if re.fullmatch(r'ADetailer model(?: \d+)?', key):
                add('detector', value, 'parameters.' + key)
        loras = hash_map(settings.get('Lora hashes', ''))
        loras.update(hash_map(settings.get('Lyco hashes', '')))
        for match in re.finditer(r'<(?:lora|lyco):([^<>]+):(-?\d+(?:\.\d+)?)>', body, re.I):
            name, weight = match.groups()
            add('lora', name, 'parameters.prompt', next((v for k, v in loras.items() if k.casefold() == name.casefold()), None), weight)
        for name, value in loras.items():
            add('lora', name, 'parameters.Lora hashes', value)
        for name, value in hash_map(settings.get('TI hashes', '')).items():
            add('embedding', name, 'parameters.TI hashes', value)
        for name in re.findall(r'\bembedding:([^\s,()]+)', body):
            add('embedding', name, 'parameters.explicit_embedding')

    for key in ('prompt', 'workflow'):
        if key not in text:
            continue
        try:
            value = json.loads(text[key])
        except (ValueError, TypeError, RecursionError):
            warnings.append(f'{key}: invalid JSON; not treated as instructions')
            continue
        if not isinstance(value, dict):
            warnings.append(f'{key}: expected JSON object')
            continue
        nodes = list(value.items()) if key == 'prompt' else [(n.get('id'), n) for n in value.get('nodes', []) if isinstance(n, dict)] if isinstance(value.get('nodes', []), list) else []
        if not any(isinstance(n, dict) and isinstance(n.get('class_type' if key == 'prompt' else 'type'), str) for _, n in nodes):
            warnings.append(f'{key}: no recognizable ComfyUI node structure')
            continue
        if 'comfyui' not in formats:
            formats.append('comfyui')
        if len(nodes) > 10000:
            warnings.append(f'{key}: too many nodes; extraction limited to 10000')
        for node_id, node in nodes[:10000]:
            if not isinstance(node, dict):
                continue
            node_type = node.get('class_type', node.get('type', 'unknown'))
            if not isinstance(node_type, str):
                warnings.append(f'{key} node {node_id}: invalid node type')
                continue
            source = f'{key}.node[{node_id}].{node_type}'
            fields = NODES.get(node_type, [])
            inputs = node.get('inputs', {})
            widgets = node.get('widgets_values', [])
            if isinstance(inputs, dict):
                for name, kind, index in fields:
                    if kind:
                        add(kind, inputs.get(name), source, weight=inputs.get('strength_model') if kind == 'lora' else None)
                if node_type in ('CLIPTextEncode', 'CLIPTextEncodeSDXL'):
                    for field in ('text', 'text_g', 'text_l'):
                        if isinstance(inputs.get(field), str):
                            for name in re.findall(r'\bembedding:([^\s,()]+)', inputs[field]):
                                add('embedding', name, source)
            if key == 'workflow' and isinstance(widgets, list):
                for name, kind, index in fields:
                    if kind and index < len(widgets):
                        add(kind, widgets[index], source, weight=widgets[1] if kind == 'lora' and len(widgets) > 1 else None)
                if node_type == 'CLIPTextEncode' and widgets and isinstance(widgets[0], str):
                    for name in re.findall(r'\bembedding:([^\s,()]+)', widgets[0]):
                        add('embedding', name, source)
            if not fields and node_type not in ('CLIPTextEncode', 'CLIPTextEncodeSDXL', 'KSampler', 'KSamplerAdvanced', 'VAEDecode', 'VAEEncode', 'SaveImage', 'PreviewImage', 'EmptyLatentImage', 'CLIPSetLastLayer', 'ImageScale', 'ImageScaleBy', 'UpscaleModelApply'):
                warnings.append(f'{source}: unsupported/custom node; inspect original metadata for additional dependencies')
    if not formats:
        warnings.append('No recognized generation metadata; request original PNG, do not guess models from pixels')
    return {'format': '+'.join(formats) or 'unknown', 'resources': resources, 'settings': settings, 'warnings': warnings}
