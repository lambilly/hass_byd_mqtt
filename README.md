# BYD MQTT Integration for Home Assistant

比亚迪车辆 MQTT 数据集成，用于将比亚迪汽车数据接入 Home Assistant。

本集成基于 Node-RED 流 `flows.json` 转换而成，订阅指定 MQTT 主题，解析比亚迪车辆 JSON 数据，自动创建设备与实体，并在 Home Assistant 中展示。

## 功能特性

- 自动订阅 MQTT 主题（默认 `/carInfo`）
- 解析比亚迪车辆数据（支持多行 JSON 格式）
- 创建设备“比亚迪”，下挂所有传感器与二进制传感器
- 支持 VIN 码、续航、电量、里程、温度、湿度、门锁、安全带、空调、车速、电机转速、方向盘角度、制动/油门深度等数据
- 聚合传感器：轮胎气压、轮胎温度（含各轮独立值及整体状态）
- 二进制传感器：车窗状态（各窗独立状态及整体开关状态）
- 状态映射（门锁、安全带、开关等自动转换为中文文本）
- 缓存机制：保留最近收到的有效值，防止数据抖动
- 重置缓存服务：`byd_mqtt.reset_cache`

## 安装方法

### 通过 HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 将本仓库添加为自定义存储库（URL: `https://github.com/lambilly/byd_mqtt`）
3. 在 HACS 中搜索 “BYD MQTT” 并安装
4. 重启 Home Assistant

### 手动安装

1. 将 `custom_components/byd_mqtt` 目录复制到 Home Assistant 的 `custom_components` 目录中
2. 重启 Home Assistant

## 配置

1. 确保 Home Assistant 中已配置 **MQTT 集成**（指向您的 MQTT 服务器）
2. 进入 **配置 → 设备与服务 → 添加集成**
3. 搜索 “BYD MQTT”
4. 填写 MQTT 主题（默认 `/carInfo`）
5. 提交

集成将自动订阅该主题，收到数据后创建实体。

## 实体说明

集成会创建一个设备“比亚迪”，包含以下实体（传感器和二进制传感器）。大多数实体会根据设备类自动分配图标和单位。

### 传感器

| 实体ID | 名称 | 单位 | 说明 |
|--------|------|------|------|
| `sensor.byd_vin` | 车架号 | - | VIN 码 |
| `sensor.byd_range` | 剩余续航 | km | 续航里程 |
| `sensor.byd_soc` | 剩余电量 | % | 电池电量 |
| `sensor.byd_energy` | 剩余能量 | kWh | 电池剩余能量 |
| `sensor.byd_mileage` | 总里程 | km | 累计行驶里程 |
| `sensor.byd_temp_out` | 车外温度 | °C | 外部温度 |
| `sensor.byd_temp_in` | 车内温度 | °C | 内部温度 |
| `sensor.byd_humidity` | 车内湿度 | % | 内部湿度 |
| `sensor.byd_door_lock` | 门锁状态 | - | 已锁/行驶中/未锁 |
| `sensor.byd_seatbelt` | 主驾安全带 | - | 已系/未系 |
| `sensor.byd_power` | 空调开关 | - | 开启/关闭 |
| `sensor.byd_ac` | A/C开关 | - | 开启/关闭 |
| `sensor.byd_wind` | 风量档级 | - | 风量档位 |
| `sensor.byd_defrost_front` | 前除霜 | - | 开启/关闭 |
| `sensor.byd_defrost_rear` | 后除霜 | - | 开启/关闭 |
| `sensor.byd_speed` | 车速 | km/h | 当前速度 |
| `sensor.byd_moto_speed` | 电机转速 | rpm | 电机转速 |
| `sensor.byd_wheel_angle` | 方向盘角度 | ° | 方向盘转角 |
| `sensor.byd_brake_depth` | 制动深度 | % | 制动踏板深度 |
| `sensor.byd_accelerate` | 油门深度 | % | 加速踏板深度 |
| `sensor.byd_update_time` | 更新时间 | - | 最后一次数据接收时间 |
| `sensor.tyre_pressure` | 轮胎气压 | kPa | 聚合传感器，含各轮气压及整体状态 |
| `sensor.tyre_temp` | 轮胎温度 | °C | 聚合传感器，含各轮温度及整体状态 |

### 二进制传感器

| 实体ID | 名称 | 说明 |
|--------|------|------|
| `binary_sensor.byd_windows` | 车窗状态 | 任意车窗打开时为“开启”，否则“关闭”，属性含各窗独立状态 |

## 服务

### `byd_mqtt.reset_cache`

重置所有缓存数据。当数据异常或需要强制刷新时，可调用此服务。

```yaml
service: byd_mqtt.reset_cache
data: {}
```
## 数据格式

集成订阅的 MQTT 主题应收到如下格式的数据（支持多行，其中一行 JSON 包含所需字段）：
```
json
{"bR":380,"bP":74,"bE":47.33,"tM":14157.1,"tempOut":24,"tempIn":26,"inHumidity":0,"wind":0,"doorLock":2,"mainBelt":1,"power":0,"compress":0,"frontDefrost":0,"rearDefrost":0,"speed":0,"motoSpeed":10,"wheelAngle":-77.5,"breakDeep":25,"accelerate":0,"lfTyreP":230,"rfTyreP":235,"lbTyreP":228,"rbTyreP":232,"lfTyreT":25,"rfTyreT":26,"lbTyreT":24,"rbTyreT":25,"windowLf":0,"windowRf":0,"windowLr":0,"windowRr":0,"windowMoon":0}
```
### 字段说明（部分）：
字段	说明
bR	剩余续航 (km)
bP	剩余电量 (%)
bE	剩余能量 (kWh)
tM	总里程 (km)
tempOut	车外温度 (°C)
tempIn	车内温度 (°C)
inHumidity	车内湿度 (%)
wind	风量档级
doorLock	门锁状态：1=已锁，2=行驶中，其他=未锁
mainBelt	主驾安全带：1=已系，其他=未系
power	空调开关：1=开启，0=关闭
compress	A/C 开关：1=开启，0=关闭
frontDefrost	前除霜：1=开启，0=关闭
rearDefrost	后除霜：1=开启，0=关闭
speed	车速 (km/h)
motoSpeed	电机转速 (rpm)
wheelAngle	方向盘角度 (°)
breakDeep	制动深度 (%)
accelerate	油门深度 (%)
lfTyreP 等	轮胎气压 (kPa)
lfTyreT 等	轮胎温度 (°C)
windowLf 等	车窗状态：0=关闭，非0=打开

### 故障排查

启用调试日志：在 configuration.yaml 添加以下内容，重启 HA，观察日志：
```yaml
logger:
  default: info
  logs:
    custom_components.byd_mqtt: debug
```
确认 MQTT 消息：使用 MQTT 客户端（如 MQTT Explorer）订阅您的主题，验证消息格式。
常见问题：

1. 实体显示“未知”：检查 MQTT 消息中是否包含对应字段；检查字段名是否与映射一致。
2. 聚合传感器显示“加载中”：确保四个轮胎的气压/温度都已收到（0 值也会更新，但为有效值）。
3.重置缓存：调用服务 byd_mqtt.reset_cache，或重启 HA。

## 作者
lambilly (https://github.com/lambilly)

## 许可证
MIT License
