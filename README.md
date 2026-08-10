# Ripper

Telegram channel reporting tool with multi-account support.

## Features

- Multi-account management (add, remove, list)
- Session-based authentication with persistent login
- Optional AES session encryption
- Sequential reporting using all active accounts
- Interactive terminal menu with colored output
- Proxy support (SOCKS5/HTTP)
- Automatic FloodWait handling with smart retry
- Configurable report reason (spam, violence, pornography, etc.)

## Requirements

- Python 3.8 or higher
- Telegram API credentials (`api_id` and `api_hash`)
- Valid Telegram account(s) with phone number

## Installation

```bash
git clone https://github.com/2nixx/Ripper.git
cd Ripper
pip install -r requirements.txt
```

## Usage

Run the tool:

```bash
python ripper.py
```

### Main Menu

```text
1. Add Account
2. List Accounts
3. Remove Account
4. Start Reporting
5. Set API Credentials
6. Exit
```

## Add Account

Select option `1` and provide:

- Phone number with country code (e.g. `+989123456789`)
- API ID and API hash
- Verification code sent by Telegram

Session files are stored in the `sessions/` folder.

## Start Reporting

Select option `4` and provide:

- Channel username (without `@`)
- Number of recent messages to report (default: `3`)
- Delay between reports in seconds (default: `2`)
- Report reason (default: `spam`)

The tool processes all active accounts sequentially.

## Dependencies

- **Telethon** – Telegram API client
- **Colorama** – Terminal colors
- **Cryptography** – Optional session encryption

Install all dependencies:

```bash
pip install -r requirements.txt
```

## FAQ

### Is this tool allowed by Telegram?

Reporting spam or policy-violating content is permitted under Telegram's Terms of Service. This tool automates the reporting process.

### Will my account get banned?

Using this tool responsibly should not result in a ban. Telegram may impose temporary `FloodWait` restrictions, which the tool handles automatically.

### Can I use multiple accounts?

Yes. Add multiple accounts and the tool will use all active accounts sequentially.

### How do I get `api_id` and `api_hash`?

Visit https://my.telegram.org/apps and create a new application.

## Contributing

Issues and pull requests are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a pull request

## License

See the `LICENSE` file for details.

## Contact Us

- **Telegram Channel:** @NetworkCriminals
