# iTunes Dark Mode for Windows

A small Windows switch that gives the desktop iTunes library a dark background, light labels, charcoal missing-artwork tiles and a dark scrollbar. You can turn it off while iTunes is open.

**[Download the installer and source as a ZIP](https://github.com/GHayes1426/itunes-dark-mode/archive/refs/heads/main.zip)**

## Before you install

* Use 64-bit Windows and the classic Apple desktop installation of **iTunes 12.13.11.1**. In iTunes, open **Help → About iTunes** to check your version. The switch looks for `iTunes\iTunes.exe` under the 64-bit Program Files folder and checks its SHA-256 before enabling the theme.
* Open a local iTunes library at least once. The switch reads the current Windows account’s Apple preferences to locate its active `.itl` file.
* Allow internet access for setup. The installer uses 64-bit Python 3.13 with Tk. If Python is missing, setup tries to install it for your account using Windows Package Manager. It then installs the versions of Frida and Pillow listed in `requirements.txt`.
* The laptop tests used native Windows scaling at **125%**. A second PC, other native display scales, and physical sleep/wake still need testing. Windows popup menus use system colors.

## Install and turn it on

1. Download the ZIP above. In File Explorer, right-click it and choose **Extract All**. Pick a folder you can write to and plan to keep, such as a folder under Documents.
2. Open the extracted folder containing **Install.cmd** and **Dark Mode.vbs**. Double-click **Install.cmd**. If Windows Package Manager asks you to approve installing Python, review its prompt. Let the console finish downloading the dependencies.
3. Setup opens a small **iTunes Dark Mode** window. Open iTunes with your usual library and select **Albums**, **Artists**, or **Songs**.
4. Check **Dark mode**. The status changes from **Connecting…** to **On** and the library repaints. Keep the switch window open while using the theme.

For later sessions, double-click **Dark Mode.vbs** in the extracted folder. Uncheck **Dark mode** to restore the original colors, or close the switch and allow it to finish disconnecting. If you restart iTunes while the switch is enabled, it watches for the new process.

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

## Update or uninstall

Close the switch first. To update, extract a fresh download into a new folder and run its **Install.cmd**. To uninstall, delete the extracted theme folder, including its local Python environment. A Python installation added by Windows Package Manager is separate and can be managed in Windows **Installed apps**.

## Source and developer tools

The root contains the installer, launcher, Tk switch, Python process checks and JavaScript drawing agents. Start with `theme_switch.py` for the attach, monitor and detach sequence, and `combined-agent.js` for the drawing components. The `tools` directory contains the development scripts, historical experiments and test runners. Run diagnostics only against a separate disposable test library. Some historical analysis scripts expect trace inputs captured during development.

Installation and theme activation were tested on the development laptop using its disposable library. The release switch reached **On**, returned to **Off**, detached its instrumentation and left iTunes responsive.
