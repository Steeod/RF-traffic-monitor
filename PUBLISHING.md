# GitHub publication procedure

## Status

The folder already has a Git repository, with no commits and no remote at review
time. This preparation does not create a GitHub repository or publish anything.
Choose the GitHub owner, repository name and visibility when uploading.

The first upload should be source only. `.gitignore` excludes `appxxx/`,
`app.zip`, `dist/`, downloads, build outputs, runtime/vendor folders, receiver
configuration, logs and all generated location/map data. It preserves local
files. `app.zip` is about 190 MiB and the satellite database about 153 MiB;
both exceed GitHub's ordinary 100 MiB per-file limit.

## Before a public upload

1. Include the selected MIT `LICENSE` for project-authored code. Preserve
   the third-party exceptions documented in `LICENSE-STATUS.md` and all notices.
2. Review the candidate files for passwords, tokens, receiver serial numbers,
   precise personal locations, captures and unpublished material. The public
   example configuration uses neutral coordinates; `setup.ps1` creates the
   ignored local configuration selected by each user.
3. Review the source staging list and run the tests. Do not force-add ignored
   folders or upload the workspace ZIP.

## Upload using Git and the GitHub website

Run these commands in the project root with Git and Python 3.12 installed:

```powershell
if (!(Test-Path app/config.json)) { Copy-Item app/config.example.json app/config.json }
Push-Location tests
python -m unittest test_radar.ModelTests test_radar.ProcessTests -v
Pop-Location
git status --short
git add --dry-run .
# Inspect the list before staging.
git add .
git diff --cached --stat
git diff --cached --check
git diff --cached
```

For a fully provisioned local build, also run
`python -m unittest discover -s tests -v`; its binary/driver checks require the
ignored vendor dependencies. Check for oversized staged files (normally this
prints nothing):

```powershell
git ls-files | ForEach-Object {
    $candidateFile = Get-Item -LiteralPath $_
    if ($candidateFile.Length -gt 50MB) { $candidateFile | Select-Object FullName,Length }
}
```

Once the content is reviewed:

```powershell
git commit -m "Initial source import"
git branch -M main
```

Create an **empty** repository named `rf-traffic-monitor` on
[GitHub](https://github.com/new), select its visibility and do not initialize it
with a README, license or gitignore. A suitable GitHub description is:

> Multi-protocol SDR monitoring for aircraft, ships, drones and radiosondes on Windows.

Suggested repository topics: `sdr`, `ads-b`, `ais`, `acars`, `vdl2`, `hfdl`,
`remote-id`, `radiosonde`, `rtl-sdr`, `hackrf`, `windows`.

Replace OWNER below with the GitHub account or organization name:

```powershell
git remote add origin https://github.com/OWNER/rf-traffic-monitor.git
git push -u origin main
```

Authenticate through Git Credential Manager when prompted. Never put a token
in the URL or commit one. The commands above assume the currently absent
`origin`; if one has since been added, inspect `git remote -v` first.

Verify on GitHub that source, credits and notices are visible and that local
configuration, logs, duplicate app copies, executables and map databases are absent.

## Portable releases are a separate step

The guided `setup.ps1` produces a local portable bundle. It should still be
treated as a local build until the following release checks are completed before
attaching any ZIP to GitHub Releases:

- Verify exact binary/source version correspondence. Master/branch archive URLs
  in existing scripts are mutable; record immutable commits, retrieval URLs and
  SHA-256 values. A hash identifies bytes but does not prove a binary was built
  from a particular source archive.
- Supply the applicable corresponding source and build information for GPL
  components, including supporting libraries. Current source ZIP checks do not
  establish complete compliance. The WSL helper currently downloads usbipd-win's
  MSI without its corresponding source.
- Preserve all upstream license, copyright and NOTICE files, including libacars
  notices within xng and notices for native runtime dependencies. Packaging file
  filters need review so files named `COPYING` or `NOTICE` are not dropped.
- Remove Realtek/Microsoft Catalog driver binaries unless redistribution terms
  are established. A valid signature is not redistribution permission. Keep
  Npcap separately installed.
- Keep EOX imagery optional and clearly label its non-commercial/share-alike
  terms; retain OSM attribution and ODbL terms. Do not label the whole binary/data
  bundle as simply MIT or Apache.
- Build through `setup.ps1` in a clean checkout. The packager recreates its
  staging directory, but the generated ZIP intentionally contains the selected
  station configuration and offline map. Inspect the final archive, include
  project license/credits, run tests and test on a clean Windows machine before
  publishing it for other users.

## References

- [GitHub: adding locally hosted code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [GitHub: large file limits and release assets](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [EOX imagery terms](https://cloudless.eox.at/license-non-commercial)
- [usbipd-win 5.3.0 license](https://github.com/dorssel/usbipd-win/blob/v5.3.0/COPYING.md)
