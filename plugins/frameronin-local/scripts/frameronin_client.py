"""Standard-library client for the local FrameRonin backend. No implicit retries."""
import argparse, json, mimetypes, uuid, urllib.request, urllib.parse, urllib.error
from pathlib import Path

VIDEO={'.mp4','.mov','.webm','.avi','.mkv'}
IMAGE={'.png','.jpg','.jpeg','.webp'}
def request(base, path, data=None, headers=None):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(urllib.request.Request(base+path,data=data,headers=headers or {}),timeout=180) as r:
        return r.read()
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Redirect refused: local API only')
def multipart(path, params=None):
    boundary='frameronin-'+uuid.uuid4().hex
    chunks=[]
    if params is not None:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n{json.dumps(params)}\r\n'.encode())
    name='upload'+path.suffix.lower()
    mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),path.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()])
    return b''.join(chunks),{'Content-Type':'multipart/form-data; boundary='+boundary}
def validate_params(p):
    allowed={'fps','max_frames','target_size','frame_range','bg_color','transparent','padding','spacing','layout_mode','columns','matte_strength','crop_mode'}
    if set(p)-allowed: raise ValueError('Unsupported parameter(s): '+str(set(p)-allowed))
    for key,lo,hi,default in [('fps',1,60,12),('max_frames',1,2000,300),('padding',0,64,4),('spacing',0,64,4),('columns',1,64,12)]:
        value=p.get(key,default)
        if type(value) is not int or not lo<=value<=hi: raise ValueError('Invalid '+key)
    if p.get('layout_mode','fixed_columns') not in ('fixed_columns','auto_square'): raise ValueError('Invalid layout_mode')
    if p.get('crop_mode','tight_bbox') not in ('none','tight_bbox','safe_bbox'): raise ValueError('Invalid crop_mode')
    if not 0<=p.get('matte_strength',.6)<=1: raise ValueError('Invalid matte_strength')
    size=p.get('target_size',{'w':256,'h':256}); pad=p.get('padding',4)
    if set(size)!={'w','h'} or any(type(v) is not int or v<=2*pad for v in size.values()): raise ValueError('Invalid target_size')
    n=p.get('max_frames',300); cols=p.get('columns',12) if p.get('layout_mode','fixed_columns')=='fixed_columns' else __import__('math').ceil(n**.5)
    rows=(n+cols-1)//cols; spacing=p.get('spacing',4)
    if max(cols*(size['w']+spacing)-spacing,rows*(size['h']+spacing)-spacing)>16384: raise ValueError('Estimated atlas exceeds 16384; reduce max_frames or target_size')
    fr=p.get('frame_range',{})
    if set(fr)-{'start_sec','end_sec'}: raise ValueError('Only second-based ranges implemented by backend')
    start=fr.get('start_sec',0); end=fr.get('end_sec')
    if start<0 or (end is not None and end<=start): raise ValueError('Invalid time range')
def save(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f: f.write(content)
    print(json.dumps({'output':str(path.resolve()),'bytes':len(content)},ensure_ascii=False))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    subs=parser.add_subparsers(dest='command',required=True)
    subs.add_parser('health')
    for action in ('submit-video','submit-watermark','matte'):
        s=subs.add_parser(action);s.add_argument('--input',type=Path,required=True)
        if action=='submit-video': s.add_argument('--params',type=Path)
        if action=='matte': s.add_argument('--output',type=Path,required=True)
    for action in ('status','download'):
        s=subs.add_parser(action);s.add_argument('--kind',choices=['jobs','watermark'],required=True);s.add_argument('--job-id',required=True)
        if action=='download': s.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();u=urllib.parse.urlsplit(a.base_url)
    if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise ValueError('Use an HTTP loopback backend URL without path/credentials')
    base=a.base_url.rstrip('/')
    if hasattr(a,'output') and a.output.exists(): raise ValueError('Output already exists; choose a new path')
    if a.command=='health':
        schema=json.loads(request(base,'/openapi.json'))
        missing={'/jobs','/matte','/watermark'}-set(schema.get('paths',{}))
        if missing: raise ValueError('Not the expected backend: '+str(missing))
        print(json.dumps({'ok':True,'title':schema.get('info',{}).get('title')}));return
    if hasattr(a,'input'):
        image=a.command=='matte'
        if not a.input.is_file() or a.input.suffix.lower() not in (IMAGE if image else VIDEO): raise ValueError('Unsupported or missing input')
        if a.input.stat().st_size>(20 if image else 200)*1024*1024: raise ValueError('Input exceeds client upload limit')
        p=json.loads(a.params.read_text(encoding='utf-8-sig')) if a.command=='submit-video' and a.params else {}
        if a.command=='submit-video': validate_params(p)
        data,headers=multipart(a.input,p if a.command=='submit-video' else None)
        endpoint={'submit-video':'/jobs','submit-watermark':'/watermark','matte':'/matte'}[a.command]
        content=request(base,endpoint,data,headers)
        if image:
            if not content.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Expected PNG')
            save(a.output,content)
        else: print(json.dumps(json.loads(content),ensure_ascii=False))
        return
    if not __import__('re').fullmatch(r'[0-9a-f]{8}-[0-9a-f]{3}',a.job_id): raise ValueError('Invalid backend job ID')
    endpoint='/'+a.kind+'/'+a.job_id
    state=json.loads(request(base,endpoint))
    if a.command=='status': print(json.dumps(state,ensure_ascii=False)); return
    if state.get('status')!='completed': raise ValueError('Job not completed: '+str(state.get('status')))
    content=request(base,endpoint+'/result'+('?format=zip' if a.kind=='jobs' else ''))
    if a.kind=='jobs' and not content.startswith(b'PK'): raise ValueError('Expected ZIP')
    if a.kind=='watermark' and content[4:8]!=b'ftyp': raise ValueError('Expected MP4')
    save(a.output,content)
if __name__=='__main__':
    try: main()
    except Exception as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False));raise SystemExit(1)
