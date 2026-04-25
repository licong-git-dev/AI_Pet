"""
PetPal - User-Agent解析服务

解析User-Agent获取设备、浏览器、操作系统等信息
"""
import re
from typing import Optional, Dict
from functools import lru_cache

from loguru import logger


# user-agents库是否可用
_ua_parser_available = False


def _init_ua_parser():
    """初始化User-Agent解析器"""
    global _ua_parser_available
    try:
        import user_agents
        _ua_parser_available = True
        return True
    except ImportError:
        logger.warning("user-agents库未安装，将使用简单UA解析")
        _ua_parser_available = False
        return False


# 初始化
_init_ua_parser()


@lru_cache(maxsize=1000)
def parse_user_agent(ua_string: Optional[str]) -> Dict[str, Optional[str]]:
    """解析User-Agent字符串

    Args:
        ua_string: User-Agent字符串

    Returns:
        包含设备信息的字典
    """
    result = {
        "user_agent": ua_string,
        "device_type": None,      # mobile/tablet/pc/bot/other
        "device": None,           # 设备名称
        "device_brand": None,     # 设备品牌
        "device_model": None,     # 设备型号
        "browser": None,          # 浏览器名称
        "browser_version": None,  # 浏览器版本
        "os": None,               # 操作系统
        "os_version": None,       # 操作系统版本
        "is_mobile": False,
        "is_tablet": False,
        "is_pc": False,
        "is_bot": False,
        "summary": None,          # 简短描述
    }

    if not ua_string:
        return result

    if _ua_parser_available:
        return _parse_with_library(ua_string, result)
    else:
        return _parse_simple(ua_string, result)


def _parse_with_library(ua_string: str, result: Dict) -> Dict:
    """使用user-agents库解析"""
    try:
        from user_agents import parse

        ua = parse(ua_string)

        # 设备类型
        if ua.is_mobile:
            result["device_type"] = "mobile"
            result["is_mobile"] = True
        elif ua.is_tablet:
            result["device_type"] = "tablet"
            result["is_tablet"] = True
        elif ua.is_pc:
            result["device_type"] = "pc"
            result["is_pc"] = True
        elif ua.is_bot:
            result["device_type"] = "bot"
            result["is_bot"] = True
        else:
            result["device_type"] = "other"

        # 设备信息
        result["device_brand"] = ua.device.brand
        result["device_model"] = ua.device.model
        result["device"] = ua.device.family

        # 浏览器信息
        result["browser"] = ua.browser.family
        result["browser_version"] = ".".join(
            str(v) for v in ua.browser.version if v
        ) or None

        # 操作系统信息
        result["os"] = ua.os.family
        result["os_version"] = ".".join(
            str(v) for v in ua.os.version if v
        ) or None

        # 生成简短描述
        result["summary"] = _generate_summary(result)

    except Exception as e:
        logger.debug(f"user-agents解析失败: {e}")
        return _parse_simple(ua_string, result)

    return result


def _parse_simple(ua_string: str, result: Dict) -> Dict:
    """简单UA解析（降级方案）"""
    ua_lower = ua_string.lower()

    # 检测设备类型
    if _is_mobile_ua(ua_lower):
        result["device_type"] = "mobile"
        result["is_mobile"] = True
    elif _is_tablet_ua(ua_lower):
        result["device_type"] = "tablet"
        result["is_tablet"] = True
    elif _is_bot_ua(ua_lower):
        result["device_type"] = "bot"
        result["is_bot"] = True
    else:
        result["device_type"] = "pc"
        result["is_pc"] = True

    # 检测浏览器
    result["browser"] = _detect_browser(ua_string)

    # 检测操作系统
    result["os"] = _detect_os(ua_string)

    # 检测设备品牌
    result["device_brand"] = _detect_device_brand(ua_string)

    # 生成简短描述
    result["summary"] = _generate_summary(result)

    return result


def _is_mobile_ua(ua_lower: str) -> bool:
    """检测是否为移动设备UA"""
    mobile_keywords = [
        "mobile", "android", "iphone", "ipod", "blackberry",
        "windows phone", "opera mini", "opera mobi", "iemobile",
        "mobile safari", "webos", "palm", "symbian"
    ]
    # 排除平板
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return False
    return any(kw in ua_lower for kw in mobile_keywords)


def _is_tablet_ua(ua_lower: str) -> bool:
    """检测是否为平板设备UA"""
    tablet_keywords = ["ipad", "tablet", "kindle", "playbook"]
    # Android平板通常不包含mobile
    if "android" in ua_lower and "mobile" not in ua_lower:
        return True
    return any(kw in ua_lower for kw in tablet_keywords)


def _is_bot_ua(ua_lower: str) -> bool:
    """检测是否为爬虫/机器人UA"""
    bot_keywords = [
        "bot", "crawler", "spider", "scraper", "curl", "wget",
        "python", "java", "http", "fetcher", "google", "bing",
        "yahoo", "baidu", "sogou", "360spider", "bytespider"
    ]
    return any(kw in ua_lower for kw in bot_keywords)


