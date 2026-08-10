#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field

try:
    from telethon import TelegramClient, errors
    from telethon.tl.functions.messages import ReportRequest
except ImportError:
    print("[ERROR] Telethon is not installed. Run: pip install telethon")
    sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class Fore:
        RED = ''
        GREEN = ''
        YELLOW = ''
        CYAN = ''
        WHITE = ''
        RESET = ''
    class Style:
        RESET_ALL = ''

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class Logger:
    def __init__(self, colorized: bool = True, level: str = "INFO"):
        self.colorized = colorized
        self.level = level.upper()
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}

    def _log(self, level: str, message: str):
        if self.levels.get(level, 0) < self.levels.get(self.level, 1):
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        if self.colorized:
            colors = {
                "DEBUG": Fore.CYAN,
                "INFO": Fore.GREEN,
                "WARNING": Fore.YELLOW,
                "ERROR": Fore.RED
            }
            prefix = f"{colors.get(level, Fore.WHITE)}{prefix}{Style.RESET_ALL}"
        print(f"{prefix} {message}")

    def debug(self, msg):
        self._log("DEBUG", msg)

    def info(self, msg):
        self._log("INFO", msg)

    def warning(self, msg):
        self._log("WARNING", msg)

    def error(self, msg):
        self._log("ERROR", msg)

    def success(self, msg):
        self._log("INFO", f"{Fore.GREEN}{msg}{Style.RESET_ALL}")

    def fail(self, msg):
        self._log("ERROR", f"{Fore.RED}{msg}{Style.RESET_ALL}")


class CryptoUtils:
    def __init__(self, salt: str = ""):
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not installed")
        self.salt = salt.encode() if salt else os.urandom(16)
        self.iterations = 100000

    def _derive_key(self, password: str = "ripper_default") -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=self.iterations
        )
        return kdf.derive(password.encode())

    def encrypt(self, data: bytes, password: str = "ripper_default") -> bytes:
        key = self._derive_key(password)
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv))
        encryptor = cipher.encryptor()
        return iv + encryptor.update(data) + encryptor.finalize()

    def decrypt(self, data: bytes, password: str = "ripper_default") -> bytes:
        key = self._derive_key(password)
        iv = data[:16]
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv))
        decryptor = cipher.decryptor()
        return decryptor.update(data[16:]) + decryptor.finalize()


@dataclass
class Account:
    phone: str
    session_name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    last_used: Optional[str] = None
    report_count: int = 0


class AccountManager:
    def __init__(self, data_dir: Path = Path("./sessions")):
        self.data_dir = data_dir
        self.accounts_file = data_dir / "accounts.json"
        self._ensure_dirs()
        self._accounts: List[Account] = self._load()

    def _ensure_dirs(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.accounts_file.exists():
            self.accounts_file.write_text("[]")

    def _load(self) -> List[Account]:
        try:
            data = json.loads(self.accounts_file.read_text())
            return [Account(**item) for item in data]
        except:
            return []

    def _save(self):
        self.accounts_file.write_text(
            json.dumps([asdict(acc) for acc in self._accounts], indent=2)
        )

    def add(self, phone: str) -> Account:
        session_name = f"session_{phone.replace('+', '').replace(' ', '')}"
        acc = Account(phone=phone, session_name=session_name)
        self._accounts.append(acc)
        self._save()
        return acc

    def remove(self, phone: str) -> bool:
        self._accounts = [a for a in self._accounts if a.phone != phone]
        self._save()
        return True

    def get(self, phone: str) -> Optional[Account]:
        for acc in self._accounts:
            if acc.phone == phone:
                return acc
        return None

    def get_active(self) -> List[Account]:
        return [a for a in self._accounts if a.is_active]

    def list(self) -> List[Dict]:
        return [asdict(acc) for acc in self._accounts]

    def mark_used(self, phone: str):
        acc = self.get(phone)
        if acc:
            acc.last_used = datetime.now().isoformat()
            acc.report_count += 1
            self._save()


class SessionManager:
    def __init__(self, data_dir: Path = Path("./sessions"), encrypt: bool = False, salt: str = ""):
        self.data_dir = data_dir
        self.encrypt = encrypt
        self.crypto = CryptoUtils(salt) if encrypt and CRYPTO_AVAILABLE else None
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, name: str) -> Path:
        return self.data_dir / name

    async def create_session(self, api_id: int, api_hash: str, phone: str) -> Tuple[bool, str]:
        session_name = f"session_{phone.replace('+', '').replace(' ', '')}"
        session_path = self._get_session_path(session_name)
        client = TelegramClient(str(session_path), api_id, api_hash)
        try:
            await client.start(phone=phone)
            await client.disconnect()
            if self.encrypt and self.crypto and session_path.exists():
                data = session_path.read_bytes()
                encrypted = self.crypto.encrypt(data)
                session_path.write_bytes(encrypted)
            return True, session_name
        except errors.rpcerrorlist.PhoneNumberInvalidError:
            return False, "Invalid phone number"
        except errors.rpcerrorlist.FloodWaitError as e:
            return False, f"Flood wait: {e.seconds}s"
        except Exception as e:
            return False, str(e)

    async def get_client(self, api_id: int, api_hash: str, account) -> TelegramClient:
        session_path = self._get_session_path(account.session_name)
        if self.encrypt and self.crypto and session_path.exists():
            data = session_path.read_bytes()
            try:
                decrypted = self.crypto.decrypt(data)
                session_path.write_bytes(decrypted)
            except:
                pass
        return TelegramClient(str(session_path), api_id, api_hash)


