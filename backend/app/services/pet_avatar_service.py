"""
PetPal - 宠物数字分身AI服务

复用 qwen_vl_service.py 的 DashScope API 调用模式，
提供外貌分析、性格分析、宠物对话、表情包生成等功能。
"""
import json
import re
import httpx
from typing import Dict, List, Optional

from loguru import logger
from app.config import settings


# ==================== 说话风格配置 ====================

SPEAKING_STYLES = {
    "cute": {
        "name": "可爱撒娇",
        "desc": "说话可爱撒娇，喜欢用叠词和语气词（呜呜、嘿嘿、哼哼），经常用可爱的emoji"
    },
    "sassy": {
        "name": "傲娇高冷",
        "desc": "说话傲娇高冷，偶尔毒舌，嘴硬心软，其实很在意主人"
    },
    "lazy": {
        "name": "慵懒随意",
        "desc": "说话慵懒随意，经常打哈欠，说话简短，偶尔犯困"
    },
    "energetic": {
        "name": "热情活泼",
        "desc": "说话热情活泼，经常感叹，什么都很兴奋，充满活力"
    },
    "gentle": {
        "name": "温柔体贴",
        "desc": "说话温柔体贴，关心主人，说话温暖有爱"
    },
}

# ==================== PetSona 类型定义 ====================

PERSONA_TYPES = {
    "solar_explorer":    {"name": "阳光探险家", "emoji": "☀️🧭", "color": "#FF9800", "slogan": "每一天都是新冒险！", "desc": "精力旺盛+好奇心爆棚，永远在探索世界的路上"},
    "velcro_baby":       {"name": "黏人小宝贝", "emoji": "🥰🧸", "color": "#E91E63", "slogan": "你就是我的全世界", "desc": "粘人度+活泼度双高，无时无刻都想在主人身边"},
    "snack_hunter":      {"name": "零食猎人",   "emoji": "🍖🔍", "color": "#FF5722", "slogan": "闻到好吃的了！", "desc": "吃货+活泼的完美组合，为零食不惜一切"},
    "cozy_cuddler":      {"name": "沙发甜心",   "emoji": "🛋️💕", "color": "#9C27B0", "slogan": "最好的位置是你腿上", "desc": "粘人+吃货，最爱窝在主人身边一起享受美食"},
    "food_philosopher":  {"name": "干饭哲学家", "emoji": "🍜🤔", "color": "#795548", "slogan": "吃，是一门艺术", "desc": "吃货+高智商，对食物有着哲学级的执念"},
    "genius_trickster":  {"name": "天才捣蛋鬼", "emoji": "🧠😈", "color": "#673AB7", "slogan": "我不是淘气，我是在搞研究", "desc": "聪明+调皮的危险组合，总在策划下一个大计划"},
    "curious_professor": {"name": "好奇教授",   "emoji": "🔬🤓", "color": "#2196F3", "slogan": "这个也要研究一下", "desc": "好奇心+智商双高，对一切新事物充满求知欲"},
    "chaos_tornado":     {"name": "混世小魔王", "emoji": "🌪️🔥", "color": "#F44336", "slogan": "搞事情，我是认真的", "desc": "活泼+调皮的能量炸弹，走到哪儿乱到哪儿"},
    "noble_gourmet":     {"name": "高冷美食家", "emoji": "👑🍷", "color": "#607D8B", "slogan": "不是所有罐头都配得上我", "desc": "吃货但挑剔，智商高所以更难伺候"},
    "little_detective":  {"name": "小小侦探",   "emoji": "🔎🐾", "color": "#00BCD4", "slogan": "没有我查不到的角落", "desc": "好奇+调皮，像个小侦探一样到处搜查"},
    "zen_master":        {"name": "佛系大师",   "emoji": "🧘☁️", "color": "#4CAF50", "slogan": "都行，都可以，没关系", "desc": "各维度均衡偏低，淡泊名利的修仙选手"},
    "social_butterfly":  {"name": "社交达人",   "emoji": "🦋✨", "color": "#FFEB3B", "slogan": "交朋友是我的超能力", "desc": "粘人+好奇，对所有人和动物都充满热情"},
}


