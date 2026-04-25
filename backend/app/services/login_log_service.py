"""
PetPal - 登录日志服务

提供登录日志记录和查询功能
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from loguru import logger

from app.models.login_log import LoginLog
from app.utils.ip_resolver import resolve_ip, check_location_change
from app.utils.ua_parser import parse_user_agent


async def record_login(
    db: Session,
    user_id: Optional[int],
    phone: Optional[str],
    login_ip: str,
    user_agent: Optional[str],
    login_type: str = "sms",
    login_status: bool = True,
    failure_reason: Optional[str] = None,
) -> LoginLog:
    """记录登录日志

    Args:
        db: 数据库会话
        user_id: 用户ID（登录失败时可能为空）
        phone: 登录手机号
        login_ip: 登录IP地址
        user_agent: User-Agent字符串
        login_type: 登录方式 (sms/password/wechat/apple)
        login_status: 登录是否成功
        failure_reason: 登录失败原因

    Returns:
        创建的登录日志记录
    """
    # 解析IP地址
    ip_info = resolve_ip(login_ip)

    # 解析User-Agent
    ua_info = parse_user_agent(user_agent)

    # 检查是否异地登录
    is_abnormal = False
    risk_level = "low"

    if user_id and login_status:
        location_check = await check_abnormal_login(db, user_id, login_ip)
        is_abnormal = location_check.get("is_abnormal", False)
        risk_level = location_check.get("risk_level", "low")

    # 创建登录日志
    login_log = LoginLog(
        user_id=user_id,
        phone=phone,
        login_type=login_type,
        login_ip=login_ip,
        login_location=ip_info.get("location"),
        login_device=ua_info.get("summary"),
        device_type=ua_info.get("device_type"),
        browser=ua_info.get("browser"),
        os=ua_info.get("os"),
        user_agent=user_agent,
        login_status=login_status,
        failure_reason=failure_reason,
        is_abnormal=is_abnormal,
        risk_level=risk_level,
        login_time=datetime.now(),
    )

    db.add(login_log)
    db.commit()
    db.refresh(login_log)

    # 记录日志
    if login_status:
        if is_abnormal:
            logger.warning(
                f"异地登录检测: user_id={user_id}, ip={login_ip}, "
                f"location={ip_info.get('location')}, risk={risk_level}"
            )
        else:
            logger.info(
                f"用户登录成功: user_id={user_id}, ip={login_ip}, "
                f"location={ip_info.get('location')}"
            )
    else:
        logger.warning(
            f"用户登录失败: phone={phone}, ip={login_ip}, "
            f"reason={failure_reason}"
        )

    return login_log


async def check_abnormal_login(
    db: Session,
    user_id: int,
    current_ip: str
) -> dict:
    """检查是否为异常登录

    Args:
        db: 数据库会话
        user_id: 用户ID
        current_ip: 当前登录IP

    Returns:
        包含异常检测结果的字典
    """
    result = {
        "is_abnormal": False,
        "risk_level": "low",
        "message": None,
    }

    # 获取上次成功登录记录
    last_login = db.query(LoginLog).filter(
        and_(
            LoginLog.user_id == user_id,
            LoginLog.login_status == True,
        )
    ).order_by(desc(LoginLog.login_time)).first()

    if not last_login:
        return result

    # 检查位置变化
    location_check = check_location_change(current_ip, last_login.login_ip)

    if location_check.get("is_abnormal"):
        result["is_abnormal"] = True
        result["risk_level"] = location_check.get("risk_level", "medium")
        result["message"] = location_check.get("message")

    # 检查短时间内多次登录失败
    recent_failures = await count_recent_failures(db, user_id, minutes=30)
    if recent_failures >= 5:
        result["is_abnormal"] = True
        result["risk_level"] = "high"
        result["message"] = f"30分钟内登录失败{recent_failures}次"

    return result


async def count_recent_failures(
    db: Session,
    user_id: int,
    minutes: int = 30
) -> int:
    """统计最近登录失败次数

    Args:
        db: 数据库会话
        user_id: 用户ID
        minutes: 时间范围（分钟）

    Returns:
        失败次数
    """
    since = datetime.now() - timedelta(minutes=minutes)

    count = db.query(LoginLog).filter(
        and_(
            LoginLog.user_id == user_id,
            LoginLog.login_status == False,
            LoginLog.login_time >= since,
        )
    ).count()

    return count


async def get_user_login_history(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[LoginLog], int]:
    """获取用户登录历史

    Args:
        db: 数据库会话
        user_id: 用户ID
        page: 页码
        page_size: 每页数量

    Returns:
        (登录日志列表, 总数)
    """
    query = db.query(LoginLog).filter(LoginLog.user_id == user_id)

    total = query.count()

    logs = query.order_by(desc(LoginLog.login_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return logs, total


async def get_recent_login_locations(
    db: Session,
    user_id: int,
    days: int = 30,
) -> List[dict]:
    """获取用户最近登录位置（用于展示）

    Args:
        db: 数据库会话
        user_id: 用户ID
        days: 天数

    Returns:
        登录位置列表
    """
    since = datetime.now() - timedelta(days=days)

    logs = db.query(LoginLog).filter(
        and_(
            LoginLog.user_id == user_id,
            LoginLog.login_status == True,
            LoginLog.login_time >= since,
        )
    ).order_by(desc(LoginLog.login_time)).limit(10).all()

    locations = []
    seen = set()

    for log in logs:
        location = log.login_location or "未知"
        if location not in seen:
            seen.add(location)
            locations.append({
                "location": location,
                "ip": log.login_ip,
                "device": log.login_device,
                "time": log.login_time.isoformat() if log.login_time else None,
            })

    return locations


async def check_login_risk(
    db: Session,
    phone: str,
    ip: str,
) -> dict:
    """检查登录风险（在登录前调用）

    Args:
        db: 数据库会话
        phone: 手机号
        ip: IP地址

    Returns:
        风险检测结果
    """
    result = {
        "allow": True,
        "risk_level": "low",
        "require_captcha": False,
        "message": None,
    }

    # 检查IP登录失败次数
    since = datetime.now() - timedelta(hours=1)
    ip_failures = db.query(LoginLog).filter(
        and_(
            LoginLog.login_ip == ip,
            LoginLog.login_status == False,
            LoginLog.login_time >= since,
        )
    ).count()

    if ip_failures >= 10:
        result["allow"] = False
        result["risk_level"] = "high"
        result["message"] = "登录失败次数过多，请稍后重试"
        return result

    if ip_failures >= 5:
        result["risk_level"] = "medium"
        result["require_captcha"] = True

    # 检查手机号登录失败次数
    phone_failures = db.query(LoginLog).filter(
        and_(
            LoginLog.phone == phone,
            LoginLog.login_status == False,
            LoginLog.login_time >= since,
        )
    ).count()

    if phone_failures >= 5:
        result["risk_level"] = "medium"
        result["require_captcha"] = True

    if phone_failures >= 10:
        result["allow"] = False
        result["risk_level"] = "high"
        result["message"] = "登录失败次数过多，请稍后重试"

    return result


async def cleanup_old_logs(
    db: Session,
    days: int = 90,
) -> int:
    """清理旧的登录日志

    Args:
        db: 数据库会话
        days: 保留天数

    Returns:
        删除的记录数
    """
    cutoff = datetime.now() - timedelta(days=days)

    deleted = db.query(LoginLog).filter(
        LoginLog.login_time < cutoff
    ).delete()

    db.commit()
    logger.info(f"清理登录日志: 删除{deleted}条{days}天前的记录")

    return deleted
