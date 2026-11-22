#include <Adafruit_NeoPixel.h>
#include "config.h"
#ifdef __AVR__
 #include <avr/power.h> // Required for 16 MHz Adafruit Trinket
#endif

#define LED_PIN     6
// #define NUM_LEDS   219
#define EXPECTED_BYTES (NUM_LEDS * 3)
// #define BAUD_RATE 100000
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

// Temporary buffer to hold incoming serial data
uint8_t colorBuffer[EXPECTED_BYTES];

const int statusLed = LED_BUILTIN;

void setup() {
  Serial.begin(BAUD_RATE);
  Serial.setTimeout(10);
  pinMode(statusLed, OUTPUT);
  strip.begin();
  strip.show();
}

void loop() {
  if (Serial.available() > 0) {
      uint8_t command = Serial.read();

      if (command == 0x01) {
        uint8_t brightness = 0;
        uint8_t endMarker = 0;
        int brightnessBytesRead = Serial.readBytes((char*)&brightness, 1);
        int endBytesRead = Serial.readBytes((char*)&endMarker, 1);

        if (brightnessBytesRead == 1 && endBytesRead == 1 && endMarker == 0x03) {
          strip.setBrightness(brightness);
          strip.show();
        }
      } else if (command == 0x10) {
        // handshake - validate serial port
        while (Serial.available() < 1) {
          // Wait for the end marker of the complete ping frame.
        }
        uint8_t endMarker = Serial.read();
        if (endMarker == 0x03) {
          const uint8_t response[] = {0x11, 'R', 'P', 'I', 'T', 'V', 0x03};
          Serial.write(response, sizeof(response));
          Serial.flush();
        }
      } else if (command == 0x02) {
      int bytesRead = Serial.readBytes((char*)colorBuffer, EXPECTED_BYTES);
      uint8_t endMarker = 0;
      int endBytesRead = Serial.readBytes((char*)&endMarker, 1);

      if (bytesRead == EXPECTED_BYTES && endBytesRead == 1 && endMarker == 0x03) {
        for (int i = 0; i < NUM_LEDS; i++) {
          int baseIdx = i * 3;
          strip.setPixelColor(
            i,
            strip.Color(
              colorBuffer[baseIdx],
              colorBuffer[baseIdx + 1],
              colorBuffer[baseIdx + 2]
            )
          );
        }

        strip.show();
        // digitalWrite(statusLed, !digitalRead(statusLed));
      }
    }
  }
}