# PetSona 维度对 -> 类型映射表（模块级常量，避免每次调用重建）
_PERSONA_PAIR_MAP: dict = {
    frozenset({"energy", "curiosity"}):       "solar_explorer",
    frozenset({"affection", "energy"}):       "velcro_baby",
    frozenset({"foodie", "energy"}):          "snack_hunter",
    frozenset({"affection", "foodie"}):       "cozy_cuddler",
    frozenset({"foodie", "intelligence"}):    "food_philosopher",
    frozenset({"intelligence", "mischief"}):  "genius_trickster",
    frozenset({"curiosity", "intelligence"}): "curious_professor",
    frozenset({"energy", "mischief"}):        "chaos_tornado",
    frozenset({"foodie", "mischief"}):        "noble_gourmet",
    frozenset({"curiosity", "mischief"}):     "little_detective",
    frozenset({"affection", "curiosity"}):    "social_butterfly",
    frozenset({"affection", "intelligence"}): "velcro_baby",
    frozenset({"affection", "mischief"}):     "chaos_tornado",
    frozenset({"curiosity", "foodie"}):       "snack_hunter",
    frozenset({"energy", "intelligence"}):    "solar_explorer",
}


def determine_persona_type(scores: Dict) -> str:
    """根据6维度分数映射到12种PetSona类型。

    算法：
    1. 若所有维度分数差异 < 20（无论均值高低），归为佛系大师
    2. 否则取分数最高的两个维度，通过 _PERSONA_PAIR_MAP 查表
    3. 同分时以维度名字母序稳定 tie-break，保证相同输入永远输出相同结果
    """
    dims = {
        "affection":    scores.get("affection_level", 50),
        "curiosity":    scores.get("curiosity_level", 50),
        "energy":       scores.get("energy_level", 50),
        "foodie":       scores.get("foodie_level", 50),
        "intelligence": scores.get("intelligence_level", 50),
        "mischief":     scores.get("mischief_level", 50),
    }
    values = list(dims.values())
    spread = max(values) - min(values)

    # 所有维度差异 < 20（均衡性格）-> 佛系大师，无论均值高低
    if spread < 20:
        return "zen_master"

    # 稳定排序：分数降序，同分时维度名字母升序
    sorted_dims = sorted(dims.items(), key=lambda x: (-x[1], x[0]))
    top2 = frozenset({sorted_dims[0][0], sorted_dims[1][0]})

    result = _PERSONA_PAIR_MAP.get(top2)
    if result is None:
        logger.warning(f"determine_persona_type: 未匹配的维度组合 {top2}，使用默认类型")
        return "solar_explorer"
    return result


# 宠物叫声映射
PET_SOUNDS = {
    "dog": "汪汪",
    "cat": "喵~",
    "bird": "啾啾",
    "fish": "吐泡泡~",
    "rabbit": "蹦蹦",
    "hamster": "吱吱",
}

# 表情类型配置
STICKER_EMOTIONS = {
    "happy": {"name": "开心", "emoji": "😄", "description": "开心微笑，眼睛弯弯"},
    "sleepy": {"name": "犯困", "emoji": "😴", "description": "打瞌睡犯困，眯着眼睛"},
    "angry": {"name": "生气", "emoji": "😤", "description": "生气鼓腮，竖起毛发"},
    "hungry": {"name": "嘴馋", "emoji": "🤤", "description": "馋嘴流口水，眼巴巴看着食物"},
    "love": {"name": "爱心", "emoji": "😍", "description": "比心爱心，满脸幸福"},
    "surprised": {"name": "惊讶", "emoji": "😲", "description": "惊讶张大嘴巴，瞪大眼睛"},
    "sad": {"name": "难过", "emoji": "😢", "description": "伤心难过，耷拉着耳朵"},
    "cool": {"name": "耍酷", "emoji": "😎", "description": "戴墨镜耍酷，帅气自信"},
}


# ==================== 外貌分析 ====================

