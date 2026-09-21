import os
import time
import subprocess
from datetime import datetime

import requests
import serial
import serial.tools.list_ports
import psutil


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_FILE = "/opt/arduino-desk/config/config.env"

LCD_WIDTH = 16

WEATHER_INTERVAL = 300
GITHUB_INTERVAL = 600
LEETCODE_INTERVAL = 600
SYSTEM_INTERVAL = 5
SMART_INTERVAL = 1800
PING_INTERVAL = 10
LCD_INTERVAL = 1

CONNECT_RETRY_DELAY = 2
CONNECT_TIMEOUT = 60


# ============================================================
# LOAD CONFIG
# ============================================================

def load_config():
    config = {}

    if not os.path.exists(CONFIG_FILE):
        return config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip('"').strip("'")

    return config


CONFIG = load_config()

API_KEY = CONFIG["OPENWEATHER_API_KEY"]
GITHUB_USER = CONFIG["GITHUB_USER"]
LEETCODE_USER = CONFIG["LEETCODE_USER"]
ARDUINO_PORT = CONFIG["ARDUINO_PORT"]
SERIAL_BAUD = int(CONFIG["ARDUINO_BAUD"])
CITY = CONFIG["CITY"]

ROUTER_IP = CONFIG.get("ROUTER_IP", "192.168.1.1")
PING_HOST = CONFIG.get("PING_HOST", "8.8.8.8")


# ============================================================
# STATE
# ============================================================

ser = None

weather_data = "Loading..."
github_data = "Loading..."
leetcode_data = "Loading..."

cpu_usage = 0
ram_usage = 0
ram_used = 0
ram_total = 0

cpu_temp = None

storage_usage = 0
storage_free = 0

sda_temp = None
sdb_temp = None
sda_smart = "?"
sdb_smart = "?"

ping_data = "..."
router_data = "..."

last_weather_time = 0
last_github_time = 0
last_leetcode_time = 0
last_system_time = 0
last_smart_time = 0
last_ping_time = 0
last_lcd_time = 0

current_screen = 0
last_screen_time = 0
last_reconnect_time = 0

SCREEN_INTERVAL = 5


# ============================================================
# SERIAL
# ============================================================

def close_serial():
    global ser

    if ser:
        try:
            ser.close()
        except Exception:
            pass

    ser = None


def try_connect():
    global ser

    if ser and ser.is_open:
        return True

    close_serial()

    try:
        if os.path.exists(ARDUINO_PORT):
            print(f"Connecting to {ARDUINO_PORT}...")

            ser = serial.Serial(
                ARDUINO_PORT,
                SERIAL_BAUD,
                timeout=1
            )

            time.sleep(2)

            print("Arduino connected.")
            return True

    except Exception as e:
        print(f"Arduino connection error: {e}")

    return False


# ============================================================
# WEATHER
# ============================================================

def get_weather():

    if not API_KEY:
        return "No Weather"

    try:
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}"
            f"&appid={API_KEY}"
            "&units=metric"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        temperature = data["main"]["temp"]
        condition = data["weather"][0]["main"][:8]

        return f"{temperature:.1f}C {condition}"

    except Exception as e:
        print("Weather error:", e)
        return "Weather Err"


# ============================================================
# GITHUB
# ============================================================

def get_github():

    try:

        profile = requests.get(
            f"https://api.github.com/users/{GITHUB_USER}",
            timeout=10
        )

        profile.raise_for_status()
        profile = profile.json()

        contributions = requests.get(
            f"https://github-contributions-api.jogruber.de/v4/"
            f"{GITHUB_USER}?y=all",
            timeout=15
        )

        contributions.raise_for_status()
        contributions = contributions.json()

        repos = profile.get("public_repos", 0)

        contribution_list = contributions.get(
            "contributions",
            []
        )

        streak = 0

        if contribution_list:

            for day in reversed(contribution_list):

                if day.get("count", 0) > 0:
                    streak += 1
                else:
                    break

        total_contributions = sum(
            (contributions.get("total") or {}).values()
        )

        return (
            f"R:{repos} "
            f"S:{streak} "
            f"C:{total_contributions}"
        )

    except Exception as e:

        print("GitHub error:", e)

        return "GitHub Err"


# ============================================================
# LEETCODE
# ============================================================

