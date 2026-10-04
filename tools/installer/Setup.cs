using System;
using System.IO;
using System.IO.Compression;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;

class Setup : Form {
    TextBox folder = new TextBox();
    Button browse = new Button(), install = new Button();
    CheckBox drivers = new CheckBox();
    ProgressBar progress = new ProgressBar();
    Label status = new Label();
    bool busy;
    [STAThread] static int Main(string[] args) {
        if (args.Length == 2 && args[0] == "--extract") {
            try { Extract(args[1], delegate(int p) {}); return 0; }
            catch (Exception e) { File.WriteAllText(args[1] + ".error.txt", e.ToString()); return 1; }
        }
        Application.EnableVisualStyles(); Application.Run(new Setup()); return 0;
    }
    Setup() {
        Text = "RF Traffic Monitor Setup"; ClientSize = new Size(600, 260);
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        var title = new Label { Text = "Install RF Traffic Monitor", Left = 20, Top = 20, Width = 550, Font = new Font(SystemFonts.DefaultFont.FontFamily, 14) };
        var hint = new Label { Text = "Choose a new or empty folder. All application files stay in this folder.", Left = 20, Top = 55, Width = 560 };
        folder.SetBounds(20, 85, 455, 25);
        folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RFTrafficMonitor");
        browse.Text = "Browse..."; browse.SetBounds(485, 83, 95, 28);
        browse.Click += delegate { using (var d = new FolderBrowserDialog()) { d.Description = "Choose an empty installation folder"; if (d.ShowDialog() == DialogResult.OK) folder.Text = d.SelectedPath; } };
        drivers.Text = "Download USB / Alfa driver packages (internet required)"; drivers.Checked = true; drivers.SetBounds(20, 120, 560, 25);
        progress.SetBounds(20, 155, 560, 20); status.SetBounds(20, 180, 560, 30);
        install.Text = "Install"; install.SetBounds(460, 215, 120, 30); install.Click += Install;
        Controls.AddRange(new Control[] {title, hint, folder, browse, drivers, progress, status, install});
        FormClosing += delegate(object s, FormClosingEventArgs e) { if (busy) e.Cancel = true; };
    }
    void Install(object sender, EventArgs args) {
        string target;
        try { target = Path.GetFullPath(folder.Text); CheckTarget(target); }
        catch (Exception e) { MessageBox.Show(e.Message); return; }
        bool fetch = drivers.Checked;
        busy = true; install.Enabled = browse.Enabled = folder.Enabled = drivers.Enabled = false;
        var worker = new BackgroundWorker { WorkerReportsProgress = true };
        worker.ProgressChanged += delegate(object s, ProgressChangedEventArgs e) { progress.Value = e.ProgressPercentage; status.Text = e.UserState as string ?? "Extracting application files..."; };
        worker.DoWork += delegate {
            Extract(target, delegate(int p) { worker.ReportProgress(p); });
            if (fetch) {
                worker.ReportProgress(100, "Downloading and verifying drivers. This may take several minutes...");
                var pi = new ProcessStartInfo(Path.Combine(target, "runtime", "python.exe"), "\"" + Path.Combine(target, "download_drivers.py") + "\"");
                pi.WorkingDirectory = target; pi.UseShellExecute = false; pi.CreateNoWindow = true;
                using (var process = Process.Start(pi)) { process.WaitForExit(); if (process.ExitCode != 0) throw new Exception("Application extracted, but driver download failed. See driver-download.log and run Download Drivers.cmd to retry."); }
            }
        };
        worker.RunWorkerCompleted += delegate(object s, RunWorkerCompletedEventArgs e) {
            busy = false;
            if (e.Error != null) { status.Text = "Setup needs attention."; MessageBox.Show(e.Error.Message, Text); }
            else { status.Text = "Installed. Use Start.cmd to launch; select your station in Settings."; MessageBox.Show("Installation complete.\n\nLaunch with Start.cmd. Drivers are in vendor\\drivers.\nUSB driver installation requires selecting your device in Zadig.\nSet your station location and download its map in the application.", Text); }
            install.Text = "Close"; install.Enabled = true; install.Click -= Install; install.Click += delegate { Close(); };
        };
        worker.RunWorkerAsync();
    }
    static void CheckTarget(string target) {
        if (File.Exists(target) || (Directory.Exists(target) && Directory.GetFileSystemEntries(target).Length != 0))
            throw new IOException("Select a new or empty folder to preserve existing settings and files.");
    }
    static void Extract(string target, Action<int> report) {
        target = Path.GetFullPath(target); CheckTarget(target);
        string temp = Path.GetTempFileName();
        try {
            using (var input = File.OpenRead(Assembly.GetExecutingAssembly().Location)) {
                input.Seek(-48, SeekOrigin.End);
                var reader = new BinaryReader(input);
                if (System.Text.Encoding.ASCII.GetString(reader.ReadBytes(8)) != "RFTMSFX1") throw new IOException("Invalid setup payload.");
                long size = reader.ReadInt64(); byte[] expected = reader.ReadBytes(32);
                if (size <= 0 || size > input.Length - 48) throw new IOException("Invalid payload length.");
                input.Position = input.Length - 48 - size;
                using (var output = File.Create(temp)) {
                    byte[] buffer = new byte[1048576]; long remaining = size;
                    while (remaining > 0) { int n = input.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining)); if (n == 0) throw new EndOfStreamException(); output.Write(buffer, 0, n); remaining -= n; }
                }
                using (var sha = SHA256.Create()) using (var payload = File.OpenRead(temp)) {
                    if (BitConverter.ToString(sha.ComputeHash(payload)) != BitConverter.ToString(expected)) throw new IOException("Setup is damaged: payload checksum mismatch.");
                }
            }
            using (var payload = File.OpenRead(temp)) using (var zip = new ZipArchive(payload, ZipArchiveMode.Read)) {
                string prefix = target.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                foreach (var entry in zip.Entries) {
                    string path = Path.GetFullPath(Path.Combine(target, entry.FullName));
                    if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) || entry.FullName.Contains(":")) throw new IOException("Unsafe payload path.");
                }
                Directory.CreateDirectory(target); int done = 0;
                foreach (var entry in zip.Entries) {
                    string path = Path.GetFullPath(Path.Combine(target, entry.FullName));
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    using (var source = entry.Open()) using (var output = new FileStream(path, FileMode.CreateNew)) source.CopyTo(output);
                    report(++done * 100 / zip.Entries.Count);
                }
            }
        } finally { File.Delete(temp); }
    }
}
