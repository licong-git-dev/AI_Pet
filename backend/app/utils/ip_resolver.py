"""
PetPal - IP地址解析服务

提供IP地址到地理位置的解析功能，用于登录日志和安全审计
"""
import os
from typing import Optional, Dict
from functools import lru_cache

from loguru import logger


# ip2region数据库实例（懒加载）
_searcher = None
_ip2region_available = False


def _init_ip2region():
    """初始化ip2region"""
    global _searcher, _ip2region_available

    if _searcher is not None:
        return _searcher

    try:
        import ip2region

        # 查找数据库文件
        db_paths = [
            os.path.join(os.path.dirname(__file__), "ip2region.xdb"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "ip2region.xdb"),
            "/usr/share/ip2region/ip2region.xdb",
        ]

        db_path = None
        for path in db_paths:
            if os.path.exists(path):
                db_path = path
                break

        if db_path:
            _searcher = ip2region.XdbSearcher(db_path)
            _ip2region_available = True
            logger.info(f"ip2region初始化成功: {db_path}")
        else:
            logger.warning("ip2region数据库文件不存在，将使用简单IP解析")
            _ip2region_available = False

    except ImportError:
        logger.warning("ip2region库未安装，将使用简单IP解析")
        _ip2region_available = False
    except Exception as e:
        logger.warning(f"ip2region初始化失败: {e}")
        _ip2region_available = False

    return _searcher


def is_private_ip(ip: str) -> bool:
    """检查是否为私有IP地址

    Args:
        ip: IP地址

    Returns:
        是否为私有IP
    """
    if not ip:
        return True

    # 本地回环
    if ip.startswith("127.") or ip == "::1" or ip == "localhost":
        return True

    # 私有地址段
    parts = ip.split(".")
    if len(parts) != 4:
        return True

    try:
        first = int(parts[0])
        second = int(parts[1])

        # 10.0.0.0/8
        if first == 10:
            return True
        # 172.16.0.0/12
        if first == 172 and 16 <= second <= 31:
            return True
        # 192.168.0.0/16
        if first == 192 and second == 168:
            return True
        # 169.254.0.0/16 (link-local)
        if first == 169 and second == 254:
            return True

    except ValueError:
        return True

    return False


@lru_cache(maxsize=1000)
def resolve_ip(ip: str) -> Dict[str, Optional[str]]:
    """解析IP地址获取地理位置信息

    Args:
        ip: IP地址

    Returns:
        包含地理位置信息的字典
    """
    result = {
        "ip": ip,
        "country": None,
        "region": None,
        "province": None,
        "city": None,
        "isp": None,
        "location": None,  # 格式化的位置字符串
    }

    if not ip:
        return result

    # 私有IP直接返回
    if is_private_ip(ip):
        result["location"] = "内网"
        result["country"] = "内网"
        return result

    # 尝试使用ip2region解析
    searcher = _init_ip2region()

    if _ip2region_available and searcher:
        try:
            # ip2region返回格式: "国家|区域|省份|城市|ISP"
            region_str = searcher.search(ip)
            if region_str:
                parts = region_str.split("|")
                if len(parts) >= 5:
                    result["country"] = parts[0] if parts[0] != "0" else None
                    result["region"] = parts[1] if parts[1] != "0" else None
                    result["province"] = parts[2] if parts[2] != "0" else None
                    result["city"] = parts[3] if parts[3] != "0" else None
                    result["isp"] = parts[4] if parts[4] != "0" else None

                    # 生成格式化位置字符串
                    location_parts = []
                    if result["country"] and result["country"] != "中国":
                        location_parts.append(result["country"])
                    if result["province"]:
                        location_parts.append(result["province"])
                    if result["city"] and result["city"] != result["province"]:
                        location_parts.append(result["city"])

                    result["location"] = "".join(location_parts) if location_parts else "未知"

        except Exception as e:
            logger.debug(f"ip2region解析失败: {ip}, error={e}")

    # 如果没有解析结果，返回基本信息
    if not result["location"]:
        result["location"] = _simple_ip_resolve(ip)

    return result


def _simple_ip_resolve(ip: str) -> str:
    """简单IP解析（当ip2region不可用时的降级方案）

    基于IP段的粗略判断
    """
    if not ip:
        return "未知"

    parts = ip.split(".")
    if len(parts) != 4:
        return "未知"

    try:
        first = int(parts[0])

        # 一些常见的IP段判断（非常粗略）
        # 这只是降级方案，生产环境应使用ip2region
        if first in [1, 14, 27, 36, 39, 42, 49, 58, 59, 60, 61]:
            return "中国"
        if first in [101, 106, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119]:
            return "中国"
        if first in [120, 121, 122, 123, 124, 125, 139, 140]:
            return "中国"
        if first in [171, 175, 180, 182, 183]:
            return "中国"
        if first in [202, 203, 210, 211, 218, 219, 220, 221, 222, 223]:
            return "中国"

    except ValueError:
        pass

    return "未知"


def get_location_string(ip: str) -> str:
    """获取IP的位置字符串（简化接口）

    Args:
        ip: IP地址

    Returns:
        位置字符串，如"北京市"、"广东省深圳市"
    """
    result = resolve_ip(ip)
    return result.get("location", "未知")


def check_location_change(
    current_ip: str,
    last_ip: Optional[str]
) -> Dict[str, any]:
    """检查登录位置是否发生变化（用于异地登录检测）

    Args:
        current_ip: 当前登录IP
        last_ip: 上次登录IP

    Returns:
        包含位置变化信息的字典
    """
    result = {
        "is_changed": False,
        "is_abnormal": False,
        "risk_level": "low",
        "current_location": None,
        "last_location": None,
        "message": None,
    }

    if not last_ip:
        result["current_location"] = get_location_string(current_ip)
        return result

    current_info = resolve_ip(current_ip)
    last_info = resolve_ip(last_ip)

    result["current_location"] = current_info.get("location")
    result["last_location"] = last_info.get("location")

    # 检查位置变化
    current_province = current_info.get("province")
    last_province = last_info.get("province")
    current_country = current_info.get("country")
    last_country = last_info.get("country")

    # 国家变化 - 高风险
    if current_country and last_country and current_country != last_country:
        result["is_changed"] = True
        result["is_abnormal"] = True
        result["risk_level"] = "high"
        result["message"] = f"登录地点从{last_info.get('location')}变更为{current_info.get('location')}"
        return result

    # 省份变化 - 中等风险
    if current_province and last_province and current_province != last_province:
        result["is_changed"] = True
        result["is_abnormal"] = True
        result["risk_level"] = "medium"
        result["message"] = f"登录地点从{last_info.get('location')}变更为{current_info.get('location')}"
        return result

    # 城市变化 - 低风险（记录但不告警）
    current_city = current_info.get("city")
    last_city = last_info.get("city")
    if current_city and last_city and current_city != last_city:
        result["is_changed"] = True
        result["risk_level"] = "low"

    return result


class IPResolver:
    """IP解析器类（提供面向对象接口）"""

    def __init__(self):
        _init_ip2region()

    def resolve(self, ip: str) -> Dict[str, Optional[str]]:
        """解析IP地址"""
        return resolve_ip(ip)

    def get_location(self, ip: str) -> str:
        """获取位置字符串"""
        return get_location_string(ip)

    def is_private(self, ip: str) -> bool:
        """检查是否为私有IP"""
        return is_private_ip(ip)

    def check_change(
        self,
        current_ip: str,
        last_ip: Optional[str]
    ) -> Dict[str, any]:
        """检查位置变化"""
        return check_location_change(current_ip, last_ip)


# 全局实例
ip_resolver = IPResolver()
