// Uses the original VRS parser, without starting VRS's web server or online services.
using System;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using InterfaceFactory;
using VirtualRadar.Interface.BaseStation;
using Newtonsoft.Json;
class VrsBridge {
    static void Main(string[] args) {
        VirtualRadar.Library.Implementations.Register(Factory.Singleton);
        var parser = Factory.Resolve<IBaseStationMessageTranslator>();
        if (args.Length > 0 && args[0] == "--stdin") {
            string line;
            while ((line = Console.ReadLine()) != null) Emit(parser, line);
            return;
        }
        while (true) {
            try {
                using (var socket = new TcpClient("127.0.0.1", 30003))
                using (var input = new StreamReader(socket.GetStream())) {
                    string line;
                    while ((line = input.ReadLine()) != null) Emit(parser, line);
                }
            } catch (IOException) { } catch (SocketException) { }
            Thread.Sleep(500);
        }
    }
    static void Emit(IBaseStationMessageTranslator parser, string line) {
        try {
            var message = parser.Translate(line, null);
            if (message != null && !String.IsNullOrEmpty(message.Icao24)) {
                Console.WriteLine(JsonConvert.SerializeObject(message));
                Console.Out.Flush();
            }
        } catch (Exception error) { Console.Error.WriteLine(error.Message); }
    }
}