class Reporter:
    def __init__(self, client: TelegramClient, logger: Logger):
        self.client = client
        self.logger = logger
        self.report_count = 0
        self.errors = 0

    async def report_messages(self, chat_username: str, message_ids: List[int],
                              delay: float = 2.0, option: str = "spam") -> bool:
        try:
            await self.client(ReportRequest(
                peer=chat_username,
                id=message_ids,
                option=b'',
                message=b''
            ))
            self.report_count += 1
            await asyncio.sleep(delay)
            return True
        except errors.rpcerrorlist.FloodWaitError as e:
            self.logger.error(f"FloodWait: {e.seconds}s for {chat_username}")
            self.errors += 1
            await asyncio.sleep(min(e.seconds + 1, 60))
            return False
        except errors.rpcerrorlist.ChannelPrivateError:
            self.logger.error(f"Channel {chat_username} is private")
            self.errors += 1
            return False
        except Exception as e:
            self.logger.error(f"Error reporting {chat_username}: {e}")
            self.errors += 1
            return False

    async def report_last_messages(self, chat_username: str, count: int = 3,
                                   delay: float = 2.0, option: str = "spam") -> bool:
        try:
            messages = await self.client.get_messages(chat_username, limit=count)
            if not messages:
                self.logger.warning(f"No messages found in {chat_username}")
                return False
            message_ids = [msg.id for msg in messages]
            return await self.report_messages(chat_username, message_ids, delay, option)
        except Exception as e:
            self.logger.error(f"Error getting messages from {chat_username}: {e}")
            self.errors += 1
            return False

    def get_stats(self) -> dict:
        total = self.report_count + self.errors
        return {
            "reports": self.report_count,
            "errors": self.errors,
            "success_rate": round(self.report_count / total * 100, 2) if total > 0 else 0
        }


