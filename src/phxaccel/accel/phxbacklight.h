/* SPDX-License-Identifier: MIT */
#ifndef PHX_BACKLIGHT_H
#define PHX_BACKLIGHT_H
#include <stdint.h>
class IOPCIDevice;
class IOService;
IOService *phxBacklightCreate(IOPCIDevice *pci,IOService *framebuffer,unsigned width,unsigned height);
void phxBacklightPower(IOService *handler,bool awake);
void phxBacklightDestroy(IOService *handler,IOService *framebuffer);
bool phxBacklightEdid(IOService *handler,uint8_t out[128]);
#endif
