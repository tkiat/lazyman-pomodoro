#!/usr/bin/env python3
"""
Simple pomodoro that supports pause, length configuration, and statistics.
"""
from datetime import datetime, timedelta
from pathlib import Path
from shutil import which
import configparser
import curses
import json
import os
import sys
import time

def create_file_if_not_exist(path, content):
    '''Create file if and only if it does not exist'''
    pathlib = Path(path)
    if not pathlib.is_file():
        pathlib.touch()
        pathlib.write_text(content)

def update_record(minutes):
    '''Update the pomodoro record and write it to the disk.'''
    today = datetime.now().date()
    this_mon = today - timedelta(days=today.weekday())
    if not str(this_mon) in RECORD_JSON:
        RECORD_JSON[str(this_mon)] = {"Mon":0, "Tue":0, "Wed":0, "Thu":0, "Fri":0, "Sat":0, "Sun":0}
    RECORD_JSON[str(this_mon)][today.strftime("%a")] += minutes
    Path(RECORD_PATH).write_text(json.dumps(RECORD_JSON))

    thiswk_stat_new = [round(y/WORK_MIN, 1) for x, y in RECORD_JSON[str(this_mon)].items()]
    wk_mon = lambda x: this_mon - timedelta(days=(x * 7))
    wk_val = lambda x: RECORD_JSON[str(wk_mon(x))].values() if str(wk_mon(x)) in RECORD_JSON \
        else [0, 0, 0, 0, 0, 0, 0]
    sessions = lambda x: round(sum(list(x))/4/WORK_MIN, 1)
    last4wk_stat_new = [sessions(item) for item in zip(wk_val(1), wk_val(2), wk_val(3), wk_val(4))]
    return thiswk_stat_new, last4wk_stat_new

def get_session_info(num):
    '''Get the type and length of the session
    one period has 9 sessions: w > b > w > b > w > b > w > b > lb'''
    if num % 9 in [1, 3, 5, 7]:
        return ["Work", WORK_MIN * 60]
    if num % 9 in [2, 4, 6, 8]:
        return ["Break", BREAK_MIN * 60]
    return ["Long Break", LONGBREAK_MIN * 60]

def sec_to_hhmmss(sec):
    '''Convert seconds to HH:MM:SS format.'''
    minute, second = divmod(sec, 60)
    hour, minute = divmod(minute, 60)
    return str(hour).zfill(2) + ":" + str(minute).zfill(2) + ":" + str(second).zfill(2)

def start_session(stdscr, sec_remaining, session, cache):
    '''Start a pomodoro session.
    return sec_left, session_num, skip_prompt, will_update_record'''
    # height, width = stdscr.getmaxyx()
    try:
        is_working = bool(get_session_info(session)[1] == WORK_MIN * 60)
        stdscr.refresh()
        while sec_remaining > 0:
            if sec_remaining % 5 == 0: # refresh every 5 seconds
                stdscr.clear()
                render_alltext(stdscr, *cache)
            stdscr.addstr(1, 0, "Time Left: " + sec_to_hhmmss(sec_remaining) + \
                    '                ', curses.A_BOLD)
            stdscr.addstr(2, 0, "CTRL + C to " + ("Pause" if is_working else "Skip") + \
                    "           ", curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)
            sec_remaining -= 1
        # os.system(f"echo . | $(which xnotify) -g 3840x2160 -s 2")
        cur_session = "Break" if is_working else "Work"
        will_skip_prompt = not os.system(f"zenity --question --ellipsize --title= 'Session Ends!' \
                --text='Do you want to start {cur_session} session now?' 2>/dev/null")
        return get_session_info(session + 1)[1], session + 1, will_skip_prompt, True
    except KeyboardInterrupt:
        # save progress if working else skip
        if session % 9 in [1, 3, 5, 7]:
            stdscr.addstr(1, 0, "Time Left: " + sec_to_hhmmss(sec_remaining) + \
                    ' (Pause)', curses.A_BOLD)
            return sec_remaining, session, False, False
        return get_session_info(session + 1)[1], session + 1, True, False

