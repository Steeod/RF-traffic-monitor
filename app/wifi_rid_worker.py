"""Passive ASTM Remote ID Wi-Fi Beacon capture through an installed Npcap."""
import argparse,base64,ctypes as C,json,os,sys,time

PCAP_ERRBUF_SIZE=256
DLT_IEEE802_11=105
DLT_IEEE802_11_RADIO=127

class PcapIf(C.Structure):pass
PcapIf._fields_=[('next',C.POINTER(PcapIf)),('name',C.c_char_p),('description',C.c_char_p),('addresses',C.c_void_p),('flags',C.c_uint)]
class Timeval(C.Structure):_fields_=[('sec',C.c_long),('usec',C.c_long)]
class PcapHeader(C.Structure):_fields_=[('ts',Timeval),('caplen',C.c_uint),('length',C.c_uint)]

class GUID(C.Structure):_fields_=[('d1',C.c_uint32),('d2',C.c_uint16),('d3',C.c_uint16),('d4',C.c_ubyte*8)]
class WLAN_INTERFACE_INFO(C.Structure):_fields_=[('guid',GUID),('description',C.c_wchar*256),('state',C.c_uint32)]
class DOT11_SSID(C.Structure):_fields_=[('length',C.c_uint32),('ssid',C.c_ubyte*32)]
class WLAN_RATE_SET(C.Structure):_fields_=[('length',C.c_uint32),('rates',C.c_uint16*126)]
class WLAN_BSS_ENTRY(C.Structure):
    _fields_=[('ssid',DOT11_SSID),('phy_id',C.c_uint32),('bssid',C.c_ubyte*6),('bss_type',C.c_uint32),
              ('phy_type',C.c_uint32),('rssi',C.c_long),('quality',C.c_uint32),('reg_domain',C.c_ubyte),
              ('beacon_period',C.c_uint16),('timestamp',C.c_uint64),('host_timestamp',C.c_uint64),
              ('capability',C.c_uint16),('frequency',C.c_uint32),('rates',WLAN_RATE_SET),
              ('ie_offset',C.c_uint32),('ie_size',C.c_uint32)]

def library():
    candidates=[os.path.join(os.environ.get('SystemRoot',r'C:\Windows'),'System32','Npcap','wpcap.dll'),'wpcap.dll']
    for candidate in candidates:
        try:
            folder=os.path.dirname(candidate)
            if folder and hasattr(os,'add_dll_directory'):os.add_dll_directory(folder)
            return C.WinDLL(candidate)
        except OSError:pass
    raise RuntimeError('Npcap (wpcap.dll) was not found. Install Npcap with raw 802.11 support.')

def api(lib):
    lib.pcap_findalldevs.argtypes=[C.POINTER(C.POINTER(PcapIf)),C.c_char_p];lib.pcap_findalldevs.restype=C.c_int
    lib.pcap_freealldevs.argtypes=[C.POINTER(PcapIf)]
    lib.pcap_create.argtypes=[C.c_char_p,C.c_char_p];lib.pcap_create.restype=C.c_void_p
    lib.pcap_set_snaplen.argtypes=[C.c_void_p,C.c_int];lib.pcap_set_timeout.argtypes=[C.c_void_p,C.c_int]
    lib.pcap_set_promisc.argtypes=[C.c_void_p,C.c_int];lib.pcap_set_rfmon.argtypes=[C.c_void_p,C.c_int]
    lib.pcap_activate.argtypes=[C.c_void_p];lib.pcap_datalink.argtypes=[C.c_void_p];lib.pcap_datalink.restype=C.c_int
    lib.pcap_next_ex.argtypes=[C.c_void_p,C.POINTER(C.POINTER(PcapHeader)),C.POINTER(C.POINTER(C.c_ubyte))];lib.pcap_next_ex.restype=C.c_int
    lib.pcap_geterr.argtypes=[C.c_void_p];lib.pcap_geterr.restype=C.c_char_p;lib.pcap_close.argtypes=[C.c_void_p]

def adapters(lib):
    head=C.POINTER(PcapIf)();err=C.create_string_buffer(PCAP_ERRBUF_SIZE)
    if lib.pcap_findalldevs(C.byref(head),err):raise RuntimeError(err.value.decode(errors='replace'))
    out=[];p=head
    while p:
        d=p.contents;out.append({'id':d.name.decode(errors='replace'),'description':(d.description or b'').decode(errors='replace')});p=d.next
    lib.pcap_freealldevs(head);return out

def frames(packet,link):
    if link==DLT_IEEE802_11_RADIO:
        if len(packet)<4:return
        offset=int.from_bytes(packet[2:4],'little')
    elif link==DLT_IEEE802_11:offset=0
    else:return
    f=packet[offset:]
    if len(f)<36:return
    frame_control=int.from_bytes(f[:2],'little');subtype=(frame_control>>4)&15;kind=(frame_control>>2)&3
    if kind!=0 or subtype not in (5,8):return
    address=f[10:16].hex().upper();pos=36
    while pos+2<=len(f):
        eid,length=f[pos],f[pos+1];pos+=2;value=f[pos:pos+length];pos+=length
        if len(value)!=length:break
        if eid==221 and len(value)>=29 and value[:4]==b'\xfa\x0b\xbc\x0d':
            yield {'address':address,'data':base64.b64encode(value[4:]).decode(),'transport':'wifi'}

def vendor_messages(ies,address,rssi=None):
    pos=0
    while pos+2<=len(ies):
        eid,length=ies[pos],ies[pos+1];pos+=2;value=ies[pos:pos+length];pos+=length
        if len(value)!=length:break
        if eid==221 and len(value)>=29 and value[:4]==b'\xfa\x0b\xbc\x0d':
            yield {'address':address,'rssi':rssi,'data':base64.b64encode(value[4:]).decode(),'transport':'wifi'}