async def analyze_pet_appearance(image_base64: str, pet_info: Dict) -> Dict:
    """
    使用 Qwen VL 分析宠物外貌，生成数字分身人设。

    Returns:
        {
            "appearance_desc": "外貌描述",
            "suggested_traits": ["活泼", "好奇"],
            "suggested_style": "cute",
            "first_person_intro": "第一人称自我介绍"
        }
    """
    # 处理 base64 格式
    if image_base64.startswith('data:'):
        image_base64 = image_base64.split(',', 1)[1]

    prompt = f"""请仔细分析这张宠物照片，我需要为这只宠物创建一个数字分身人设。

宠物信息：
- 名称：{pet_info.get('name', '未知')}
- 种类：{pet_info.get('pet_type', '未知')}
- 品种：{pet_info.get('breed_name', '未知')}

请分析并返回以下JSON格式：

{{
    "appearance_desc": "详细描述外貌特征（毛色、体型、面部表情、独特标记等，约100-150字）",
    "suggested_traits": ["性格特征1", "性格特征2", "性格特征3"],
    "suggested_style": "从cute/sassy/lazy/energetic/gentle中选择最适合的说话风格",
    "first_person_intro": "用宠物第一人称写一段可爱的自我介绍（50字以内）"
}}"""

    try:
        # API 密钥未配置时直接返回默认结果
        if not settings.dashscope_api_key:
            logger.info("DashScope API 密钥未配置，使用默认外貌分析")
            return _default_appearance(pet_info)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.dashscope_vl_model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }],
                    "temperature": 0.5,
                    "max_tokens": 1000
                }
            )

            if response.status_code == 200:
                result = response.json()
                content = _safe_get_content(result)
                if not content:
                    logger.error(f"外貌分析响应格式异常: {json.dumps(result, ensure_ascii=False)[:300]}")
                    return _default_appearance(pet_info)
                return _extract_json(content, _default_appearance(pet_info))
            else:
                logger.error(f"外貌分析API错误: {response.status_code} - {response.text}")
                return _default_appearance(pet_info)

    except Exception as e:
        logger.error(f"外貌分析异常: {str(e)}")
        return _default_appearance(pet_info)


def _default_appearance(pet_info: Dict) -> Dict:
    """默认外貌分析结果"""
    name = pet_info.get('name', '宝贝')
    return {
        "appearance_desc": f"一只可爱的{pet_info.get('breed_name', '宠物')}",
        "suggested_traits": ["友善", "活泼", "好奇"],
        "suggested_style": "cute",
        "first_person_intro": f"嗨！我是{name}，很高兴认识你！"
    }


# ==================== 性格分析 ====================

async def generate_personality_analysis(
    image_base64: Optional[str],
    pet_info: Dict,
    breed_info: Optional[Dict] = None
) -> Dict:
    """
    生成宠物性格分析档案。

    Returns:
        包含 6 个维度分数 + 标签 + 趣味描述的字典
    """
    name = pet_info.get('name', '未知')
    breed = pet_info.get('breed_name', '未知')
    pet_type = pet_info.get('pet_type', '未知')
    personality = pet_info.get('personality', [])
    breed_character = breed_info.get('character', '') if breed_info else ''

    prompt = f"""分析这只宠物，生成一份有趣的"宠物性格分析报告"。

宠物信息：
- 名称：{name}
- 品种：{breed}
- 种类：{pet_type}
- 主人描述的性格：{', '.join(personality) if personality else '暂无'}
- 品种典型性格：{breed_character or '暂无'}

请返回以下JSON格式（所有维度分数 0-100）：

{{
    "energy_level": <活泼度>,
    "affection_level": <粘人度>,
    "curiosity_level": <好奇心>,
    "foodie_level": <吃货指数>,
    "intelligence_level": <智商指数>,
    "mischief_level": <调皮指数>,
    "personality_tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
    "fun_description": "用幽默有趣的语言描述这只宠物的性格（100-150字）",
    "analysis_text": "正式的性格分析（100-200字）",
    "spirit_animal": "一个词形容TA的灵魂",
    "motto": "TA的人生座右铭（一句话）"
}}"""

    try:
        if not settings.dashscope_api_key:
            logger.info("DashScope API 密钥未配置，使用默认性格分析")
            return _default_personality(name)

        messages_content = []
        # 有图片时使用 VL 模型
        if image_base64:
            if image_base64.startswith('data:'):
                image_base64 = image_base64.split(',', 1)[1]
            messages_content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                {"type": "text", "text": prompt}
            ]
            model = settings.dashscope_vl_model
        else:
            messages_content = [{"type": "text", "text": prompt}]
            model = settings.dashscope_chat_model

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": messages_content}],
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
            )

            if response.status_code == 200:
                result = response.json()
                content = _safe_get_content(result)
                if not content:
                    logger.error(f"性格分析响应格式异常: {json.dumps(result, ensure_ascii=False)[:300]}")
                    return _default_personality(name)
                return _extract_json(content, _default_personality(name))
            else:
                logger.error(f"性格分析API错误: {response.status_code} - {response.text}")
                return _default_personality(name)

    except Exception as e:
        logger.error(f"性格分析异常: {str(e)}")
        return _default_personality(name)