def return_progress(session):
    '''Return progress string with marker.'''
    marker = "(*)"
    progress = "w - b - w - b - w - b - w - b - lb"
    marker_index = 4 * (session - 1) + 1 if session % 9 != 0 else len(progress)
    return progress[:marker_index] + marker + progress[marker_index:]

def render_alltext(stdscr, session_len, remaining, session, stat):
    '''Render everyting onto the screen.'''
    stdscr.addstr(0, 0, return_progress(session), curses.A_BOLD)
    stdscr.addstr(1, 0, "Time Left: " + sec_to_hhmmss(remaining), curses.A_BOLD)
    stdscr.addstr(2, 0, "Press s to Start, q to Quit", curses.A_BOLD)
    stdscr.addstr(3, 0, "# Sessions (Mon-Sun, " + str(session_len) + " Mins Each)", curses.A_BOLD)
    stdscr.addstr(4, 0, "This Week", curses.A_BOLD)
    stdscr.addstr(5, 0, str(stat[0]) + " Total: " + str(sum(stat[0])), curses.A_BOLD)
    stdscr.addstr(6, 0, "Last Four Weeks (avg)", curses.A_BOLD)
    stdscr.addstr(7, 0, str(stat[1]) + " Total: " + str(sum(stat[1])), curses.A_BOLD)

def main(stdscr):
    '''Main function'''
    skip_prompt = False
    will_update_record = False
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(1)
    curses.curs_set(0)

    cache_var = [] # cache current variables (to quickly redraw screen)
    thiswk_stat = [] # this week
    last4k_stat = []
    session_num = 1
    sec_left = WORK_MIN * 60
    try:
        thiswk_stat, last4k_stat = update_record(0)
        while 1:
            if will_update_record:
                thiswk_stat, last4k_stat = update_record(WORK_MIN)
                will_update_record = False
            cache_var = [WORK_MIN, sec_left, session_num, [thiswk_stat, last4k_stat]]
            render_alltext(stdscr, *cache_var)
            if not skip_prompt:
                ans = stdscr.getch()
            if ans == ord('s'):
                if sec_left:
                    sec_left, session_num, skip_prompt, will_update_record = \
                        start_session(stdscr, sec_left, session_num, cache_var)
            elif ans == ord('q'):
                break
            elif ans == curses.KEY_RESIZE:
                stdscr.clear()
                render_alltext(stdscr, WORK_MIN, sec_left, session_num, [thiswk_stat, last4k_stat])
            elif ans == 410: # return value from zenity
                pass
    finally:
        stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()
# --------------------------------------------------------------------------------------------------
# check prerequisites
if which("zenity") is None:
    print("Zenity is not installed. exiting... ")
    sys.exit()
# declare paths
FOLDER_PATH = os.path.expanduser("~") + "/.local/share/lazyman-pomodoro/"
RECORD_PATH = FOLDER_PATH + "record.json"
CONFIG_PATH = FOLDER_PATH + "config.conf"
# create if not exist
os.makedirs(FOLDER_PATH, 0o755, exist_ok=True)
create_file_if_not_exist(RECORD_PATH, "{}")
create_file_if_not_exist(CONFIG_PATH, """[DEFAULT]
WorkMinutes = 25
BreakMinutes = 5
LongbreakMinutes = 15
""")
# read config
CONFIG = configparser.ConfigParser()
CONFIG.read(CONFIG_PATH)
CONF = CONFIG['DEFAULT']
WORK_MIN = CONF.getint('WorkMinutes')
BREAK_MIN = CONF.getint('BreakMinutes')
LONGBREAK_MIN = CONF.getint('LongbreakMinutes')
# read record
try:
    RECORD_JSON = json.loads(Path(RECORD_PATH).read_text())
except ValueError:
    print(RECORD_PATH + " is not a valid JSON. At least try to make it {}.")
    sys.exit()
if __name__ == '__main__':
    curses.wrapper(main)
