"""WSL2/usbipd diagnostics and passive 802.11 capture for Remote ID."""
import argparse,ctypes as C,json,shutil,struct,subprocess,sys
from wifi_rid_worker import frames,DLT_IEEE802_11,DLT_IEEE802_11_RADIO

NO_WINDOW=0x08000000 if sys.platform=='win32' else 0

def run(command,timeout=20):
    return subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=NO_WINDOW)

def status():
    result={'wsl':False,'distro':'','usbipd':bool(shutil.which('usbipd.exe')),'driver':False,'iw':False,'interface':'','ready':False}
    listing=run(['wsl.exe','--list','--quiet'])
    if listing.returncode:return result
    names=[x.replace('\0','').strip() for x in listing.stdout.splitlines() if x.replace('\0','').strip()]
    if not names:return result
    result['wsl']=True;result['distro']='Ubuntu-22.04' if 'Ubuntu-22.04' in names else names[0]
    probe=run(['wsl.exe','-d',result['distro'],'-u','root','--','bash','-lc',
               "command -v iw >/dev/null && echo IW=1; (modinfo 88XXau >/dev/null 2>&1 || modinfo rtw88_8821au >/dev/null 2>&1) && echo DRIVER=1; iw dev 2>/dev/null | awk '$1==\"Interface\"{print \"IFACE=\"$2;exit}'"])
    for line in probe.stdout.splitlines():
        if line=='IW=1':result['iw']=True
        elif line=='DRIVER=1':result['driver']=True
        elif line.startswith('IFACE='):result['interface']=line[6:]
    result['ready']=all((result['wsl'],result['usbipd'],result['driver'],result['iw'],result['interface']))
    return result

def capture(distro):
    script="set -e; i=$(iw dev | awk '$1==\"Interface\"{print $2;exit}'); test -n \"$i\"; ip link set \"$i\" down; iw dev \"$i\" set type monitor; ip link set \"$i\" up; exec tcpdump -U -i \"$i\" -s 4096 -w -"
    proc=subprocess.Popen(['wsl.exe','-d',distro,'-u','root','--','bash','-lc',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=NO_WINDOW)
    header=proc.stdout.read(24)
    if len(header)!=24:raise RuntimeError(proc.stderr.read().decode(errors='replace') or 'WSL capture did not start.')
    magic=header[:4];endian='<' if magic in (b'\xd4\xc3\xb2\xa1',b'\x4d\x3c\xb2\xa1') else '>'
    link=struct.unpack(endian+'I',header[20:24])[0]
    if link not in (DLT_IEEE802_11,DLT_IEEE802_11_RADIO):raise RuntimeError('The WSL interface did not return raw 802.11 frames.')
    print(json.dumps({'status':'ready','backend':'wsl2','interface':status().get('interface'),'linktype':link}),flush=True)
    while True:
        record=proc.stdout.read(16)
        if len(record)!=16:break
        _,_,captured,_=struct.unpack(endian+'IIII',record);packet=proc.stdout.read(captured)
        if len(packet)!=captured:break
        for message in frames(packet,link):print(json.dumps(message),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--status',action='store_true');parser.add_argument('--capture',action='store_true');parser.add_argument('--distro',default='Ubuntu-22.04');args=parser.parse_args()
    try:
        if args.status:print(json.dumps(status()));return
        if args.capture:capture(args.distro);return
    except Exception as error:print(json.dumps({'status':'error','error':str(error)}),flush=True);raise SystemExit(1)

if __name__=='__main__':main()