def _detect_browser(ua_string: str) -> Optional[str]:
    """检测浏览器"""
    ua_lower = ua_string.lower()

    # 顺序很重要，需要先检测具体的再检测通用的
    browser_patterns = [
        (r"edg[e/]", "Edge"),
        (r"opr/|opera", "Opera"),
        (r"firefox", "Firefox"),
        (r"chrome", "Chrome"),
        (r"safari", "Safari"),
        (r"msie|trident", "IE"),
        (r"ucbrowser", "UC浏览器"),
        (r"qqbrowser", "QQ浏览器"),
        (r"micromessenger", "微信"),
        (r"aliapp", "支付宝"),
    ]

    for pattern, name in browser_patterns:
        if re.search(pattern, ua_lower):
            return name

    return "Other"


def _detect_os(ua_string: str) -> Optional[str]:
    """检测操作系统"""
    ua_lower = ua_string.lower()

    os_patterns = [
        (r"windows nt 10", "Windows 10"),
        (r"windows nt 6\.3", "Windows 8.1"),
        (r"windows nt 6\.2", "Windows 8"),
        (r"windows nt 6\.1", "Windows 7"),
        (r"windows nt 6\.0", "Windows Vista"),
        (r"windows nt 5\.1", "Windows XP"),
        (r"windows", "Windows"),
        (r"iphone os (\d+)", "iOS"),
        (r"ipad.*os (\d+)", "iPadOS"),
        (r"mac os x", "macOS"),
        (r"android (\d+)", "Android"),
        (r"linux", "Linux"),
        (r"ubuntu", "Ubuntu"),
        (r"chromeos", "Chrome OS"),
    ]

    for pattern, name in os_patterns:
        if re.search(pattern, ua_lower):
            return name

    return "Other"


def _detect_device_brand(ua_string: str) -> Optional[str]:
    """检测设备品牌"""
    ua_lower = ua_string.lower()

    brand_patterns = [
        (r"iphone|ipad|ipod|mac", "Apple"),
        (r"huawei|honor", "华为"),
        (r"xiaomi|mi |redmi", "小米"),
        (r"oppo", "OPPO"),
        (r"vivo", "vivo"),
        (r"samsung", "三星"),
        (r"oneplus", "一加"),
        (r"meizu", "魅族"),
        (r"realme", "realme"),
        (r"nokia", "诺基亚"),
        (r"sony", "索尼"),
        (r"lg", "LG"),
        (r"htc", "HTC"),
        (r"zte", "中兴"),
        (r"lenovo", "联想"),
    ]

    for pattern, name in brand_patterns:
        if re.search(pattern, ua_lower):
            return name

    return None


def _generate_summary(result: Dict) -> str:
    """生成简短描述"""
    parts = []

    # 设备类型
    device_type_names = {
        "mobile": "手机",
        "tablet": "平板",
        "pc": "电脑",
        "bot": "爬虫",
        "other": "其他",
    }
    device_type = device_type_names.get(result.get("device_type"), "")

    # 品牌
    brand = result.get("device_brand", "")

    # 操作系统
    os_name = result.get("os", "")

    # 浏览器
    browser = result.get("browser", "")

    if brand:
        parts.append(brand)
    if os_name:
        parts.append(os_name)
    if browser:
        parts.append(browser)

    if parts:
        return " / ".join(parts)

    return device_type or "未知设备"


def get_device_info_string(ua_string: Optional[str]) -> str:
    """获取设备信息字符串（简化接口）

    Args:
        ua_string: User-Agent字符串

    Returns:
        设备信息描述
    """
    result = parse_user_agent(ua_string)
    return result.get("summary", "未知设备")


def is_mobile_device(ua_string: Optional[str]) -> bool:
    """检查是否为移动设备

    Args:
        ua_string: User-Agent字符串

    Returns:
        是否为移动设备
    """
    if not ua_string:
        return False
    result = parse_user_agent(ua_string)
    return result.get("is_mobile", False) or result.get("is_tablet", False)


def is_known_bot(ua_string: Optional[str]) -> bool:
    """检查是否为已知爬虫

    Args:
        ua_string: User-Agent字符串

    Returns:
        是否为爬虫
    """
    if not ua_string:
        return False
    result = parse_user_agent(ua_string)
    return result.get("is_bot", False)


class UAParser:
    """User-Agent解析器类（提供面向对象接口）"""

    def parse(self, ua_string: Optional[str]) -> Dict[str, Optional[str]]:
        """解析User-Agent"""
        return parse_user_agent(ua_string)

    def get_device_info(self, ua_string: Optional[str]) -> str:
        """获取设备信息字符串"""
        return get_device_info_string(ua_string)

    def is_mobile(self, ua_string: Optional[str]) -> bool:
        """检查是否为移动设备"""
        return is_mobile_device(ua_string)

    def is_bot(self, ua_string: Optional[str]) -> bool:
        """检查是否为爬虫"""
        return is_known_bot(ua_string)


# 全局实例
ua_parser = UAParser()
