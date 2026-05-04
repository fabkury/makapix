"""Shared player teardown logic — used by both the delete-player endpoint
and the user-account-deletion Celery task so cleanup never bypasses cert
revocation, MQTT password removal, or the audit log."""

from __future__ import annotations

import logging
import os
import subprocess

from sqlalchemy.orm import Session

from .. import models
from ..mqtt.cert_generator import disconnect_mqtt_client, revoke_certificate
from ..mqtt.player_commands import log_command

logger = logging.getLogger(__name__)


def teardown_player(
    db: Session,
    player: models.Player,
    *,
    removed_by: int | None = None,
) -> None:
    """Tear down a registered player: audit log, cert revocation, MQTT
    disconnect, DB delete, and Mosquitto password removal.

    Idempotent w.r.t. cert revocation and password removal — safe to retry
    if a previous attempt partially succeeded. Errors in side-effect steps
    are logged and swallowed; only DB delete failures propagate.

    Args:
        db: Active SQLAlchemy session.
        player: Player ORM instance to tear down. Must be a fresh reference
            attached to ``db`` (caller must not have deleted it yet).
        removed_by: User id recorded in the ``remove_device`` audit log.
            Defaults to ``player.owner_id`` (owner-initiated deletion).
    """
    player_key_str = str(player.player_key)
    player_name = player.name
    device_model = player.device_model
    firmware_version = player.firmware_version
    cert_serial = player.cert_serial_number
    owner_id = player.owner_id
    actor_id = removed_by if removed_by is not None else owner_id

    log_command(
        db=db,
        player_id=player.id,
        command_type="remove_device",
        payload={
            "player_key": player_key_str,
            "owner_id": str(owner_id) if owner_id is not None else None,
            "device_name": player_name,
            "device_model": device_model,
            "firmware_version": firmware_version,
            "removed_by": str(actor_id) if actor_id is not None else None,
        },
    )

    if cert_serial:
        ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
        ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
        crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")

        try:
            revoked = revoke_certificate(
                serial_number=cert_serial,
                ca_cert_path=ca_cert_path,
                ca_key_path=ca_key_path,
                crl_path=crl_path,
            )
            if revoked:
                logger.info(
                    f"Revoked certificate {cert_serial} for player {player_key_str}"
                )
            else:
                logger.warning(
                    f"Failed to revoke certificate {cert_serial} for player {player_key_str}"
                )
        except Exception as e:
            logger.exception(
                f"Error revoking certificate for player {player_key_str}: {e}"
            )

    try:
        disconnect_mqtt_client(player.player_key)
    except Exception as e:
        logger.warning(f"Error disconnecting MQTT client {player_key_str}: {e}")

    db.delete(player)
    db.commit()

    passwd_file = os.getenv("MQTT_PASSWD_FILE", "/mqtt-config/passwords")
    try:
        subprocess.run(
            ["mosquitto_passwd", "-D", passwd_file, player_key_str],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to remove player_key from MQTT password file: {e}")
    except FileNotFoundError:
        logger.warning("mosquitto_passwd not found - MQTT password not cleaned up")
