import requests

API_KEY = "d821a6c603b0ca782d321eaf80b52c0b"
SET_NUM = "75220-1"  # Набор Sandcrawler (к артикулу всегда добавляется -1)

headers = {
    "Accept": "application/json",
    "Authorization": f"key {API_KEY}"
}

# 1. Запрашиваем общую информацию о наборе
set_url = f"https://rebrickable.com/api/v3/lego/sets/{SET_NUM}/"
set_response = requests.get(set_url, headers=headers)

if set_response.status_code == 200:
    set_data = set_response.json()
    print(f"Набор найден: {set_data['name']} ({set_data['year']} год)")
    print(f"Всего деталей: {set_data['num_parts']}")
    print("-" * 40)
    
    # 2. Запрашиваем первые несколько деталей набора
    parts_url = f"https://rebrickable.com/api/v3/lego/sets/{SET_NUM}/parts/?page_size=5"
    parts_response = requests.get(parts_url, headers=headers)
    
    if parts_response.status_code == 200:
        parts_data = parts_response.json()
        print("Примеры деталей из набора:")
        for item in parts_data["results"]:
            part = item["part"]
            color = item["color"]
            print(f"- {part['name']} | Цвет: {color['name']} | Нужно: {item['quantity']} шт.")
            print(f"  Картинка: {part['part_img_url']}")
else:
    print(f"Ошибка запроса: {set_response.status_code}")
    print(set_response.text)