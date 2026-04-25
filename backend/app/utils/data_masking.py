"""
PetPal - 数据脱敏工具

提供敏感数据的脱敏处理功能
"""
import re
from typing import Optional


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """手机号脱敏

    将手机号中间4位替换为****
    示例: 13812345678 -> 138****5678

    Args:
        phone: 手机号

    Returns:
        脱敏后的手机号
    """
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_email(email: Optional[str]) -> Optional[str]:
    """邮箱脱敏

    将邮箱用户名部分进行脱敏处理
    示例: test@example.com -> t***@example.com
    示例: ab@example.com -> a*@example.com

    Args:
        email: 邮箱地址

    Returns:
        脱敏后的邮箱
    """
    if not email or "@" not in email:
        return email

    parts = email.split("@")
    username = parts[0]
    domain = parts[1]

    if len(username) <= 1:
        return email
    elif len(username) <= 3:
        masked = username[0] + "*" * (len(username) - 1)
    else:
        masked = username[0] + "***"

    return f"{masked}@{domain}"


def mask_id_card(id_card: Optional[str]) -> Optional[str]:
    """身份证号脱敏

    保留前3位和后4位，中间用*替换
    示例: 110101199001011234 -> 110***********1234

    Args:
        id_card: 身份证号

    Returns:
        脱敏后的身份证号
    """
    if not id_card or len(id_card) < 8:
        return id_card
    return id_card[:3] + "*" * (len(id_card) - 7) + id_card[-4:]


def mask_bank_card(card_number: Optional[str]) -> Optional[str]:
    """银行卡号脱敏

    只保留后4位，其余用*替换
    示例: 6222021234567890 -> ************7890

    Args:
        card_number: 银行卡号

    Returns:
        脱敏后的银行卡号
    """
    if not card_number or len(card_number) < 4:
        return card_number
    return "*" * (len(card_number) - 4) + card_number[-4:]


def mask_name(name: Optional[str]) -> Optional[str]:
    """姓名脱敏

    两个字的姓名：保留姓，名用*替换
    三个字及以上：保留姓和最后一个字，中间用*替换
    示例: 张三 -> 张*
    示例: 王小明 -> 王*明
    示例: 欧阳小龙 -> 欧***龙

    Args:
        name: 姓名

    Returns:
        脱敏后的姓名
    """
    if not name or len(name) < 2:
        return name

    if len(name) == 2:
        return name[0] + "*"
    else:
        return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_address(address: Optional[str], keep_length: int = 10) -> Optional[str]:
    """地址脱敏

    保留前keep_length个字符，后面用***替换

    Args:
        address: 地址
        keep_length: 保留的字符长度

    Returns:
        脱敏后的地址
    """
    if not address or len(address) <= keep_length:
        return address
    return address[:keep_length] + "***"


def mask_ip(ip: Optional[str]) -> Optional[str]:
    """IP地址脱敏

    将最后一段替换为*
    示例: 192.168.1.100 -> 192.168.1.*

    Args:
        ip: IP地址

    Returns:
        脱敏后的IP地址
    """
    if not ip:
        return ip

    # IPv4
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        parts = ip.split(".")
        parts[-1] = "*"
        return ".".join(parts)

    # IPv6 简单处理
    if ":" in ip:
        parts = ip.split(":")
        if len(parts) > 2:
            parts[-1] = "*"
            return ":".join(parts)

    return ip


def mask_vehicle_number(plate: Optional[str]) -> Optional[str]:
    """车牌号脱敏

    保留前2位和后2位
    示例: 京A12345 -> 京A***45

    Args:
        plate: 车牌号

    Returns:
        脱敏后的车牌号
    """
    if not plate or len(plate) < 5:
        return plate
    return plate[:2] + "***" + plate[-2:]


class DataMasker:
    """数据脱敏器

    提供链式调用和批量脱敏功能
    """

    @staticmethod
    def mask(value: Optional[str], mask_type: str) -> Optional[str]:
        """通用脱敏方法

        Args:
            value: 要脱敏的值
            mask_type: 脱敏类型 (phone, email, id_card, bank_card, name, address, ip, vehicle)

        Returns:
            脱敏后的值
        """
        mask_functions = {
            "phone": mask_phone,
            "email": mask_email,
            "id_card": mask_id_card,
            "bank_card": mask_bank_card,
            "name": mask_name,
            "address": mask_address,
            "ip": mask_ip,
            "vehicle": mask_vehicle_number,
        }

        func = mask_functions.get(mask_type)
        if func:
            return func(value)
        return value

    @staticmethod
    def mask_dict(data: dict, mask_rules: dict) -> dict:
        """批量脱敏字典数据

        Args:
            data: 要脱敏的字典数据
            mask_rules: 脱敏规则 {字段名: 脱敏类型}

        Returns:
            脱敏后的字典

        Example:
            >>> data = {"phone": "13812345678", "email": "test@example.com"}
            >>> rules = {"phone": "phone", "email": "email"}
            >>> DataMasker.mask_dict(data, rules)
            {"phone": "138****5678", "email": "t***@example.com"}
        """
        result = data.copy()
        for field, mask_type in mask_rules.items():
            if field in result and result[field]:
                result[field] = DataMasker.mask(result[field], mask_type)
        return result
