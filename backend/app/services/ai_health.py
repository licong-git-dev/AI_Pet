"""
PetPal - AI健康服务模块

提供AI驱动的宠物健康分析功能：
- 多模型支持（OpenAI、阿里云通义千问）
- 症状分析和健康评估
- 智能问诊对话
- 图像分析（皮肤、眼睛等）
- 问诊总结生成
"""
import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

import httpx
from loguru import logger

from app.config import settings


# ==================== 分析类型枚举 ====================

class AnalysisType(str, Enum):
    """分析类型枚举"""
    GENERAL = "general"      # 综合分析
    SKIN = "skin"            # 皮肤问题
    EYE = "eye"              # 眼部问题
    POOP = "poop"            # 排便问题
    BEHAVIOR = "behavior"    # 行为异常
    RESPIRATORY = "respiratory"  # 呼吸问题
    DIGESTIVE = "digestive"  # 消化问题
    EMERGENCY = "emergency"  # 紧急情况


class RiskLevel(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ==================== 专业提示词模板 ====================

ANALYSIS_PROMPTS = {
    AnalysisType.GENERAL: """请作为专业宠物医生，对以下宠物健康状况进行综合分析。注意评估整体健康状态和潜在风险。""",

    AnalysisType.SKIN: """请作为皮肤科专业兽医，分析以下宠物的皮肤问题。
重点关注：
- 皮肤病变类型（红疹、脱毛、结痂等）
- 可能的病因（过敏、真菌、寄生虫、细菌感染等）
- 是否具有传染性
- 建议的检查项目（皮肤刮片、真菌培养等）""",

    AnalysisType.EYE: """请作为眼科专业兽医，分析以下宠物的眼部问题。
重点关注：
- 眼部症状（分泌物、红肿、混浊等）
- 可能的病因（结膜炎、角膜炎、青光眼等）
- 是否需要紧急处理
- 日常护理建议""",

    AnalysisType.POOP: """请作为消化科专业兽医，分析以下宠物的排便问题。
重点关注：
- 粪便性状异常（腹泻、便秘、血便等）
- 可能的病因（饮食、感染、寄生虫、肠道疾病等）
- 是否需要禁食
- 饮食调整建议""",

    AnalysisType.BEHAVIOR: """请作为动物行为学专家，分析以下宠物的行为异常。
重点关注：
- 行为变化类型（焦虑、攻击、抑郁等）
- 可能的原因（疼痛、疾病、环境、心理）
- 是否需要医学检查排除器质性病变
- 行为矫正建议""",

    AnalysisType.RESPIRATORY: """请作为呼吸科专业兽医，分析以下宠物的呼吸问题。
重点关注：
- 呼吸症状（咳嗽、喘息、鼻塞等）
- 可能的病因（感染、过敏、心脏问题等）
- 紧急程度评估
- 环境改善建议""",

    AnalysisType.DIGESTIVE: """请作为消化内科专业兽医，分析以下宠物的消化问题。
重点关注：
- 消化症状（呕吐、食欲不振、腹胀等）
- 可能的病因（饮食不当、胃肠炎、异物等）
- 是否需要禁食观察
- 饮食管理建议""",

    AnalysisType.EMERGENCY: """请作为急诊科专业兽医，快速评估以下宠物的紧急状况。
重点关注：
- 是否存在生命危险
- 需要立即采取的措施
- 送医前的急救处理
- 紧急联系建议"""
}


# ==================== 症状关键词映射 ====================

SYMPTOM_KEYWORDS = {
    "皮肤": AnalysisType.SKIN,
    "脱毛": AnalysisType.SKIN,
    "红疹": AnalysisType.SKIN,
    "痒": AnalysisType.SKIN,
    "皮屑": AnalysisType.SKIN,

    "眼睛": AnalysisType.EYE,
    "眼屎": AnalysisType.EYE,
    "流泪": AnalysisType.EYE,
    "眼红": AnalysisType.EYE,

    "拉稀": AnalysisType.POOP,
    "腹泻": AnalysisType.POOP,
    "便血": AnalysisType.POOP,
    "便秘": AnalysisType.POOP,

    "咳嗽": AnalysisType.RESPIRATORY,
    "喘": AnalysisType.RESPIRATORY,
    "呼吸": AnalysisType.RESPIRATORY,
    "打喷嚏": AnalysisType.RESPIRATORY,

    "呕吐": AnalysisType.DIGESTIVE,
    "不吃": AnalysisType.DIGESTIVE,
    "食欲": AnalysisType.DIGESTIVE,

    "抽搐": AnalysisType.EMERGENCY,
    "昏迷": AnalysisType.EMERGENCY,
    "中毒": AnalysisType.EMERGENCY,
    "大出血": AnalysisType.EMERGENCY,
    "呼吸困难": AnalysisType.EMERGENCY,
}


def detect_analysis_type(symptoms: str) -> AnalysisType:
    """根据症状描述自动检测分析类型"""
    for keyword, analysis_type in SYMPTOM_KEYWORDS.items():
        if keyword in symptoms:
            # 紧急情况优先级最高
            if analysis_type == AnalysisType.EMERGENCY:
                return AnalysisType.EMERGENCY

    # 再次检查非紧急类型
    for keyword, analysis_type in SYMPTOM_KEYWORDS.items():
        if keyword in symptoms:
            return analysis_type

    return AnalysisType.GENERAL


# ==================== AI模型调用封装 ====================

async def call_openai_api(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    response_format: Optional[Dict] = None
) -> Optional[str]:
    """调用OpenAI兼容API"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "model": model or settings.openai_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            if response_format:
                payload["response_format"] = response_format

            response = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API错误: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"OpenAI API调用失败: {str(e)}")
        return None


async def call_dashscope_api(
    messages: List[Dict],
    model: str = "qwen-turbo",
    temperature: float = 0.7,
    max_tokens: int = 1000
) -> Optional[str]:
    """调用阿里云通义千问API"""
    try:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = settings.dashscope_api_key

        response = Generation.call(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message'
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            logger.error(f"DashScope API错误: {response.code} - {response.message}")
            return None

    except ImportError:
        logger.warning("DashScope SDK未安装")
        return None
    except Exception as e:
        logger.error(f"DashScope API调用失败: {str(e)}")
        return None


async def call_ai_api(
    messages: List[Dict],
    temperature: float = 0.7,
    max_tokens: int = 1000,
    prefer_provider: str = "auto"
) -> Optional[str]:
    """统一的AI API调用接口，支持自动切换"""
    # 确定使用的提供商
    if prefer_provider == "dashscope" and settings.dashscope_api_key:
        result = await call_dashscope_api(messages, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result

    # 默认使用OpenAI（或兼容API）
    if settings.openai_api_key:
        result = await call_openai_api(messages, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result

    # 如果OpenAI失败，尝试DashScope
    if settings.dashscope_api_key and prefer_provider != "dashscope":
        result = await call_dashscope_api(messages, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result

    return None


# ==================== 健康分析功能 ====================

async def analyze_pet_health(
    pet_type: str,
    breed: Optional[str],
    age: Optional[int],
    symptoms: str,
    image_urls: Optional[List[str]] = None,
    analysis_type: str = "general"
) -> Dict:
    """
    AI分析宠物健康状况

    Args:
        pet_type: 宠物类型
        breed: 品种
        age: 年龄
        symptoms: 症状描述
        image_urls: 相关图片
        analysis_type: 分析类型

    Returns:
        分析结果字典
    """
    # 自动检测分析类型
    if analysis_type == "general" or analysis_type == "auto":
        detected_type = detect_analysis_type(symptoms)
        analysis_type = detected_type.value

    # 获取专业提示词
    type_enum = AnalysisType(analysis_type) if analysis_type in [t.value for t in AnalysisType] else AnalysisType.GENERAL
    specialist_prompt = ANALYSIS_PROMPTS.get(type_enum, ANALYSIS_PROMPTS[AnalysisType.GENERAL])

    # 构建系统提示词
    system_prompt = f"""你是PetPal平台的专业AI宠物医生助手。
{specialist_prompt}

重要提醒：
1. 你的分析仅供参考，不能替代专业兽医诊断
2. 对于严重或紧急情况，必须建议立即就医
3. 回答要专业但易于理解
4. 给出具体可行的建议"""

    # 构建用户消息
    pet_info = f"""
宠物信息：
- 类型：{pet_type}
- 品种：{breed or '未知'}
- 年龄：{f'{age}岁' if age else '未知'}

症状描述：
{symptoms}
"""

    if image_urls:
        pet_info += f"\n（用户上传了{len(image_urls)}张相关图片，请结合描述分析）"

    user_prompt = f"""{pet_info}

请按以下JSON格式返回分析结果：
{{
    "analysis": "详细的症状分析",
    "possible_conditions": ["可能的疾病1", "可能的疾病2"],
    "risk_level": "low/medium/high/urgent",
    "risk_explanation": "风险评估说明",
    "recommended_actions": ["建议措施1", "建议措施2"],
    "need_vet_visit": true/false,
    "urgency": "观察/尽快就医/立即就医",
    "home_care": ["家庭护理建议1", "家庭护理建议2"],
    "warning_signs": ["需要警惕的恶化症状"]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # 调用AI API
    response = await call_ai_api(messages, temperature=0.5, max_tokens=1500)

    if response:
        try:
            # 尝试解析JSON
            result = parse_json_response(response)
            if result:
                # 确保必要字段存在
                result.setdefault("analysis", response)
                result.setdefault("suggestions", result.get("recommended_actions", []))
                result.setdefault("risk_level", "medium")
                return result
        except Exception as e:
            logger.warning(f"解析AI响应失败: {e}")

        # 解析失败，返回原始内容
        return {
            "analysis": response,
            "suggestions": ["建议咨询专业兽医获取更准确的诊断"],
            "risk_level": "medium",
            "possible_conditions": [],
            "recommended_actions": ["观察症状变化", "保持宠物舒适", "必要时就医"]
        }

    # AI服务不可用，返回默认结果
    return _get_default_analysis(symptoms, analysis_type)


def parse_json_response(response: str) -> Optional[Dict]:
    """解析AI返回的JSON响应"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试提取JSON块
    json_patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'\{[\s\S]*\}'
    ]

    for pattern in json_patterns:
        match = re.search(pattern, response)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                continue

    return None


def _get_default_analysis(symptoms: str, analysis_type: str) -> Dict:
    """获取默认分析结果（当AI服务不可用时）"""
    # 根据分析类型给出更具体的默认建议
    type_specific_advice = {
        "skin": ["保持皮肤清洁干燥", "避免抓挠患处", "检查是否有跳蚤或螨虫"],
        "eye": ["用生理盐水轻轻清洁眼部", "避免强光刺激", "不要自行用药"],
        "poop": ["暂时禁食4-6小时", "保持充足饮水", "观察粪便性状变化"],
        "respiratory": ["保持环境通风", "避免刺激性气味", "观察呼吸频率"],
        "digestive": ["少食多餐", "选择易消化食物", "避免喂食人类食物"],
        "emergency": ["保持冷静", "立即联系宠物医院", "准备好就医所需资料"],
    }

    specific_advice = type_specific_advice.get(analysis_type, [])

    return {
        "analysis": f"根据您描述的症状「{symptoms[:100]}{'...' if len(symptoms) > 100 else ''}」，建议您密切观察宠物状况。由于AI服务暂时不可用，建议您咨询专业兽医获取准确诊断。",
        "suggestions": [
            "密切观察宠物的精神状态和食欲",
            "保持环境清洁和适宜温度",
            "如症状持续或加重，请及时就医",
            *specific_advice
        ],
        "risk_level": "medium",
        "possible_conditions": ["需要专业检查进行判断"],
        "recommended_actions": [
            "记录症状变化和发生时间",
            "拍照记录患处情况",
            "建议咨询专业兽医"
        ],
        "need_vet_visit": True,
        "urgency": "观察后决定"
    }


# ==================== 问诊对话功能 ====================

async def generate_consultation_response(
    pet_type: str,
    breed: Optional[str],
    chief_complaint: str,
    symptoms: Optional[str] = None,
    message_history: Optional[List[Dict]] = None,
    new_message: Optional[str] = None,
    image_urls: Optional[List[str]] = None,
    is_initial: bool = False
) -> str:
    """
    生成问诊对话回复

    Args:
        pet_type: 宠物类型
        breed: 品种
        chief_complaint: 主诉
        symptoms: 症状
        message_history: 历史消息
        new_message: 新消息
        image_urls: 图片
        is_initial: 是否初始回复

    Returns:
        AI回复内容
    """
    system_prompt = f"""你是PetPal平台的专业宠物医生AI助手，正在为宠物主人提供在线问诊服务。

当前宠物信息：
- 类型：{pet_type}
- 品种：{breed or '未知'}
- 主诉：{chief_complaint}
{f'- 症状：{symptoms}' if symptoms else ''}

问诊指南：
1. 用专业但易于理解的语言交流
2. 系统性地收集病史信息（症状持续时间、严重程度、伴随症状等）
3. 给出具体可行的建议
4. 必要时明确建议就医
5. 每次回复控制在150字以内，重点突出
6. 适时总结已知信息，避免重复询问

安全提醒：
- 不要做出确定性诊断
- 对于紧急情况，优先建议就医
- 提醒用户AI建议仅供参考"""

    messages = [{"role": "system", "content": system_prompt}]

    if is_initial:
        # 初始问诊回复
        initial_prompt = f"我的{pet_type}{chief_complaint}"
        if symptoms:
            initial_prompt += f"，{symptoms}"
        initial_prompt += "，请帮我分析一下可能是什么问题。"
        messages.append({"role": "user", "content": initial_prompt})
    else:
        # 继续对话
        if message_history:
            # 限制历史消息数量，保留最近的对话
            for msg in message_history[-10:]:
                messages.append(msg)
        if new_message:
            content = new_message
            if image_urls:
                content += f"\n（我上传了{len(image_urls)}张图片供参考）"
            messages.append({"role": "user", "content": content})

    # 调用AI API
    response = await call_ai_api(messages, temperature=0.7, max_tokens=500)

    if response:
        return response

    return _get_default_consultation_response(is_initial, chief_complaint)


def _get_default_consultation_response(is_initial: bool, chief_complaint: str) -> str:
    """获取默认问诊回复"""
    if is_initial:
        return f"""您好！我了解到您的宠物{chief_complaint}。

为了更准确地帮助您分析，请告诉我：
1. 这个症状是什么时候开始的？
2. 宠物目前的精神状态和食欲如何？
3. 最近有没有更换过食物或接触过其他动物？
4. 除了主要症状，还有其他异常表现吗？

请尽量详细描述，我会根据您提供的信息给出专业建议。"""
    else:
        return """感谢您的补充信息。

根据目前了解的情况，建议您：
1. 继续密切观察宠物状态
2. 记录症状的变化情况
3. 如果症状持续或加重，请及时带宠物就医检查

您还有其他问题需要咨询吗？"""


# ==================== 问诊总结功能 ====================

async def generate_consultation_summary(
    chief_complaint: str,
    messages: List[Dict]
) -> Dict:
    """
    生成问诊总结

    Args:
        chief_complaint: 主诉
        messages: 对话记录

    Returns:
        总结字典
    """
    # 构建对话内容
    conversation = "\n".join([
        f"{'宠物主人' if m['role'] == 'user' else 'AI医生'}: {m['content']}"
        for m in messages
    ])

    system_prompt = """你是一位专业的宠物医生，需要根据问诊记录生成结构化的总结报告。
总结应该专业、准确、对宠物主人有帮助。"""

    user_prompt = f"""请根据以下宠物问诊记录，生成一份问诊总结报告。

主诉：{chief_complaint}

问诊记录：
{conversation}

请按以下JSON格式返回总结：
{{
    "summary": "问诊过程摘要（100字以内）",
    "collected_info": {{
        "symptoms": ["收集到的症状列表"],
        "duration": "症状持续时间",
        "severity": "严重程度评估"
    }},
    "diagnosis": "初步判断和分析",
    "suggestions": ["建议措施1", "建议措施2", "建议措施3"],
    "follow_up": "后续注意事项",
    "need_vet": true/false,
    "vet_urgency": "无需/建议/尽快/立即"
}}"""

    messages_payload = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = await call_ai_api(messages_payload, temperature=0.5, max_tokens=800)

    if response:
        result = parse_json_response(response)
        if result:
            # 确保必要字段存在
            result.setdefault("summary", "问诊已完成")
            result.setdefault("diagnosis", "建议进一步检查确诊")
            result.setdefault("suggestions", ["继续观察", "必要时就医"])
            return result

        # 解析失败，返回带原始内容的结构
        return {
            "summary": response[:200] if len(response) > 200 else response,
            "diagnosis": "建议进一步检查确诊",
            "suggestions": ["继续观察", "保持宠物舒适", "必要时就医"]
        }

    return _get_default_summary(chief_complaint)


def _get_default_summary(chief_complaint: str) -> Dict:
    """获取默认问诊总结"""
    return {
        "summary": f"本次问诊主要针对宠物{chief_complaint}的问题进行了咨询和分析。",
        "diagnosis": "根据描述的症状，建议进行进一步专业检查以明确诊断。",
        "suggestions": [
            "密切观察宠物状态变化",
            "记录症状的发展情况",
            "保持生活环境清洁",
            "如症状持续或加重，建议前往宠物医院检查"
        ],
        "follow_up": "建议持续关注宠物状态，如有变化可再次咨询",
        "need_vet": True,
        "vet_urgency": "建议"
    }


# ==================== 辅助功能 ====================

async def get_breed_health_info(pet_type: str, breed: str) -> Optional[Dict]:
    """获取特定品种的健康信息和常见疾病"""
    prompt = f"""请提供{pet_type}品种"{breed}"的健康相关信息：

请以JSON格式返回：
{{
    "common_diseases": ["常见疾病1", "常见疾病2"],
    "health_tips": ["健康养护建议1", "健康养护建议2"],
    "diet_recommendations": ["饮食建议"],
    "exercise_needs": "运动需求说明",
    "grooming_needs": "美容护理需求",
    "lifespan": "预期寿命"
}}"""

    messages = [
        {"role": "system", "content": "你是一位宠物品种专家，请提供准确的品种健康信息。"},
        {"role": "user", "content": prompt}
    ]

    response = await call_ai_api(messages, temperature=0.3, max_tokens=500)

    if response:
        return parse_json_response(response)

    return None


async def analyze_symptom_severity(symptoms: str) -> Dict:
    """分析症状严重程度"""
    # 紧急关键词检测
    emergency_keywords = ["抽搐", "昏迷", "大出血", "呼吸困难", "中毒", "休克", "心跳停止"]
    urgent_keywords = ["持续呕吐", "血便", "高烧", "无法站立", "剧烈疼痛", "完全不吃"]
    warning_keywords = ["精神萎靡", "食欲下降", "腹泻", "咳嗽", "流鼻涕"]

    severity = {
        "level": "low",
        "score": 0,
        "detected_keywords": [],
        "recommendation": "可以继续观察"
    }

    for keyword in emergency_keywords:
        if keyword in symptoms:
            severity["level"] = "urgent"
            severity["score"] = 100
            severity["detected_keywords"].append(keyword)
            severity["recommendation"] = "请立即就医！"
            return severity

    for keyword in urgent_keywords:
        if keyword in symptoms:
            severity["level"] = "high"
            severity["score"] = max(severity["score"], 70)
            severity["detected_keywords"].append(keyword)
            severity["recommendation"] = "建议尽快就医"

    for keyword in warning_keywords:
        if keyword in symptoms:
            if severity["level"] == "low":
                severity["level"] = "medium"
            severity["score"] = max(severity["score"], 40)
            severity["detected_keywords"].append(keyword)
            if severity["recommendation"] == "可以继续观察":
                severity["recommendation"] = "建议密切观察，必要时就医"

    return severity
