# iTunes Dark Mode for Windows

A small Windows switch that gives the desktop iTunes library a dark background, light labels, charcoal missing-artwork tiles and a dark scrollbar. You can turn it off while iTunes is open.

**[Download the installer and source as a ZIP](https://github.com/GHayes1426/itunes-dark-mode/archive/refs/heads/main.zip)**

## Before you install

* Use 64-bit Windows and the classic Apple desktop installation of **iTunes 12.13.11.1 or 12.13.12.3**. In iTunes, open **Help → About iTunes** to check your version. The switch looks for `iTunes\iTunes.exe` under the 64-bit Program Files folder and checks its SHA-256 before enabling the theme.
* Open a local iTunes library at least once. The switch reads the current Windows account’s Apple preferences to locate its active `.itl` file.
* Allow internet access for setup. The installer uses 64-bit Python 3.13 with Tk. If Python is missing, setup tries to install it for your account using Windows Package Manager. It then installs the versions of Frida and Pillow listed in `requirements.txt`.
* The laptop tests used native Windows scaling at **125%**. A second PC, other native display scales, and physical sleep/wake still need testing. Windows popup menus use system colors.

## Verified executable

Compatibility is checked against the executable fingerprint. Both tested versions are supported.

| Desktop iTunes version | SHA-256 of iTunes.exe |
| --- | --- |
| 12.13.11.1 | `c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c` |
| 12.13.12.3 | `2370b094ec723529907ae133b291fa4df97f6e95c13f4dd600b78283a1ed1d52` |

Version 12.13.12.3 moved the drawing functions and changed the register used for rectangle geometry. The switch selects the verified drawing locations for each executable through `build_compat.py`. On the updated laptop, bounded rendering tests passed in Artists, Albums and Songs, including album-title contrast and placeholder artwork. Two GUI on/off cycles also passed. An unsupported-build message shows the version detected on your computer.

## Install and turn it on

1. Download the ZIP above. In File Explorer, right-click it and choose **Extract All**. Pick a folder you can write to and plan to keep, such as a folder under Documents.
2. Open the extracted folder containing **Install.cmd** and **Dark Mode.vbs**. Double-click **Install.cmd**. If Windows Package Manager asks you to approve installing Python, review its prompt. Let the console finish downloading the dependencies.
3. Setup opens a small **iTunes Dark Mode** window. Open iTunes with your usual library and select **Albums**, **Artists**, or **Songs**.
4. Check **Dark mode**. The status changes from **Connecting…** to **On** and the library repaints. Close the switch window with **X** whenever you want. Dark mode keeps running in the background.

For later sessions, double-click **Dark Mode.vbs** in the extracted folder. If the switch is already running, this brings its existing window back. Uncheck **Dark mode** to restore the original colors. Choose **Quit and turn off** to restore the colors and exit the background process. If you restart iTunes while the switch is enabled, it watches for the new process.

## How it works

The switch identifies the running iTunes process, verifies its executable against the tested build, and reads the selected library path. These checks matter because the drawing hooks depend on the rendering code in that particular executable.

After you enable the switch, it uses Frida to attach to iTunes in memory. A short discovery pass locates the Direct2D text drawing function. The theme then intercepts selected GDI+ and Direct2D drawing calls as iTunes paints its window. It recognizes library surfaces, labels and controls from their draw locations, colors and image signatures. For missing album art, it compares the entire placeholder bitmap with known fingerprints before changing how it appears.

The changes last for the active session. Turning the switch off removes the drawing hooks and requests a repaint. Music files, embedded art and library metadata are only represented on screen during this process. Local switch logs are written next to the launcher.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Setup cannot find Python or Windows Package Manager | Install **64-bit Python 3.13** for Windows with **Tcl/Tk** and the **Python launcher** selected, then run **Install.cmd** again. |
| Dependency download fails | Check your internet connection and rerun **Install.cmd** from the extracted folder. |
| Double-clicking the launcher produces no switch | Run **Install.cmd** again. If Windows Script Host is disabled, open a terminal in the extracted folder and run `diagnostics-venv\Scripts\pythonw.exe "Dark Mode.pyw"`. |
| Waiting for desktop iTunes or library window | Open the supported desktop iTunes installation, dismiss any startup dialog, and show its main library window. Use one iTunes instance and one theme switch. |
| Unsupported iTunes build | Check **Help → About iTunes**. Each executable build requires separate verification. |
| Waiting for library view | Open **Albums**, **Artists**, or **Songs** and restore the main window. |
| Windows DPI compatibility mode | Check the iTunes executable’s compatibility settings for a high-DPI scaling override. Use native scaling and restart iTunes. |
| Switch stops after changing libraries | Open the intended library and enable the switch again. For more detail, inspect the latest `switch-*.jsonl` file in the extracted folder. |

## Layout and control updates

The theme measures painted library surfaces and artwork bounds as iTunes redraws. Album labels follow the displayed artwork size, and Artists and Genres follow the current panel boundaries. The selected sidebar row is detected from the drawing buffer and receives a white background with black text. Sidebar icons use light colors on dark rows.

Search and playback controls repaint their dark backing when their state changes. The switch window has a DPI-scaled minimum size and can be widened to keep its title-bar controls accessible. Closing its window hides it while the theme continues. Reopening the launcher shows the existing switch.

The latest laptop checks covered a resized Artists column, Genres, Recently Added, Albums, Songs, clicked playback controls, album-title contrast, and two on/off cycles with clean restoration. These changes still require confirmation on the main PC. Native display scales beyond the tested 125% and Windows bitmap-scaled compatibility mode remain outside the verified coverage.

## Popup, hover and expanded-album fixes

Search and Up Next now theme their popup frame and text. The focused Search field also uses a dark native edit background with light text. The theme observes that control's color request; it does not replace its window procedure or intercept mouse clicks.

The smaller missing-artwork tile in expanded albums is also darkened using its complete bitmap fingerprint, preserving real cover images. Its dark appearance, visible note glyph and exact restoration were verified in the disposable library.

Expanded-album separators follow their current drawing position, including partial repaints. Artist-list and album-panel redraws preserve the other dark regions, and partially transparent album labels remain readable. Inactive selected track rows use a dark background, including the rounded CoreGraphics path painted when focus moves to Search. Caption buttons clear their backing before drawing hover frames so translucent highlights do not accumulate.

The November 9�10 laptop checks on **12.13.12.3 at 125% scaling** covered focused Search, populated Up Next, three distinct artist names, expanded albums, selected labels, playback hover, caption hover, one-click minimize/maximize, two On/Off cycles, and hiding/reopening/quitting the switch. The native Search brush was released and all instrumentation detached. The reported two-click behavior was not reproduced on the laptop and still needs confirmation on the main PC. These checks do not establish coverage for every popup state or display scale.

An already-open popup may retain its cached colors when dark mode is turned off. Dismiss and reopen Search or Up Next to refresh it.

## Update or uninstall

Open **Dark Mode.vbs** and choose **Quit and turn off** first. To update, extract a fresh download into a new folder and run its **Install.cmd**. To uninstall, choose **Quit and turn off**, then delete the extracted theme folder, including its local Python environment. A Python installation added by Windows Package Manager is separate and can be managed in Windows **Installed apps**.

## Source and developer tools

The root contains the installer, launcher, Tk switch, Python process checks and JavaScript drawing agents. Start with `theme_switch.py` for the attach, monitor and detach sequence, and `combined-agent.js` for the drawing components. The `tools` directory contains the development scripts, historical experiments and test runners. Run diagnostics only against a separate disposable test library. Some historical analysis scripts expect trace inputs captured during development.

Installation and theme activation were tested on the development laptop using its disposable library. The release switch reached **On**, returned to **Off**, detached its instrumentation and left iTunes responsive.