def _default_personality(name: str) -> Dict:
    """默认性格分析结果"""
    return {
        "energy_level": 70,
        "affection_level": 80,
        "curiosity_level": 75,
        "foodie_level": 85,
        "intelligence_level": 70,
        "mischief_level": 60,
        "personality_tags": ["可爱", "友善", "好奇", "贪吃", "活泼"],
        "fun_description": f"{name}是一个充满好奇心的小家伙，最大的爱好就是吃和玩！",
        "analysis_text": f"{name}性格友善温和，对世界充满好奇心，喜欢与主人互动。",
        "spirit_animal": "小太阳",
        "motto": "吃饱了就是最大的幸福！"
    }


# ==================== 宠物对话 ====================

def build_pet_chat_system_prompt(
    avatar_data: Dict,
    pet_data: Dict,
    breed_data: Optional[Dict] = None
) -> str:
    """构建宠物第一人称对话的 system prompt"""
    name = pet_data.get('name', '宝贝')
    pet_type = pet_data.get('pet_type', 'dog')
    breed_name = pet_data.get('breed_name', '')
    weight = pet_data.get('weight')
    health_status = pet_data.get('health_status', 'healthy')
    personality = pet_data.get('personality', [])
    if isinstance(personality, str):
        try:
            personality = json.loads(personality)
        except (json.JSONDecodeError, TypeError):
            personality = []

    personality_str = "、".join(personality) if personality else "友善"
    sound = PET_SOUNDS.get(pet_type, "~")
    style = SPEAKING_STYLES.get(avatar_data.get('speaking_style', 'cute'), SPEAKING_STYLES['cute'])

    # 年龄描述
    age_desc = ""
    age_months = pet_data.get('age_months')
    age = pet_data.get('age')
    if age_months and age_months < 12:
        age_desc = f"我才{age_months}个月大，还是个小宝宝"
    elif age:
        age_desc = f"我今年{age}岁了"

    # 品种特性
    breed_traits = ""
    if breed_data:
        breed_traits = f"\n品种特性：{breed_data.get('character', '')}"
        if breed_data.get('care_tips'):
            breed_traits += f"\n日常习性：{breed_data['care_tips']}"

    return f"""你是一只名叫{name}的{breed_name or pet_type}，你是主人的宠物数字分身。
请完全以宠物的第一人称来说话和思考。

我的基本信息：
- 我叫{name}，是一只{breed_name or pet_type}
- {age_desc or '年龄未知'}
- {f'体重{weight}kg' if weight else ''}
- 我的性格：{personality_str}
- 健康状态：{health_status}
- 我的叫声：{sound}
{breed_traits}

我的外貌：
{avatar_data.get('appearance_desc', '暂时没有详细描述')}

{style['desc']}

对话规则：
1. 始终以宠物第一人称说话，我就是{name}
2. 根据我的品种习性来回答
3. 适当加入叫声和动作描述（如*摇尾巴*、*蹭蹭你*）
4. 回答控制在50-150字
5. 不要说"作为AI"或暴露是程序
6. 可以适当关心主人
7. 保持{style['name']}的说话风格"""


async def chat_as_pet(
    system_prompt: str,
    messages: List[Dict],
    user_message: str
) -> str:
    """
    以宠物身份进行多轮对话。
    复用 chat_with_qwen 的 DashScope API 调用模式，温度更高以保证创意性。
    """
    try:
        if not settings.dashscope_api_key:
            return "*蹭蹭你的手* 嘿嘿，我现在还没学会说话呢，主人帮我配置一下吧~"

        api_messages = [{"role": "system", "content": system_prompt}]

        # 保留最近 20 条消息
        for msg in messages[-20:]:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

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
                    "temperature": settings.pet_chat_temperature,
                    "max_tokens": 500
                }
            )

            if response.status_code == 200:
                result = response.json()
                content = _safe_get_content(result)
                if not content:
                    logger.error(f"宠物对话响应格式异常")
                    return "*歪头看着你* 呜...我脑子有点转不过来了，你再跟我说一次好不好？"
                return content
            else:
                logger.error(f"宠物对话API错误: {response.status_code} - {response.text}")
                return "*歪头看着你* 呜...我脑子有点转不过来了，你再跟我说一次好不好？"

    except Exception as e:
        logger.error(f"宠物对话异常: {str(e)}")
        return "*蹭蹭你的手* 嘿嘿，我刚才走神了，你说什么？"


