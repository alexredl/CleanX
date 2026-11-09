// CleanX - monthly LaserLab cleaning reminder
//
// Started every few minutes by the Task Scheduler. If the last cleaning is at least
// IntervalDays ago and CleanX.ini says it's a good moment, it covers EVERY connected
// monitor with a full-screen, always-on-top window showing the messy lab, a headline
// of the day (messages.txt), how long ago the lab was last cleaned, and two buttons:
//   "Cleaned!" -> appends a timestamp to clean_book.log and exits
//   "Dismiss"  -> remembers it in CleanX.state and exits (back after SnoozeMinutes / tomorrow)
// While shown, Alt+Tab, Alt+F4, Alt/Ctrl+Esc and the Windows key are blocked.
// (Ctrl+Alt+Del can never be blocked by an application - that's the emergency exit.)
//
// Command line:
//   CleanX.exe --force                     show the reminder right now, ignoring all rules
//   CleanX.exe --status                    print whether the reminder is due, and why
//   CleanX.exe --preview out.png [W H]     render the screen into a PNG (no windows)
//   --day N                                use the headline of N days from today
//
// Optional: put a "background.jpg" / "background.png" next to the exe to override the
// built-in picture.

#define NOMINMAX
#include <windows.h>
#include <objidl.h>
#include <algorithm>
using std::max;
using std::min;
#include <gdiplus.h>
#include <shlwapi.h>
#include <shellapi.h>

#include <cstdio>
#include <ctime>
#include <string>
#include <vector>

#include "resource.h"

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "shell32.lib")

using namespace Gdiplus;

// ------------------------------------------------------------------ state

static const wchar_t* kClassName = L"CleanXReminderWindow";
static const wchar_t* kLogName = L"clean_book.log";

struct Win {
    HWND hwnd = nullptr;
    int w = 0, h = 0;
    HBITMAP bg = nullptr;  // pre-scaled background for this monitor
    int hover = -1;        // button under the mouse (0 = cleaned, 1 = dismiss)
    int pressed = -1;
};

static std::vector<Win> g_wins;
static HINSTANCE g_inst;
static Bitmap* g_image = nullptr;
static IStream* g_imageStream = nullptr;
static HHOOK g_kbHook = nullptr;
static bool g_allowClose = false;
static bool g_rebuildPending = false;
static time_t g_lastShownSecond = 0;

static std::wstring g_logPath;
static bool g_hasLast = false;
static std::tm g_lastTm = {};
static time_t g_lastTime = 0;
static int g_cleanCount = 0;
static std::tm g_firstTm = {};
static bool g_logEndsWithNewline = true;

// ------------------------------------------------------------------ logbook

static std::wstring ExeDir() {
    wchar_t buf[MAX_PATH];
    DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
    std::wstring p(buf, n);
    size_t slash = p.find_last_of(L"\\/");
    return slash == std::wstring::npos ? L"." : p.substr(0, slash);
}

static bool ParseStamp(const char* s, std::tm& out) {
    int Y, M, D, h, m, sec;
    if (sscanf_s(s, "%d-%d-%d %d:%d:%d", &Y, &M, &D, &h, &m, &sec) != 6) return false;
    if (Y < 2000 || M < 1 || M > 12 || D < 1 || D > 31 || h < 0 || h > 23 || m < 0 || m > 59 || sec < 0 || sec > 60)
        return false;
    out = {};
    out.tm_year = Y - 1900;
    out.tm_mon = M - 1;
    out.tm_mday = D;
    out.tm_hour = h;
    out.tm_min = m;
    out.tm_sec = sec;
    out.tm_isdst = -1;
    return true;
}

// Reads the logbook (same format as the old Python version). Creates it if missing.
static void ReadLog() {
    FILE* f = nullptr;
    if (_wfopen_s(&f, g_logPath.c_str(), L"rb") != 0 || !f) {
        if (_wfopen_s(&f, g_logPath.c_str(), L"wb") == 0 && f) {
            fputs("Cleaning Logbook\n", f);
            fclose(f);
        }
        return;
    }
    std::string data;
    char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) data.append(buf, n);
    fclose(f);

    g_logEndsWithNewline = data.empty() || data.back() == '\n';
    size_t pos = 0;
    while (pos < data.size()) {
        size_t end = data.find('\n', pos);
        if (end == std::string::npos) end = data.size();
        std::string line = data.substr(pos, end - pos);
        std::tm tm;
        if (ParseStamp(line.c_str(), tm)) {
            if (g_cleanCount == 0) g_firstTm = tm;
            g_cleanCount++;
            g_lastTm = tm;
            g_hasLast = true;
        }
        pos = end + 1;
    }
    if (g_hasLast) {
        std::tm copy = g_lastTm;
        g_lastTime = mktime(&copy);
    }
}

static void AppendCleaning() {
    FILE* f = nullptr;
    if (_wfopen_s(&f, g_logPath.c_str(), L"ab") != 0 || !f) {
        MessageBoxW(nullptr, (L"Could not write to\n" + g_logPath).c_str(), L"CleanX", MB_ICONERROR | MB_TOPMOST);
        return;
    }
    time_t now = time(nullptr);
    std::tm t;
    localtime_s(&t, &now);
    if (!g_logEndsWithNewline) fputc('\n', f);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d\n", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min,
            t.tm_sec);
    fclose(f);
}