def wlan_interfaces():
    wlan=C.WinDLL('wlanapi.dll');handle=C.c_void_p();version=C.c_uint32()
    wlan.WlanOpenHandle.argtypes=[C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32),C.POINTER(C.c_void_p)];wlan.WlanOpenHandle.restype=C.c_uint32
    wlan.WlanEnumInterfaces.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p)];wlan.WlanEnumInterfaces.restype=C.c_uint32
    wlan.WlanScan.argtypes=[C.c_void_p,C.POINTER(GUID),C.c_void_p,C.c_void_p,C.c_void_p];wlan.WlanScan.restype=C.c_uint32
    wlan.WlanGetNetworkBssList.argtypes=[C.c_void_p,C.POINTER(GUID),C.c_void_p,C.c_uint32,C.c_bool,C.c_void_p,C.POINTER(C.c_void_p)];wlan.WlanGetNetworkBssList.restype=C.c_uint32
    wlan.WlanFreeMemory.argtypes=[C.c_void_p];wlan.WlanCloseHandle.argtypes=[C.c_void_p,C.c_void_p]
    if wlan.WlanOpenHandle(2,None,C.byref(version),C.byref(handle)):raise RuntimeError('Could not open the Windows WLAN API.')
    listing=C.c_void_p()
    try:
        if wlan.WlanEnumInterfaces(handle,None,C.byref(listing)):raise RuntimeError('No Wi-Fi interfaces were found.')
        count=C.c_uint32.from_address(listing.value).value;base=listing.value+8
        # Copy each item: WlanFreeMemory invalidates views into the returned list.
        return wlan,handle,[WLAN_INTERFACE_INFO.from_buffer_copy(C.string_at(base+i*C.sizeof(WLAN_INTERFACE_INFO),C.sizeof(WLAN_INTERFACE_INFO))) for i in range(count)]
    finally:
        if listing:wlan.WlanFreeMemory(listing)

def windows_scan(check=False):
    wlan,handle,interfaces=wlan_interfaces()
    try:
        if not interfaces:raise RuntimeError('No active Windows Wi-Fi adapter is available.')
        print(json.dumps({'status':'ready','backend':'windows-wlan','interfaces':[x.description for x in interfaces]}),flush=True)
        if check:return
        seen={}
        while True:
            for interface in interfaces:
                wlan.WlanScan(handle,C.byref(interface.guid),None,None,None)
            time.sleep(3)
            for interface in interfaces:
                listing=C.c_void_p()
                if wlan.WlanGetNetworkBssList(handle,C.byref(interface.guid),None,3,False,None,C.byref(listing)):continue
                try:
                    count=C.c_uint32.from_address(listing.value+4).value;base=listing.value+8
                    for i in range(count):
                        addr=base+i*C.sizeof(WLAN_BSS_ENTRY);entry=WLAN_BSS_ENTRY.from_address(addr)
                        if entry.ie_size>65535:continue
                        ies=C.string_at(addr+entry.ie_offset,entry.ie_size);mac=bytes(entry.bssid).hex().upper()
                        for message in vendor_messages(ies,mac,entry.rssi):
                            key=(mac,message['data'])
                            if time.time()-seen.get(key,0)>2:print(json.dumps(message),flush=True);seen[key]=time.time()
                finally:wlan.WlanFreeMemory(listing)
            cutoff=time.time()-300;seen={k:v for k,v in seen.items() if v>cutoff}
    finally:wlan.WlanCloseHandle(handle,None)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--list',action='store_true');parser.add_argument('--check');parser.add_argument('--wlan-scan',action='store_true');parser.add_argument('--check-wlan',action='store_true');parser.add_argument('adapter',nargs='?');args=parser.parse_args()
    try:
        if args.wlan_scan or args.check_wlan:windows_scan(args.check_wlan);return
        lib=library();api(lib)
        if args.list:print(json.dumps({'status':'adapters','adapters':adapters(lib)}));return
        name=(args.check or args.adapter or '').encode();err=C.create_string_buffer(PCAP_ERRBUF_SIZE);handle=lib.pcap_create(name,err)
        if not handle:raise RuntimeError(err.value.decode(errors='replace') or 'Failed to open the adapter.')
        try:
            lib.pcap_set_snaplen(handle,4096);lib.pcap_set_timeout(handle,500);lib.pcap_set_promisc(handle,1)
            rfmon=lib.pcap_set_rfmon(handle,1);activated=lib.pcap_activate(handle)
            if activated<0:raise RuntimeError((lib.pcap_geterr(handle) or b'Npcap activate failed').decode(errors='replace'))
            link=lib.pcap_datalink(handle)
            if link not in (DLT_IEEE802_11,DLT_IEEE802_11_RADIO):
                raise RuntimeError('The driver returned Ethernet frames instead of raw 802.11. Monitor mode is not active.')
            print(json.dumps({'status':'ready','monitor_request':rfmon==0,'linktype':link}),flush=True)
            if args.check:return
            header=C.POINTER(PcapHeader)();data=C.POINTER(C.c_ubyte)()
            while True:
                result=lib.pcap_next_ex(handle,C.byref(header),C.byref(data))
                if result==1:
                    packet=C.string_at(data,header.contents.caplen)
                    for message in frames(packet,link):print(json.dumps(message),flush=True)
                elif result<0:raise RuntimeError((lib.pcap_geterr(handle) or b'Npcap capture stopped').decode(errors='replace'))
        finally:lib.pcap_close(handle)
    except Exception as error:
        print(json.dumps({'status':'error','error':str(error)}),flush=True);sys.exit(1)
if __name__=='__main__':main()