def get_leetcode():

    try:

        query = """
        {
          matchedUser(username: "%s") {
            submitStats {
              acSubmissionNum {
                difficulty
                count
              }
            }
          }
        }
        """ % LEETCODE_USER

        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query},
            headers={
                "Content-Type": "application/json"
            },
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        stats = (
            data["data"]
            ["matchedUser"]
            ["submitStats"]
            ["acSubmissionNum"]
        )

        total = 0
        easy = 0
        medium = 0
        hard = 0

        for item in stats:

            difficulty = item["difficulty"]
            count = item["count"]

            if difficulty == "All":
                total = count

            elif difficulty == "Easy":
                easy = count

            elif difficulty == "Medium":
                medium = count

            elif difficulty == "Hard":
                hard = count

        return f"{total} E{easy} M{medium} H{hard}"

    except Exception as e:

        print("LeetCode error:", e)

        return "LC Err"


# ============================================================
# CPU TEMPERATURE
# ============================================================

def get_cpu_temperature():

    try:

        sensors = psutil.sensors_temperatures()

        if "coretemp" in sensors:

            entries = sensors["coretemp"]

            package_temp = None

            for entry in entries:

                if entry.label.lower() == "package id 0":
                    package_temp = entry.current
                    break

            if package_temp is not None:
                return package_temp

            if entries:
                return max(
                    entry.current
                    for entry in entries
                )

        return None

    except Exception as e:

        print("CPU temperature error:", e)

        return None


