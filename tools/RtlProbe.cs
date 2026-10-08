using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;

// Must be compiled x86 and deployed beside dump1090's rtlsdr.dll.
class RtlProbe {
    [DllImport("rtlsdr.dll", CallingConvention=CallingConvention.Cdecl)] static extern uint rtlsdr_get_device_count();
    [DllImport("rtlsdr.dll", CallingConvention=CallingConvention.Cdecl)] static extern int rtlsdr_get_device_usb_strings(uint index, byte[] manufacturer, byte[] product, byte[] serial);
    [DllImport("rtlsdr.dll", CallingConvention=CallingConvention.Cdecl)] static extern int rtlsdr_open(out IntPtr handle, uint index);
    [DllImport("rtlsdr.dll", CallingConvention=CallingConvention.Cdecl)] static extern int rtlsdr_close(IntPtr handle);
    public class Device { public uint index; public string serial; }
    static List<Device> Devices() {
        var devices = new List<Device>();
        uint count = rtlsdr_get_device_count();
        Console.Error.WriteLine("RTL library enumerated {0} device(s).", count);
        for(uint i=0;i<count;i++) {
            byte[] manufacturer=new byte[256], product=new byte[256], serial=new byte[256];
            int result=rtlsdr_get_device_usb_strings(i,manufacturer,product,serial);
            if(result!=0) { Console.Error.WriteLine("USB strings unavailable at index {0}: {1}",i,result); continue; }
            int end=Array.IndexOf(serial,(byte)0); if(end<0)end=serial.Length;
            string value=Encoding.UTF8.GetString(serial,0,end);
            if(value.Length==0) { Console.Error.WriteLine("Empty USB serial at index {0}.",i); continue; }
            devices.Add(new Device { index=i, serial=value });
        }
        return devices;
    }
    static int Main(string[] args) {
        try {
            var devices=Devices();var json=new JavaScriptSerializer();
            if(args.Length==1 && args[0]=="--list") { Console.WriteLine(json.Serialize(devices)); return 0; }
            if(args.Length!=3 || args[0]!="--open")throw new Exception("Invalid probe arguments.");
            uint index=uint.Parse(args[1]);string serial=Encoding.UTF8.GetString(Convert.FromBase64String(args[2]));
            var matches=devices.FindAll(d=>d.serial==serial);
            if(matches.Count!=1 || matches[0].index!=index)throw new Exception("Receiver identity changed or is ambiguous. Reconnect and retry.");
            IntPtr handle;int status=rtlsdr_open(out handle,index);
            if(status!=0)throw new Exception("rtlsdr_open failed at index "+index+" (code "+status+"). Check WinUSB and close other SDR applications.");
            try { Console.WriteLine(json.Serialize(matches[0])); }
            finally { rtlsdr_close(handle); }
            return 0;
        } catch(Exception error) { Console.Error.WriteLine(error.ToString()); return 1; }
    }
}
