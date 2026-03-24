"""Data handler for BYD MQTT integration."""
import json
import logging
from typing import Any, Dict, Optional

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BYDDataHandler:
    """Handle MQTT data and cache."""

    def __init__(self, hass: HomeAssistant, topic: str):
        self.hass = hass
        self.topic = topic
        self.cache: Dict[str, Any] = {}
        self._unsubscribe = None

    async def async_subscribe(self) -> None:
        """Subscribe to MQTT topic using HA MQTT integration."""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            _LOGGER.error("MQTT client not available")
            return

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass, self.topic, self._mqtt_message_received, 1
        )
        _LOGGER.info("Subscribed to MQTT topic: %s", self.topic)

    async def async_unsubscribe(self) -> None:
        """Unsubscribe from MQTT topic."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
            _LOGGER.info("Unsubscribed from MQTT topic: %s", self.topic)

    @callback
    def _mqtt_message_received(self, msg):
        """Process incoming MQTT message."""
        payload = msg.payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
    
        _LOGGER.debug("Received raw MQTT message: %s", payload)
    
        data = self._parse_payload(payload)
        if not data:
            _LOGGER.warning("Failed to parse payload: %s", payload)
            return
    
        _LOGGER.debug("Parsed JSON data: %s", data)
    
        # 提取 VIN（优先从 JSON 中获取，否则从第一行 "byd=" 提取）
        vin = data.get("vin", "")
        if not vin:
            try:
                lines = payload.splitlines()
                for line in lines:
                    if line.startswith("byd="):
                        vin = line.split("byd=")[1].split("}}")[0].strip()
                        break
            except Exception as e:
                _LOGGER.debug("VIN extraction failed: %s", e)
    
        # 更新缓存的 VIN
        if vin:
            self.cache['vin'] = vin
        else:
            # 如果本次未提取到，保留缓存中的 VIN（不更新）
            vin = self.cache.get('vin', '')
    
        # 更新其他数据缓存
        self._update_cache_from_data(data)
    
        _LOGGER.debug("Cache after update: %s", self.cache)
    
        # 触发实体更新
        async_dispatcher_send(self.hass, f"{DOMAIN}_new_data", {
            "data": data,
            "vin": vin,          # 此处仍传递当前提取的 vin（可能为空），但传感器会从缓存读取
            "cache": self.cache.copy(),
        })

    def _parse_payload(self, payload: str) -> Optional[Dict]:
        """Parse payload (multi-line JSON)."""
        lines = payload.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    def _update_cache_from_data(self, data: Dict):
        """Update internal cache with non-null values (keep previous values for missing fields)."""
        # 字段映射（与 Node-RED 中的 MqttData 完全一致）
        field_map = {
            "bR": "range",
            "bP": "soc",
            "bE": "energy",
            "tM": "mileage",
            "tempOut": "temp_out",
            "tempIn": "temp_in",
            "inHumidity": "humidity",
            "wind": "wind",
            "doorLock": "door_lock",
            "mainBelt": "seatbelt",
            "power": "power",
            "compress": "ac",
            "frontDefrost": "defrost_front",
            "rearDefrost": "defrost_rear",
            "speed": "speed",
            "motoSpeed": "moto_speed",
            "wheelAngle": "wheel_angle",
            "breakDeep": "brake_depth",
            "accelerate": "accelerate",
            "lfTyreP": "lf_tyre_p",
            "rfTyreP": "rf_tyre_p",
            "lbTyreP": "lb_tyre_p",
            "rbTyreP": "rb_tyre_p",
            "lfTyreT": "lf_tyre_t",
            "rfTyreT": "rf_tyre_t",
            "lbTyreT": "lb_tyre_t",
            "rbTyreT": "rb_tyre_t",
            "windowLf": "window_lf",
            "windowRf": "window_rf",
            "windowLr": "window_lr",
            "windowRr": "window_rr",
            "windowMoon": "window_moon",
        }

        for old, new in field_map.items():
            if old in data:
                value = data[old]
                if value is not None:  # 0 是有效值，会更新缓存
                    self.cache[new] = value
                # 如果值为 None，则保持原缓存不变（不删除）

    def reset_cache(self):
        """Reset all cached data."""
        self.cache.clear()
        async_dispatcher_send(self.hass, f"{DOMAIN}_reset_cache")
        _LOGGER.info("Cache reset")