// ------------------------------------------------------------------ calendar helpers (H. Hinnant)

// days since 1970-01-01 for a civil date
static long long DaysFromCivil(int y, int m, int d) {
    y -= m <= 2;
    long long era = (y >= 0 ? y : y - 399) / 400;
    unsigned yoe = (unsigned)(y - era * 400);
    unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + (long long)doe - 719468;
}

// civil date for days since 1970-01-01
static void CivilFromDays(long long z, int& y, int& m, int& d) {
    z += 719468;
    long long era = (z >= 0 ? z : z - 146096) / 146097;
    unsigned doe = (unsigned)(z - era * 146097);
    unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    unsigned mp = (5 * doy + 2) / 153;
    d = (int)(doy - (153 * mp + 2) / 5 + 1);
    m = (int)(mp < 10 ? mp + 3 : mp - 9);
    y = (int)(yoe + era * 400 + (m <= 2));
}

static long long TodayNumber() {
    time_t now = time(nullptr);
    std::tm t;
    localtime_s(&t, &now);
    return DaysFromCivil(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday);
}

static long long LastCleaningDayNumber() {
    return DaysFromCivil(g_lastTm.tm_year + 1900, g_lastTm.tm_mon + 1, g_lastTm.tm_mday);
}

static int WeekdayOf(long long dayNumber) {  // 0 = Sunday (1970-01-01 was a Thursday)
    return (int)(((dayNumber % 7) + 7 + 4) % 7);
}

// ------------------------------------------------------------------ config (CleanX.ini)

struct Config {
    int startMin = 7 * 60;                                    // Time    (minutes after midnight)
    int endMin = 23 * 60 + 59;                                // EndTime
    bool days[7] = {false, true, true, true, true, true, false};  // tm_wday order: Sun..Sat
    int intervalDays = 30;                                    // IntervalDays
    int snoozeMinutes = 0;                                    // 0 = after Dismiss, come back tomorrow
};
static Config g_cfg;
static std::wstring g_iniPath, g_statePath, g_messagesPath;

static const char* kDefaultIni =
    "; CleanX configuration\r\n"
    "; The Task Scheduler starts CleanX every few minutes; CleanX itself decides with these\r\n"
    "; settings whether the reminder is shown. Changes take effect at the next check -\r\n"
    "; no need to re-run the scheduler setup.\r\n"
    "\r\n"
    "[Reminder]\r\n"
    "; Earliest time of day the reminder may pop up (24h format HH:MM)\r\n"
    "Time=07:00\r\n"
    "\r\n"
    "; Latest time of day the reminder may pop up (HH:MM)\r\n"
    "EndTime=23:59\r\n"
    "\r\n"
    "; Days of the week on which it may pop up: Mon,Tue,Wed,Thu,Fri,Sat,Sun  (or: All)\r\n"
    "Days=Mon,Tue,Wed,Thu,Fri\r\n"
    "\r\n"
    "; The reminder is due this many days after the last cleaning\r\n"
    "; (cleaned on 30.11. with IntervalDays=30 -> due again on 30.12.)\r\n"
    "IntervalDays=30\r\n"
    "\r\n"
    "; After pressing \"Dismiss\": minutes until it pops up again (0 = not before tomorrow)\r\n"
    "SnoozeMinutes=0\r\n";

static int ParseHHMM(const wchar_t* s, int def) {
    int h, m;
    if (swscanf_s(s, L"%d:%d", &h, &m) == 2 && h >= 0 && h <= 23 && m >= 0 && m <= 59) return h * 60 + m;
    return def;
}

static void WriteTextFile(const std::wstring& path, const std::string& utf8) {
    FILE* f = nullptr;
    if (_wfopen_s(&f, path.c_str(), L"wb") == 0 && f) {
        fwrite(utf8.data(), 1, utf8.size(), f);
        fclose(f);
    }
}

static void LoadConfig() {
    if (GetFileAttributesW(g_iniPath.c_str()) == INVALID_FILE_ATTRIBUTES) WriteTextFile(g_iniPath, kDefaultIni);
    const wchar_t* ini = g_iniPath.c_str();
    wchar_t buf[256];

    GetPrivateProfileStringW(L"Reminder", L"Time", L"07:00", buf, 256, ini);
    g_cfg.startMin = ParseHHMM(buf, g_cfg.startMin);
    GetPrivateProfileStringW(L"Reminder", L"EndTime", L"23:59", buf, 256, ini);
    g_cfg.endMin = ParseHHMM(buf, g_cfg.endMin);

    GetPrivateProfileStringW(L"Reminder", L"Days", L"Mon,Tue,Wed,Thu,Fri", buf, 256, ini);
    _wcslwr_s(buf);
    static const wchar_t* names[7] = {L"sun", L"mon", L"tue", L"wed", L"thu", L"fri", L"sat"};
    bool any = false;
    for (int i = 0; i < 7; i++) any |= (g_cfg.days[i] = wcsstr(buf, names[i]) != nullptr);
    if (!any) // "All", "Daily", empty or nonsense -> every day
        for (bool& d : g_cfg.days) d = true;

    g_cfg.intervalDays = max(1, min(3650, (int)GetPrivateProfileIntW(L"Reminder", L"IntervalDays", 30, ini)));
    g_cfg.snoozeMinutes = max(0, (int)GetPrivateProfileIntW(L"Reminder", L"SnoozeMinutes", 0, ini));
}

