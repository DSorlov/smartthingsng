# Changelog

All notable changes to this project will be documented in this file.

## [1.7.0] - 2025-10-03

### Enhanced Diagnostics & Monitoring

Added comprehensive system health monitoring and device diagnostics to help you keep track of your SmartThings setup.

**New diagnostic sensors:**
- Device counts (total, healthy, warning, error states)
- Battery monitoring (battery-powered devices, low battery alerts)  
- Network quality (average signal strength across devices)
- System uptime and integration performance

**New services:**
- `get_diagnostics` - Generate detailed system health reports
- `device_health_check` - Test device connectivity and performance

**Enhanced device information:**
All your SmartThings devices now show detailed diagnostic info including firmware versions, signal strength, battery health, and update statistics.

---

## [1.6.0] - 2025-10-03

### Robot Vacuum Support

Added full support for SmartThings robot vacuums with proper Home Assistant vacuum entity integration.

**What works:**
- Start, stop, pause cleaning
- Return to dock/charging station
- Different cleaning modes (auto, spot, edge, turbo)
- Battery level monitoring
- Real-time status updates

**Supported devices:**
- Samsung robot vacuums (full feature support)
- Generic SmartThings-compatible cleaners
- Basic models with essential controls

---

## [1.5.0] - 2025-10-03

### Media Player Support

Added media player platform for TVs, soundbars, and streaming devices.

**What you can control:**
- Volume (set level, mute/unmute, step up/down)
- Playback (play, pause, stop, next/previous)
- TV channels and input sources (HDMI, etc.)
- Power on/off

**Supported devices:**
- Samsung Smart TVs (full feature set)
- Soundbars and audio systems
- Streaming devices and AV receivers

---

## [1.4.0] - 2025-10-03

### Button Controls

Added button platform for one-way controls and automation triggers.

**Button types available:**
- Scene execution buttons
- Appliance controls (washer, dryer, dishwasher start/stop)
- Safety device testing (smoke, CO, water sensors)
- Robot vacuum controls
- Doorbell and chime buttons
- TV input switching

Perfect for creating simple automation triggers and one-tap controls.

---

## [1.3.0] - 2025-10-03

### Code Cleanup & Performance

Cleaned up the codebase by removing old compatibility layers and streamlining the code.

**What changed:**
- Removed legacy pysmartthings 0.7.8 support (now requires 3.3.0+)
- Simplified service calls for better reliability
- Removed 120+ lines of compatibility code
- Faster startup and lower memory usage

**Benefits:**
- More reliable device commands
- Better error messages when things go wrong
- Easier to maintain and add new features

---

## [1.2.0] - 2025-10-03

### Major Performance & Security Update

Upgraded the core SmartThings library with 4+ years of improvements and security fixes.

**What's better:**
- Much faster JSON processing (better performance)
- 4+ years of security patches included
- Better error handling and diagnostics
- More stable connections to SmartThings

**Migration:**
No action needed - automatic upgrade with zero downtime and full compatibility with existing setups.

---

## [1.1.0] - 2025-10-03

### More Control Options

Added new ways to control your SmartThings devices.

**New controls:**
- **Select dropdowns** - Choose washing machine modes, AC settings, oven modes, etc.
- **Number inputs** - Set volumes, temperatures, and other numeric values
- **Advanced services** - Send custom commands, refresh devices, execute scenes

**What you can now control:**
- Appliance modes (washer, dryer, dishwasher, oven)
- Media input sources and volumes
- Temperature setpoints for fridges and ovens
- Custom device commands for automation

## [1.0.0] - 2025-10-03

### 🎉 Initial Release

Complete SmartThings integration that works alongside the official Home Assistant integration.

**Key features:**
- **New domain** - Uses `smartthingsng` so it won't conflict with the official integration
- **Complete device support** - All SmartThings device types and capabilities
- **Easy setup** - Step-by-step configuration with direct links to create tokens
- **Modern codebase** - Built for Home Assistant 2024.1.0+ with latest patterns

**Supported devices:**
- Climate control (thermostats, AC units)
- Sensors and appliances (fridges, washers, dryers, dishwashers)
- Lights, switches, locks, and covers
- All standard SmartThings device types

**Migration from old version:**
If you used a previous version, you'll need to remove the old integration and set this up fresh with your SmartThings Personal Access Token. The new domain means both integrations can coexist if needed.

## Credits
Based on the original work by:
- Home Assistant Core team: https://github.com/home-assistant/core/pull/99924
- contemplator1998: https://github.com/contemplator1998/smartthings
