# LocalLink

**English** | [简体中文](README.md)

LocalLink is a device-to-device transfer tool that never touches the public internet. Both Windows and Android can act as a LAN host, so phones and computers discover each other directly and exchange files, images, links and plain text.

## Deliverables

- Windows portable single file: `dist/LocalLink-Portable.exe`
- Windows 2.4.4 single file: `dist/2.4.4/LocalLink-Portable.exe`
- Android 2.4.4 APK: `dist/2.4.4/LocalLink-Android-2.4.4-debug.apk`

Both the Windows EXE and the APK are currently unsigned / debug-signed builds intended for personal device testing. Configure a code signing certificate and an Android release keystore before distributing them publicly.

## Implemented features

### Transfer core

- Send text, links, single files and multiple files
- Large files are streamed to disk instead of being buffered entirely in server memory
- SHA-256 integrity check with cleanup of failed temporary files
- Resumable downloads via HTTP Range
- Transfer history with search, type filtering, full-text reading, copy, preview, open, download and delete
- Long text collapses to a three-line summary; filenames and action areas wrap responsively instead of overflowing the page
- On Windows, Word, Excel and PowerPoint files can be converted to cached PDFs for in-browser preview when LibreOffice is installed
- 6-digit per-process pairing code
- Filename sanitization and directory traversal protection
- Local storage item count and disk usage statistics

### Network

- Bind to a specific real Wi-Fi/Ethernet IPv4, avoiding VPN/TUN/VMware adapters
- UDP multicast LocalLink node discovery
- Active scan of the current `/24` subnet to list reachable LocalLink devices
- Diagnostics for VPN, gateway and LAN blocking
- Android USB/ADB reverse port forwarding when a VPN such as ProtonVPN blocks LAN traffic
- No accounts, no cloud, no internet dependency

### Windows EXE

- The EXE is the default transfer host: double-click it and it detects the LAN address and starts listening on `53317` immediately
- Default pairing code is `123456`; there is no need to run `python -m locallink` separately
- Embedded Chromium transfer console, so no extra browser window is required
- "Open" resolves a local file strictly by record ID and hands it to the default Windows application; a web page cannot pass an arbitrary path
- Save dialog for file downloads
- Closing the window stops the service and cleans up ADB reverse mappings

### Android app

- Android 2.4 ships a built-in local host and its own inbox, so it no longer depends on Windows
- The native device home page is compressed to a single screen; the manual connection form expands on demand
- The inbox uses a "Home / Send / Records / Devices" bottom navigation instead of stacking every feature vertically
- A unified LocalLink blue app icon (shared by the Windows EXE and the Android app)
- Share into LocalLink from the gallery, a file manager or a browser via "Share → LocalLink", then pick the receiving device
- QR codes are generated fully offline; scanning with the phone camera opens the LAN connection address
- Devices you have connected to can be saved as trusted-device shortcuts (stored locally; this is not the encrypted identity authentication planned for 3.0)
- Text, images, audio, video, PDFs and common text files can be previewed directly
- Word, Excel and PowerPoint files can be downloaded into the app cache and opened by a compatible app
- The APK is installed only after package verification, the LocalLink risk confirmation and the Android system install confirmation; silent installation is not supported
- Connections go through service identification, pairing-code authentication and trusted device ID verification; when the identity changes, the phone is prompted to re-trust after authentication instead of blocking the upgraded device forever
- Trusted devices are keyed by a stable ID, so the address refreshes automatically after a Wi-Fi reconnect or a DHCP change, while each device keeps its own pairing code
- When recovering from a long offline period, the connection pre-check retries a limited number of times and distinguishes "service not responding yet" from "pairing failed", avoiding false reports about being on different subnets
- After a successful send from the system share sheet, the native result page stays on screen so you can keep sending, view records or return to the device list
- Android shows a system notification when content arrives
- On Windows, closing the main window minimizes the app to the system tray, where it keeps receiving content
- Windows shows a tray notification when text or a file arrives
- The Windows tray menu can open or change the local receiving directory
- A foreground service keeps the host online and shows an ongoing notification
- Two phones on the same Wi-Fi can send to each other directly in both directions
- The last host address and pairing code are remembered
- Connections are forced onto the phone's Wi-Fi network, preventing a phone-side VPN or mobile data from misrouting traffic
- You can paste a full share link, and the computer's health endpoint is checked before the page opens
- Both LAN and USB connection modes
- Android system file picker with multi-file selection
- Downloads land in the system Downloads folder via DownloadManager
- Connection failure messages, refresh and a way back to the connection page
- Automatically adapts to the responsive LocalLink transfer UI
- The "Network Dawn Control Cabin" dark visual system: the desktop emphasizes a single-screen overview, while mobile keeps four bottom-navigation pages
- Low-interference connection, success and error sounds that can be turned off in both UIs, with the setting remembered
- Background signal light bands linked to connection state; static effects are used automatically when the system disables animation

