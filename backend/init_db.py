"""
PetPal - 数据库初始化脚本
创建所有表并填充初始数据
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text


def create_tables_sqlite(engine):
    """使用原始SQL创建SQLite表（支持AUTOINCREMENT）"""
    print("正在创建数据库表...")

    import sqlite3

    # 直接使用sqlite3连接
    db_path = str(engine.url).replace("sqlite:///", "")
    if db_path.startswith("./"):
        import os
        db_path = os.path.join(os.path.dirname(__file__), db_path[2:])

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 定义表创建语句列表
    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone VARCHAR(20) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            nickname VARCHAR(100),
            avatar_url VARCHAR(500),
            gender INTEGER DEFAULT 0,
            birthday DATE,
            bio TEXT,
            member_level INTEGER DEFAULT 0,
            member_expire_at DATETIME,
            points INTEGER DEFAULT 0,
            followers_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            posts_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            role VARCHAR(20) DEFAULT 'user',
            last_login_at DATETIME,
            last_login_ip VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS pet_breeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_type VARCHAR(20) NOT NULL,
            name VARCHAR(100) NOT NULL,
            name_en VARCHAR(100),
            description TEXT,
            origin VARCHAR(100),
            life_span VARCHAR(50),
            weight_range VARCHAR(50),
            character TEXT,
            care_tips TEXT,
            common_diseases TEXT,
            diet_tips TEXT,
            exercise_needs VARCHAR(20),
            grooming_needs VARCHAR(20),
            image_url VARCHAR(500),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            breed_id INTEGER,
            name VARCHAR(100) NOT NULL,
            pet_type VARCHAR(20) NOT NULL,
            breed_name VARCHAR(100),
            avatar_url VARCHAR(500),
            gender INTEGER DEFAULT 0,
            birthday DATE,
            adoption_date DATE,
            weight REAL,
            is_neutered INTEGER DEFAULT 0,
            health_status VARCHAR(20) DEFAULT 'healthy',
            allergies TEXT,
            medical_history TEXT,
            vaccination_records TEXT,
            personality TEXT,
            posts_count INTEGER DEFAULT 0,
            fans_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            pet_id INTEGER,
            content_type VARCHAR(20) DEFAULT 'image',
            title VARCHAR(200),
            content TEXT,
            media_urls TEXT,
            cover_url VARCHAR(500),
            video_duration INTEGER,
            tags TEXT,
            topics TEXT,
            product_ids TEXT,
            location VARCHAR(200),
            latitude VARCHAR(20),
            longitude VARCHAR(20),
            views_count INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            shares_count INTEGER DEFAULT 0,
            collects_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            is_top INTEGER DEFAULT 0,
            is_hot INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            parent_id INTEGER,
            reply_to_user_id INTEGER,
            content TEXT NOT NULL,
            image_url VARCHAR(500),
            likes_count INTEGER DEFAULT 0,
            replies_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_type VARCHAR(20) NOT NULL,
            target_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            conversation_id VARCHAR(50) NOT NULL,
            message_type VARCHAR(20) DEFAULT 'text',
            content TEXT,
            media_url VARCHAR(500),
            is_read INTEGER DEFAULT 0,
            read_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS health_diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            diagnosis_type VARCHAR(20) NOT NULL,
            image_url TEXT,
            symptom_desc TEXT,
            health_score INTEGER,
            risk_level VARCHAR(20),
            ai_analysis TEXT,
            suggestions TEXT,
            ai_model VARCHAR(50) DEFAULT 'qwen-vl-max',
            confidence REAL,
            status VARCHAR(20) DEFAULT 'completed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS diagnosis_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis_id INTEGER NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            record_type VARCHAR(50) NOT NULL,
            health_score INTEGER,
            risk_level VARCHAR(20),
            analysis_result TEXT,
            suggestions TEXT,
            title VARCHAR(200),
            content TEXT,
            images TEXT,
            weight REAL,
            temperature REAL,
            vaccine_name VARCHAR(100),
            next_date DATETIME,
            record_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS health_consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pet_id INTEGER,
            consultation_type VARCHAR(20) DEFAULT 'ai',
            title VARCHAR(200),
            symptoms TEXT,
            symptom_duration VARCHAR(100),
            images TEXT,
            videos TEXT,
            ai_diagnosis TEXT,
            ai_suggestions TEXT,
            confidence_score REAL,
            possible_diseases TEXT,
            urgency_level VARCHAR(20),
            expert_id INTEGER,
            expert_reply TEXT,
            expert_reply_at DATETIME,
            messages TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            is_paid INTEGER DEFAULT 0,
            price REAL DEFAULT 0,
            rating INTEGER,
            feedback TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS consultation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id INTEGER NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            image_urls TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            subtitle VARCHAR(500),
            description TEXT,
            images TEXT,
            video_url VARCHAR(500),
            category VARCHAR(100),
            category_name VARCHAR(100),
            cover_image VARCHAR(500),
            pet_type VARCHAR(50),
            brand VARCHAR(100),
            original_price REAL NOT NULL,
            price REAL NOT NULL,
            points_price INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0,
            sales_count INTEGER DEFAULT 0,
            specs TEXT,
            skus TEXT,
            views_count INTEGER DEFAULT 0,
            favorites_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 5.0,
            review_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            is_recommended INTEGER DEFAULT 0,
            is_hot INTEGER DEFAULT 0,
            is_new INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no VARCHAR(50) UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            points_amount REAL DEFAULT 0,
            freight_amount REAL DEFAULT 0,
            pay_amount REAL NOT NULL,
            points_used INTEGER DEFAULT 0,
            points_earned INTEGER DEFAULT 0,
            address_id INTEGER,
            receiver_name VARCHAR(50),
            receiver_phone VARCHAR(20),
            receiver_address VARCHAR(500),
            pay_method VARCHAR(20),
            pay_type VARCHAR(20),
            pay_time DATETIME,
            paid_at DATETIME,
            pay_trade_no VARCHAR(100),
            ship_company VARCHAR(50),
            ship_no VARCHAR(50),
            ship_time DATETIME,
            receive_time DATETIME,
            cancelled_at DATETIME,
            completed_at DATETIME,
            status VARCHAR(20) DEFAULT 'pending',
            remark VARCHAR(500),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name VARCHAR(200) NOT NULL,
            product_image VARCHAR(500),
            sku_info VARCHAR(500),
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            amount REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS points_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            balance INTEGER NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            source_id INTEGER,
            description VARCHAR(500),
            expire_at DATETIME,
            is_expired INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS points_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            image VARCHAR(500),
            points_price INTEGER NOT NULL,
            original_value REAL,
            product_type VARCHAR(50) NOT NULL,
            coupon_value REAL,
            coupon_min_amount REAL,
            stock INTEGER DEFAULT 0,
            exchange_count INTEGER DEFAULT 0,
            limit_per_user INTEGER DEFAULT 0,
            member_level_required INTEGER DEFAULT 0,
            exchange_limit INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            category VARCHAR(50),
            status INTEGER DEFAULT 1,
            is_hot INTEGER DEFAULT 0,
            start_time DATETIME,
            end_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS points_exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name VARCHAR(200) NOT NULL,
            points_cost INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            address_id INTEGER,
            receiver_name VARCHAR(50),
            receiver_phone VARCHAR(20),
            receiver_address VARCHAR(500),
            coupon_code VARCHAR(50),
            coupon_expire_at DATETIME,
            status VARCHAR(20) DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            cover_image VARCHAR(500),
            images TEXT,
            activity_type VARCHAR(50) NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            location_name VARCHAR(200),
            location_address VARCHAR(500),
            latitude VARCHAR(20),
            longitude VARCHAR(20),
            max_participants INTEGER DEFAULT 0,
            current_participants INTEGER DEFAULT 0,
            fee REAL DEFAULT 0,
            pet_types TEXT,
            pet_required INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'upcoming',
            views_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS activity_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            pet_id INTEGER,
            status VARCHAR(20) DEFAULT 'registered',
            check_in_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    ]

    # 执行每个表创建语句
    for sql in tables:
        try:
            cursor.execute(sql)
        except Exception as e:
            print(f"Warning creating table: {e}")

    conn.commit()
    conn.close()

    print("数据库表创建完成！")


def init_pet_breeds(db):
    """初始化宠物品种数据"""
    from sqlalchemy import text

    # 检查是否已有数据
    result = db.execute(text("SELECT COUNT(*) FROM pet_breeds")).scalar()
    if result > 0:
        print("宠物品种数据已存在，跳过初始化")
        return

    print("正在初始化宠物品种数据...")

    breeds = [
        # 狗狗品种
        ("dog", "金毛寻回犬", "Golden Retriever", "英国", "10-12年", "25-34kg", "温顺、友善、聪明", "high", "medium"),
        ("dog", "拉布拉多", "Labrador Retriever", "加拿大", "10-12年", "25-36kg", "友善、活泼、忠诚", "high", "low"),
        ("dog", "柯基", "Corgi", "英国威尔士", "12-15年", "10-14kg", "活泼、聪明、勇敢", "medium", "medium"),
        ("dog", "泰迪", "Poodle", "法国/德国", "12-15年", "3-32kg", "聪明、活泼、易训练", "medium", "high"),
        ("dog", "哈士奇", "Siberian Husky", "俄罗斯西伯利亚", "12-15年", "16-27kg", "活泼、友善、独立", "high", "medium"),
        ("dog", "柴犬", "Shiba Inu", "日本", "12-15年", "8-11kg", "忠诚、机警、活泼", "medium", "medium"),
        ("dog", "边境牧羊犬", "Border Collie", "英国", "12-15年", "14-20kg", "聪明、敏捷、顺从", "high", "medium"),
        ("dog", "法国斗牛犬", "French Bulldog", "法国", "10-12年", "8-14kg", "友善、活泼、顽皮", "low", "low"),
        ("dog", "德国牧羊犬", "German Shepherd", "德国", "10-13年", "22-40kg", "忠诚、勇敢、聪明", "high", "medium"),
        ("dog", "萨摩耶", "Samoyed", "俄罗斯", "12-14年", "16-30kg", "友善、温柔、活泼", "high", "high"),
        ("dog", "博美", "Pomeranian", "德国", "12-16年", "1.4-3.2kg", "活泼、聪明、勇敢", "low", "high"),
        ("dog", "比熊", "Bichon Frise", "法国/比利时", "12-15年", "3-5kg", "友善、活泼、温顺", "low", "high"),
        # 猫咪品种
        ("cat", "英国短毛猫", "British Shorthair", "英国", "12-20年", "4-8kg", "温顺、安静、亲人", "low", "low"),
        ("cat", "美国短毛猫", "American Shorthair", "美国", "15-20年", "3.5-7kg", "温和、活泼、聪明", "medium", "low"),
        ("cat", "布偶猫", "Ragdoll", "美国", "12-17年", "4.5-9kg", "温顺、粘人、安静", "low", "medium"),
        ("cat", "波斯猫", "Persian", "伊朗", "12-17年", "3.2-6.8kg", "温顺、安静、优雅", "low", "high"),
        ("cat", "暹罗猫", "Siamese", "泰国", "12-15年", "2.5-5.5kg", "活泼、聪明、好奇", "medium", "low"),
        ("cat", "缅因猫", "Maine Coon", "美国", "12-15年", "5.5-11kg", "温顺、聪明、友善", "medium", "medium"),
        ("cat", "俄罗斯蓝猫", "Russian Blue", "俄罗斯", "15-20年", "3-5.5kg", "安静、害羞、温柔", "low", "low"),
        ("cat", "苏格兰折耳猫", "Scottish Fold", "英国苏格兰", "11-14年", "2.7-6kg", "温顺、安静、粘人", "low", "low"),
        ("cat", "加菲猫", "Exotic Shorthair", "美国", "12-15年", "3-6kg", "温顺、安静、亲人", "low", "low"),
        ("cat", "孟加拉猫", "Bengal", "美国", "12-16年", "3.6-6.8kg", "活泼、聪明、好动", "high", "low"),
        ("cat", "中华田园猫", "Chinese Li Hua", "中国", "12-20年", "3-6kg", "独立、聪明、适应力强", "medium", "low"),
        ("cat", "橘猫", "Orange Tabby", "中国", "12-18年", "4-8kg", "亲人、活泼、贪吃", "medium", "low"),
    ]

    sql = text("""
        INSERT INTO pet_breeds (pet_type, name, name_en, origin, life_span, weight_range, character, exercise_needs, grooming_needs)
        VALUES (:pet_type, :name, :name_en, :origin, :life_span, :weight_range, :character, :exercise_needs, :grooming_needs)
    """)

    for breed_data in breeds:
        db.execute(sql, {
            "pet_type": breed_data[0],
            "name": breed_data[1],
            "name_en": breed_data[2],
            "origin": breed_data[3],
            "life_span": breed_data[4],
            "weight_range": breed_data[5],
            "character": breed_data[6],
            "exercise_needs": breed_data[7],
            "grooming_needs": breed_data[8]
        })

    db.commit()
    print(f"成功添加 {len(breeds)} 个宠物品种")


def init_points_products(db):
    """初始化积分商品数据"""
    from sqlalchemy import text

    result = db.execute(text("SELECT COUNT(*) FROM points_products")).scalar()
    if result > 0:
        print("积分商品数据已存在，跳过初始化")
        return

    print("正在初始化积分商品数据...")

    products = [
        ("5元商城优惠券", "满50可用", 100, "coupon", 5.0, 50.0, 999, 0),
        ("10元商城优惠券", "满100可用", 180, "coupon", 10.0, 100.0, 999, 0),
        ("宠物小零食", "精选优质零食一份", 500, "physical", None, None, 100, 0),
        ("宠物玩具球", "耐咬磨牙玩具", 300, "physical", None, None, 200, 0),
        ("VIP会员体验7天", "体验会员专属权益", 200, "virtual", None, None, 999, 1),
    ]

    sql = text("""
        INSERT INTO points_products (name, description, points_price, product_type, coupon_value, coupon_min_amount, stock, is_hot)
        VALUES (:name, :desc, :points, :type, :cv, :cmin, :stock, :hot)
    """)

    for p in products:
        db.execute(sql, {
            "name": p[0], "desc": p[1], "points": p[2], "type": p[3],
            "cv": p[4], "cmin": p[5], "stock": p[6], "hot": p[7]
        })

    db.commit()
    print(f"成功添加 {len(products)} 个积分商品")


def init_shop_products(db):
    """初始化商城商品数据"""
    from sqlalchemy import text

    result = db.execute(text("SELECT COUNT(*) FROM products")).scalar()
    if result > 0:
        print("商城商品数据已存在，跳过初始化")
        return

    print("正在初始化商城商品数据...")

    # 先创建一个测试商家用户
    db.execute(text("""
        INSERT INTO users (phone, nickname, avatar_url, role)
        VALUES ('13800000001', 'PetPal官方店', 'https://img.yzcdn.cn/vant/cat.jpeg', 'merchant')
    """))
    db.commit()

    # 获取商家ID
    merchant_id = db.execute(text("SELECT id FROM users WHERE phone='13800000001'")).scalar()

    products = [
        # (name, subtitle, description, category, price, original_price, stock, is_hot, is_new, is_recommended)
        ("皇家狗粮成犬通用型", "添加益生菌 易消化", "皇家(ROYAL CANIN)狗粮 小型犬成犬粮 2KG装，添加益生菌，呵护肠道健康", "food", 128.00, 158.00, 100, 1, 0, 1),
        ("猫砂豆腐砂除臭", "6L大容量 结团快", "原味豆腐猫砂6L，除臭结团好，可冲厕所，环保猫砂", "supplies", 29.90, 49.90, 200, 1, 1, 1),
        ("宠物自动饮水机", "循环过滤 新鲜水源", "智能宠物饮水机，2.5L大容量，循环过滤，保持水质新鲜", "supplies", 89.00, 129.00, 50, 0, 1, 1),
        ("狗狗牵引绳套装", "舒适胸背带设计", "宠物牵引绳套装，可调节胸背带，反光设计，夜间更安全", "accessories", 35.00, 55.00, 150, 0, 0, 0),
        ("猫爬架四层豪华款", "剑麻柱 多层平台", "大型猫爬架，剑麻磨爪柱，多层平台，猫窝猫抓板一体", "furniture", 299.00, 399.00, 30, 0, 1, 1),
        ("宠物驱虫药体外", "福来恩滴剂", "福来恩体外驱虫滴剂，适用于小型犬，一支有效期一个月", "health", 68.00, 88.00, 80, 1, 0, 1),
        ("冻干猫零食鸡胸肉", "高蛋白低脂肪", "冻干鸡胸肉猫零食，100%纯肉，无添加，高蛋白营养", "snacks", 25.00, 35.00, 300, 1, 0, 0),
        ("狗狗玩具球发声", "耐咬不伤牙", "宠物发声玩具球，天然橡胶，耐咬磨牙，互动解闷", "toys", 15.00, 25.00, 200, 0, 0, 0),
        ("猫罐头湿粮金枪鱼", "进口原料 营养丰富", "泰国进口猫罐头，金枪鱼口味，80g*6罐装", "food", 45.00, 60.00, 150, 0, 1, 0),
        ("宠物沐浴露犬用", "温和不刺激", "宠物专用沐浴露，温和配方，去污除臭，毛发顺滑", "grooming", 39.00, 59.00, 100, 0, 0, 0),
    ]

    sql = text("""
        INSERT INTO products (merchant_id, name, subtitle, description, category, category_name, price, original_price, stock, is_hot, is_new, is_recommended, status)
        VALUES (:merchant_id, :name, :subtitle, :desc, :cat, :cat_name, :price, :orig_price, :stock, :hot, :new, :rec, 1)
    """)

    category_names = {
        "food": "宠物食品",
        "supplies": "宠物用品",
        "accessories": "配件饰品",
        "furniture": "宠物家具",
        "health": "健康护理",
        "snacks": "零食奖励",
        "toys": "玩具互动",
        "grooming": "美容清洁"
    }

    for p in products:
        db.execute(sql, {
            "merchant_id": merchant_id,
            "name": p[0], "subtitle": p[1], "desc": p[2],
            "cat": p[3], "cat_name": category_names.get(p[3], p[3]),
            "price": p[4], "orig_price": p[5], "stock": p[6],
            "hot": p[7], "new": p[8], "rec": p[9]
        })

    db.commit()
    print(f"成功添加 {len(products)} 个商城商品")


def main():
    """主函数"""
    from app.database import engine, SessionLocal
    from app.config import settings

    print("=" * 50)
    print("PetPal 数据库初始化")
    print("=" * 50)

    # 创建表
    if settings.database_url.startswith("sqlite"):
        create_tables_sqlite(engine)
    else:
        from app.database import Base
        Base.metadata.create_all(bind=engine)
        print("数据库表创建完成！")

    # 初始化数据
    db = SessionLocal()
    try:
        init_pet_breeds(db)
        init_points_products(db)
        init_shop_products(db)
        print("=" * 50)
        print("数据库初始化完成！")
        print("=" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
