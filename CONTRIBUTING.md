# Contributing to SmartThings NG

Thank you for considering contributing to SmartThings NG! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive in all interactions. We're all here to improve this integration for everyone.

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report:
1. Check existing issues to see if the problem has already been reported
2. Collect relevant information (Home Assistant version, device types, logs)
3. Use the bug report template when creating a new issue

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:
1. Use a clear and descriptive title
2. Provide a detailed description of the suggested enhancement
3. Explain why this enhancement would be useful
4. Include examples if applicable

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes
4. Test your changes thoroughly
5. Follow the coding style of the project
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11 or newer
- Home Assistant development environment
- SmartThings account with devices

### Setting Up Development Environment

1. Clone your fork:
```bash
git clone https://github.com/yourusername/smartthingsng.git
cd smartthingsng
```

2. Create a symbolic link to your Home Assistant config:
```bash
ln -s $(pwd)/custom_components/smartthingsng ~/.homeassistant/custom_components/
```

3. Restart Home Assistant to load the development version

### Running Tests

Before submitting a PR, ensure your code:
- Has no syntax errors
- Follows Home Assistant coding standards
- Works with the latest Home Assistant release

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add docstrings to functions and classes
- Keep functions focused and single-purpose

Example:
```python
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartThings sensors from a config entry."""
    # Implementation
```

## Project Structure

```
custom_components/smartthingsng/
├── __init__.py          # Integration setup
├── binary_sensor.py     # Binary sensor platform
├── climate.py           # Climate platform
├── config_flow.py       # Configuration flow
├── const.py             # Constants
├── cover.py             # Cover platform
├── fan.py               # Fan platform
├── light.py             # Light platform
├── lock.py              # Lock platform
├── manifest.json        # Integration manifest
├── scene.py             # Scene platform
├── sensor.py            # Sensor platform
├── smartapp.py          # SmartApp webhook handling
├── strings.json         # UI strings
└── switch.py            # Switch platform
```

## Adding Support for New Capabilities

When adding support for new SmartThings capabilities:

1. Update `const.py` with any new constants
2. Add capability mapping in the appropriate platform file
3. Test with actual devices if possible
4. Document the new capability in the PR description

Example for adding a sensor capability:
```python
# In sensor.py
CAPABILITY_TO_SENSORS: dict[str, list[Map]] = {
    # ... existing capabilities ...
    Capability.new_capability: [
        Map(
            Attribute.new_attribute,
            "Display Name",
            "unit",
            SensorDeviceClass.APPROPRIATE_CLASS,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
}
```

## Commit Messages

Use clear and descriptive commit messages:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs when applicable

Examples:
```
Add support for dishwasher completion time sensor
Fix temperature unit conversion for thermostats
Update documentation for installation process
```

## Documentation

When adding new features:
- Update README.md if necessary
- Add entries to CHANGELOG.md
- Document breaking changes clearly
- Include examples where helpful

## Questions?

If you have questions about contributing:
1. Check existing issues and discussions
2. Open a new discussion on GitHub
3. Reference relevant documentation

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE.md).
