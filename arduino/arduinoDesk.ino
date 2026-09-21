#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// ============================================================
// DATA
// ============================================================

String dateLine = "";
String timeLine = "";
String weatherLine = "";
String githubLine = "";
String leetcodeLine = "";
String mediaLine = "";

String pingLine = "...";
String routerLine = "...";

String cpuLine = "...";
String ramLine = "...";

String diskALine = "...";
String diskBLine = "...";

// ============================================================
// TIMING
// ============================================================

unsigned long lastDataTime = 0;

const unsigned long TIMEOUT = 10000;

int currentScreen = 0;

bool screenDrawn = false;

// ============================================================
// CUSTOM CHARACTERS
// ============================================================

byte heart[8] = {
  B00000,
  B01010,
  B11111,
  B11111,
  B11111,
  B01110,
  B00100,
  B00000
};

byte wifiIcon[8] = {
  B01110,
  B10001,
  B00000,
  B01110,
  B00000,
  B00100,
  B00000,
  B00000
};

byte tick[8] = {
  B00000,
  B00001,
  B00010,
  B10100,
  B01000,
  B00000,
  B00000,
  B00000
};

byte cross[8] = {
  B00000,
  B10001,
  B01010,
  B00100,
  B01010,
  B10001,
  B00000,
  B00000
};

// ============================================================
// HELPERS
// ============================================================

void printLine(String text) {

  if (text.length() > 16)
    text = text.substring(0, 16);

  lcd.print(text);

  for (int i = text.length(); i < 16; i++)
    lcd.print(" ");
}


// ============================================================
// INTRO MARQUEE
// ============================================================

void runHeartMarquee(int row) {

  int width = 16;
  int hearts = 5;

  for (int i = 0; i < width + hearts; i++) {

    lcd.setCursor(0, row);
    lcd.print("                ");

    for (int j = 0; j < hearts; j++) {

      int pos = i - j;

      if (pos >= 0 && pos < width) {

        lcd.setCursor(pos, row);
        lcd.write(byte(0));
      }
    }

    delay(200);
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(9600);

  lcd.init();
  lcd.backlight();
  lcd.clear();

  delay(100);

  lcd.createChar(0, heart);
  lcd.createChar(1, wifiIcon);
  lcd.createChar(2, tick);
  lcd.createChar(3, cross);

  lcd.setCursor(2, 0);
  lcd.print("Hi Prashu");
  lcd.write(byte(0));

  runHeartMarquee(1);

  delay(1000);

  lcd.clear();

  lastDataTime = millis();
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop() {

  readSerial();

  // ----------------------------------------------------------
  // NO DATA
  // ----------------------------------------------------------

  if (millis() - lastDataTime > TIMEOUT) {

    showNoData();

    screenDrawn = false;

    return;
  }

  // ----------------------------------------------------------
  // DRAW SCREEN
  // ----------------------------------------------------------

  if (!screenDrawn) {

    lcd.clear();

    displayScreen();

    screenDrawn = true;
  }
}


// ============================================================
// SERIAL
// ============================================================

void readSerial() {

  static String input = "";

  while (Serial.available()) {

    char c = Serial.read();

    if (c == '\n') {

      processData(input);

      input = "";

      lastDataTime = millis();

    } else {

      input += c;
    }
  }
}


// ============================================================
// PROCESS DATA
// ============================================================

void processData(String data) {

  if (data.startsWith("D|"))
    dateLine = data.substring(2);

  else if (data.startsWith("T|"))
    timeLine = data.substring(2);

  else if (data.startsWith("W|"))
    weatherLine = data.substring(2);

  else if (data.startsWith("G|"))
    githubLine = data.substring(2);

  else if (data.startsWith("L|"))
    leetcodeLine = data.substring(2);

  else if (data.startsWith("M|"))
    mediaLine = data.substring(2);

  else if (data.startsWith("P|"))
    pingLine = data.substring(2);

  else if (data.startsWith("F|"))
    routerLine = data.substring(2);

  else if (data.startsWith("S|"))
    cpuLine = data.substring(2);

  else if (data.startsWith("R|"))
    ramLine = data.substring(2);

  else if (data.startsWith("K|"))
    diskALine = data.substring(2);

  else if (data.startsWith("J|"))
    diskBLine = data.substring(2);

  else if (data.startsWith("X|")) {

    int screen = data.substring(2).toInt();

    if (screen >= 0 && screen < 7) {

      currentScreen = screen;
      screenDrawn = false;
    }
  }
}


// ============================================================
// SCREEN SELECTOR
// ============================================================

void displayScreen() {

  switch (currentScreen) {

    case 0:
      showDateTime();
      break;

    case 1:
      showLine("Weather:", weatherLine);
      break;

    case 2:
      showLine("GitHub:", githubLine);
      break;

    case 3:
      showLine("LeetCode:", leetcodeLine);
      break;

    case 4:
      showServer();
      break;

    case 5:
      showDisk();
      break;

    case 6:
      showNetwork();
      break;
  }
}


// ============================================================
// DATE / TIME
// ============================================================

void showDateTime() {

  lcd.setCursor(0, 0);
  printLine(dateLine);

  lcd.setCursor(0, 1);
  printLine(timeLine);
}


// ============================================================
// SIMPLE SCREEN
// ============================================================

void showLine(String title, String value) {

  lcd.setCursor(0, 0);
  printLine(title);

  lcd.setCursor(0, 1);
  printLine(value);
}


// ============================================================
// SERVER
// ============================================================

void showServer() {

  lcd.setCursor(0, 0);
  printLine(cpuLine);

  lcd.setCursor(0, 1);
  printLine(ramLine);
}


// ============================================================
// DISK
// ============================================================

void showDisk() {

  lcd.setCursor(0, 0);
  printLine(diskALine);

  lcd.setCursor(0, 1);
  printLine(diskBLine);
}


// ============================================================
// NETWORK
// ============================================================

void showNetwork() {

  lcd.setCursor(0, 0);

  String line1 = "Ping " + pingLine;

  printLine(line1);

  lcd.setCursor(0, 1);

  String line2 = "Router " + routerLine;

  printLine(line2);
}


// ============================================================
// NO DATA
// ============================================================

void showNoData() {

  lcd.clear();

  lcd.setCursor(4, 0);
  lcd.print("NO DATA");

  lcd.setCursor(1, 1);
  lcd.print("Check Server!");

  delay(1000);
}
