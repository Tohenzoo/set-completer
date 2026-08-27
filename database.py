import sqlite3
import os

def get_app_dir():
    # Находим системную папку AppData/Local (или домашнюю папку на Mac/Linux)
    base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    app_dir = os.path.join(base_dir, "SetCompleter")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

# Путь до базы данных теперь в скрытой системной папке
DB_NAME = os.path.join(get_app_dir(), "completer.db")

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sets (
                set_num TEXT PRIMARY KEY,
                name TEXT,
                year INTEGER,
                num_parts INTEGER,
                status TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS set_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_num TEXT,
                part_num TEXT,
                color_id INTEGER,
                color_name TEXT,
                color_rgb TEXT,
                part_name TEXT,
                part_img_url TEXT,
                quantity_needed INTEGER,
                quantity_found INTEGER DEFAULT 0,
                quantity_missing INTEGER DEFAULT 0,
                is_spare BOOLEAN DEFAULT 0,
                FOREIGN KEY(set_num) REFERENCES sets(set_num)
            )
        ''')
        conn.commit()

def get_all_sets():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT set_num, name, year, num_parts, status FROM sets")
        return cursor.fetchall()

def get_set_parts(set_num):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, part_num, color_id, color_name, color_rgb, part_name, part_img_url, 
                   quantity_needed, quantity_found, quantity_missing, is_spare
            FROM set_parts
            WHERE set_num = ?
            ORDER BY is_spare ASC, color_name ASC, part_name ASC
        """, (set_num,))
        return cursor.fetchall()

def update_part_status(part_id, found, missing):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE set_parts
            SET quantity_found = ?, quantity_missing = ?
            WHERE id = ?
        """, (found, missing, part_id))
        conn.commit()

def get_colors_for_sets(set_nums):
    if not set_nums:
        return []
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(set_nums))
        cursor.execute(f"""
            SELECT DISTINCT color_id, color_name
            FROM set_parts
            WHERE set_num IN ({placeholders}) AND is_spare = 0
            ORDER BY color_name
        """, set_nums)
        return cursor.fetchall()

def get_aggregated_parts(set_nums, color_id=None):
    if not set_nums:
        return []
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(set_nums))
        
        query = f"""
            SELECT 
                part_num, color_id, color_name, color_rgb, part_name, part_img_url,
                SUM(quantity_needed) as total_req,
                SUM(quantity_found) as total_fnd,
                SUM(quantity_missing) as total_mis,
                GROUP_CONCAT(set_num || ':' || quantity_needed || ':' || quantity_found, '; ') as breakdown
            FROM set_parts
            WHERE set_num IN ({placeholders}) AND is_spare = 0
        """
        params = list(set_nums)
        
        if color_id is not None:
            query += " AND color_id = ?"
            params.append(color_id)
            
        query += " GROUP BY part_num, color_id ORDER BY color_name ASC, part_name ASC"
        
        cursor.execute(query, params)
        return cursor.fetchall()

def get_missing_parts_for_export(set_nums=None):
    """Возвращает список недостающих деталей (для одного набора или списка)"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        if isinstance(set_nums, str):
            cursor.execute("""
                SELECT part_num, color_id, quantity_missing
                FROM set_parts
                WHERE set_num = ? AND quantity_missing > 0
            """, (set_nums,))
            
        elif isinstance(set_nums, (list, tuple)) and set_nums:
            placeholders = ",".join(["?"] * len(set_nums))
            cursor.execute(f"""
                SELECT part_num, color_id, SUM(quantity_missing)
                FROM set_parts
                WHERE set_num IN ({placeholders}) AND quantity_missing > 0
                GROUP BY part_num, color_id
            """, set_nums)
            
        else:
            cursor.execute("""
                SELECT part_num, color_id, SUM(quantity_missing)
                FROM set_parts
                WHERE quantity_missing > 0
                GROUP BY part_num, color_id
            """)
        return cursor.fetchall()

def delete_set(set_num):
    """Удаляет набор и все его детали из базы данных."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sets WHERE set_num = ?", (set_num,))
        cursor.execute("DELETE FROM set_parts WHERE set_num = ?", (set_num,))
        conn.commit()

def get_set_progress(set_num):
    """Считает общее количество требуемых и найденных деталей для набора (без экстра-деталей)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(quantity_needed), 0),
                COALESCE(SUM(quantity_found), 0)
            FROM set_parts
            WHERE set_num = ? AND is_spare = 0
        """, (set_num,))
        needed, found = cursor.fetchone()
        return needed, found

def increment_part_for_set(set_num, part_num, color_id, delta=1):
    """Увеличивает или уменьшает quantity_found для конкретной детали в конкретном наборе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, quantity_needed, quantity_found, quantity_missing
            FROM set_parts
            WHERE set_num = ? AND part_num = ? AND color_id = ? AND is_spare = 0
        """, (set_num, part_num, color_id))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        p_id, req, found, missing = row
        new_found = max(0, min(req, found + delta))
        new_missing = max(0, req - new_found) if missing > 0 else 0
        
        cursor.execute("""
            UPDATE set_parts
            SET quantity_found = ?, quantity_missing = ?
            WHERE id = ?
        """, (new_found, new_missing, p_id))
        conn.commit()
        return new_found, req

def save_set(set_num, name, year, num_parts, parts):
    """
    Сохраняет информацию о наборе и его деталях в базу данных.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # 1. Сохраняем или обновляем сам набор
        cursor.execute('''
            INSERT OR REPLACE INTO sets (set_num, name, year, num_parts, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (set_num, name, year, num_parts, "Active"))
        
        # 2. Очищаем старые детали этого набора (если мы его перезаписываем)
        cursor.execute("DELETE FROM set_parts WHERE set_num = ?", (set_num,))
        
        # 3. Сохраняем новые детали
        for p in parts:
            cursor.execute('''
                INSERT INTO set_parts (
                    set_num, part_num, color_id, color_name, color_rgb, 
                    part_name, part_img_url, quantity_needed, is_spare
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (set_num, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]))
        
        conn.commit()