// CleanX.state remembers when "Dismiss" was pressed last
static time_t ReadDismissed() {
    FILE* f = nullptr;
    if (_wfopen_s(&f, g_statePath.c_str(), L"rb") != 0 || !f) return 0;
    char line[128] = {};
    fgets(line, sizeof(line), f);
    fclose(f);
    std::tm tm;
    const char* p = strchr(line, '=');
    if (!p || !ParseStamp(p + 1, tm)) return 0;
    return mktime(&tm);
}

static void WriteDismissed() {
    time_t now = time(nullptr);
    std::tm t;
    localtime_s(&t, &now);
    char buf[64];
    sprintf_s(buf, "dismissed=%04d-%02d-%02d %02d:%02d:%02d\r\n", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour,
              t.tm_min, t.tm_sec);
    WriteTextFile(g_statePath, buf);
}

// Decides whether the reminder is due right now. 'why' explains the decision.
// First day (day number) on which the reminder may appear: last cleaning + IntervalDays,
// moved forward to the next allowed weekday. Never cleaned -> today.
static long long NextDueDay() {
    long long due = g_hasLast ? LastCleaningDayNumber() + g_cfg.intervalDays : TodayNumber();
    for (int i = 0; i < 7 && !g_cfg.days[WeekdayOf(due)]; i++) due++;
    return due;
}

static std::wstring FormatDay(long long dayNumber) {
    static const wchar_t* wd[7] = {L"Sun", L"Mon", L"Tue", L"Wed", L"Thu", L"Fri", L"Sat"};
    int y, m, d;
    CivilFromDays(dayNumber, y, m, d);
    wchar_t buf[40];
    swprintf_s(buf, L"%s %02d.%02d.%04d", wd[WeekdayOf(dayNumber)], d, m, y);
    return buf;
}

static bool ShouldShow(std::wstring& why) {
    time_t now = time(nullptr);
    std::tm t;
    localtime_s(&t, &now);
    if (g_hasLast && TodayNumber() < LastCleaningDayNumber() + g_cfg.intervalDays) {
        wchar_t buf[200];
        swprintf_s(buf, L"No - cleaned %lld day(s) ago, next due %s (IntervalDays=%d).",
                   TodayNumber() - LastCleaningDayNumber(), FormatDay(NextDueDay()).c_str(), g_cfg.intervalDays);
        why = buf;
        return false;
    }
    if (!g_cfg.days[t.tm_wday]) {
        why = L"No - today is not one of the configured Days.";
        return false;
    }
    int nowMin = t.tm_hour * 60 + t.tm_min;
    bool inWindow = g_cfg.startMin <= g_cfg.endMin ? (nowMin >= g_cfg.startMin && nowMin <= g_cfg.endMin)
                                                   : (nowMin >= g_cfg.startMin || nowMin <= g_cfg.endMin);
    if (!inWindow) {
        why = L"No - outside the configured Time..EndTime window.";
        return false;
    }
    time_t dismissed = ReadDismissed();
    if (dismissed) {
        if (g_cfg.snoozeMinutes == 0) {
            std::tm d;
            localtime_s(&d, &dismissed);
            if (d.tm_year == t.tm_year && d.tm_yday == t.tm_yday) {
                why = L"No - dismissed today already (SnoozeMinutes=0 -> back tomorrow).";
                return false;
            }
        } else if (difftime(now, dismissed) < g_cfg.snoozeMinutes * 60.0) {
            why = L"No - dismissed less than SnoozeMinutes ago.";
            return false;
        }
    }
    why = L"YES - the reminder is due.";
    return true;
}

// ------------------------------------------------------------------ daily headline (messages.txt)

static const wchar_t* kBuiltinHeadlines[] = {
    L"It's time to clean the Laser-Lab!",
    L"Entropy is winning. Fight back!",
    L"The dust has reached quantum coherence.",
    L"Heisenberg is uncertain where the floor is.",
    L"Even the photons refuse to work in this mess.",
    L"Your beam path is clear. Your floor is not.",
    L"That's not cable management. That's spaghetti.",
    L"The ions are trapped. You don't have to be.",
    L"Maxwell's demon quit. Someone has to sort this.",
    L"Schrödinger's lab: clean AND messy - until you look.",
    L"UHV in the chamber, ultra-high chaos below.",
    L"Mode-lock your broom and start sweeping!",
    L"Dust is not a valid beam diagnostic.",
    L"Cleaning: the only experiment that always works.",
    L"Today's alignment target: the floor.",
    L"Scattering losses detected: 87 % dust.",
    L"Reviewer 2 says: \"The lab is a mess.\"",
    L"Please collimate the screws back into their box.",
    L"Time to bring the lab back to its ground state.",
    L"Your optics called. They can't see anything.",
    L"The dust bunnies have started a PhD.",
    L"Lower the noise floor - by cleaning the floor.",
    L"Doppler cooling won't cool down this chaos.",
    L"Lost your Allen key? Clean the lab and find it!",
    L"Signal-to-mess ratio critically low!",
    L"A whole ecosystem lives under the optical table.",
    L"Reduce the lab's entropy by at least 1 J/K today.",
    L"The vacuum is great. The lab needs a vacuum cleaner.",
    L"Nobel prizes are rarely awarded to messy labs.",
    L"Even the turbo pump can't suck up this much dust.",
    L"First align the lab, then align the lasers.",
    L"Paper sheets are not a floor coating.",
    L"Clean lab, happy ions!",
    L"Warning: dust density exceeds the Rayleigh limit.",
    L"This lab has more loose screws than a theorist.",
    L"Optical table: isolated. Mess: not isolated.",
};