# ============================================================
# HDD TEMPERATURE
# ============================================================
def get_disk_temperature(device):

    try:

        result = subprocess.run(
            [
                "/usr/bin/sudo",
                "-n",
                "/usr/local/sbin/arduino-desk-smartctl",
                "-A",
                device
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        temperature_lines = []

        for line in result.stdout.splitlines():

            if "Temperature_Celsius" in line:
                temperature_lines.insert(0, line)

            elif "Airflow_Temperature_Cel" in line:
                temperature_lines.append(line)

        for line in temperature_lines:

            parts = line.split()

            # SMART format:
            #
            # ID
            # ATTRIBUTE_NAME
            # FLAG
            # VALUE
            # WORST
            # THRESH
            # TYPE
            # UPDATED
            # WHEN_FAILED
            # RAW_VALUE
            #
            # RAW_VALUE is therefore parts[9].

            if len(parts) >= 10:

                raw_value = parts[9]

                # Handle values such as:
                # 39
                # 40
                # 39 (0 25 0 0 0)

                if raw_value.isdigit():

                    temperature = int(raw_value)

                    if 0 < temperature < 100:
                        return temperature

        return None

    except Exception as e:

        print(f"SMART temperature error {device}:", e)

        return None


# ============================================================
# SMART HEALTH
# ============================================================

def get_smart_health(device):

    try:

        result = subprocess.run(
            [
                "/usr/bin/sudo",
                "-n",
                "/usr/local/sbin/arduino-desk-smartctl",
                "-H",
                device
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout.upper()

        if "PASSED" in output:
            return "OK"

        if "FAILED" in output:
            return "BAD"

        return "?"

    except Exception as e:

        print(f"SMART health error {device}:", e)

        return "?"


# ============================================================
# SYSTEM INFORMATION
# ============================================================

def update_system_info():

    global cpu_usage
    global ram_usage
    global ram_used
    global ram_total
    global cpu_temp
    global storage_usage
    global storage_free

    cpu_usage = int(psutil.cpu_percent(interval=None))

    memory = psutil.virtual_memory()

    ram_usage = int(memory.percent)

    ram_used = memory.used / (1024 ** 3)
    ram_total = memory.total / (1024 ** 3)

    cpu_temp = get_cpu_temperature()

    try:

        disk = psutil.disk_usage("/srv/storage")

        storage_usage = int(disk.percent)
        storage_free = disk.free / (1024 ** 3)

    except Exception:

        storage_usage = 0
        storage_free = 0


# ============================================================
# NETWORK PING
# ============================================================

def ping_host(host):

    try:

        result = subprocess.run(
            [
                "ping",
                "-c",
                "1",
                "-W",
                "3",
                host
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():

            if "time=" in line:

                value = line.split("time=")[1]

                value = value.split()[0]

                value = value.replace("ms", "")

                return float(value)

        return None

    except Exception:

        return None


def update_network():

    global ping_data
    global router_data

    internet_ping = ping_host(PING_HOST)

    if internet_ping is None:
        ping_data = "No Net"

    else:
        ping_data = f"{int(internet_ping)}ms"

    router_ping = ping_host(ROUTER_IP)

    if router_ping is None:

        router_data = "Lost"

    elif router_ping <= 5:

        router_data = "Strong"

    elif router_ping <= 20:

        router_data = "OK"

    elif router_ping <= 50:

        router_data = "Weak"

    else:

        router_data = "Poor"


# ============================================================
# SMART UPDATE
# ============================================================

def update_smart():

    global sda_temp
    global sdb_temp
    global sda_smart
    global sdb_smart

    sda_temp = get_disk_temperature("/dev/sda")
    sdb_temp = get_disk_temperature("/dev/sdb")

    sda_smart = get_smart_health("/dev/sda")
    sdb_smart = get_smart_health("/dev/sdb")


# ============================================================
# LCD HELPERS
# ============================================================

def lcd_line(text):

    text = str(text)

    if len(text) > LCD_WIDTH:
        return text[:LCD_WIDTH]

    return text.ljust(LCD_WIDTH)


def send(tag, value):

    global ser

    if not ser or not ser.is_open:
        return False

    try:

        message = f"{tag}|{lcd_line(value)}\n"

        ser.write(message.encode("utf-8"))
        ser.flush()

        return True

    except Exception as e:

        print("Serial error:", e)

        close_serial()

        return False


# ============================================================
# SCREENS
# ============================================================

def screen_datetime():

    now = datetime.now()

    date = now.strftime("%a %d %b")
    current_time = now.strftime("%I:%M %p")

    # Percentage of the current day completed
    minutes_today = now.hour * 60 + now.minute
    day_percent = int((minutes_today / 1440) * 100)

    percent_text = f"{day_percent}%"

    # Right-align percentage on the 16-character LCD
    time_display = (
        f"{current_time}"
        f"{percent_text:>{LCD_WIDTH - len(current_time)}}"
    )

    send("D", date)
    send("T", time_display)


def screen_weather():

    send("W", weather_data)


def screen_github():

    send("G", github_data)


def screen_leetcode():

    send("L", leetcode_data)


def screen_server():

    temp = "--"

    if cpu_temp is not None:
        temp = f"{int(cpu_temp)}C"

    # CPU: CPU <usage>% <temperature>
    send(
        "S",
        f"CPU {cpu_usage}% {temp}"
    )

    # RAM: RAM <usage>% <used>/<total>
    send(
        "R",
        f"RAM {ram_usage}% {ram_used:.1f}/{ram_total:.1f}G"
    )


def screen_disk():

    temp1 = "--" if sda_temp is None else f"{sda_temp}C"
    temp2 = "--" if sdb_temp is None else f"{sdb_temp}C"

    # HDD1 = /dev/sda
    send(
        "K",
        f"HDD1(sda) {temp1} {sda_smart}"
    )

    # HDD2 = /dev/sdb
    send(
        "J",
        f"HDD2(sdb) {temp2} {sdb_smart}"
    )


def screen_network():

    send("P", ping_data)
    send("F", router_data)


def update_lcd():

    global current_screen
    global last_screen_time

    now = time.time()

    if now - last_screen_time >= SCREEN_INTERVAL:

        current_screen = (current_screen + 1) % 7

        last_screen_time = now

    # Tell Arduino which screen to display
    send("X", str(current_screen))

    if current_screen == 0:
        screen_datetime()

    elif current_screen == 1:
        screen_weather()

    elif current_screen == 2:
        screen_github()

    elif current_screen == 3:
        screen_leetcode()

    elif current_screen == 4:
        screen_server()

    elif current_screen == 5:
        screen_disk()

    elif current_screen == 6:
        screen_network()


# ============================================================
# MAIN
# ============================================================

def main():

    global weather_data
    global github_data
    global leetcode_data
    
    global last_weather_time
    global last_github_time
    global last_leetcode_time
    global last_system_time
    global last_smart_time
    global last_ping_time
    global last_lcd_time

    global current_screen
    global last_screen_time
    global last_reconnect_time

    try_connect()

    print("Arduino Desk started.")

    while True:

        now = time.time()

        # Weather
        if now - last_weather_time >= WEATHER_INTERVAL:

            weather_data = get_weather()

            last_weather_time = now

        # GitHub
        if now - last_github_time >= GITHUB_INTERVAL:

            github_data = get_github()

            last_github_time = now

        # LeetCode
        if now - last_leetcode_time >= LEETCODE_INTERVAL:

            leetcode_data = get_leetcode()

            last_leetcode_time = now

        # System
        if now - last_system_time >= SYSTEM_INTERVAL:

            update_system_info()

            last_system_time = now

        # SMART
        if now - last_smart_time >= SMART_INTERVAL:

            update_smart()

            last_smart_time = now

        # Network
        if now - last_ping_time >= PING_INTERVAL:

            update_network()

            last_ping_time = now

        # LCD
        if now - last_lcd_time >= LCD_INTERVAL:

            update_lcd()

            last_lcd_time = now

        # Reconnect Arduino (non-blocking, retry every 2 seconds)
        if not ser or not ser.is_open:

            if now - last_reconnect_time >= CONNECT_RETRY_DELAY:

                try_connect()

                last_reconnect_time = now

        time.sleep(0.5)


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print("Arduino Desk stopped.")

    finally:

        close_serial()
