#!/usr/bin/env python3
from datetime import datetime, timedelta
from pathlib import Path
import configparser
import curses
import json
import os
import sys
import time
import traceback

def create_file_if_not_exist(path, content):
    p = Path(path)
    if not p.is_file():
        p.touch()
        p.write_text(content)

def update_record(minutes):
    today = datetime.now().date()
    thisweek_start = str(today - timedelta(days=today.weekday()))
    if not thisweek_start in record_json:
        record_json[thisweek_start] = {"Mon": 0, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 0, "Sat": 0, "Sun": 0}
    record_json[thisweek_start][today.strftime("%a")] += minutes
    Path(record_path).write_text(json.dumps(record_json))

    thisweek_summary = [round(y/work_min, 1) for x, y in record_json[thisweek_start].items()]
    stdscr.addstr(6, 0, str(thisweek_summary) + " Total: " + str(sum(thisweek_summary)), curses.A_BOLD)
    wk = lambda x: record_json[str(today - timedelta(days=(today.weekday() + x)))].values() if str(today - timedelta(days=(today.weekday() + x))) in record_json else [0, 0, 0, 0, 0, 0, 0]
    last_fourweek = [round(sum(list(item))/4/work_min,1) for item in zip(wk(7), wk(14), wk(21), wk(28))]
    stdscr.addstr(8, 0, str(last_fourweek) + " Total: " + str(sum(last_fourweek)), curses.A_BOLD)

def get_session_info(period_num):
    # one session has 9 period: w > b > w > b > w > b > w > b > lb
    num = period_num % 9
    if num in [1, 3, 5, 7]:
        return ["Work", work_min * 60]
    elif num in [2, 4, 6, 8]:
        return ["Break", break_min * 60]
    else:
        return ["Long Break", longbreak_min * 60]

def sec_to_hhmmss(sec):
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return str(h).zfill(2) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)

def pomodoro_session(remaining_sec, period_num):
    try:
        is_working = True if get_session_info(period_num)[1] == work_min * 60 else False
        stdscr.refresh()
        stdscr.addstr(0, 0, "Current Session: " + get_session_info(period_num)[0] + "                 ", curses.A_BOLD)
        stdscr.addstr(2, 0, "CTRL + C to " + ("Pause" if is_working else "Skip" ) + "           ", curses.A_BOLD)
        while remaining_sec > 0:
            stdscr.addstr(1, 0, "Time Left: " + sec_to_hhmmss(remaining_sec), curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)
            remaining_sec -= 1
        if is_working:
            update_record(work_min)
        os.system(f"echo . | $(which xnotify) -g 3840x2160 -s 2")
        will_skip_prompt = not os.system(f"zenity --question --ellipsize --title='Session Ends!' --text='Do you want to start " + ("Break" if is_working else "Work") + " session now\?' 2>/dev/null")
        return get_session_info(period_num + 1)[1], period_num + 1, will_skip_prompt
    except KeyboardInterrupt:
        # save progress if working else skip
        if period_num % 9 in [1, 3, 5, 7]:
            stdscr.addstr(0, 0, "Current Session: " + get_session_info(period_num)[0] + " - Pause!", curses.A_BOLD)
            return remaining_sec, period_num, False
        else:
            stdscr.addstr(0, 0, "Current Session: " + get_session_info(period_num)[0] + " - Stop!", curses.A_BOLD)
            return get_session_info(period_num + 1)[1], period_num + 1, True

# declare paths
folder_path = os.path.expanduser("~") + "/.local/share/lazyman-pomodoro/"
record_path = folder_path + "record.json"
config_path = folder_path + "config.conf"
# create if not exist
os.makedirs(folder_path, 0o755, exist_ok=True)
create_file_if_not_exist(record_path, "{}")
create_file_if_not_exist(config_path, """[DEFAULT]
WorkMinutes = 25
BreakMinutes = 5
LongbreakMinutes = 15
""")
# read record
record_content = Path(record_path).read_text()
try:
    record_json = json.loads(record_content)
except ValueError:
    print(record_path + " is not a valid JSON")
    sys.exit()
# read config
config = configparser.ConfigParser()
config.read(config_path)
conf = config['DEFAULT']
work_min = conf.getint('WorkMinutes')
break_min = conf.getint('BreakMinutes')
longbreak_min = conf.getint('LongbreakMinutes')

skip_prompt = False
# ncurses
stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
stdscr.keypad(1)
curses.curs_set(0)

stdscr.addstr(3, 0, "---------------------------------", curses.A_BOLD)
stdscr.addstr(4, 0, "# Sessions from Monday (" + str(work_min) + " Minutes Each)", curses.A_BOLD)
stdscr.addstr(5, 0, "This Week", curses.A_BOLD)
stdscr.addstr(7, 0, "Last Four Weeks (avg)", curses.A_BOLD)
try:
    remaining_sec = work_min * 60
    session_num = 0
    period_num = 1
    update_record(0)
    while 1:
        stdscr.addstr(0, 0, "Current Session: " + get_session_info(period_num)[0], curses.A_BOLD)
        stdscr.addstr(1, 0, "Time Left: " + sec_to_hhmmss(remaining_sec), curses.A_BOLD)
        stdscr.addstr(2, 0, "Press s to Start, q to Quit", curses.A_BOLD)
        if not skip_prompt:
            ans = stdscr.getch()
        if ans == ord('s'):
            if remaining_sec:
                remaining_sec, period_num, skip_prompt = pomodoro_session(remaining_sec, period_num)
        elif ans == ord('q'):
            break
        else:
            stdscr.addstr(0, 0, "Current Session: " + get_session_info(period_num)[0] + " - Invalid Input!", curses.A_BOLD)
except:
    traceback.print_exc()
finally:
    stdscr.keypad(0)
    curses.echo()
    curses.nocbreak()
    curses.endwin()
