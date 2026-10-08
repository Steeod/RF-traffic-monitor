# Release publishing procedure

Maintainer instructions for publishing RF Traffic Monitor updates.

Repository: https://github.com/Steeod/RF-traffic-monitor

For application downloads and installation instructions, see README.md
and the relevant GitHub release.

## 1. Prepare the source changes

- Update the application version and user-facing documentation.
- Include all required source files and application assets.
- Review changes against the current main branch before replacing files.
- Exclude private configuration, receiver serials, personal coordinates,
  logs, captures, downloaded maps and local build directories.
- Preserve project and third-party licenses, credits and notices.
- Run the checks appropriate to the changes.
- Review and merge the source changes before tagging a release.

## 2. Build and verify the packages

For version 0.10.2, the user-facing release assets are:

- RFTrafficMonitor-0.10.2-Setup-win64.exe
- RFTrafficMonitor-0.10.2-update.zip
- SHA256SUMS-0.10.2.txt

Use the corresponding version number for future releases.

The source-update ZIP is for updating repository files.
It must not be presented as the application update package.

Before uploading:

- Verify that the Setup EXE extracts into a new or empty folder.
- Verify that the update ZIP includes every required replacement file.
- Test that updating preserves existing settings, maps and logs.
- Check that packages contain neutral defaults and no personal data.
- Verify the executable and browser icons.
- Generate checksums after the final build.
- Confirm that the checksums match the exact files being uploaded.
- Record automated checks and hardware tests separately.
- State clearly when real receiver operation remains unconfirmed.

## 3. Review third-party distribution requirements

These checks require supporting evidence. This document does not
establish that every distribution requirement has been satisfied.

- Record exact dependency versions, immutable source references,
  download URLs and SHA-256 values.
- Verify correspondence between distributed binaries and their source.
  A matching download hash alone does not establish that correspondence.
- Supply applicable corresponding source and build information for
  GPL components and their supporting libraries.
- Review source availability for bundled usbipd-win packages.
- Preserve upstream LICENSE, COPYING, COPYRIGHT and NOTICE files,
  including notices for libacars and native runtime dependencies.
- Establish redistribution terms before bundling third-party driver
  binaries. A digital signature alone does not establish permission.
- Keep Npcap installation separate.
- Keep EOX imagery optional and retain its applicable
  non-commercial/share-alike terms.
- Retain OpenStreetMap attribution and applicable ODbL terms.
- Describe the project-authored license separately from licenses
  covering third-party software and map data.

Consult THIRD-PARTY.md and LICENSE-STATUS.md for dependency details.

## 4. Create the GitHub release

1. Open the repository's Releases page.
2. Choose Draft a new release.
3. Create a new version tag on the commit containing the reviewed changes.
   Example: v0.10.3-beta.1.
4. Enter a title identifying the version and its main change.
5. Write release notes covering changes, installation, updating,
   validation and known limitations.
6. Attach the final Setup EXE, application update ZIP and checksum file.
7. Select This is a pre-release for beta versions.
8. Save the draft while completing package and distribution checks.
9. Publish when the release is ready.

Keep maintainer upload instructions out of user-facing release notes.

Use a new version or beta tag for subsequent builds.
Record package changes rather than silently replacing published binaries.

## 5. Verify after publication

- Open the public release page and test its download links.
- Check the published filenames and downloaded file checksums.
- Confirm that release notes reference assets actually attached.
- Confirm that README.md links to the intended release.
- Ensure that the tagged source includes the assets and build changes
  used for the published packages.
- Add a clear link to the newer release in older release notes when useful.

## References

- [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub large file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [EOX imagery terms](https://cloudless.eox.at/license-non-commercial)
