// Uses the original VRS parser, without starting VRS's web server or online services.
using System;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using InterfaceFactory;
using VirtualRadar.Interface.BaseStation;
using Newtonsoft.Json;
class VrsBridge {
    static long lines, translated;
    static void Main(string[] args) {
        VirtualRadar.Library.Implementations.Register(Factory.Singleton);
        var parser = Factory.Resolve<IBaseStationMessageTranslator>();
        if (args.Length > 0 && args[0] == "--stdin") {
            string line;
            while ((line = Console.ReadLine()) != null) Emit(parser, line);
            return;
        }
        var diagnostics = new Timer(delegate { Console.Error.WriteLine("SBS health: lines=" + Interlocked.Read(ref lines) + " translated=" + Interlocked.Read(ref translated)); }, null, 30000, 30000);
        bool reported = false;
        while (true) {
            try {
                using (var socket = new TcpClient("127.0.0.1", 30003))
                using (var input = new StreamReader(socket.GetStream())) {
                    Console.Error.WriteLine("SBS connected to dump1090 on 127.0.0.1:30003"); reported = false;
                    string line;
                    while ((line = input.ReadLine()) != null) Emit(parser, line);
                    Console.Error.WriteLine("SBS connection closed by decoder");
                }
            } catch (IOException e) { if (!reported) Console.Error.WriteLine("SBS connection failed: " + e.Message); reported = true; }
              catch (SocketException e) { if (!reported) Console.Error.WriteLine("SBS connection failed: " + e.Message); reported = true; }
            GC.KeepAlive(diagnostics);
            Thread.Sleep(500);
        }
    }
    static void Emit(IBaseStationMessageTranslator parser, string line) {
        Interlocked.Increment(ref lines);
        try {
            var message = parser.Translate(line, null);
            if (message != null && !String.IsNullOrEmpty(message.Icao24)) {
                Console.WriteLine(JsonConvert.SerializeObject(message));
                Interlocked.Increment(ref translated);
                Console.Out.Flush();
            }
        } catch (Exception error) { Console.Error.WriteLine(error.Message); }
    }
}
