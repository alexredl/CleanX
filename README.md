# CleanX: LaserLab cleaning reminder

CleanX reminds us once a month to clean the LaserLab, and it doesn't take "later" for an answer.

When the last cleaning is longer ago than the configured interval (30 days by default), CleanX covers **every connected monitor** with a
picture of a hopelessly messy laser lab. The screen shows:

- a **headline of the day**, a different joke every day (*"Heisenberg is uncertain where the floor is."*)
- when the lab was **last cleaned**, with a live counter (*"63 days 03 h 02 min 45 s ago"*)
- two buttons:

| Button       | What it does                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------ |
| **Cleaned!** | Writes the current date/time into `clean_book.log` and closes. Next reminder in `IntervalDays`.  |
| **Dismiss**  | Closes. The reminder comes back tomorrow (or after `SnoozeMinutes`, see [Configuration](#configuration)). |

While the reminder is shown, **Alt+Tab, Alt+F4, Alt/Ctrl+Esc and the Windows key are blocked**.
Windows doesn't let any program block Ctrl+Alt+Del, so that's the emergency exit.

`CleanX.exe` is a small standalone program (~800 KB). It needs no Python and no installation, and the
background picture is built into it.

---

## Setup

1. **Get `CleanX.exe`.** Use the one in this folder, or rebuild it with `build.bat` (see [Building](#building)).
2. **Double-click `install_scheduler.bat`.** This creates the Task Scheduler task *"Cleaning LaserLab"* for
   the current user. No admin rights are needed. The task starts CleanX **every 15 minutes and at logon**.
   CleanX exits immediately unless the reminder is due.
3. **Adjust `CleanX.ini`** if you like (see [Configuration](#configuration)). Changes take effect at the next
   check. You don't need to re-run the setup.
4. **Test it** with `CleanX.exe --force`, which shows the reminder right now.
5. Done <3

Options for `setup_scheduler.ps1` (the script behind the `.bat` files):

```powershell
.\setup_scheduler.ps1                      # install / update the task
.\setup_scheduler.ps1 -IntervalMinutes 5   # check every 5 minutes instead of 15
.\setup_scheduler.ps1 -Uninstall           # remove the task
```

> Running the setup again replaces an existing *"Cleaning LaserLab"* task, including one created by hand
> with the old instructions.

<details>
<summary>Manual setup (without the script)</summary>

1. Open the **Task Scheduler** (*Aufgabenplanung*).
2. Under *Actions* (*Aktionen*), click **Create Basic Task** (*Einfache Aufgabe erstellen*).
3. Name it "Cleaning LaserLab".
4. Trigger: **daily**. Afterwards open the task's properties and, under *Triggers → Edit*, tick
   *Repeat task every 15 minutes* for *indefinitely*.
5. Action: **Start a program** (*Programm starten*), then choose `C:\...\CleanX\CleanX.exe`.
6. Finish the wizard.

</details>

---

## Configuration

### `CleanX.ini`: when the reminder may pop up

CleanX creates this file with default values on its first run.

```ini
[Reminder]
; Earliest time of day the reminder may pop up (24h format HH:MM)
Time=07:00

; Latest time of day the reminder may pop up (HH:MM)
EndTime=23:59

; Days of the week on which it may pop up: Mon,Tue,Wed,Thu,Fri,Sat,Sun  (or: All)
Days=Mon,Tue,Wed,Thu,Fri

; The reminder is due this many days after the last cleaning
; (cleaned on 30.11. with IntervalDays=30 -> due again on 30.12.)
IntervalDays=30

; After pressing "Dismiss": minutes until it pops up again (0 = not before tomorrow)
SnoozeMinutes=0
```

- `IntervalDays` counts from the date of the last **Cleaned!**. If the due day falls on a day that isn't in
  `Days` (for example a Sunday), the reminder appears on the next allowed day instead.
- A window across midnight also works, for example `Time=22:00` and `EndTime=06:00`.
- Set `SnoozeMinutes=60` if *Dismiss* should only buy one hour of peace.
- Put comments on their own line, starting with `;`, not after a value.

To check what CleanX would do right now, and why, run it from a terminal:

```
> CleanX.exe --status

Show reminder now?  YES - the reminder is due.

Config:   Time=07:00  EndTime=23:59  Days=Mon,Tue,Wed,Thu,Fri  IntervalDays=30  SnoozeMinutes=0
Logbook:  20 cleanings, last: 63 days  03 h  02 min  45 s  ago
Next due: due since Wed 07.10.2026, from 07:00
Today:    "That's not cable management. That's spaghetti."
Tomorrow: "Lost your Allen key? Clean the lab and find it!"
```

### `messages.txt`: the headlines

There's one headline per line (UTF-8), and lines starting with `#` are ignored. A different headline is
picked every day, in shuffled order. It stays the same all day and on all monitors. Add your own, or
delete the ones you don't like. Delete the whole file to get the built-in list back.

### Background picture

Put a `background.jpg` or `background.png` next to `CleanX.exe` to replace the built-in picture. It's
scaled to fill each monitor.

---

## Command line

| Command                                   | Effect                                                         |
| ----------------------------------------- | -------------------------------------------------------------- |
| `CleanX.exe`                              | Normal run: shows the reminder only if it's due                |
| `CleanX.exe --force`                      | Shows the reminder right now, ignoring all rules               |
| `CleanX.exe --status`                     | Prints whether the reminder is due, and why                    |
| `CleanX.exe --preview out.png 1920 1080`  | Renders the screen into a PNG without opening any window       |
| `--day N`                                 | Uses the headline of *N* days from today (for testing)         |

---

## Files

| File / folder                                 | Purpose                                                              |
| --------------------------------------------- | -------------------------------------------------------------------- |
| `CleanX.exe`                                  | The program                                                          |
| `CleanX.ini`                                  | Settings: when the reminder may appear                               |
| `messages.txt`                                | The daily headlines                                                  |
| `clean_book.log`                              | The logbook, one line per cleaning (`YYYY-MM-DD HH:MM:SS`)           |
| `CleanX.state`                                | Remembers the last *Dismiss* (created automatically)                 |
| `install_scheduler.bat` / `uninstall_scheduler.bat` | Set up or remove the Task Scheduler task (double-click)        |
| `setup_scheduler.ps1`                         | The PowerShell script behind the two `.bat` files                    |
| `build.bat`                                   | Rebuilds `CleanX.exe`                                                |
| `src/`                                        | C++ source code and resources                                        |
| `res/messy_lab.jpg`                           | Background picture (embedded into the exe at build time)             |
| `tools/make_background.py`                    | Draws `res/messy_lab.jpg` from code                                  |
| `tools/make_icon.py`                          | Draws the program icon (`icons/cleanx.ico` + PNGs) from code         |
| `icons/`                                      | Program icon                                                         |
| `legacy_python/`                              | The old Python/PyQt6 version (not used anymore)                      |

---

## Building

You need **Visual Studio** (Community is fine) with the **"Desktop development with C++"** workload.
Then double-click `build.bat`, or run it in a terminal. It finds the compiler by itself, and the result
is `CleanX.exe` in this folder.

To change the background picture, edit `tools/make_background.py` and run it, then run `build.bat`.
The script needs Pillow (`pip install pillow`). Changing `SEED` gives a different arrangement of the mess.

The same goes for the program icon: edit and run `tools/make_icon.py`, then run `build.bat`.

```
python tools\make_background.py
python tools\make_icon.py
build.bat
```

All artwork (background and icon) is drawn by these scripts, so it contains no third-party images.

---

## Uninstall

1. Double-click `uninstall_scheduler.bat`, or delete the task *"Cleaning LaserLab"* in the Task Scheduler
   (*Löschen* in the *Ausgewähltes Element* panel).
2. Delete this `CleanX` folder.
3. Done :(
