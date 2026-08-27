import requests
from database import save_set

API_KEY = "d821a6c603b0ca782d321eaf80b52c0b"
BASE_URL = "https://rebrickable.com/api/v3/lego"

def search_sets(query):
    """
    Ищет наборы по названию, артикулу ИЛИ названию серии (темы),
    исключая объекты без деталей (мукулатуру, часы, постеры и т.д.).
    """
    all_results = []
    seen_set_nums = set()

    # 1. Прямой поиск по названию или артикулу
    try:
        res = requests.get(
            f"{BASE_URL}/sets/", 
            params={"search": query, "key": API_KEY, "page_size": 50}, 
            timeout=10
        )
        if res.status_code == 200:
            for s in res.json().get("results", []):
                # Добавляем только если в наборе есть детали (> 0)
                if s.get("num_parts", 0) > 0 and s["set_num"] not in seen_set_nums:
                    all_results.append(s)
                    seen_set_nums.add(s["set_num"])
    except Exception as e:
        print(f"Ошибка поиска по названию: {e}")

    # 2. Умный поиск по названию серии (темы)
    try:
        themes_res = requests.get(
            f"{BASE_URL}/themes/", 
            params={"page_size": 1000, "key": API_KEY}, 
            timeout=10
        )
        if themes_res.status_code == 200:
            themes_data = themes_res.json().get("results", [])
            
            query_lower = query.lower()
            matched_theme = None
            for t in themes_data:
                if query_lower in t["name"].lower():
                    matched_theme = t
                    break
            
            if matched_theme:
                theme_id = matched_theme["id"]
                theme_sets_res = requests.get(
                    f"{BASE_URL}/sets/", 
                    params={"theme_id": theme_id, "key": API_KEY, "page_size": 100}, 
                    timeout=10
                )
                
                if theme_sets_res.status_code == 200:
                    for s in theme_sets_res.json().get("results", []):
                        # Также фильтруем по наличию деталей
                        if s.get("num_parts", 0) > 0 and s["set_num"] not in seen_set_nums:
                            all_results.append(s)
                            seen_set_nums.add(s["set_num"])
    except Exception as e:
        print(f"Ошибка поиска по теме: {e}")

    return all_results

def fetch_and_save_set(set_num):
    """
    Скачивает информацию о наборе и его деталях, затем сохраняет в БД.
    """
    try:
        set_url = f"{BASE_URL}/sets/{set_num}/"
        set_res = requests.get(set_url, params={"key": API_KEY}, timeout=10)
        
        if set_res.status_code != 200:
            return False
            
        set_data = set_res.json()
        name = set_data.get("name", "Unknown")
        year = set_data.get("year", 0)
        num_parts = set_data.get("num_parts", 0)

        parts_url = f"{BASE_URL}/sets/{set_num}/parts/"
        parts_params = {
            "key": API_KEY, 
            "page_size": 1000, 
            "inc_minifig_parts": 1
        }
        parts_res = requests.get(parts_url, params=parts_params, timeout=15)
        
        if parts_res.status_code != 200:
            return False

        parts_data = parts_res.json().get("results", [])
        
        next_url = parts_res.json().get("next")
        while next_url:
            next_res = requests.get(next_url, timeout=15)
            if next_res.status_code == 200:
                next_data = next_res.json()
                parts_data.extend(next_data.get("results", []))
                next_url = next_data.get("next")
            else:
                break

        formatted_parts = []
        for item in parts_data:
            part = item.get("part", {})
            color = item.get("color", {})
            
            part_num = part.get("part_num", "")
            color_id = color.get("id", 0)
            color_name = color.get("name", "Unknown")
            color_rgb = color.get("rgb", "000000")
            part_name = part.get("name", "Unknown")
            part_img_url = part.get("part_img_url", "")
            qty = item.get("quantity", 1)
            is_spare = 1 if item.get("is_spare") else 0
            
            formatted_parts.append((
                part_num, color_id, color_name, color_rgb,
                part_name, part_img_url, qty, is_spare
            ))

        save_set(set_num, name, year, num_parts, formatted_parts)
        return True

    except Exception as e:
        print(f"Ошибка при скачивании набора {set_num}: {e}")
        return False