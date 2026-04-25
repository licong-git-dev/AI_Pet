"""
PetPal - 阿里云通义千问VL服务
图像理解 + 多模态对话
"""
import json
import base64
import httpx
from typing import Dict, List, Optional
from app.config import settings


# 诊断类型配置
DIAGNOSIS_TYPE_CONFIG = {
    "skin": {
        "name": "皮肤/毛发检测",
        "description": "检测皮肤红肿、脱毛、皮屑等问题",
        "prompt_focus": "皮肤状态、毛发质量、是否有红肿、脱毛、皮屑、伤口等"
    },
    "eye": {
        "name": "眼睛检测",
        "description": "检测眼睛红肿、分泌物、泪痕等问题",
        "prompt_focus": "眼睛是否有红肿、分泌物、泪痕、浑浊、异物等"
    },
    "mouth": {
        "name": "口腔检测",
        "description": "检测牙龈红肿、牙结石等问题",
        "prompt_focus": "牙龈颜色、是否有红肿、牙结石、口腔溃疡、牙齿状况等"
    },
    "feces": {
        "name": "粪便检测",
        "description": "检测消化问题、寄生虫迹象等",
        "prompt_focus": "粪便颜色、形状、质地、是否有血丝、寄生虫、异物等"
    },
    "symptom": {
        "name": "症状描述",
        "description": "直接描述症状，AI帮你分析",
        "prompt_focus": "综合症状分析"
    }
}


def build_diagnosis_prompt(
    diagnosis_type: str,
    pet_name: str,
    pet_type: str,
    breed: Optional[str],
    age: Optional[str],
    weight: Optional[float],
    symptom_desc: Optional[str]
) -> str:
    """构建图像诊断提示词"""
    type_config = DIAGNOSIS_TYPE_CONFIG.get(diagnosis_type, DIAGNOSIS_TYPE_CONFIG["symptom"])

    prompt = f"""你是一位专业的宠物健康顾问AI。用户上传了一张宠物的{type_config['name']}照片。

宠物信息：
- 名称：{pet_name}
- 种类：{pet_type}
- 品种：{breed or '未知'}
- 年龄：{age or '未知'}
- 体重：{f'{weight}kg' if weight else '未知'}

用户描述的症状：{symptom_desc or '无'}

请重点分析：{type_config['prompt_focus']}

请分析这张图片，并提供以下JSON格式的结果：

{{
    "health_score": <0-100的健康评分>,
    "risk_level": "<low/medium/high/urgent>",
    "issues": [
        {{
            "name": "<问题名称>",
            "confidence": <0-1的置信度>,
            "possible_causes": ["<可能原因1>", "<可能原因2>"],
            "severity": "<mild/moderate/severe>"
        }}
    ],
    "overall_assessment": "<总体评估描述>",
    "suggestions": [
        {{
            "priority": <1-5优先级>,
            "content": "<建议内容>",
            "type": "<medical/observation/care/diet>"
        }}
    ],
    "urgency": "<就医建议，如：建议3天内就医/无需就医/立即就医>"
}}

重要提醒：
- 诊断结论要谨慎，不要过度诊断
- 如果图片不清晰或无法判断，要明确说明
- 置信度要诚实反映判断的确定性
- 始终建议用户在严重情况下咨询专业兽医"""

    return prompt


def build_chat_prompt(
    diagnosis_context: Dict,
    pet_info: Dict
) -> str:
    """构建继续问诊的系统提示词"""
    return f"""你是一位专业的宠物健康顾问AI，正在与用户进行关于宠物健康的问答。

诊断背景：
- 宠物名称：{pet_info.get('name', '未知')}
- 宠物种类：{pet_info.get('pet_type', '未知')}
- 品种：{pet_info.get('breed', '未知')}
- 诊断类型：{diagnosis_context.get('diagnosis_type', '未知')}
- 健康评分：{diagnosis_context.get('health_score', '未知')}分
- 风险等级：{diagnosis_context.get('risk_level', '未知')}
- AI分析结果：{json.dumps(diagnosis_context.get('ai_analysis', {}), ensure_ascii=False)}

请回答用户的问题，要求：
1. 专业、准确、有依据
2. 语言通俗易懂
3. 适当提醒用户严重情况需就医
4. 不要做超出能力范围的诊断承诺
5. 回答简洁明了，不超过300字"""


