import sys
import os
import shutil
import threading
from tkinter import filedialog, messagebox
from io import BytesIO
import requests
from PIL import Image, ImageTk
import customtkinter as ctk

from database import (
    init_db,
    get_all_sets,
    get_set_parts,
    update_part_status,
    get_colors_for_sets,
    get_aggregated_parts,
    get_missing_parts_for_export,
    delete_set,
    get_set_progress,
    increment_part_for_set,
)
from api_service import fetch_and_save_set
from image_cache import get_cached_image, get_cached_set_image
from exporter import generate_bricklink_xml

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Надежная установка иконки с небольшой задержкой
        def set_app_icon():
            try:
                if hasattr(sys, '_MEIPASS'):
                    icon_path = os.path.join(sys._MEIPASS, "icon.ico")
                else:
                    icon_path = "icon.ico"
                    
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            except Exception:
                try:
                    from PIL import ImageTk
                    pil_icon = Image.open(icon_path)
                    self.icon_image = ImageTk.PhotoImage(pil_icon)
                    self.iconphoto(False, self.icon_image)
                except Exception as e:
                    print(f"Не удалось установить иконку: {e}")

        self.after(200, set_app_icon)

        self.title("Set Completer")
        self.geometry("1100x750")
        self.minsize(950, 600)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.hide_completed_var = ctk.BooleanVar(value=False)
        self.ITEMS_PER_PAGE = 50

        # Сайдбар
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Set Completer",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 15))

        self.btn_my_sets = ctk.CTkButton(
            self.sidebar_frame, text="Мои наборы", font=ctk.CTkFont(size=14), height=35, command=self.show_my_sets,
        )
        self.btn_my_sets.grid(row=1, column=0, padx=20, pady=10)

        self.btn_multi_search = ctk.CTkButton(
            self.sidebar_frame, text="Мульти-поиск", font=ctk.CTkFont(size=14), height=35, command=self.show_multi_search,
        )
        self.btn_multi_search.grid(row=2, column=0, padx=20, pady=10)

        self.btn_add_set = ctk.CTkButton(
            self.sidebar_frame, text="Добавить набор", font=ctk.CTkFont(size=14), height=35, command=self.show_add_set,
        )
        self.btn_add_set.grid(row=3, column=0, padx=20, pady=10)

        self.btn_export_db = ctk.CTkButton(
            self.sidebar_frame, text="Сохранить коллекции", font=ctk.CTkFont(size=14), height=35, command=self.export_database,
        )
        self.btn_export_db.grid(row=4, column=0, padx=20, pady=10)

        self.btn_import_db = ctk.CTkButton(
            self.sidebar_frame, text="Загрузить коллекции", font=ctk.CTkFont(size=14), height=35, 
            fg_color="#455a64", hover_color="#37474f", command=self.import_database,
        )
        self.btn_import_db.grid(row=5, column=0, padx=20, pady=10)

        # Основная область
        self.main_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.image_load_queue = []
        self.search_image_queue = []
        self.selected_set_vars = {}
        self.selected_color_id = None
        
        self.show_my_sets()
        
        # Глобальная привязка колесика мыши для скролла в Windows
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """Глобальный обработчик прокрутки колесиком мыши"""
        try:
            if self.main_frame.winfo_exists():
                self.main_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def scroll_to_top(self):
        self.after(10, lambda: self.main_frame._parent_canvas.yview_moveto(0))

    def clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def open_image_preview(self, img_url, title_text):
        if not img_url:
            return

        top = ctk.CTkToplevel(self)
        top.title("Просмотр изображения")
        top.geometry("450x500")
        top.minsize(350, 400)
        top.grab_set()

        ctk.CTkLabel(
            top, text=title_text, font=ctk.CTkFont(size=14, weight="bold"), wraplength=400
        ).pack(pady=(15, 10))

        img_frame = ctk.CTkFrame(top, fg_color="#1c1c1c", corner_radius=10)
        img_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        preview_label = ctk.CTkLabel(img_frame, text="Загрузка в высоком разрешении...", text_color="gray")
        preview_label.pack(expand=True)

        def load_high_res():
            try:
                res = requests.get(img_url, timeout=10)
                if res.status_code == 200:
                    pil_img = Image.open(BytesIO(res.content))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 320))
                    self.after(0, lambda: preview_label.configure(image=ctk_img, text=""))
                    preview_label.image = ctk_img 
                else:
                    self.after(0, lambda: preview_label.configure(text="Не удалось загрузить картинку."))
            except Exception:
                self.after(0, lambda: preview_label.configure(text="Ошибка соединения."))

        threading.Thread(target=load_high_res, daemon=True).start()

    def export_database(self):
        """Сохраняет текущую базу данных в файл"""
        db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SetCompleter", "completer.db")
        if not os.path.exists(db_path):
            messagebox.showerror("Ошибка", "База данных пока пуста. Добавьте хотя бы один набор!")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".scbak",
            filetypes=[("Set Completer Backup", "*.scbak"), ("All files", "*.*")],
            initialfile="MyLegoCollection.scbak",
            title="Сохранить файл коллекции"
        )
        
        if filepath:
            try:
                shutil.copy2(db_path, filepath)
                messagebox.showinfo("Успех", f"Коллекция успешно сохранена в файл:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать файл: {e}")

    def import_database(self):
        """Загружает базу данных из файла, заменяя текущую"""
        filepath = filedialog.askopenfilename(
            filetypes=[("Set Completer Backup", "*.scbak"), ("All files", "*.*")],
            title="Открыть файл коллекции"
        )
        
        if filepath:
            confirm = messagebox.askyesno(
                "Внимание", 
                "Текущая коллекция на этом компьютере будет ПОЛНОСТЬЮ ЗАМЕНЕНА данными из файла.\n\nВы уверены, что хотите загрузить этот файл?"
            )
            if confirm:
                try:
                    db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SetCompleter", "completer.db")
                    os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    
                    shutil.copy2(filepath, db_path)
                    messagebox.showinfo("Успех", "Коллекция успешно загружена!\nВсе ваши наборы и прогресс восстановлены.")
                    self.show_my_sets() 
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось импортировать файл: {e}")

    def show_my_sets(self):
        self.clear_main_frame()
        self.scroll_to_top()

        title = ctk.CTkLabel(
            self.main_frame, text="Мои наборы", font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 20))

        sets = get_all_sets()
        if not sets:
            ctk.CTkLabel(
                self.main_frame, text="Пока нет добавленных наборов.", font=ctk.CTkFont(size=16), text_color="gray",
            ).pack(pady=20)
            return

        for set_data in sets:
            set_num, name, year, num_parts, status = set_data
            
            needed, found = get_set_progress(set_num)
            progress_ratio = (found / needed) if needed > 0 else 0.0
            percent = int(progress_ratio * 100)

            card = ctk.CTkFrame(self.main_frame)
            card.pack(fill="x", pady=8, padx=5)

            left_block = ctk.CTkFrame(card, fg_color="transparent")
            left_block.pack(side="left", padx=20, pady=15, fill="x", expand=True)

            info_text = f"Артикул: {set_num}   |   {name} ({year})"
            ctk.CTkLabel(
                left_block, text=info_text, font=ctk.CTkFont(size=16, weight="bold"),
            ).pack(anchor="w")

            progress_text = f"Собрано: {found} / {needed} шт. ({percent}%)"
            ctk.CTkLabel(
                left_block, text=progress_text, font=ctk.CTkFont(size=13),
                text_color="#81c784" if percent == 100 else "#b0bec5",
            ).pack(anchor="w", pady=(4, 6))

            progress_bar = ctk.CTkProgressBar(left_block, height=10)
            progress_bar.set(progress_ratio)
            if percent == 100:
                progress_bar.configure(progress_color="#4caf50")
            progress_bar.pack(anchor="w", fill="x", pady=(0, 5))

            btn_block = ctk.CTkFrame(card, fg_color="transparent")
            btn_block.pack(side="right", padx=20, pady=15)

            open_btn = ctk.CTkButton(
                btn_block, text="Открыть", font=ctk.CTkFont(size=14), width=100, height=35,
                command=lambda num=set_num: self.show_set_inventory(num, page=1),
            )
            open_btn.pack(side="left", padx=(0, 10))

            del_btn = ctk.CTkButton(
                btn_block, text="Удалить", font=ctk.CTkFont(size=14), width=80, height=35,
                fg_color="#c62828", hover_color="#8e0000",
                command=lambda num=set_num, s_name=name: self.confirm_delete_set(num, s_name),
            )
            del_btn.pack(side="left")

    def confirm_delete_set(self, set_num, set_name):
        confirm = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы точно хотите удалить набор {set_num} ({set_name}) и всю историю его комплектации?",
        )
        if confirm:
            delete_set(set_num)
            self.show_my_sets()

    def show_set_inventory(self, set_num, page=1, color_id=None):
        self.clear_main_frame()
        self.scroll_to_top()

        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        back_btn = ctk.CTkButton(
            header_frame, text="← Назад", font=ctk.CTkFont(size=14), width=110, height=35, command=self.show_my_sets,
        )
        back_btn.pack(side="left")

        title = ctk.CTkLabel(
            header_frame, text=f"Инвентарь набора {set_num}", font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.pack(side="left", padx=20)

        export_btn = ctk.CTkButton(
            header_frame, text="Экспорт в BrickLink (XML)", font=ctk.CTkFont(size=13),
            fg_color="#ef6c00", hover_color="#b53d00", height=35,
            command=lambda num=set_num: self.export_set_missing(num),
        )
        export_btn.pack(side="right")

        filter_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 15), padx=5)

        ctk.CTkLabel(
            filter_frame, text="Фильтр по цвету:", font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(0, 10))

        all_parts = get_set_parts(set_num)
        color_stats = {}
        total_parts_all_colors = 0
        
        for p in all_parts:
            c_id = p[2]
            req = p[7]
            found = p[8]
            
            if c_id not in color_stats:
                color_stats[c_id] = {"total": 0, "completed": True}
                
            color_stats[c_id]["total"] += req
            total_parts_all_colors += req
            
            if found < req:
                color_stats[c_id]["completed"] = False

        db_colors = get_colors_for_sets([set_num])
        color_map = {}
        color_names = []

        all_colors_base_str = f"Все цвета [{total_parts_all_colors} шт.]"
        display_all_colors = f"➤ {all_colors_base_str}" if color_id is None else all_colors_base_str
        color_names.append(display_all_colors)
        color_map[display_all_colors] = None

        for cid, cname in db_colors:
            stats = color_stats.get(cid, {"total": 0, "completed": False})
            disp_name = f"{cname} [{stats['total']} шт.]"
            
            if stats["completed"]:
                disp_name += " (✓)"
                
            if cid == color_id:
                disp_name = f"➤ {disp_name}"
                
            color_names.append(disp_name)
            color_map[disp_name] = cid

        def on_color_change(choice):
            c_id = color_map.get(choice)
            self.show_set_inventory(set_num, page=1, color_id=c_id)

        color_dropdown = ctk.CTkOptionMenu(
            filter_frame, values=color_names, width=280, command=on_color_change
        )
        color_dropdown.pack(side="left")

        for name, cid in color_map.items():
            if cid == color_id:
                color_dropdown.set(name)
                break

        hide_switch = ctk.CTkSwitch(
            filter_frame, text="Скрыть собранные", font=ctk.CTkFont(size=13, weight="bold"),
            variable=self.hide_completed_var,
            command=lambda: self.show_set_inventory(set_num, page=1, color_id=color_id)
        )
        hide_switch.pack(side="left", padx=25)

        refresh_btn = ctk.CTkButton(
            filter_frame, text="↻ Обновить список", width=130, height=28,
            fg_color="#1976d2", hover_color="#1565c0", font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.show_set_inventory(set_num, page=page, color_id=color_id)
        )
        refresh_btn.pack(side="left", padx=10)

        if color_id is not None:
            all_parts = [p for p in all_parts if p[2] == color_id]

        if self.hide_completed_var.get():
            all_parts = [p for p in all_parts if p[8] < p[7]]

        if not all_parts:
            ctk.CTkLabel(
                self.main_frame, text="Детали не найдены (или все уже собраны).",
                font=ctk.CTkFont(size=16), text_color="gray",
            ).pack(pady=20)
            return

        total_items = len(all_parts)
        total_pages = (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        start_idx = (page - 1) * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_parts = all_parts[start_idx:end_idx]

        self.image_load_queue = []
        spare_header_drawn = False

        for part in page_parts:
            (
                part_id, part_num, c_id, color_name, color_rgb,
                part_name, part_img_url, req, found, missing, is_spare,
            ) = part

            if is_spare and not spare_header_drawn:
                spare_header_drawn = True
                separator_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
                separator_frame.pack(fill="x", pady=(25, 10), padx=5)
                sep_line = ctk.CTkFrame(separator_frame, height=2, fg_color="#555555")
                sep_line.pack(fill="x", pady=(0, 10))
                ctk.CTkLabel(
                    separator_frame, text="Запасные детали (Extra Parts)",
                    font=ctk.CTkFont(size=18, weight="bold"), text_color="#ffa726",
                ).pack(anchor="w")

            row = ctk.CTkFrame(self.main_frame)
            row.pack(fill="x", pady=4, padx=5)

            img_label = ctk.CTkLabel(
                row, text="", width=80, height=80, fg_color="#1c1c1c", corner_radius=8, cursor="hand2"
            )
            img_label.pack(side="left", padx=10, pady=10)
            img_label.bind("<Button-1>", lambda e, url=part_img_url, name=f"{part_name} ({color_name})": self.open_image_preview(url, name))

            self.image_load_queue.append((img_label, part_num, c_id, part_img_url))

            hex_color = f"#{color_rgb}" if color_rgb else "#555555"
            ctk.CTkLabel(
                row, text="", width=20, height=20, fg_color=hex_color, corner_radius=4
            ).pack(side="left", padx=(5, 10))

            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", padx=10)

            ctk.CTkLabel(
                info_frame, text=part_name, font=ctk.CTkFont(size=13, weight="bold"),
                justify="left", anchor="w", width=260, wraplength=260,  
            ).pack(anchor="w")

            ctk.CTkLabel(
                info_frame, text=f"Артикул: {part_num}  |  Цвет: {color_name}",
                font=ctk.CTkFont(size=12), text_color="#b0bec5", justify="left", anchor="w"
            ).pack(anchor="w", pady=(2, 0))

            actions_frame = ctk.CTkFrame(row, fg_color="transparent")
            actions_frame.pack(side="right", padx=15)

            status_label = ctk.CTkLabel(
                actions_frame, text="", font=ctk.CTkFont(size=14, weight="bold"), width=100
            )
            status_label.pack(side="left", padx=10)

            btn_minus = ctk.CTkButton(actions_frame, text="-", width=32, height=32, font=ctk.CTkFont(size=16, weight="bold"))
            btn_minus.pack(side="left", padx=2)

            btn_plus = ctk.CTkButton(actions_frame, text="+", width=32, height=32, font=ctk.CTkFont(size=16, weight="bold"))
            btn_plus.pack(side="left", padx=2)

            btn_all = ctk.CTkButton(actions_frame, text="✓ Все", width=55, height=32, font=ctk.CTkFont(size=12), fg_color="#2e7d32", hover_color="#1b5e20")
            btn_all.pack(side="left", padx=4)

            def bind_controls(
                p_id=part_id, needed=req, current_found=found,
                lbl=status_label, r_card=row, b_p=btn_plus, b_m=btn_minus, b_a=btn_all
            ):
                state = {"found": current_found}

                def refresh_ui():
                    if state["found"] >= needed:
                        lbl.configure(text=f"Собрано: {state['found']}/{needed}", text_color="#4caf50")
                        r_card.configure(border_width=1, border_color="#2e7d32")
                    else:
                        lbl.configure(text=f"Найдено: {state['found']}/{needed}", text_color="white")
                        r_card.configure(border_width=0)

                def add_one():
                    if state["found"] < needed:
                        state["found"] += 1
                        missing = needed - state["found"]
                        update_part_status(p_id, state["found"], missing)
                        refresh_ui()

                def remove_one():
                    if state["found"] > 0:
                        state["found"] -= 1
                        missing = needed - state["found"]
                        update_part_status(p_id, state["found"], missing)
                        refresh_ui()

                def mark_all():
                    state["found"] = needed
                    update_part_status(p_id, state["found"], 0)
                    refresh_ui()

                b_p.configure(command=add_one)
                b_m.configure(command=remove_one)
                b_a.configure(command=mark_all)
                refresh_ui()

            bind_controls()

        if total_pages > 1:
            pag_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            pag_frame.pack(pady=20)

            if page > 1:
                ctk.CTkButton(pag_frame, text="← Назад", width=100, 
                              command=lambda p=page-1: self.show_set_inventory(set_num, page=p, color_id=color_id)).pack(side="left", padx=10)
            
            ctk.CTkLabel(pag_frame, text=f"Страница {page} из {total_pages}", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=15)
            
            if page < total_pages:
                ctk.CTkButton(pag_frame, text="Вперед →", width=100, 
                              command=lambda p=page+1: self.show_set_inventory(set_num, page=p, color_id=color_id)).pack(side="left", padx=10)

        queue_copy = list(self.image_load_queue)
        threading.Thread(target=self.process_image_queue, args=(queue_copy,), daemon=True).start()

    def export_set_missing(self, set_num):
        # Принудительно обновляем базу перед экспортом, чтобы недостачей считалось (требуется - найдено)
        all_parts = get_set_parts(set_num)
        for p in all_parts:
            update_part_status(p[0], p[8], max(0, p[7] - p[8]))
            
        missing_parts = get_missing_parts_for_export(set_num)
        if not missing_parts:
            messagebox.showinfo("Экспорт", "В этом наборе собраны абсолютно все детали!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xml", filetypes=[("XML files", "*.xml")],
            initialfile=f"missing_{set_num}.xml", title="Сохранить файл недостачи"
        )
        if filepath:
            generate_bricklink_xml(missing_parts, filepath)
            messagebox.showinfo("Успех", f"Файл успешно сохранен:\n{filepath}")

    # --- РАЗДЕЛ МУЛЬТИ-ПОИСКА ---
    def show_multi_search(self):
        self.clear_main_frame()
        self.scroll_to_top()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(title_frame, text="Мульти-поиск деталей", font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")

        ctk.CTkButton(
            title_frame, text="Экспорт в BrickLink (XML)", font=ctk.CTkFont(size=13),
            fg_color="#ef6c00", hover_color="#b53d00", height=35,
            command=self.export_multi_missing,
        ).pack(side="right")

        sets = get_all_sets()
        if not sets:
            ctk.CTkLabel(self.main_frame, text="Сначала добавьте наборы для поиска.", font=ctk.CTkFont(size=16), text_color="gray").pack(pady=20)
            return

        sets_select_frame = ctk.CTkFrame(self.main_frame)
        sets_select_frame.pack(fill="x", pady=(0, 15), padx=5)

        ctk.CTkLabel(sets_select_frame, text="Выберите наборы для одновременного поиска:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.selected_set_vars = {}
        chk_container = ctk.CTkFrame(sets_select_frame, fg_color="transparent")
        chk_container.pack(fill="x", padx=15, pady=(0, 10))

        for s in sets:
            set_num, name, year, _, _ = s
            var = ctk.BooleanVar(value=True)
            self.selected_set_vars[set_num] = var
            ctk.CTkCheckBox(chk_container, text=f"{set_num} ({name})", variable=var, command=self.refresh_multi_search_view).pack(side="left", padx=(0, 15), pady=5)

        filter_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 15), padx=5)

        ctk.CTkLabel(filter_frame, text="Фильтр по цвету:", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 10))

        self.color_dropdown = ctk.CTkOptionMenu(filter_frame, values=["Все цвета"], width=280, command=self.on_color_selected)
        self.color_dropdown.pack(side="left")

        ctk.CTkSwitch(
            filter_frame, text="Скрыть собранные", font=ctk.CTkFont(size=13, weight="bold"),
            variable=self.hide_completed_var, command=lambda: self.render_aggregated_parts(page=1)
        ).pack(side="left", padx=25)

        refresh_btn = ctk.CTkButton(
            filter_frame, text="↻ Обновить список", width=130, height=28,
            fg_color="#1976d2", hover_color="#1565c0", font=ctk.CTkFont(size=12, weight="bold"),
            command=self.refresh_multi_search_view
        )
        refresh_btn.pack(side="left", padx=10)

        self.multi_results_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.multi_results_frame.pack(fill="x")

        self.refresh_multi_search_view()

    def get_active_multi_sets(self):
        return [s_num for s_num, var in self.selected_set_vars.items() if var.get()]

    def on_color_selected(self, choice):
        self.selected_color_id = self.color_map.get(choice)
        self.refresh_multi_search_view()

    def refresh_multi_search_view(self):
        active_sets = self.get_active_multi_sets()
        if not active_sets:
            self.color_map = {}
            self.color_dropdown.configure(values=["Все цвета"])
            self.color_dropdown.set("Все цвета")
            self.selected_color_id = None
            self.render_aggregated_parts(page=1)
            return

        all_agg_parts = get_aggregated_parts(active_sets, color_id=None)
        color_stats = {}
        total_parts_all_colors = 0
        
        for p in all_agg_parts:
            c_id = p[1]
            req = p[6]
            found = p[7]
            
            if c_id not in color_stats:
                color_stats[c_id] = {"total": 0, "completed": True}
                
            color_stats[c_id]["total"] += req
            total_parts_all_colors += req
            
            if found < req:
                color_stats[c_id]["completed"] = False

        db_colors = get_colors_for_sets(active_sets)
        self.color_map = {}
        color_names = []

        all_colors_base_str = f"Все цвета [{total_parts_all_colors} шт.]"
        display_all_colors = f"➤ {all_colors_base_str}" if self.selected_color_id is None else all_colors_base_str
        color_names.append(display_all_colors)
        self.color_map[display_all_colors] = None

        for cid, cname in db_colors:
            stats = color_stats.get(cid, {"total": 0, "completed": False})
            disp_name = f"{cname} [{stats['total']} шт.]"
            
            if stats["completed"]:
                disp_name += " (✓)"
                
            if cid == self.selected_color_id:
                disp_name = f"➤ {disp_name}"
                
            color_names.append(disp_name)
            self.color_map[disp_name] = cid

        self.color_dropdown.configure(values=color_names)

        found = False
        for name, cid in self.color_map.items():
            if cid == self.selected_color_id:
                self.color_dropdown.set(name)
                found = True
                break
        if not found:
            self.color_dropdown.set(display_all_colors)
            self.selected_color_id = None

        self.render_aggregated_parts(page=1)

    def render_aggregated_parts(self, page=1):
        for w in self.multi_results_frame.winfo_children():
            w.destroy()
            
        self.scroll_to_top()

        active_sets = self.get_active_multi_sets()
        if not active_sets:
            ctk.CTkLabel(self.multi_results_frame, text="Не выбран ни один набор.", text_color="gray").pack(pady=20)
            return

        all_agg_parts = get_aggregated_parts(active_sets, self.selected_color_id)
        
        if self.hide_completed_var.get():
            all_agg_parts = [p for p in all_agg_parts if p[7] < p[6]] 

        if not all_agg_parts:
            ctk.CTkLabel(self.multi_results_frame, text="Детали с выбранным цветом не найдены.", text_color="gray").pack(pady=20)
            return

        total_items = len(all_agg_parts)
        total_pages = (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        start_idx = (page - 1) * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_parts = all_agg_parts[start_idx:end_idx]

        self.image_load_queue = []

        for p in page_parts:
            part_num, color_id, color_name, color_rgb, part_name, part_img_url, total_req, total_fnd, total_mis, breakdown = p

            row = ctk.CTkFrame(self.multi_results_frame)
            row.pack(fill="x", pady=4, padx=5)

            row_state = {"total_req": total_req, "total_fnd": total_fnd}

            img_label = ctk.CTkLabel(row, text="", width=80, height=80, fg_color="#1c1c1c", corner_radius=8, cursor="hand2")
            img_label.pack(side="left", padx=10, pady=10)
            img_label.bind("<Button-1>", lambda e, url=part_img_url, name=f"{part_name} ({color_name})": self.open_image_preview(url, name))

            self.image_load_queue.append((img_label, part_num, color_id, part_img_url))

            hex_color = f"#{color_rgb}" if color_rgb else "#555555"
            ctk.CTkLabel(row, text="", width=20, height=20, fg_color=hex_color, corner_radius=4).pack(side="left", padx=(5, 10))

            text_container = ctk.CTkFrame(row, fg_color="transparent")
            text_container.pack(side="left", padx=10)

            ctk.CTkLabel(
                text_container, text=part_name, font=ctk.CTkFont(size=13, weight="bold"),
                justify="left", anchor="w", width=350, wraplength=350,  
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_container, text=f"Арт: {part_num}  |  Цвет: {color_name}",
                font=ctk.CTkFont(size=12), text_color="#b0bec5", justify="left", anchor="w",
            ).pack(anchor="w", pady=(2, 0))

            distrib_container = ctk.CTkFrame(text_container, fg_color="transparent")
            distrib_container.pack(anchor="w", pady=(4, 0))

            ctk.CTkLabel(distrib_container, text="Куда:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#64b5f6").pack(side="left", padx=(0, 6))

            status_label = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=15, weight="bold"), justify="right")
            status_label.pack(side="right", padx=25)

            def update_status_label():
                rem_needed = max(0, row_state["total_req"] - row_state["total_fnd"])
                status_label.configure(
                    text=f"Осталось найти:\n{rem_needed} / {row_state['total_req']} шт.",
                    text_color="#4caf50" if rem_needed == 0 else "white",
                )
            update_status_label()

            for item in breakdown.split("; "):
                s_num, s_req, s_fnd = item.split(":")
                req_i, fnd_i = int(s_req), int(s_fnd)

                badge = ctk.CTkFrame(distrib_container, fg_color="#263238", corner_radius=6)
                badge.pack(side="left", padx=3)

                badge_label = ctk.CTkLabel(
                    badge, text=f"{s_num}: {fnd_i}/{req_i}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#4caf50" if fnd_i >= req_i else "#eceff1",
                )
                badge_label.pack(side="left", padx=(6, 2), pady=2)

                def make_actions(target_set=s_num, p_n=part_num, c_i=color_id, b_lbl=badge_label, r_i=req_i, f_i=fnd_i):
                    badge_state = {"fnd": f_i}

                    def do_inc():
                        if badge_state["fnd"] < r_i:
                            res = increment_part_for_set(target_set, p_n, c_i, delta=1)
                            if res:
                                new_f, r = res
                                diff = new_f - badge_state["fnd"]
                                badge_state["fnd"] = new_f
                                row_state["total_fnd"] += diff
                                b_lbl.configure(text=f"{target_set}: {new_f}/{r}", text_color="#4caf50" if new_f >= r else "#eceff1")
                                update_status_label()

                    def do_dec():
                        if badge_state["fnd"] > 0:
                            res = increment_part_for_set(target_set, p_n, c_i, delta=-1)
                            if res:
                                new_f, r = res
                                diff = new_f - badge_state["fnd"]
                                badge_state["fnd"] = new_f
                                row_state["total_fnd"] += diff
                                b_lbl.configure(text=f"{target_set}: {new_f}/{r}", text_color="#4caf50" if new_f >= r else "#eceff1")
                                update_status_label()

                    btn_m = ctk.CTkButton(badge, text="-", width=18, height=18, font=ctk.CTkFont(size=10, weight="bold"), command=do_dec)
                    btn_m.pack(side="left", padx=1, pady=2)
                    btn_p = ctk.CTkButton(badge, text="+", width=18, height=18, font=ctk.CTkFont(size=10, weight="bold"), command=do_inc)
                    btn_p.pack(side="left", padx=(1, 3), pady=2)

                make_actions()

        if total_pages > 1:
            pag_frame = ctk.CTkFrame(self.multi_results_frame, fg_color="transparent")
            pag_frame.pack(pady=20)

            if page > 1:
                ctk.CTkButton(pag_frame, text="← Назад", width=100, command=lambda p=page-1: self.render_aggregated_parts(page=p)).pack(side="left", padx=10)
            
            ctk.CTkLabel(pag_frame, text=f"Страница {page} из {total_pages}", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=15)
            
            if page < total_pages:
                ctk.CTkButton(pag_frame, text="Вперед →", width=100, command=lambda p=page+1: self.render_aggregated_parts(page=p)).pack(side="left", padx=10)

        queue_copy = list(self.image_load_queue)
        threading.Thread(target=self.process_image_queue, args=(queue_copy,), daemon=True).start()

    def process_image_queue(self, queue):
        for img_label, part_num, color_id, img_url in queue:
            if not img_label.winfo_exists():
                continue
            img = get_cached_image(part_num, color_id, img_url, size=(80, 80))
            self.after(0, self.update_image_label, img_label, img)

    def process_set_image_queue(self, queue):
        for img_label, set_num, img_url in queue:
            if not img_label.winfo_exists():
                continue
            img = get_cached_set_image(set_num, img_url, size=(80, 80))
            self.after(0, self.update_image_label, img_label, img)

    def update_image_label(self, label, img):
        if label.winfo_exists():
            label.configure(image=img, fg_color="transparent")

    def export_multi_missing(self):
        active_sets = self.get_active_multi_sets()
        if not active_sets:
            messagebox.showinfo("Экспорт", "Выберите хотя бы один набор галочкой.")
            return

        # Принудительно обновляем базу перед экспортом, чтобы недостачей считалось (требуется - найдено)
        for s_num in active_sets:
            for p in get_set_parts(s_num):
                update_part_status(p[0], p[8], max(0, p[7] - p[8]))

        missing_parts = get_missing_parts_for_export(active_sets)
        if not missing_parts:
            messagebox.showinfo("Экспорт", "В выбранных наборах собраны абсолютно все детали!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml")],
            initialfile="missing_multi_sets.xml",
            title="Сохранить файл общей недостачи BrickLink",
        )

        if filepath:
            generate_bricklink_xml(missing_parts, filepath)
            messagebox.showinfo("Успех", f"Общий файл успешно сохранен:\n{filepath}")

    # --- РАЗДЕЛ ДОБАВЛЕНИЯ НАБОРА ---
    def show_add_set(self):
        self.clear_main_frame()
        self.scroll_to_top()
        
        ctk.CTkLabel(
            self.main_frame, text="Поиск и добавление наборов", font=ctk.CTkFont(size=26, weight="bold")
        ).pack(anchor="w", pady=(0, 20))
        
        ctk.CTkLabel(
            self.main_frame, text="Введите артикул (например, 75035) или название (например, Kashyyyk):", font=ctk.CTkFont(size=15)
        ).pack(anchor="w", pady=(0, 10))

        search_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 15))

        self.set_entry = ctk.CTkEntry(
            search_frame, width=320, height=35, font=ctk.CTkFont(size=14), placeholder_text="Артикул или название..."
        )
        self.set_entry.pack(side="left", padx=(0, 10))
        
        self.set_entry.bind("<Return>", lambda event: self.start_search())

        self.search_btn = ctk.CTkButton(
            search_frame, text="Найти", font=ctk.CTkFont(size=14), height=35, width=100, command=self.start_search
        )
        self.search_btn.pack(side="left")

        self.status_label = ctk.CTkLabel(self.main_frame, text="", font=ctk.CTkFont(size=14), text_color="gray")
        self.status_label.pack(anchor="w", pady=(5, 10))

        self.search_results_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.search_results_frame.pack(fill="both", expand=True)

    def start_search(self):
        query = self.set_entry.get().strip()
        if not query:
            self.status_label.configure(text="Пожалуйста, введите поисковый запрос.", text_color="red")
            return

        self.status_label.configure(text="Идет поиск в базе Rebrickable...", text_color="yellow")
        self.search_btn.configure(state="disabled")
        
        for widget in self.search_results_frame.winfo_children():
            widget.destroy()

        threading.Thread(target=self.search_process, args=(query,), daemon=True).start()

    def search_process(self, query):
        from api_service import search_sets
        results = search_sets(query)
        self.after(0, self.display_search_results, results)

    def display_search_results(self, results):
        self.search_btn.configure(state="normal")
        
        if not results:
            self.status_label.configure(text="По вашему запросу ничего не найдено.", text_color="red")
            return
            
        self.status_label.configure(text=f"Найдено совпадений: {len(results)}", text_color="#4caf50")
        
        self.search_image_queue = []

        for s in results:
            s_num = s.get("set_num")
            s_name = s.get("name")
            s_year = s.get("year")
            s_parts = s.get("num_parts")
            set_img_url = s.get("set_img_url")

            row = ctk.CTkFrame(self.search_results_frame)
            row.pack(fill="x", pady=6, padx=5)
            
            img_label = ctk.CTkLabel(row, text="", width=80, height=80, fg_color="#1c1c1c", corner_radius=8, cursor="hand2")
            img_label.pack(side="left", padx=10, pady=10)
            img_label.bind("<Button-1>", lambda e, url=set_img_url, name=f"{s_name} ({s_num})": self.open_image_preview(url, name))

            self.search_image_queue.append((img_label, s_num, set_img_url))
            
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", padx=15, fill="x", expand=True)

            ctk.CTkLabel(
                info_frame, text=s_name, font=ctk.CTkFont(size=15, weight="bold"), justify="left", anchor="w"
            ).pack(anchor="w")
            
            meta_text = f"Артикул: {s_num}   |   Год: {s_year}   |   Деталей: {s_parts}"
            ctk.CTkLabel(
                info_frame, text=meta_text, font=ctk.CTkFont(size=13), text_color="#b0bec5", justify="left", anchor="w"
            ).pack(anchor="w", pady=(4, 0))

            download_btn = ctk.CTkButton(
                row, text="Скачать инвентарь", font=ctk.CTkFont(size=13), width=140, height=35
            )
            self.bind_download_btn(download_btn, s_num)
            download_btn.pack(side="right", padx=20)

        queue_copy = list(self.search_image_queue)
        threading.Thread(target=self.process_set_image_queue, args=(queue_copy,), daemon=True).start()

    def bind_download_btn(self, btn, set_num):
        btn.configure(command=lambda: self.test_download(set_num, btn))

    def test_download(self, set_num, btn):
        self.start_download(set_num, btn)

    def start_download(self, set_num, btn):
        self.status_label.configure(text=f"Загрузка деталей для {set_num}... Подождите.", text_color="yellow")
        btn.configure(state="disabled", text="Скачивание...")
        
        for widget in self.search_results_frame.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.configure(state="disabled")
        
        threading.Thread(target=self.download_process, args=(set_num,), daemon=True).start()

    def download_process(self, set_num):
        success = fetch_and_save_set(set_num)
        self.after(0, self.download_finished, success)

    def download_finished(self, success):
        if success:
            self.status_label.configure(text="Набор успешно скачан и добавлен!", text_color="#4caf50")
            self.after(1200, self.show_my_sets)
        else:
            self.status_label.configure(text="Ошибка загрузки. Проверьте сеть или попробуйте позже.", text_color="red")
            for widget in self.search_results_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkButton):
                        child.configure(state="normal", text="Скачать инвентарь")


if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()