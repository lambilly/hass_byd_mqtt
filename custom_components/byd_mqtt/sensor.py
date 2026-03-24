"""Sensor platform for BYD MQTT integration."""
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTemperature, UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEVICE_ID, SENSORS, AGGREGATE_SENSORS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    handler = hass.data[DOMAIN][entry.entry_id]["handler"]

    entities = []

    # 基本传感器
    for sensor_id, name, unit, device_class, state_class in SENSORS:
        entities.append(
            BYDSensor(
                device_info,
                sensor_id,
                name,
                unit,
                device_class,
                state_class,
                handler,
            )
        )

    # 聚合传感器：胎压、胎温
    for agg_id, config in AGGREGATE_SENSORS.items():
        entities.append(
            BYDAggregateSensor(
                device_info,
                agg_id,
                config["name"],
                config.get("unit"),
                config.get("device_class"),
                config.get("state_class"),
                handler,
            )
        )

    async_add_entities(entities)


class BYDSensor(SensorEntity):
    """Representation of a BYD sensor."""

    def __init__(
        self,
        device_info: DeviceInfo,
        sensor_id: str,
        name: str,
        unit: Optional[str],
        device_class: Optional[str],
        state_class: Optional[str],
        handler,
    ) -> None:
        self._attr_device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{sensor_id}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._handler = handler
        self._sensor_id = sensor_id

        # 特殊处理
        self._is_update_time = sensor_id == "byd_update_time"
        self._is_vin = sensor_id == "byd_vin"
        self._is_door = sensor_id == "byd_door_lock"
        self._is_belt = sensor_id == "byd_seatbelt"
        self._is_switch = sensor_id in [
            "byd_power",
            "byd_ac",
            "byd_defrost_front",
            "byd_defrost_rear",
        ]

    async def async_added_to_hass(self):
        """Register dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_new_data",
                self._handle_new_data,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_reset_cache",
                self._handle_reset,
            )
        )

    @callback
    def _handle_new_data(self, payload: Dict[str, Any]):
        """Handle new data."""
        cache = payload["cache"]
        vin = payload.get("vin", "")

        # 更新时间：直接使用当前时间
        if self._is_update_time:
            self._attr_native_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.async_write_ha_state()
            return

        # VIN 从缓存中读取
        if self._is_vin:
            self._attr_native_value = cache.get('vin', '')
            self.async_write_ha_state()
            return

        # 从缓存中获取值
        key_map = {
            "byd_range": "range",
            "byd_soc": "soc",
            "byd_energy": "energy",
            "byd_mileage": "mileage",
            "byd_temp_out": "temp_out",
            "byd_temp_in": "temp_in",
            "byd_humidity": "humidity",
            "byd_wind": "wind",
            "byd_speed": "speed",
            "byd_moto_speed": "moto_speed",
            "byd_wheel_angle": "wheel_angle",
            "byd_brake_depth": "brake_depth",
            "byd_accelerate": "accelerate",
            "byd_power": "power",
            "byd_ac": "ac",
            "byd_defrost_front": "defrost_front",
            "byd_defrost_rear": "defrost_rear",
        }

        value = None
        if self._sensor_id in key_map:
            key = key_map[self._sensor_id]
            value = cache.get(key)

            # 格式化数值
            if value is not None:
                if self._sensor_id in ["byd_range", "byd_speed"]:
                    value = int(value)
                elif self._sensor_id == "byd_energy":
                    value = round(float(value), 2)
                elif self._sensor_id == "byd_wheel_angle":
                    value = round(float(value), 2)

        # 门锁状态
        if self._is_door:
            val = cache.get("door_lock")
            if val is not None:
                value = self._map_door(val)

        # 主驾安全带
        if self._is_belt:
            val = cache.get("seatbelt")
            if val is not None:
                value = self._map_belt(val)

        # 开关类（上面 key_map 已经处理，但需要映射文本）
        if self._is_switch and value is not None:
            # value 已经是数值，映射为文本
            value = self._map_switch(value)

        if value is not None:
            self._attr_native_value = value
            _LOGGER.debug("Sensor %s updated to: %s", self._sensor_id, value)
        else:
            # 可选：记录缓存中缺失的键
            if self._sensor_id in key_map:
                _LOGGER.debug("Sensor %s: key %s not in cache", self._sensor_id, key_map[self._sensor_id])

        self.async_write_ha_state()

    @callback
    def _handle_reset(self):
        """Handle cache reset."""
        pass

    @staticmethod
    def _map_door(val):
        return "已锁" if val == 1 else ("行驶中" if val == 2 else "未锁")

    @staticmethod
    def _map_belt(val):
        return "已系" if val == 1 else "未系"

    @staticmethod
    def _map_switch(val):
        return "开启" if val == 1 else "关闭"


class BYDAggregateSensor(SensorEntity):
    """Aggregated sensors (tyre pressure, tyre temp)."""

    def __init__(
        self,
        device_info: DeviceInfo,
        agg_id: str,
        name: str,
        unit: Optional[str],
        device_class: Optional[str],
        state_class: Optional[str],
        handler,
    ) -> None:
        self._attr_device_info = device_info
        self._attr_unique_id = f"{DOMAIN}_{agg_id}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._handler = handler
        self._agg_id = agg_id

    async def async_added_to_hass(self):
        """Register dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_new_data",
                self._handle_new_data,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_reset_cache",
                self._handle_reset,
            )
        )

    @callback
    def _handle_new_data(self, payload: Dict[str, Any]):
        """Handle new data and compute aggregate."""
        cache = payload["cache"]

        if self._agg_id == "tyre_pressure":
            values = {
                "左前胎压": cache.get("lf_tyre_p"),
                "右前胎压": cache.get("rf_tyre_p"),
                "左后胎压": cache.get("lb_tyre_p"),
                "右后胎压": cache.get("rb_tyre_p"),
            }
            # 过滤掉 None 和 0
            valid = [v for v in values.values() if v is not None and v != 0]
            if len(valid) == 4:
                state = "正常" if all(220 <= v <= 260 for v in valid) else "异常"
            else:
                state = "加载中"
        
            self._attr_native_value = state
            self._attr_extra_state_attributes = {
                k: (f"{v} kPa" if v is not None and v != 0 else "加载中")
                for k, v in values.items()
            }
        
        elif self._agg_id == "tyre_temp":
            values = {
                "左前胎温": cache.get("lf_tyre_t"),
                "右前胎温": cache.get("rf_tyre_t"),
                "左后胎温": cache.get("lb_tyre_t"),
                "右后胎温": cache.get("rb_tyre_t"),
            }
            valid = [v for v in values.values() if v is not None and v != 0]
            if len(valid) == 4:
                state = "正常" if all(v < 90 for v in valid) else "异常"
            else:
                state = "加载中"
        
            self._attr_native_value = state
            self._attr_extra_state_attributes = {
                k: (f"{v} °C" if v is not None and v != 0 else "加载中")
                for k, v in values.items()
            }
            
            _LOGGER.debug("Tyre temperature aggregated: state=%s, values=%s", state, values)

        self.async_write_ha_state()

    @callback
    def _handle_reset(self):
        """Handle cache reset."""
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        self.async_write_ha_state()