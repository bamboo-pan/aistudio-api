"""账号存储层，管理多 Google 账号的注册表和 storage state。"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 默认搜索路径（与 config.py 保持一致）
_SEARCH_ROOTS: list[Path] = [
    Path.cwd(),
    Path(__file__).resolve().parents[4],  # src/aistudio_api/infrastructure/account -> 项目根
]

BACKUP_FORMAT = "aistudio-api.credentials.backup"
BACKUP_VERSION = 1
BACKUP_WARNING = (
    "This backup contains sensitive browser cookies and tokens. Anyone with this file "
    "may be able to access the exported AI Studio accounts. Store it securely and do not share it."
)


def _resolve_accounts_dir() -> Path:
    """发现 accounts 目录，默认为 data/accounts。"""
    env = os.getenv("AISTUDIO_ACCOUNTS_DIR")
    if env:
        return Path(env).resolve()
    for root in _SEARCH_ROOTS:
        candidate = root / "data" / "accounts"
        if candidate.is_dir():
            return candidate
    # 默认在第一个搜索根下创建
    return (_SEARCH_ROOTS[0] / "data" / "accounts").resolve()


def _resolve_legacy_auth_file() -> Path | None:
    """查找遗留的 data/auth.json 文件。"""
    for root in _SEARCH_ROOTS:
        candidate = root / "data" / "auth.json"
        if candidate.is_file():
            return candidate
    return None


def _generate_account_id() -> str:
    """生成 acc_ 前缀的随机 ID。"""
    import secrets
    return f"acc_{secrets.token_hex(4)}"


def _is_safe_account_id(account_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", account_id))


@dataclass
class AccountMeta:
    """账号元数据。"""
    id: str
    name: str
    email: str | None
    created_at: str
    last_used: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountMeta:
        return cls(**data)


@dataclass
class Registry:
    """账号注册表。"""
    accounts: dict[str, AccountMeta]
    active_account_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": {k: v.to_dict() for k, v in self.accounts.items()},
            "active_account_id": self.active_account_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Registry:
        accounts = {
            k: AccountMeta.from_dict(v) for k, v in data.get("accounts", {}).items()
        }
        return cls(
            accounts=accounts,
            active_account_id=data.get("active_account_id"),
        )


class AccountStore:
    """账号存储管理器。"""

    def __init__(self, accounts_dir: Path | None = None) -> None:
        self._accounts_dir = accounts_dir or _resolve_accounts_dir()
        self._registry_path = self._accounts_dir / "registry.json"
        self._registry: Registry | None = None
        self._ensure_dirs()
        self._migrate_legacy_if_needed()

    def _ensure_dirs(self) -> None:
        """确保目录存在。"""
        self._accounts_dir.mkdir(parents=True, exist_ok=True)

    def _migrate_legacy_if_needed(self) -> None:
        """如果 accounts 目录为空且存在 data/auth.json，自动迁移。"""
        if self._registry_path.exists():
            return  # 已有注册表，无需迁移
        legacy = _resolve_legacy_auth_file()
        if legacy is None:
            return
        # 创建一个迁移账号
        account_id = "acc_migrated"
        now = datetime.now(timezone.utc).isoformat()
        meta = AccountMeta(
            id=account_id,
            name="迁移的账号",
            email=None,
            created_at=now,
            last_used=now,
        )
        account_dir = self._accounts_dir / account_id
        account_dir.mkdir(parents=True, exist_ok=True)
        # 复制 auth.json
        shutil.copy2(legacy, account_dir / "auth.json")
        # 写入 meta.json
        (account_dir / "meta.json").write_text(
            json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 创建注册表
        registry = Registry(
            accounts={account_id: meta},
            active_account_id=account_id,
        )
        self._save_registry(registry)

    def _load_registry(self) -> Registry:
        """加载注册表。"""
        if self._registry is not None:
            return self._registry
        if not self._registry_path.exists():
            self._registry = Registry(accounts={})
            return self._registry
        data = json.loads(self._registry_path.read_text(encoding="utf-8"))
        self._registry = Registry.from_dict(data)
        return self._registry

    def _save_registry(self, registry: Registry) -> None:
        """保存注册表。"""
        self._registry = registry
        self._registry_path.write_text(
            json.dumps(registry.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_accounts(self) -> list[AccountMeta]:
        """列出所有账号。"""
        registry = self._load_registry()
        return list(registry.accounts.values())

    def get_account(self, account_id: str) -> AccountMeta | None:
        """获取单个账号。"""
        registry = self._load_registry()
        return registry.accounts.get(account_id)

    def get_active_account(self) -> AccountMeta | None:
        """获取当前活跃账号。"""
        registry = self._load_registry()
        if registry.active_account_id is None:
            return None
        return registry.accounts.get(registry.active_account_id)

    def get_active_auth_path(self) -> Path | None:
        """获取当前活跃账号的 auth.json 路径。"""
        account = self.get_active_account()
        if account is None:
            return None
        return self._accounts_dir / account.id / "auth.json"

    def set_active_account(self, account_id: str) -> AccountMeta | None:
        """设置活跃账号，返回账号元数据或 None（如果不存在）。"""
        registry = self._load_registry()
        if account_id not in registry.accounts:
            return None
        registry.active_account_id = account_id
        now = datetime.now(timezone.utc).isoformat()
        registry.accounts[account_id].last_used = now
        self._save_registry(registry)
        return registry.accounts[account_id]

    def save_account(
        self,
        name: str,
        email: str | None,
        storage_state: dict[str, Any],
        account_id: str | None = None,
        created_at: str | None = None,
        last_used: str | None = None,
        activate: bool = True,
    ) -> AccountMeta:
        """保存新账号。"""
        now = datetime.now(timezone.utc).isoformat()
        if account_id is None or not _is_safe_account_id(account_id):
            account_id = self._generate_unique_account_id()
        elif self.get_account(account_id) is not None:
            account_id = self._generate_unique_account_id()
        meta = AccountMeta(
            id=account_id,
            name=name,
            email=email,
            created_at=created_at or now,
            last_used=last_used or (now if activate else None),
        )
        account_dir = self._accounts_dir / account_id
        account_dir.mkdir(parents=True, exist_ok=True)
        # 写入 auth.json
        (account_dir / "auth.json").write_text(
            json.dumps(storage_state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 写入 meta.json
        (account_dir / "meta.json").write_text(
            json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 更新注册表
        registry = self._load_registry()
        registry.accounts[account_id] = meta
        if activate:
            registry.active_account_id = account_id
        self._save_registry(registry)
        return meta

    def export_credentials(self, account_id: str | None = None) -> dict[str, Any]:
        """导出单个或全部账号凭证为项目备份包。"""
        registry = self._load_registry()
        account_ids = [account_id] if account_id else list(registry.accounts)
        accounts = []
        manifest_accounts = []

        for current_id in account_ids:
            if current_id is None or current_id not in registry.accounts:
                raise KeyError(current_id or "")
            meta = registry.accounts[current_id]
            auth_path = self.get_auth_path(current_id)
            if auth_path is None:
                raise FileNotFoundError(current_id)
            storage_state = json.loads(auth_path.read_text(encoding="utf-8"))
            self._validate_storage_state(storage_state)
            meta_payload = meta.to_dict()
            manifest_accounts.append(meta_payload)
            accounts.append({"meta": meta_payload, "auth": storage_state})

        return {
            "format": BACKUP_FORMAT,
            "version": BACKUP_VERSION,
            "manifest": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "warning": BACKUP_WARNING,
                "account_count": len(accounts),
                "active_account_id": registry.active_account_id,
                "accounts": manifest_accounts,
            },
            "accounts": accounts,
        }

    def import_credentials(
        self,
        payload: dict[str, Any],
        *,
        name: str | None = None,
        activate: bool = True,
    ) -> list[AccountMeta]:
        """导入项目备份包或兼容的 Playwright storage state。"""
        if self._is_backup_package(payload):
            return self._import_backup_package(payload, activate=activate)
        self._validate_storage_state(payload)
        return [
            self.save_account(
                name=name or "Imported account",
                email=None,
                storage_state=payload,
                activate=activate,
            )
        ]

    def delete_account(self, account_id: str) -> bool:
        """删除账号，返回是否成功。"""
        registry = self._load_registry()
        if account_id not in registry.accounts:
            return False
        # 删除目录
        account_dir = self._accounts_dir / account_id
        if account_dir.is_dir():
            shutil.rmtree(account_dir)
        # 从注册表移除
        del registry.accounts[account_id]
        if registry.active_account_id == account_id:
            registry.active_account_id = next(iter(registry.accounts), None)
        self._save_registry(registry)
        return True

    def update_account(self, account_id: str, name: str) -> AccountMeta | None:
        """更新账号名称。"""
        registry = self._load_registry()
        if account_id not in registry.accounts:
            return None
        registry.accounts[account_id].name = name
        # 同步更新 meta.json
        account_dir = self._accounts_dir / account_id
        meta_path = account_dir / "meta.json"
        if meta_path.exists():
            meta_path.write_text(
                json.dumps(registry.accounts[account_id].to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        self._save_registry(registry)
        return registry.accounts[account_id]

    def get_auth_path(self, account_id: str) -> Path | None:
        """获取指定账号的 auth.json 路径。"""
        registry = self._load_registry()
        if account_id not in registry.accounts:
            return None
        path = self._accounts_dir / account_id / "auth.json"
        return path if path.exists() else None

    def _generate_unique_account_id(self) -> str:
        registry = self._load_registry()
        account_id = _generate_account_id()
        while account_id in registry.accounts:
            account_id = _generate_account_id()
        return account_id

    def _is_backup_package(self, payload: dict[str, Any]) -> bool:
        return payload.get("format") == BACKUP_FORMAT or (
            isinstance(payload.get("manifest"), dict) and isinstance(payload.get("accounts"), list)
        )

    def _import_backup_package(self, payload: dict[str, Any], *, activate: bool) -> list[AccountMeta]:
        if payload.get("format") != BACKUP_FORMAT:
            raise ValueError(f"credential backup format must be '{BACKUP_FORMAT}'")
        if payload.get("version") != BACKUP_VERSION:
            raise ValueError(f"unsupported credential backup version: {payload.get('version')}")
        accounts = payload.get("accounts")
        if not isinstance(accounts, list) or not accounts:
            raise ValueError("credential backup must contain at least one account")

        manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
        requested_active_id = manifest.get("active_account_id")
        imported: list[AccountMeta] = []
        id_map: dict[str, str] = {}

        validated_accounts: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
        for entry in accounts:
            if not isinstance(entry, dict):
                raise ValueError("credential backup account entries must be objects")
            meta_payload = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
            storage_state = entry.get("auth") or entry.get("storage_state") or entry.get("storageState")
            self._validate_storage_state(storage_state)
            requested_id = meta_payload.get("id") if isinstance(meta_payload.get("id"), str) else None
            validated_accounts.append((meta_payload, storage_state, requested_id))

        for meta_payload, storage_state, requested_id in validated_accounts:
            account = self.save_account(
                name=str(meta_payload.get("name") or meta_payload.get("email") or "Imported account"),
                email=meta_payload.get("email") if isinstance(meta_payload.get("email"), str) else None,
                storage_state=storage_state,
                account_id=requested_id,
                created_at=meta_payload.get("created_at") if isinstance(meta_payload.get("created_at"), str) else None,
                last_used=meta_payload.get("last_used") if isinstance(meta_payload.get("last_used"), str) else None,
                activate=False,
            )
            if requested_id:
                id_map[requested_id] = account.id
            imported.append(account)

        if activate and imported:
            active_id = id_map.get(requested_active_id) if isinstance(requested_active_id, str) else None
            self.set_active_account(active_id or imported[-1].id)

        return imported

    def _validate_storage_state(self, storage_state: Any) -> None:
        if not isinstance(storage_state, dict):
            raise ValueError("credential storage state must be a JSON object")
        cookies = storage_state.get("cookies")
        origins = storage_state.get("origins", [])
        if not isinstance(cookies, list) or not cookies:
            raise ValueError("credential storage state must contain a non-empty cookies array")
        if not isinstance(origins, list):
            raise ValueError("credential storage state origins must be an array when present")
        required_cookie_fields = {"name", "value", "domain", "path"}
        has_google_cookie = False
        for cookie in cookies:
            if not isinstance(cookie, dict):
                raise ValueError("credential storage state cookies must be objects")
            missing = [field for field in required_cookie_fields if not isinstance(cookie.get(field), str)]
            if missing:
                raise ValueError(f"credential storage state cookie is missing fields: {', '.join(missing)}")
            domain = cookie["domain"].lstrip(".").lower()
            if domain == "google.com" or domain.endswith(".google.com"):
                has_google_cookie = True
        if not has_google_cookie:
            raise ValueError("credential storage state must include at least one Google cookie")