static std::vector<std::wstring> g_headlines;
static std::wstring g_headline;

static std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
}

static std::string WideToUtf8(const std::wstring& w) {
    if (w.empty()) return "";
    int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

// messages.txt: one headline per line (UTF-8), lines starting with # are comments.
// Created with the built-in list on first run, so it can simply be edited.
static void LoadMessages() {
    FILE* f = nullptr;
    if (_wfopen_s(&f, g_messagesPath.c_str(), L"rb") != 0 || !f) {
        std::string out =
            "# CleanX headlines - one per line, a different one is picked every day.\r\n"
            "# Lines starting with # are ignored. Delete this file to restore the defaults.\r\n\r\n";
        for (auto* h : kBuiltinHeadlines) out += WideToUtf8(h) + "\r\n";
        WriteTextFile(g_messagesPath, out);
    } else {
        std::string data;
        char buf[4096];
        size_t n;
        while ((n = fread(buf, 1, sizeof(buf), f)) > 0) data.append(buf, n);
        fclose(f);
        if (data.size() >= 3 && (unsigned char)data[0] == 0xEF && (unsigned char)data[1] == 0xBB &&
            (unsigned char)data[2] == 0xBF)
            data.erase(0, 3);
        size_t pos = 0;
        while (pos < data.size()) {
            size_t end = data.find('\n', pos);
            if (end == std::string::npos) end = data.size();
            std::string line = data.substr(pos, end - pos);
            pos = end + 1;
            size_t a = line.find_first_not_of(" \t\r"), b = line.find_last_not_of(" \t\r");
            if (a == std::string::npos || line[a] == '#') continue;
            g_headlines.push_back(Utf8ToWide(line.substr(a, b - a + 1)));
        }
    }
    if (g_headlines.empty())
        for (auto* h : kBuiltinHeadlines) g_headlines.push_back(h);
}

// Same headline all day on all monitors, a different one every day, shuffled order.
static std::wstring HeadlineForDay(long long dayOffset) {
    time_t now = time(nullptr);
    std::tm t;
    localtime_s(&t, &now);
    long long day = DaysFromCivil(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday) + dayOffset;
    long long n = (long long)g_headlines.size();
    long long step = 1;
    for (long long p : {17LL, 19LL, 23LL, 29LL, 31LL})
        if (n % p) {
            step = p;
            break;
        }
    return g_headlines[(size_t)(((day * step) % n + n) % n)];
}

// ------------------------------------------------------------------ texts

static const wchar_t* kDays[] = {L"Sunday", L"Monday", L"Tuesday", L"Wednesday", L"Thursday", L"Friday", L"Saturday"};
static const wchar_t* kMonths[] = {L"Jan", L"Feb", L"Mar", L"Apr", L"May", L"Jun",
                                   L"Jul", L"Aug", L"Sep", L"Oct", L"Nov", L"Dec"};

static long long SecondsSinceLast() {
    if (!g_hasLast) return 0;
    long long d = (long long)difftime(time(nullptr), g_lastTime);
    return d < 0 ? 0 : d;
}

static std::wstring LastCleanedLine() {
    if (!g_hasLast) return L"There is no cleaning in the logbook yet. Be the first!";
    std::tm t = g_lastTm;
    std::tm copy = t;
    mktime(&copy);  // fills tm_wday
    wchar_t buf[200];
    swprintf_s(buf, L"The Laser-Lab was last cleaned on %s, %02d %s %04d at %02d:%02d. That was",
               kDays[copy.tm_wday], t.tm_mday, kMonths[t.tm_mon], t.tm_year + 1900, t.tm_hour, t.tm_min);
    return buf;
}

static std::wstring CounterLine() {
    if (!g_hasLast) return L"∞ days ago";
    long long s = SecondsSinceLast();
    wchar_t buf[120];
    swprintf_s(buf, L"%lld days  %02lld h  %02lld min  %02lld s  ago", s / 86400, (s / 3600) % 24, (s / 60) % 60,
               s % 60);
    return buf;
}

static std::wstring QuipLine() {
    long long days = SecondsSinceLast() / 86400;
    const wchar_t* quip;
    if (!g_hasLast)
        quip = L"Clean once and the counter starts ticking.";
    else if (days < 35)
        quip = L"Keep the streak alive!";
    else if (days < 60)
        quip = L"The dust bunnies are starting to form a union.";
    else if (days < 120)
        quip = L"Somewhere under that cable pile an optic is crying.";
    else
        quip = L"Archaeologists have requested access to the lab.";
    wchar_t buf[300];
    if (g_cleanCount > 0)
        swprintf_s(buf, L"%s   •   %d cleaning%s logged since %s %04d", quip, g_cleanCount, g_cleanCount == 1 ? L"" : L"s",
                   kMonths[g_firstTm.tm_mon], g_firstTm.tm_year + 1900);
    else
        swprintf_s(buf, L"%s", quip);
    return buf;
}

// ------------------------------------------------------------------ drawing

struct Layout {
    float k;
    RectF panel;
    RectF btn[2];
};

static Layout GetLayout(int W, int H) {
    Layout L;
    L.k = max(0.4f, min(W / 1920.f, H / 1080.f));
    float k = L.k;
    float pw = min(1560 * k, W - 32.f);
    L.panel = RectF((W - pw) / 2, 26 * k, pw, 344 * k);
    float bw = 420 * k, bh = 120 * k, gap = 70 * k;
    float bx = (W - (2 * bw + gap)) / 2, by = H - bh - 60 * k;
    L.btn[0] = RectF(bx, by, bw, bh);
    L.btn[1] = RectF(bx + bw + gap, by, bw, bh);
    return L;
}

static void RoundRect(GraphicsPath& p, RectF r, float rad) {
    float d = rad * 2;
    p.AddArc(r.X, r.Y, d, d, 180, 90);
    p.AddArc(r.X + r.Width - d, r.Y, d, d, 270, 90);
    p.AddArc(r.X + r.Width - d, r.Y + r.Height - d, d, d, 0, 90);
    p.AddArc(r.X, r.Y + r.Height - d, d, d, 90, 90);
    p.CloseFigure();
}

static void OutlinedText(Graphics& g, const std::wstring& s, RectF box, float size, int style, Color fill,
                         Color outline, float ow) {
    FontFamily ff(L"Segoe UI");
    StringFormat sf;
    sf.SetAlignment(StringAlignmentCenter);
    sf.SetLineAlignment(StringAlignmentCenter);
    sf.SetFormatFlags(StringFormatFlagsNoWrap);
    sf.SetTrimming(StringTrimmingNone);
    GraphicsPath path;
    // lay out in a very wide box (no clipping), centred on the target box
    RectF wide(box.X - 10000, box.Y, box.Width + 20000, box.Height);
    path.AddString(s.c_str(), -1, &ff, style, size, wide, &sf);

    // shrink to fit (long headline / narrow monitor), scaling around the box centre
    RectF b;
    path.GetBounds(&b);
    if (b.Width > box.Width * 0.97f && b.Width > 0) {
        float f = box.Width * 0.97f / b.Width;
        float cx = box.X + box.Width / 2, cy = box.Y + box.Height / 2;
        Matrix m;
        m.Translate(cx, cy);
        m.Scale(f, f);
        m.Translate(-cx, -cy);
        path.Transform(&m);
    }
    if (ow > 0) {
        Pen pen(outline, ow);
        pen.SetLineJoin(LineJoinRound);
        g.DrawPath(&pen, &path);
    }
    SolidBrush br(fill);
    g.FillPath(&br, &path);
}

static void DrawButton(Graphics& g, RectF r, float k, const wchar_t* label, Color base, Color hover, Color border,
                       Color text, bool isHover, bool isPressed) {
    float off = isPressed ? 4 * k : 0;
    RectF shadow(r.X + 8 * k, r.Y + 10 * k, r.Width, r.Height);
    GraphicsPath ps;
    RoundRect(ps, shadow, 18 * k);
    SolidBrush sb(Color(110, 0, 0, 0));
    g.FillPath(&sb, &ps);

    RectF body(r.X + off, r.Y + off, r.Width, r.Height);
    GraphicsPath pb;
    RoundRect(pb, body, 18 * k);
    SolidBrush fb(isHover ? hover : base);
    g.FillPath(&fb, &pb);
    Pen pen(border, 9 * k);
    g.DrawPath(&pen, &pb);
    OutlinedText(g, label, body, 54 * k, FontStyleBold, text, Color(0, 0, 0, 0), 0);
}

static void BuildBackground(Win& w) {
    if (w.bg) DeleteObject(w.bg);
    HDC screen = GetDC(nullptr);
    w.bg = CreateCompatibleBitmap(screen, w.w, w.h);
    HDC mem = CreateCompatibleDC(screen);
    HGDIOBJ old = SelectObject(mem, w.bg);
    {
        Graphics g(mem);
        SolidBrush dark(Color(255, 30, 32, 40));
        g.FillRectangle(&dark, 0, 0, w.w, w.h);
        if (g_image && g_image->GetLastStatus() == Ok) {
            // "cover" scaling: fill the whole monitor, crop the overflow
            float iw = (float)g_image->GetWidth(), ih = (float)g_image->GetHeight();
            float sc = max(w.w / iw, w.h / ih);
            float dw = iw * sc, dh = ih * sc;
            g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
            g.SetPixelOffsetMode(PixelOffsetModeHighQuality);
            g.DrawImage(g_image, RectF((w.w - dw) / 2, (w.h - dh) / 2, dw, dh));
        }
    }
    SelectObject(mem, old);
    DeleteDC(mem);
    ReleaseDC(nullptr, screen);
}

static void Paint(Win& w, HDC hdc) {
    HDC frame = CreateCompatibleDC(hdc);
    HBITMAP fb = CreateCompatibleBitmap(hdc, w.w, w.h);
    HGDIOBJ oldF = SelectObject(frame, fb);

    HDC bgdc = CreateCompatibleDC(hdc);
    HGDIOBJ oldB = SelectObject(bgdc, w.bg);
    BitBlt(frame, 0, 0, w.w, w.h, bgdc, 0, 0, SRCCOPY);
    SelectObject(bgdc, oldB);
    DeleteDC(bgdc);

    {
        Graphics g(frame);
        g.SetSmoothingMode(SmoothingModeAntiAlias);
        g.SetPixelOffsetMode(PixelOffsetModeHighQuality);
        Layout L = GetLayout(w.w, w.h);
        float k = L.k;

        // info panel
        GraphicsPath pp;
        RoundRect(pp, L.panel, 28 * k);
        SolidBrush pbr(Color(200, 14, 16, 28));
        g.FillPath(&pbr, &pp);
        Pen ppen(Color(140, 255, 200, 60), 4 * k);
        g.DrawPath(&ppen, &pp);

        float x = L.panel.X + 24 * k, wdt = L.panel.Width - 48 * k, y = L.panel.Y;
        OutlinedText(g, g_headline, RectF(x, y + 22 * k, wdt, 110 * k), 82 * k,
                     FontStyleBold, Color(255, 255, 255, 255), Color(255, 10, 10, 20), 10 * k);
        OutlinedText(g, LastCleanedLine(), RectF(x, y + 138 * k, wdt, 44 * k), 30 * k, FontStyleRegular,
                     Color(255, 215, 220, 230), Color(0, 0, 0, 0), 0);
        OutlinedText(g, CounterLine(), RectF(x, y + 180 * k, wdt, 96 * k), 72 * k, FontStyleBold,
                     Color(255, 255, 196, 50), Color(255, 60, 20, 0), 6 * k);
        OutlinedText(g, QuipLine(), RectF(x, y + 280 * k, wdt, 46 * k), 27 * k, FontStyleItalic,
                     Color(255, 170, 180, 195), Color(0, 0, 0, 0), 0);

        // buttons (same colours as the old version)
        DrawButton(g, L.btn[0], k, L"Cleaned!", Color(255, 0x00, 0xAD, 0xB1), Color(255, 0x97, 0xE6, 0x81),
                   Color(255, 0x00, 0x8A, 0xB1), Color(255, 255, 255, 255), w.hover == 0, w.pressed == 0);
        DrawButton(g, L.btn[1], k, L"Dismiss", Color(255, 0xB7, 0x6A, 0xAE), Color(255, 0xD5, 0x6A, 0xA3),
                   Color(255, 0x93, 0x6B, 0xB3), Color(255, 0, 0, 0), w.hover == 1, w.pressed == 1);
    }

    BitBlt(hdc, 0, 0, w.w, w.h, frame, 0, 0, SRCCOPY);
    SelectObject(frame, oldF);
    DeleteObject(fb);
    DeleteDC(frame);
}

// ------------------------------------------------------------------ windows

static Win* FindWin(HWND h) {
    for (auto& w : g_wins)
        if (w.hwnd == h) return &w;
    return nullptr;
}

static int HitTest(Win& w, int x, int y) {
    Layout L = GetLayout(w.w, w.h);
    for (int i = 0; i < 2; i++)
        if (L.btn[i].Contains((REAL)x, (REAL)y)) return i;
    return -1;
}

static void Finish(bool cleaned) {
    if (cleaned)
        AppendCleaning();
    else
        WriteDismissed();
    g_allowClose = true;
    PostQuitMessage(0);
}

static BOOL CALLBACK MonitorEnum(HMONITOR, HDC, LPRECT rc, LPARAM lp) {
    reinterpret_cast<std::vector<RECT>*>(lp)->push_back(*rc);
    return TRUE;
}

static void DestroyWindows() {
    bool prev = g_allowClose;
    g_allowClose = true;
    for (auto& w : g_wins) {
        if (w.hwnd) DestroyWindow(w.hwnd);
        if (w.bg) DeleteObject(w.bg);
    }
    g_wins.clear();
    g_allowClose = prev;
}

static void CreateWindows() {
    std::vector<RECT> mons;
    EnumDisplayMonitors(nullptr, nullptr, MonitorEnum, (LPARAM)&mons);
    g_wins.resize(mons.size());
    for (size_t i = 0; i < mons.size(); i++) {
        Win& w = g_wins[i];
        RECT r = mons[i];
        w.w = r.right - r.left;
        w.h = r.bottom - r.top;
        BuildBackground(w);
        w.hwnd = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, kClassName, L"CleanX", WS_POPUP, r.left, r.top,
                                 w.w, w.h, nullptr, nullptr, g_inst, nullptr);
    }
    for (auto& w : g_wins) ShowWindow(w.hwnd, SW_SHOW);
    if (!g_wins.empty()) {
        SetForegroundWindow(g_wins[0].hwnd);
        SetFocus(g_wins[0].hwnd);
    }
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    Win* w = FindWin(hwnd);
    switch (msg) {
        case WM_ERASEBKGND:
            return 1;
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            if (w) Paint(*w, hdc);
            EndPaint(hwnd, &ps);
            return 0;
        }
        case WM_MOUSEMOVE: {
            if (!w) break;
            int hit = HitTest(*w, (short)LOWORD(lp), (short)HIWORD(lp));
            if (hit != w->hover) {
                w->hover = hit;
                InvalidateRect(hwnd, nullptr, FALSE);
            }
            TRACKMOUSEEVENT tme = {sizeof(tme), TME_LEAVE, hwnd, 0};
            TrackMouseEvent(&tme);
            return 0;
        }
        case WM_MOUSELEAVE:
            if (w && w->hover != -1) {
                w->hover = -1;
                InvalidateRect(hwnd, nullptr, FALSE);
            }
            return 0;
        case WM_LBUTTONDOWN:
            if (w) {
                w->pressed = HitTest(*w, (short)LOWORD(lp), (short)HIWORD(lp));
                if (w->pressed >= 0) SetCapture(hwnd);
                InvalidateRect(hwnd, nullptr, FALSE);
            }
            return 0;
        case WM_LBUTTONUP:
            if (w) {
                int hit = HitTest(*w, (short)LOWORD(lp), (short)HIWORD(lp));
                int was = w->pressed;
                w->pressed = -1;
                ReleaseCapture();
                InvalidateRect(hwnd, nullptr, FALSE);
                if (was >= 0 && hit == was) Finish(was == 0);
            }
            return 0;
        case WM_SETCURSOR:
            if (w && LOWORD(lp) == HTCLIENT) {
                SetCursor(LoadCursor(nullptr, w->hover >= 0 ? IDC_HAND : IDC_ARROW));
                return TRUE;
            }
            break;
        case WM_SYSCOMMAND:
            switch (wp & 0xFFF0) {
                case SC_CLOSE:
                case SC_MINIMIZE:
                case SC_KEYMENU:
                case SC_TASKLIST:
                case SC_SCREENSAVE:
                    return 0;
            }
            break;
        case WM_CLOSE:
            if (!g_allowClose) return 0;  // no Alt+F4 escape
            break;
        case WM_DISPLAYCHANGE:
            g_rebuildPending = true;  // monitor plugged in/out -> recreate windows
            return 0;
        case WM_DPICHANGED:
            return 0;  // keep covering the monitor exactly
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

// Swallow the keys that would let you sneak past the reminder.
static LRESULT CALLBACK KeyboardHook(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION) {
        auto* k = reinterpret_cast<KBDLLHOOKSTRUCT*>(lp);
        bool alt = (k->flags & LLKHF_ALTDOWN) != 0;
        bool ctrl = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
        switch (k->vkCode) {
            case VK_LWIN:
            case VK_RWIN:
            case VK_APPS:
                return 1;
            case VK_TAB:
                if (alt) return 1;
                break;
            case VK_ESCAPE:
                if (alt || ctrl) return 1;
                break;
            case VK_F4:
                if (alt) return 1;
                break;
        }
    }
    return CallNextHookEx(g_kbHook, code, wp, lp);
}