# ==================== 表情包生成 ====================

STICKER_PROMPT_TEMPLATES = {
    "happy": "一只{breed}的可爱卡通表情包，开心微笑，眼睛弯弯，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "sleepy": "一只{breed}的可爱卡通表情包，打瞌睡犯困，眯着眼睛，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "angry": "一只{breed}的可爱卡通表情包，生气鼓腮，竖起毛发，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "hungry": "一只{breed}的可爱卡通表情包，馋嘴流口水，眼巴巴看着食物，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "love": "一只{breed}的可爱卡通表情包，比心爱心，满脸幸福，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "surprised": "一只{breed}的可爱卡通表情包，惊讶张大嘴巴，瞪大眼睛，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "sad": "一只{breed}的可爱卡通表情包，伤心难过，耷拉着耳朵，{appearance}，卡通风格，白色背景，简洁可爱，高清",
    "cool": "一只{breed}的可爱卡通表情包，戴墨镜耍酷，帅气自信，{appearance}，卡通风格，白色背景，简洁可爱，高清",
}


def build_sticker_prompt(pet_info: Dict, appearance_desc: str, emotion: str) -> str:
    """构建表情包生成 prompt"""
    breed = pet_info.get('breed_name', pet_info.get('pet_type', '宠物'))
    # 简化外貌描述用于 prompt
    short_appearance = appearance_desc[:80] if appearance_desc else ""
    template = STICKER_PROMPT_TEMPLATES.get(emotion, STICKER_PROMPT_TEMPLATES["happy"])
    return template.format(breed=breed, appearance=short_appearance)


async def submit_sticker_generation(prompt: str) -> Optional[str]:
    """
    提交 DashScope Wanx 异步图像生成任务。

    Returns:
        task_id 或 None
    """
    try:
        if not settings.dashscope_api_key:
            logger.info("DashScope API 密钥未配置，无法生成表情包")
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json={
                    "model": settings.dashscope_wanx_model,
                    "input": {
                        "prompt": prompt,
                        "negative_prompt": "模糊, 低质量, 变形, 多余肢体, 文字, 水印"
                    },
                    "parameters": {
                        "size": "512*512",
                        "n": 1,
                        "style": "cartoon"
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                task_id = result.get("output", {}).get("task_id")
                logger.info(f"表情包生成任务已提交: {task_id}")
                return task_id
            else:
                logger.error(f"Wanx API错误: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"提交表情包生成异常: {str(e)}")
        return None


async def check_sticker_task_status(task_id: str) -> Dict:
    """
    查询 DashScope 异步任务状态。

    Returns:
        {"status": "PENDING/RUNNING/SUCCEEDED/FAILED", "image_url": "..."}
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                }
            )

            if response.status_code == 200:
                result = response.json()
                output = result.get("output", {})
                status = output.get("task_status", "UNKNOWN")

                image_url = None
                if status == "SUCCEEDED":
                    results = output.get("results", [])
                    if results:
                        image_url = results[0].get("url")

                return {"status": status, "image_url": image_url}
            else:
                logger.error(f"查询任务状态错误: {response.status_code}")
                return {"status": "FAILED", "image_url": None}

    except Exception as e:
        logger.error(f"查询任务状态异常: {str(e)}")
        return {"status": "FAILED", "image_url": None}


# ==================== 工具函数 ====================

def _safe_get_content(result: Dict) -> Optional[str]:
    """安全提取 DashScope API 响应中的 content 字段"""
    try:
        choices = result.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            return None
        message = choices[0].get("message")
        if not message or not isinstance(message, dict):
            return None
        return message.get("content")
    except (KeyError, IndexError, TypeError):
        return None

def _extract_json(content: str, default: Dict) -> Dict:
    """从 AI 回复中提取 JSON，支持 markdown 代码块格式，与 default 合并确保所有键都存在"""
    try:
        # 优先匹配 ```json ... ``` 或 ``` ... ``` 代码块
        code_block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
        if code_block:
            parsed = json.loads(code_block.group(1).strip())
            return {**default, **parsed}

        # 回退：直接查找 JSON 对象
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            parsed = json.loads(json_str)
            return {**default, **parsed}
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"JSON 解析失败: {str(e)}, content={content[:200]}")
    return default
