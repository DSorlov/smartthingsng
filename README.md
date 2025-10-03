![maintained](https://img.shields.io/maintenance/yes/2025.svg)
[![hacs_badge](https://img.shields.io/badge/hacs-default-green.svg)](https://github.com/custom-components/hacs)
[![ha_version](https://img.shields.io/badge/home%20assistant-2024.10%2B-green.svg)](https://www.home-assistant.io)
![version](https://img.shields.io/badge/version-1.7.0-green.svg)
![stability](https://img.shields.io/badge/stability-stable-green.svg)
[![CI](https://github.com/DSorlov/smartthingsng/workflows/CI/badge.svg)](https://github.com/DSorlov/smartthingsng/actions/workflows/ci.yaml)
[![hassfest](https://github.com/DSorlov/smartthingsng/workflows/Validate%20with%20hassfest/badge.svg)](https://github.com/DSorlov/smartthingsng/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/DSorlov/smartthingsng/workflows/HACS%20Validation/badge.svg)](https://github.com/DSorlov/smartthingsng/actions/workflows/hacs.yaml)
[![maintainer](https://img.shields.io/badge/maintainer-dsorlov-blue.svg)](https://github.com/DSorlov)
[![License](https://img.shields.io/badge/License-Apache-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# SmartThings NG v1.7.0

A SmartThings integration for Home Assistant with advanced features and modern implementation, the official implementation does not implement all devices, and the already existing community integration uses the same namespace and does not provide all devices either. This is a try to remedy that.



## Key Features & Fixes

- **Domain renamed to `smartthingsng`** - Coexists with official SmartThings integration
- **Pure Modern API**: Now exclusively using pysmartthings 3.3.0 
- **Enhanced Performance**: Up to 3x faster JSON processing with orjson
- **Latest Security**: All 2024 security patches and dependency updates (4+ years!)
- **Complete device support** - All SmartThings capabilities and device types
- **Real-time updates** - WebHook-based push notifications  
- **Advanced automation** - Service calls for direct device control
- **Modern codebase** - Latest Home Assistant patterns and compatibility

## Installation

### Via HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=smartthingsng&owner=dsorlov)

1. Open HACS
2. Go to Integrations
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/dsorlov/smartthingsng` as an Integration
6. Search for "SmartThings NG" and install

### Manual Installation

1. Copy the `custom_components/smartthingsng` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "SmartThings NG"

## Configuration

### Prerequisites

Before you begin, ensure that:
- Your Home Assistant instance is accessible via HTTPS (required for webhooks)
  - Use [Nabu Casa](https://www.nabucasa.com/) (easiest option), or
  - Configure your own SSL certificate with external access

### Step-by-Step Setup

1. **Add the Integration**
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "SmartThings NG"

2. **Verify Webhook URL**
   - The integration will show your webhook URL
   - Confirm it starts with `https://`
   - Click "Submit" to continue

3. **Create Personal Access Token**
   - Click the link to open the [SmartThings Token Creation Page](https://account.smartthings.com/tokens)
   - Click "Generate new token"
   - Enter a token name (e.g., "Home Assistant")
   - Select the following authorized scopes:
     - **Devices** (select all device permissions)
   - Click "Generate token"
   - **Important**: Copy the token immediately (it will only be shown once)
   - Paste the token in Home Assistant and click "Submit"

4. **Select Location**
   - Choose which SmartThings Location to integrate
   - Click "Submit"

5. **Authorize Installation**
   - A new browser window will open
   - Log in to your SmartThings account
   - Authorize Home Assistant to access your location
   - Return to Home Assistant

6. **Complete Setup**
   - Your devices should now appear in Home Assistant
   - Check Settings → Devices & Services → SmartThings NG to see all devices

### Troubleshooting

**Webhook URL is not HTTPS:**
- Enable Nabu Casa, or
- Configure external HTTPS access to your Home Assistant instance

**Token is invalid:**
- Ensure you copied the entire token
- Verify the token has the correct device permissions
- Generate a new token if needed

**Devices not appearing:**
- Check that devices are in the selected SmartThings location
- Review Home Assistant logs for errors
- Try removing and re-adding the integration

## Features

### Core Features
- All device types supported by SmartThings
- Real-time push updates via webhooks
- Support for all SmartThings capabilities
- Samsung appliances (refrigerators, washers, dryers, dishwashers)
- Climate control devices
- Sensors and binary sensors
- Lights, switches, locks, covers, and fans
- Media player controls (Samsung TVs, soundbars, streaming devices)
- One-way button controls (scenes, panic buttons, appliance controls)
- Energy monitoring
- Advanced automation with `send_command`, `refresh_device`, `execute_scene`
- Control numeric values (volume, temperature setpoints)
- Control device modes (washer cycles, input sources, etc.)

## Credits

Based on the original work by:
- Home Assistant Core team: https://github.com/home-assistant/core/pull/99924
- contemplator1998: https://github.com/contemplator1998/smartthings

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apahce 2.0 license - see the [LICENSE](LICENSE) file for details.

## Support

- :bug: [Report a Bug](https://github.com/dsorlov/smartthingsng/issues)
- :bulb: [Request a Feature](https://github.com/dsorlov/smartthingsng/issues)
- :book: [Documentation](https://github.com/dsorlov/smartthingsng)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.