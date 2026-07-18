"""MySQL 连接适配器。

职责：
- 从项目公开配置和私密配置拼装本地 MySQL 连接参数。
- 通过 MySQL 原生协议完成最小连接握手和健康检查。
- 通过本机 mysql CLI 执行最小写入和查询，用于示例接口验证数据库读写能力。
- 为后端启动时的数据库可用性校验提供确定性实现。

边界：
- 这里只处理连接、认证、ping、关闭和最小 SQL 执行。
- 不实现 ORM，不管理表结构，也不负责业务查询编排。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import socket
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any

from ..config.private_config import PrivateConfig, load_private_config
from ..config.project_config import ProjectConfig, load_project_config


CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PLUGIN_AUTH = 0x00080000
CLIENT_DEPRECATE_EOF = 0x01000000
CLIENT_LONG_FLAG = 0x00000004

COM_QUIT = 0x01
COM_PING = 0x0E
DEMO_TABLE_NAME = "astock_demo_records"


@dataclass(frozen=True)
class MysqlConnectionSettings:
    """MySQL 连接参数。"""

    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout_seconds: float = 5.0


def build_mysql_connection_settings(
    project_config: ProjectConfig | str | Path | None = None,
    private_config: PrivateConfig | str | Path | None = None,
) -> MysqlConnectionSettings:
    """从项目配置和私密配置拼装 MySQL 连接参数。"""
    if isinstance(project_config, (str, Path)):
        public_config = load_project_config(project_config)
    else:
        public_config = project_config or load_project_config()
    if isinstance(private_config, (str, Path)):
        secret_config = load_private_config(private_config)
    else:
        secret_config = private_config or load_private_config()
    return MysqlConnectionSettings(
        host=public_config.mysql.host,
        port=public_config.mysql.port,
        database=public_config.mysql.database,
        user=secret_config.mysql.user,
        password=secret_config.mysql.password,
        connect_timeout_seconds=public_config.mysql.connect_timeout_seconds,
    )


def _read_exact(conn: socket.socket, size: int) -> bytes:
    """从 socket 中读取指定长度的数据。"""
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("MySQL 连接已断开")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_packet(conn: socket.socket) -> tuple[int, bytes]:
    """读取 MySQL 协议包头和载荷。"""
    header = _read_exact(conn, 4)
    payload_length = header[0] | (header[1] << 8) | (header[2] << 16)
    sequence_id = header[3]
    payload = _read_exact(conn, payload_length)
    return sequence_id, payload


def _write_packet(conn: socket.socket, sequence_id: int, payload: bytes) -> None:
    """写入一个 MySQL 协议包。"""
    length = len(payload)
    header = bytes((length & 0xFF, (length >> 8) & 0xFF, (length >> 16) & 0xFF, sequence_id & 0xFF))
    conn.sendall(header + payload)


def _read_null_terminated_string(payload: bytes, start: int = 0) -> tuple[str, int]:
    """从载荷中读取 NUL 结尾字符串。"""
    end = payload.index(0, start)
    return payload[start:end].decode("utf-8", errors="replace"), end + 1


def _scramble_native_password(password: str, seed: bytes) -> bytes:
    """生成 mysql_native_password 认证响应。"""
    if not password:
        return b""
    stage1 = hashlib.sha1(password.encode("utf-8")).digest()
    stage2 = hashlib.sha1(stage1).digest()
    stage3 = hashlib.sha1(seed + stage2).digest()
    return bytes(left ^ right for left, right in zip(stage3, stage1))


def _parse_handshake(payload: bytes) -> dict[str, Any]:
    """解析 MySQL 握手包。"""
    index = 0
    protocol_version = payload[index]
    index += 1
    server_version, index = _read_null_terminated_string(payload, index)
    connection_id = int.from_bytes(payload[index : index + 4], "little")
    index += 4
    auth_plugin_data_part_1 = payload[index : index + 8]
    index += 8
    index += 1  # 保留字节
    capability_flags_lower = int.from_bytes(payload[index : index + 2], "little")
    index += 2
    character_set = payload[index]
    index += 1
    status_flags = int.from_bytes(payload[index : index + 2], "little")
    index += 2
    capability_flags_upper = int.from_bytes(payload[index : index + 2], "little")
    index += 2
    capability_flags = capability_flags_lower | (capability_flags_upper << 16)
    auth_plugin_data_len = payload[index] if capability_flags & CLIENT_PLUGIN_AUTH else 0
    index += 1
    index += 10  # 保留字段
    auth_plugin_data_part_2_len = max(13, auth_plugin_data_len - 8) if auth_plugin_data_len else 13
    auth_plugin_data_part_2 = payload[index : index + auth_plugin_data_part_2_len]
    index += auth_plugin_data_part_2_len
    if index < len(payload) and payload[index] == 0:
        index += 1
    auth_plugin_name = ""
    if capability_flags & CLIENT_PLUGIN_AUTH and index < len(payload):
        auth_plugin_name, _ = _read_null_terminated_string(payload, index)
    return {
        "protocol_version": protocol_version,
        "server_version": server_version,
        "connection_id": connection_id,
        "auth_seed": auth_plugin_data_part_1 + auth_plugin_data_part_2,
        "capability_flags": capability_flags,
        "character_set": character_set,
        "status_flags": status_flags,
        "auth_plugin_name": auth_plugin_name,
    }


def _build_handshake_response(settings: MysqlConnectionSettings, handshake: dict[str, Any]) -> bytes:
    """构造 MySQL 握手响应包。"""
    capability_flags = (
        CLIENT_LONG_PASSWORD
        | CLIENT_LONG_FLAG
        | CLIENT_PROTOCOL_41
        | CLIENT_SECURE_CONNECTION
        | CLIENT_CONNECT_WITH_DB
        | CLIENT_PLUGIN_AUTH
        | CLIENT_DEPRECATE_EOF
    )
    if handshake["capability_flags"] & capability_flags != capability_flags:
        # 这里不做严格硬失败，只要服务端支持最小握手能力即可。
        capability_flags &= handshake["capability_flags"]
    auth_response = _scramble_native_password(settings.password, handshake["auth_seed"])
    payload = bytearray()
    payload.extend(capability_flags.to_bytes(4, "little"))
    payload.extend((1024 * 1024 * 16).to_bytes(4, "little"))
    payload.append(handshake["character_set"])
    payload.extend(b"\x00" * 23)
    payload.extend(settings.user.encode("utf-8"))
    payload.append(0)
    payload.append(len(auth_response))
    payload.extend(auth_response)
    payload.extend(settings.database.encode("utf-8"))
    payload.append(0)
    payload.extend(b"mysql_native_password\x00")
    return bytes(payload)


def _is_ok_packet(payload: bytes) -> bool:
    """判断载荷是否为 OK 包。"""
    return bool(payload) and payload[0] == 0x00


def _is_auth_switch_request(payload: bytes) -> bool:
    """判断载荷是否为认证切换包。"""
    return bool(payload) and payload[0] == 0xFE


class MysqlClient:
    """最小 MySQL 连接客户端。"""

    def __init__(self, settings: MysqlConnectionSettings) -> None:
        """初始化客户端。"""
        self._settings = settings
        self._socket: socket.socket | None = None

    @property
    def connected(self) -> bool:
        """当前是否已建立连接。"""
        return self._socket is not None

    def connect(self) -> None:
        """建立连接并完成认证。"""
        if self._socket is not None:
            return
        conn = socket.create_connection(
            (self._settings.host, self._settings.port),
            timeout=self._settings.connect_timeout_seconds,
        )
        conn.settimeout(self._settings.connect_timeout_seconds)
        try:
            _, payload = _read_packet(conn)
            handshake = _parse_handshake(payload)
            if not handshake["auth_plugin_name"]:
                raise ConnectionError("MySQL 服务端未返回认证插件信息")
            if handshake["auth_plugin_name"] != "mysql_native_password":
                raise ConnectionError(
                    f"当前仅支持 mysql_native_password，服务端插件为 {handshake['auth_plugin_name']}"
                )
            response = _build_handshake_response(self._settings, handshake)
            _write_packet(conn, 1, response)
            _, auth_payload = _read_packet(conn)
            if _is_auth_switch_request(auth_payload):
                plugin_name, index = _read_null_terminated_string(auth_payload, 1)
                if plugin_name != "mysql_native_password":
                    raise ConnectionError(f"认证切换到不支持的插件：{plugin_name}")
                seed = auth_payload[index:]
                seed = seed[:-1] if seed.endswith(b"\x00") else seed
                switch_response = _scramble_native_password(self._settings.password, seed)
                _write_packet(conn, 2, switch_response)
                _, auth_payload = _read_packet(conn)
            if not _is_ok_packet(auth_payload):
                raise ConnectionError("MySQL 认证失败")
            self._socket = conn
        except Exception:
            conn.close()
            raise

    def ping(self) -> None:
        """向 MySQL 服务端发送探活命令。

        优先走原生协议的 `COM_PING`，如果本机 MySQL 使用了当前客户端不支持的认证插件，
        则回退到 `mysql` CLI 执行最小查询，保证本地启动和接口探测仍然可用。
        """
        try:
            if self._socket is None:
                self.connect()
            assert self._socket is not None
            _write_packet(self._socket, 0, bytes([COM_PING]))
            _, payload = _read_packet(self._socket)
            if not _is_ok_packet(payload):
                raise ConnectionError("MySQL ping 失败")
        except ConnectionError:
            # 本地环境可能使用 caching_sha2_password 等插件，CLI 能覆盖这类认证差异。
            self._run_sql("SELECT 1;")

    def close(self) -> None:
        """关闭连接。"""
        if self._socket is None:
            return
        try:
            _write_packet(self._socket, 0, bytes([COM_QUIT]))
        except Exception:
            pass
        try:
            self._socket.close()
        finally:
            self._socket = None

    def _mysql_cli(self) -> str:
        """解析本机 mysql CLI 路径。"""
        return which("mysql") or "mysql"

    def _run_sql(self, sql: str) -> str:
        """通过 mysql CLI 执行 SQL 并返回标准输出。

        这里用于示例接口验证“写入后再查询”的数据库交互链路。
        """
        command = [
            self._mysql_cli(),
            "--protocol=tcp",
            "--host",
            self._settings.host,
            "--port",
            str(self._settings.port),
            "--user",
            self._settings.user,
            "--database",
            self._settings.database,
            "--batch",
            "--skip-column-names",
            "--raw",
        ]
        env = os.environ.copy()
        env["MYSQL_PWD"] = self._settings.password
        result = subprocess.run(
            command,
            input=sql,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[5]),
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "MySQL command failed"
            raise ConnectionError(stderr)
        return result.stdout.strip()

    @staticmethod
    def _escape_sql_text(value: str) -> str:
        """对示例接口的文本值做最小 SQL 转义。"""
        return value.replace("\\", "\\\\").replace("'", "''")

    def run_demo_round_trip(self, note: str = "hello") -> dict[str, int]:
        """执行示例写入并读取当前记录数。

        该方法用于后端示例接口，证明项目可以对本机 MySQL 做写入和查询。
        """
        cleaned_note = (note or "hello").strip() or "hello"
        escaped_note = self._escape_sql_text(cleaned_note)
        sql = f"""
CREATE TABLE IF NOT EXISTS `{DEMO_TABLE_NAME}` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `note` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO `{DEMO_TABLE_NAME}` (`note`) VALUES ('{escaped_note}');
SELECT COUNT(*) FROM `{DEMO_TABLE_NAME}`;
"""
        output = self._run_sql(sql)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("MySQL demo query returned empty output")
        try:
            total_rows = int(lines[-1].split("\t", 1)[0])
        except ValueError as exc:
            raise ConnectionError(f"MySQL demo query returned invalid count: {lines[-1]}") from exc
        return {"inserted": 1, "total_rows": total_rows}


def build_mysql_client(
    project_config: ProjectConfig | str | Path | None = None,
    private_config: PrivateConfig | str | Path | None = None,
) -> MysqlClient:
    """根据项目配置创建 MySQL 客户端。"""
    return MysqlClient(build_mysql_connection_settings(project_config, private_config))