class RipperCLI:
    def __init__(self):
        self.logger = Logger(colorized=True)
        self.account_manager = AccountManager()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        config_path = Path("config.json")
        default = {
            "telethon": {"api_id": 0, "api_hash": ""},
            "report": {"default_delay": 2, "max_messages": 3, "option": "spam"},
            "proxy": {"enabled": False, "type": "socks5", "host": "127.0.0.1", "port": 1080},
            "crypto": {"encrypt_sessions": False, "salt": "static_salt_placeholder"},
            "logging": {"level": "INFO", "colorized": True}
        }
        if config_path.exists():
            try:
                with open(config_path) as f:
                    return {**default, **json.load(f)}
            except:
                return default
        return default

    def _save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)

    # ======================== NEW MENU DESIGN ========================
    def _print_menu(self):
        ascii_art = f"""
{Fore.YELLOW}   ██████╗ ██╗██████╗ ██████╗ ███████╗██████╗
{Fore.YELLOW}   ██╔══██╗██║██╔══██╗██╔══██╗██╔════╝██╔══██╗
{Fore.CYAN}   ██████╔╝██║██████╔╝██████╔╝█████╗  ██████╔╝
{Fore.CYAN}   ██╔══██╗██║██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗
{Fore.RED}   ██║  ██║██║██║     ██║     ███████╗██║  ██║
{Fore.RED}   ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝{Style.RESET_ALL}
"""
        print(ascii_art)
        print(f"{Fore.YELLOW}  ╔═══════════════════════════════════════════════╗")
        print(f"  ║ {Fore.WHITE}        TELEGRAM REPORTING TOOL               {Fore.YELLOW}║")
        print(f"  ╠═══════════════════════════════════════════════╣")
        print(f"  ║  {Fore.CYAN}1.{Fore.WHITE} Add Account                         {Fore.YELLOW}║")
        print(f"  ║  {Fore.CYAN}2.{Fore.WHITE} List Accounts                       {Fore.YELLOW}║")
        print(f"  ║  {Fore.CYAN}3.{Fore.WHITE} Remove Account                      {Fore.YELLOW}║")
        print(f"  ║  {Fore.CYAN}4.{Fore.WHITE} Start Reporting                     {Fore.YELLOW}║")
        print(f"  ║  {Fore.CYAN}5.{Fore.WHITE} Set API Credentials                 {Fore.YELLOW}║")
        print(f"  ║  {Fore.RED}6.{Fore.WHITE} Exit                               {Fore.YELLOW}║")
        print(f"  ╚═══════════════════════════════════════════════╝{Style.RESET_ALL}")

    def _get_input(self, prompt: str, default: str = "", required: bool = True) -> str:
        while True:
            value = input(f"{Fore.CYAN}{prompt} {Fore.WHITE}: {Style.RESET_ALL}").strip()
            if value:
                return value
            if not required:
                return default
            print(f"{Fore.RED}This field is required. Please try again.{Style.RESET_ALL}")

    def _get_int_input(self, prompt: str, default: int = 0) -> int:
        while True:
            value = input(f"{Fore.CYAN}{prompt} {Fore.WHITE}: {Style.RESET_ALL}").strip()
            if not value and default:
                return default
            try:
                return int(value)
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")

    def _get_float_input(self, prompt: str, default: float = 0.0) -> float:
        while True:
            value = input(f"{Fore.CYAN}{prompt} {Fore.WHITE}: {Style.RESET_ALL}").strip()
            if not value and default:
                return default
            try:
                return float(value)
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")

    def _cmd_list(self):
        accounts = self.account_manager.list()
        if not accounts:
            self.logger.warning("No accounts found")
            return
        self.logger.info(f"Found {len(accounts)} account(s):")
        for acc in accounts:
            status = "Active" if acc['is_active'] else "Inactive"
            self.logger.info(f"  {acc['phone']} | {status} | Reports: {acc['report_count']}")

    def _cmd_remove(self, phone: str):
        if not phone:
            self.logger.error("Phone number is required")
            return
        if self.account_manager.remove(phone):
            self.logger.success(f"Account {phone} removed")
        else:
            self.logger.fail(f"Account {phone} not found")

    async def _cmd_add(self, phone: str, api_id: int, api_hash: str):
        if not phone or not api_id or not api_hash:
            self.logger.error("Phone, API ID, and API Hash are required")
            return
        self.logger.info(f"Adding account: {phone}")
        session_mgr = SessionManager(
            encrypt=self.config['crypto']['encrypt_sessions'],
            salt=self.config['crypto']['salt']
        )
        success, msg = await session_mgr.create_session(api_id, api_hash, phone)
        if success:
            self.account_manager.add(phone)
            self.logger.success(f"Account {phone} added successfully")
        else:
            self.logger.fail(f"Failed to add account: {msg}")

    async def _cmd_report(self, channel: str, count: int, delay: float, option: str):
        if not channel:
            self.logger.error("Channel is required for reporting")
            return
        accounts = self.account_manager.get_active()
        if not accounts:
            self.logger.error("No active accounts found. Add an account first.")
            return

        api_id = self.config['telethon']['api_id']
        api_hash = self.config['telethon']['api_hash']
        if not api_id or not api_hash:
            self.logger.error("API credentials not set. Please set them in menu option 5.")
            return

        self.logger.info(f"Starting reporting on {channel} with {len(accounts)} account(s)")
        session_mgr = SessionManager(encrypt=self.config['crypto']['encrypt_sessions'])

        success_count = 0
        for acc in accounts:
            self.logger.info(f"Using account: {acc.phone}")
            try:
                client = await session_mgr.get_client(api_id, api_hash, acc)
                await client.connect()
                if not await client.is_user_authorized():
                    self.logger.error(f"Account {acc.phone} not authorized")
                    continue
                reporter = Reporter(client, self.logger)
                result = await reporter.report_last_messages(channel, count, delay, option)
                if result:
                    success_count += 1
                    self.account_manager.mark_used(acc.phone)
                stats = reporter.get_stats()
                self.logger.info(
                    f"Account {acc.phone}: {stats['reports']} reports, "
                    f"{stats['errors']} errors, {stats['success_rate']}% success"
                )
                await client.disconnect()
            except Exception as e:
                self.logger.error(f"Error with {acc.phone}: {e}")

        self.logger.success(f"Completed: {success_count}/{len(accounts)} accounts succeeded")

    def _cmd_set_api(self):
        print(f"\n{Fore.YELLOW}Set Telegram API Credentials{Style.RESET_ALL}")
        print(f"{Fore.WHITE}You can get these from https://my.telegram.org/apps{Style.RESET_ALL}")
        api_id = self._get_int_input("API ID", default=self.config['telethon']['api_id'])
        api_hash = self._get_input("API Hash", default=self.config['telethon']['api_hash'], required=False)
        if api_hash:
            self.config['telethon']['api_id'] = api_id
            self.config['telethon']['api_hash'] = api_hash
            self._save_config()
            self.logger.success("API credentials saved")
        else:
            self.logger.warning("API Hash not changed")

    async def _interactive(self):
        while True:
            self._print_menu()
            choice = self._get_input("Select option (1-6)", required=False)
            if choice == "1":
                print(f"\n{Fore.YELLOW}--- Add Account ---{Style.RESET_ALL}")
                phone = self._get_input("Phone number with country code (e.g., +989123456789)")
                api_id = self._get_int_input("API ID")
                api_hash = self._get_input("API Hash")
                await self._cmd_add(phone, api_id, api_hash)
                input(f"{Fore.CYAN}\nPress Enter to continue...{Style.RESET_ALL}")

            elif choice == "2":
                print(f"\n{Fore.YELLOW}--- List Accounts ---{Style.RESET_ALL}")
                self._cmd_list()
                input(f"{Fore.CYAN}\nPress Enter to continue...{Style.RESET_ALL}")

            elif choice == "3":
                print(f"\n{Fore.YELLOW}--- Remove Account ---{Style.RESET_ALL}")
                phone = self._get_input("Phone number to remove")
                self._cmd_remove(phone)
                input(f"{Fore.CYAN}\nPress Enter to continue...{Style.RESET_ALL}")

            elif choice == "4":
                print(f"\n{Fore.YELLOW}--- Start Reporting ---{Style.RESET_ALL}")
                channel = self._get_input("Channel username (without @)")
                count = self._get_int_input("Number of messages to report (default 3)", default=3)
                delay = self._get_float_input("Delay between reports in seconds (default 2.0)", default=2.0)
                option = self._get_input("Report option (spam, violence, etc.)", default="spam", required=False)
                await self._cmd_report(channel, count, delay, option if option else "spam")
                input(f"{Fore.CYAN}\nPress Enter to continue...{Style.RESET_ALL}")

            elif choice == "5":
                self._cmd_set_api()
                input(f"{Fore.CYAN}\nPress Enter to continue...{Style.RESET_ALL}")

            elif choice == "6":
                self.logger.info("Exiting Ripper")
                break

            else:
                print(f"{Fore.RED}Invalid option. Please choose 1-6.{Style.RESET_ALL}")


def main():
    cli = RipperCLI()
    try:
        asyncio.run(cli._interactive())
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[!] Interrupted by user{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"{Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()