Received content is stored in the receiving device's own `LocalLinkData` directory. Transfer records clearly show the sender and the receiver; text can be copied, files can be downloaded to the system Downloads folder, and records support search, filtering and deletion.

## Using the Windows EXE

Run:

```text
dist\LocalLink-Portable.exe
```

There is no mode to select and no background command to run. By the time the main window appears the service is already running, and the phone only needs the `IP:port` and pairing code shown on the EXE page.

The first time a new EXE runs, Windows asks for administrator approval once, used to create the `LocalLink LAN TCP 53317` inbound rule. That rule only allows access from the local subnet and is not open to the internet. You must approve it, otherwise phones cannot connect. The EXE listens on all local IPv4 interfaces but only advertises the auto-detected real LAN address, so switching a VPN or virtual adapter will not make the service unreachable.

If you previously denied the prompt, run this manually in an elevated PowerShell:

```powershell
netsh advfirewall firewall add rule name="LocalLink LAN TCP 53317" dir=in action=allow protocol=TCP localport=53317 remoteip=localsubnet profile=any enable=yes
```

For USB/ADB reverse port mode, the source command `python -m locallink --usb --code 123456` is still available.

## Using the Android app

Install:

```powershell
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

Opening the app automatically starts "My device inbox", and the page shows the phone's Wi-Fi IP and pairing code. Nearby phones or computers that have LocalLink installed and open appear in the device list automatically; you can also tap "Scan" to actively probe the current subnet.

Phone-to-phone transfer:

1. Connect both phones to the same Wi-Fi and open LocalLink on each.
2. On phone A, pick phone B in "Nearby devices".
3. The content is saved directly into phone B's local inbox.
4. On phone B, open "My device inbox" to copy text, download files or manage records.

Manual connection example:

```text
Host: 192.168.1.82:53317
Pairing code: 123456
```

On Android 2.4, port `53317` is used by default for the phone's own inbox. USB/ADB reverse port mode is a source-compatibility mode; stop the Android LocalLink foreground service first to avoid a port conflict. LAN transfers do not require ADB.

### What's new in LocalLink 2.4

1. Tap "QR code" on the home page so a device on the same LAN can scan and connect.
2. Tap "Trust device" to save that address and pairing code on the current device for a quick next connection.
3. Record previews support text, images, audio, video, PDF, Markdown, JSON and CSV.
4. Android can receive text, links, a single file or multiple files from the system share sheet.
5. On Windows, clicking the close button moves the service to the system tray; the tray menu can open or change the receiving directory, and only "Quit and stop service" shuts the host down.
6. Long text uses a three-line summary plus a dedicated full-text reader; the full text can be copied or saved as TXT.
7. Windows can preview Office files after converting them to PDF; Android opens Office files with a compatible system app.
8. The APK enters the Android permission and system install confirmation flow only after the user taps "Install".
9. The connection flow checks the LocalLink identity first, then authenticates the pairing code, then verifies the trusted device ID; if an upgrade or reinstall changed the identity, the phone asks for re-trust before continuing.
10. PC/Web and Android share a near-black, cobalt-blue and cyan signal system; mobile keeps four separate workspaces: home, send, records and devices.
11. Added restrained LAN signal background animation, button state feedback and optional sound effects, and the system "reduce motion" preference is respected.

The QR code feature uses QRCode.js, distributed offline with the program. It comes from davidshimjs/qrcodejs under the MIT License; the license text is at `locallink/static/qrcodejs.LICENSE`.

## Running from source

Requires Python 3.10+. The transfer host is stdlib only; the desktop console
additionally needs the packages in `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

```powershell
python -m locallink --list-interfaces
python -m locallink --interface 192.168.1.82 --code 123456
python -m locallink --usb --code 123456
python -m locallink.desktop
```

The default receiving directory is `LocalLinkData` next to the EXE.

## Building

Windows:

```powershell
python -m PyInstaller --noconfirm --clean LocalLink-Portable.spec
```

Android:

```powershell
cd android
gradle --no-daemon assembleDebug
```

`local.properties` in the Android project holds the local SDK path and applies only to the current development environment; regenerate it after moving to another machine.

## Testing

Python server (stdlib only, no pytest required):

```powershell
python -m unittest discover -s tests -v
```

Frontend state machine and UI model (requires Node.js):

```powershell
node tests/connection_state.test.mjs
node tests/web_ui.test.mjs
```

Android unit tests:

```powershell
cd android
gradle --no-daemon testDebugUnitTest
```

All three run automatically on push and pull requests via
[`.github/workflows/tests.yml`](.github/workflows/tests.yml).

See [protocol/protocol.md](protocol/protocol.md) for protocol details and security boundaries.

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before taking part.

Please do not disclose security vulnerabilities publicly; follow the private reporting process in [SECURITY.md](SECURITY.md).

## License

This project is open source under the [MIT License](LICENSE), copyright the LocalLink contributors.

The QR code feature uses [qrcodejs](https://github.com/davidshimjs/qrcodejs) (MIT License), distributed offline with the program; see `locallink/static/qrcodejs.LICENSE` for the license text.