// Runs 4x per second: stay on top of everything, keep focus, tick the counter.
static void CALLBACK Tick(HWND, UINT, UINT_PTR, DWORD) {
    if (g_rebuildPending) {
        g_rebuildPending = false;
        DestroyWindows();
        CreateWindows();
    }
    bool ours = false;
    HWND fg = GetForegroundWindow();
    for (auto& w : g_wins) {
        SetWindowPos(w.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        if (w.hwnd == fg) ours = true;
    }
    if (!ours && !g_wins.empty()) SetForegroundWindow(g_wins[0].hwnd);

    time_t now = time(nullptr);
    if (now != g_lastShownSecond) {
        g_lastShownSecond = now;
        for (auto& w : g_wins) InvalidateRect(w.hwnd, nullptr, FALSE);
    }
}

// ------------------------------------------------------------------ image

static void LoadBackgroundImage() {
    std::wstring dir = ExeDir();
    for (const wchar_t* name : {L"background.jpg", L"background.png"}) {
        std::wstring p = dir + L"\\" + name;
        if (GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES) {
            g_image = Bitmap::FromFile(p.c_str());
            if (g_image && g_image->GetLastStatus() == Ok) return;
            delete g_image;
            g_image = nullptr;
        }
    }
    HRSRC res = FindResourceW(nullptr, MAKEINTRESOURCEW(IDR_BACKGROUND), RT_RCDATA);
    if (!res) return;
    HGLOBAL h = LoadResource(nullptr, res);
    DWORD size = SizeofResource(nullptr, res);
    const BYTE* data = static_cast<const BYTE*>(LockResource(h));
    if (!data || !size) return;
    g_imageStream = SHCreateMemStream(data, size);  // must outlive g_image
    if (g_imageStream) g_image = Bitmap::FromStream(g_imageStream);
}

// ------------------------------------------------------------------ preview (no windows)

// CleanX.exe --preview out.png 1920 1080   renders the reminder into a PNG and exits
static int RenderPreview(const wchar_t* path, int W, int H) {
    CLSID png = {};
    UINT num = 0, size = 0;
    GetImageEncodersSize(&num, &size);
    std::vector<BYTE> buf(size);
    auto* enc = reinterpret_cast<ImageCodecInfo*>(buf.data());
    GetImageEncoders(num, size, enc);
    for (UINT i = 0; i < num; i++)
        if (wcscmp(enc[i].MimeType, L"image/png") == 0) png = enc[i].Clsid;

    Win w;
    w.w = W;
    w.h = H;
    BuildBackground(w);
    HDC screen = GetDC(nullptr);
    HDC mem = CreateCompatibleDC(screen);
    HBITMAP out = CreateCompatibleBitmap(screen, W, H);
    HGDIOBJ old = SelectObject(mem, out);
    Paint(w, mem);
    SelectObject(mem, old);
    Status st;
    {
        Bitmap bmp(out, nullptr);
        st = bmp.Save(path, &png, nullptr);
    }
    DeleteObject(out);
    DeleteObject(w.bg);
    DeleteDC(mem);
    ReleaseDC(nullptr, screen);
    return st == Ok ? 0 : 1;
}

// ------------------------------------------------------------------ main

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE, PWSTR cmd, int) {
    g_inst = inst;
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    bool force = false, status = false;
    const wchar_t* previewPath = nullptr;
    int previewW = 1920, previewH = 1080, dayOffset = 0;
    for (int i = 1; i < argc; i++) {
        if (!_wcsicmp(argv[i], L"--force") || !_wcsicmp(argv[i], L"-f") || !_wcsicmp(argv[i], L"/force")) force = true;
        if (!_wcsicmp(argv[i], L"--status")) status = true;
        if (!_wcsicmp(argv[i], L"--day") && i + 1 < argc) dayOffset = _wtoi(argv[++i]);
        if (!_wcsicmp(argv[i], L"--preview") && i + 1 < argc) {
            previewPath = argv[++i];
            if (i + 2 < argc && iswdigit(argv[i + 1][0])) {
                previewW = _wtoi(argv[++i]);
                previewH = _wtoi(argv[++i]);
            }
        }
    }
    (void)cmd;

    std::wstring dir = ExeDir();
    g_logPath = dir + L"\\" + kLogName;
    g_iniPath = dir + L"\\CleanX.ini";
    g_statePath = dir + L"\\CleanX.state";
    g_messagesPath = dir + L"\\messages.txt";
    ReadLog();
    LoadConfig();
    LoadMessages();
    g_headline = HeadlineForDay(dayOffset);

    if (status) {
        std::wstring why;
        ShouldShow(why);
        static const wchar_t* dn[7] = {L"Sun", L"Mon", L"Tue", L"Wed", L"Thu", L"Fri", L"Sat"};
        std::wstring days;
        for (int i = 1; i <= 7; i++)
            if (g_cfg.days[i % 7]) days += std::wstring(days.empty() ? L"" : L",") + dn[i % 7];
        long long due = NextDueDay();
        wchar_t dueText[100];
        swprintf_s(dueText, L"%s%s, from %02d:%02d", due <= TodayNumber() ? L"due since " : L"",
                   FormatDay(due).c_str(), g_cfg.startMin / 60, g_cfg.startMin % 60);
        wchar_t buf[2048];
        swprintf_s(buf,
                   L"Show reminder now?  %s\n\n"
                   L"Config:   Time=%02d:%02d  EndTime=%02d:%02d  Days=%s  IntervalDays=%d  SnoozeMinutes=%d\n"
                   L"Logbook:  %d cleanings, last: %s\n"
                   L"Next due: %s\n"
                   L"Today:    \"%s\"\n"
                   L"Tomorrow: \"%s\"\n",
                   why.c_str(), g_cfg.startMin / 60, g_cfg.startMin % 60, g_cfg.endMin / 60, g_cfg.endMin % 60,
                   days.c_str(), g_cfg.intervalDays, g_cfg.snoozeMinutes, g_cleanCount,
                   g_hasLast ? CounterLine().c_str() : L"never", dueText, g_headline.c_str(),
                   HeadlineForDay(dayOffset + 1).c_str());
        if (AttachConsole(ATTACH_PARENT_PROCESS)) {  // started from a terminal -> print there
            HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
            std::string s = "\n" + WideToUtf8(buf);
            DWORD written;
            if (!WriteFile(out, s.data(), (DWORD)s.size(), &written, nullptr)) WriteConsoleW(out, buf, (DWORD)wcslen(buf), &written, nullptr);
        } else {
            MessageBoxW(nullptr, buf, L"CleanX status", MB_ICONINFORMATION);
        }
        return 0;
    }

    if (previewPath) {
        GdiplusStartupInput gsi;
        ULONG_PTR tok;
        GdiplusStartup(&tok, &gsi, nullptr);
        LoadBackgroundImage();
        int rc = RenderPreview(previewPath, max(320, previewW), max(240, previewH));
        delete g_image;
        g_image = nullptr;
        GdiplusShutdown(tok);
        return rc;
    }

    HANDLE mutex = CreateMutexW(nullptr, TRUE, L"Local\\CleanX.LaserLab.Reminder");
    if (GetLastError() == ERROR_ALREADY_EXISTS) return 0;  // already showing

    std::wstring why;
    if (!force && !ShouldShow(why)) return 0;

    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

    GdiplusStartupInput gsi;
    ULONG_PTR gdipToken;
    GdiplusStartup(&gdipToken, &gsi, nullptr);
    LoadBackgroundImage();

    WNDCLASSEXW wc = {sizeof(wc)};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(IDI_APP));
    wc.hIconSm = wc.hIcon;
    wc.lpszClassName = kClassName;
    RegisterClassExW(&wc);

    CreateWindows();
    g_kbHook = SetWindowsHookExW(WH_KEYBOARD_LL, KeyboardHook, inst, 0);
    UINT_PTR timer = SetTimer(nullptr, 0, 250, Tick);

    MSG m;
    while (GetMessageW(&m, nullptr, 0, 0) > 0) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }

    KillTimer(nullptr, timer);
    if (g_kbHook) UnhookWindowsHookEx(g_kbHook);
    DestroyWindows();
    delete g_image;
    if (g_imageStream) g_imageStream->Release();
    GdiplusShutdown(gdipToken);
    if (mutex) {
        ReleaseMutex(mutex);
        CloseHandle(mutex);
    }
    return 0;
}