async def analyze_image_with_qwen_vl(
    image_base64: str,
    prompt: str
) -> Dict:
    """
    使用通义千问VL分析图片

    Args:
        image_base64: Base64编码的图片（带或不带data:image前缀）
        prompt: 分析提示词

    Returns:
        AI分析结果
    """
    # 处理base64格式
    if image_base64.startswith('data:'):
        # 移除 data:image/xxx;base64, 前缀
        image_base64 = image_base64.split(',', 1)[1]

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.dashscope_vl_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 尝试解析JSON
                try:
                    # 查找JSON内容
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

                # 如果无法解析JSON，返回默认结构
                return get_default_diagnosis_result(content)
            else:
                print(f"通义千问VL API错误: {response.status_code} - {response.text}")
                return get_default_diagnosis_result("AI服务暂时不可用，请稍后重试")

    except Exception as e:
        print(f"通义千问VL调用异常: {str(e)}")
        return get_default_diagnosis_result(f"分析过程中出现错误: {str(e)}")


async def chat_with_qwen(
    system_prompt: str,
    messages: List[Dict],
    user_message: str
) -> str:
    """
    使用通义千问进行多轮对话

    Args:
        system_prompt: 系统提示词
        messages: 历史消息列表
        user_message: 用户新消息

    Returns:
        AI回复内容
    """
    try:
        # 构建消息列表
        api_messages = [{"role": "system", "content": system_prompt}]

        # 添加历史消息（最多保留10轮）
        for msg in messages[-20:]:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # 添加新消息
        api_messages.append({"role": "user", "content": user_message})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.dashscope_chat_model,
                    "messages": api_messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"通义千问API错误: {response.status_code} - {response.text}")
                return "抱歉，AI服务暂时不可用，请稍后重试。如有紧急情况，建议直接咨询专业兽医。"

    except Exception as e:
        print(f"通义千问调用异常: {str(e)}")
        return "抱歉，服务出现异常，请稍后重试。"


def get_default_diagnosis_result(message: str = "") -> Dict:
    """获取默认诊断结果"""
    return {
        "health_score": 70,
        "risk_level": "medium",
        "issues": [
            {
                "name": "需要进一步检查",
                "confidence": 0.5,
                "possible_causes": ["图片质量或AI服务限制"],
                "severity": "unknown"
            }
        ],
        "overall_assessment": message or "无法完成自动分析，建议咨询专业兽医",
        "suggestions": [
            {
                "priority": 1,
                "content": "建议咨询专业兽医获取准确诊断",
                "type": "medical"
            },
            {
                "priority": 2,
                "content": "密切观察宠物状态变化",
                "type": "observation"
            },
            {
                "priority": 3,
                "content": "保持宠物生活环境清洁",
                "type": "care"
            }
        ],
        "urgency": "建议近期就医检查"
    }


async def analyze_symptom_only(
    pet_name: str,
    pet_type: str,
    breed: Optional[str],
    age: Optional[str],
    symptom_desc: str
) -> Dict:
    """
    仅根据症状描述进行分析（无图片）

    Args:
        pet_name: 宠物名称
        pet_type: 宠物类型
        breed: 品种
        age: 年龄
        symptom_desc: 症状描述

    Returns:
        AI分析结果
    """
    prompt = f"""你是一位专业的宠物健康顾问AI。用户描述了宠物的症状，请帮助分析。

宠物信息：
- 名称：{pet_name}
- 种类：{pet_type}
- 品种：{breed or '未知'}
- 年龄：{age or '未知'}

用户描述的症状：
{symptom_desc}

请分析症状，并提供以下JSON格式的结果：

{{
    "health_score": <0-100的健康评分>,
    "risk_level": "<low/medium/high/urgent>",
    "issues": [
        {{
            "name": "<问题名称>",
            "confidence": <0-1的置信度>,
            "possible_causes": ["<可能原因1>", "<可能原因2>"],
            "severity": "<mild/moderate/severe>"
        }}
    ],
    "overall_assessment": "<总体评估描述>",
    "suggestions": [
        {{
            "priority": <1-5优先级>,
            "content": "<建议内容>",
            "type": "<medical/observation/care/diet>"
        }}
    ],
    "urgency": "<就医建议>"
}}

注意：由于没有图片，分析会有一定局限性，请在结果中说明这一点。"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.dashscope_chat_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 尝试解析JSON
                try:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

                return get_default_diagnosis_result(content)
            else:
                return get_default_diagnosis_result("AI服务暂时不可用")

    except Exception as e:
        print(f"症状分析异常: {str(e)}")
        return get_default_diagnosis_result(f"分析过程中出现错误")
