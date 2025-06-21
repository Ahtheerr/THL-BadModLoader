import os
import sys
import json
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, Toplevel, Listbox, Scrollbar

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText

# --- Constants ---
CONFIG_FILE = "config.json"
MODS_DIR = "Mods"
EXTRACTED_DIR = "Extracted"
EXTRACTED_PATCHES_DIR = "Extracted_Patches"
PACKING_TEMP_DIR = "BadProgrammingModdingStuffHappeningFolder"
PACKED_DIR = "Packed" # Pasta de destino para a opção "Pack Only"

LANGUAGES = {
    "English": "1",
    "Japanese": "0",
    "Simplified Chinese": "2",
    "Traditional Chinese": "3"
}

# Versão correta para empacotar recursos dentro do .exe principal.
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

TOOLS_EXE_PATH = resource_path(os.path.join("THL-Tools", "DSCSToolsCLI.exe"))

class ModManagerApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="cyborg", title="The Hundred Line - Mod Manager")
        self.geometry("800x750")
        self.minsize(600, 550)

        # --- Variables ---
        self.game_path = tk.StringVar()
        self.language_var = tk.StringVar()
        self.mod_vars = {}

        # --- Setup Paths ---
        self.setup_initial_directories()

        # --- UI Creation ---
        self.create_widgets()

        # --- Initial Load ---
        self.load_config()
        self.refresh_mod_list()

    def setup_initial_directories(self):
        """Create necessary directories on startup if they don't exist."""
        for dir_path in [MODS_DIR, EXTRACTED_DIR, EXTRACTED_PATCHES_DIR, PACKED_DIR]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

    def create_widgets(self):
        """Creates and places all the GUI widgets."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=BOTH, expand=True)
        config_frame = ttk.Labelframe(main_frame, text="Configuration", padding="10")
        config_frame.pack(fill=X, pady=(0, 10))
        path_label = ttk.Label(config_frame, text="Game Folder:")
        path_label.grid(row=0, column=0, sticky=W, padx=(0, 5))
        path_entry = ttk.Entry(config_frame, textvariable=self.game_path, state="readonly")
        path_entry.grid(row=0, column=1, sticky=EW, padx=(0, 10))
        path_button = ttk.Button(config_frame, text="Select...", command=self.select_game_folder, style="success.TButton")
        path_button.grid(row=0, column=2, sticky=E)
        lang_label = ttk.Label(config_frame, text="Mod Language:")
        lang_label.grid(row=1, column=0, sticky=W, padx=(0, 5), pady=(10, 0))
        lang_combo = ttk.Combobox(config_frame, textvariable=self.language_var, values=list(LANGUAGES.keys()), state="readonly")
        lang_combo.grid(row=1, column=1, sticky=EW, pady=(10, 0))
        lang_combo.bind("<<ComboboxSelected>>", self.save_config)
        config_frame.columnconfigure(1, weight=1)
        mods_frame = ttk.Labelframe(main_frame, text="Available Mods", padding="10")
        mods_frame.pack(fill=BOTH, expand=True, pady=10)
        self.mod_list_canvas = ttk.Frame(mods_frame)
        self.mod_list_canvas.pack(fill=BOTH, expand=True)
        actions_frame = ttk.Frame(main_frame, padding="10")
        actions_frame.pack(fill=X)
        left_actions = ttk.Frame(actions_frame)
        left_actions.pack(side=LEFT)
        create_mod_btn = ttk.Button(left_actions, text="Create New Mod", command=self.create_mod)
        create_mod_btn.pack(side=LEFT, padx=(0, 5))
        self.extract_btn = ttk.Button(left_actions, text="Extract MVGL", command=self.open_extract_window, state=DISABLED)
        self.extract_btn.pack(side=LEFT)
        right_actions = ttk.Frame(actions_frame)
        right_actions.pack(side=RIGHT)
        pack_btn = ttk.Button(right_actions, text="Pack Only", command=lambda: self.pack_mods(install=False), style="info.TButton")
        pack_btn.pack(side=LEFT, padx=(0, 5))
        pack_install_btn = ttk.Button(right_actions, text="Pack and Install", command=lambda: self.pack_mods(install=True), style="primary.TButton")
        pack_install_btn.pack(side=LEFT)
        log_frame = ttk.Labelframe(main_frame, text="Log", padding="10")
        log_frame.pack(fill=X, pady=(10, 0))
        self.log_text = ScrolledText(log_frame, height=8, autohide=True)
        self.log_text.pack(fill=X, expand=True)
        self.log_text.text.configure(state='disabled')

    def log(self, message):
        self.log_text.text.configure(state='normal')
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.text.configure(state='disabled')
        self.update_idletasks()

    def run_command(self, command):
        self.log(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None: break
                if output: self.log(output.strip())
            stderr_output = process.stderr.read()
            if stderr_output: self.log(f"ERROR: {stderr_output.strip()}")
            if process.returncode != 0:
                self.log(f"Command failed with return code {process.returncode}")
                return False
            self.log("Command executed successfully.")
            return True
        except FileNotFoundError:
            self.log(f"ERROR: Command not found. Make sure '{TOOLS_EXE_PATH}' exists.")
            messagebox.showerror("Error", f"Tool not found!\n\nPlease ensure 'THL-Tools.exe' is in the 'THL-Tools' subfolder.")
            return False
        except Exception as e:
            self.log(f"An unexpected error occurred: {e}")
            messagebox.showerror("Execution Error", f"An error occurred while running the tool:\n{e}")
            return False

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    path = config.get("game_path")
                    if path and os.path.isdir(path):
                        self.game_path.set(path)
                        self.validate_game_path()
                    language = config.get("language", "English")
                    if language in LANGUAGES: self.language_var.set(language)
                    else: self.language_var.set("English")
            else: self.language_var.set("English")
        except (json.JSONDecodeError, IOError):
            self.log("Could not read config file. Using defaults.")
            self.language_var.set("English")

    def save_config(self, event=None):
        config_data = {"game_path": self.game_path.get(), "language": self.language_var.get()}
        with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)
        self.log(f"Configuration saved. (Language: {self.language_var.get()})")

    def select_game_folder(self):
        path = filedialog.askdirectory(title="Select The Hundred Line Game Folder")
        if path:
            self.game_path.set(path)
            self.validate_game_path()
            self.save_config()

    def validate_game_path(self):
        path = self.game_path.get()
        gamedata_path = os.path.join(path, "gamedata")
        if os.path.isdir(gamedata_path):
            self.extract_btn.config(state=NORMAL)
            self.log(f"Game folder set to: {path}")
        else:
            self.extract_btn.config(state=DISABLED)
            self.log(f"Invalid game folder selected: {path}. 'gamedata' not found.")

    def refresh_mod_list(self):
        for widget in self.mod_list_canvas.winfo_children(): widget.destroy()
        self.mod_vars = {}
        if not os.path.exists(MODS_DIR): os.makedirs(MODS_DIR)
        try:
            mod_names = sorted([d for d in os.listdir(MODS_DIR) if os.path.isdir(os.path.join(MODS_DIR, d))])
            for mod_name in mod_names:
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(self.mod_list_canvas, text=mod_name, variable=var, style="primary.TCheckbutton")
                cb.pack(anchor=W, padx=5, pady=2)
                self.mod_vars[mod_name] = var
        except FileNotFoundError: self.log(f"'{MODS_DIR}' folder not found. It will be created.")

    def create_mod(self):
        mod_name = simpledialog.askstring("Create Mod", "Enter the name for the new mod:")
        if not mod_name: return
        sanitized_name = "".join(c for c in mod_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        if not sanitized_name:
            messagebox.showerror("Invalid Name", "Mod name contains invalid characters.")
            return
        mod_path = os.path.join(MODS_DIR, sanitized_name)
        if os.path.exists(mod_path):
            messagebox.showwarning("Mod Exists", f"A mod named '{sanitized_name}' already exists.")
            return
        try:
            os.makedirs(mod_path)
            # Adicionada a pasta 'root'
            subfolders = ["lua", "images", "text", "message", "data", "root"]
            for folder in subfolders:
                os.makedirs(os.path.join(mod_path, folder))
            self.log(f"Created mod: {sanitized_name}")
            self.refresh_mod_list()
        except OSError as e:
            messagebox.showerror("Error", f"Could not create mod directory: {e}")

    def open_extract_window(self):
        gamedata_path = os.path.join(self.game_path.get(), "gamedata")
        if not os.path.isdir(gamedata_path):
            messagebox.showerror("Error", "Game 'gamedata' folder not found.")
            return
        mvgl_files = sorted([f for f in os.listdir(gamedata_path) if f.lower().endswith(".mvgl")])
        if not mvgl_files:
            messagebox.showinfo("No Files", "No .mvgl files found in the gamedata folder.")
            return
        top = Toplevel(self); top.title("Select MVGL files to Extract"); top.geometry("400x400")
        listbox_frame = ttk.Frame(top, padding=10); listbox_frame.pack(fill=BOTH, expand=True)
        listbox = Listbox(listbox_frame, selectmode=EXTENDED)
        for f in mvgl_files: listbox.insert(END, f)
        listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = Scrollbar(listbox_frame, orient=VERTICAL, command=listbox.yview); scrollbar.pack(side=RIGHT, fill=Y)
        listbox.config(yscrollcommand=scrollbar.set)
        btn_frame = ttk.Frame(top, padding=10); btn_frame.pack(fill=X)
        extract_button = ttk.Button(btn_frame, text="Extract Selected", command=lambda: self.perform_extraction(listbox, top))
        extract_button.pack()

    def perform_extraction(self, listbox, top_window):
        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select one or more files to extract.", parent=top_window)
            return
        selected_files = [listbox.get(i) for i in selected_indices]
        top_window.destroy()
        gamedata_path = os.path.join(self.game_path.get(), "gamedata")
        if not os.path.exists(EXTRACTED_DIR): os.makedirs(EXTRACTED_DIR)
        extracted_patches = []
        for filename in selected_files:
            file_path = os.path.join(gamedata_path, filename)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(EXTRACTED_DIR, base_name)
            if os.path.exists(output_path): shutil.rmtree(output_path)
            command = [TOOLS_EXE_PATH, "--extract", file_path, output_path]
            self.run_command(command)
            if filename.lower().startswith("patch"): extracted_patches.append(base_name)
        self.log("Extraction process finished.")
        if extracted_patches:
            msg = "You have extracted patch files. Would you like to copy them to a dedicated 'Extracted_Patches' folder?\n\n" \
                  "IMPORTANT:\n" \
                  "- You need 'Patch_0.dx11' for Lua modding.\n" \
                  f"- For the selected language '{self.language_var.get()}', you need 'Patch_{LANGUAGES[self.language_var.get()]}.dx11' for Images/Data/Root and 'Patch_text0{LANGUAGES[self.language_var.get()]}.dx11' for Text/Message."
            if messagebox.askyesno("Copy Patches?", msg):
                self.log("Copying extracted patches...")
                if not os.path.exists(EXTRACTED_PATCHES_DIR): os.makedirs(EXTRACTED_PATCHES_DIR)
                for patch_name in extracted_patches:
                    src = os.path.join(EXTRACTED_DIR, patch_name)
                    dest = os.path.join(EXTRACTED_PATCHES_DIR, patch_name)
                    if os.path.exists(dest): shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                    self.log(f"Copied '{patch_name}' to '{EXTRACTED_PATCHES_DIR}'.")
                messagebox.showinfo("Success", "Patches copied successfully to Extracted_Patches folder.")

    def is_dir_empty(self, path):
        if not os.path.isdir(path): return True
        return not any(os.scandir(path))

    def get_dynamic_patch_map(self):
        selected_language_name = self.language_var.get()
        if not selected_language_name:
            selected_language_name = "English"
            self.log("Warning: No language selected, defaulting to English.")
        lang_code = LANGUAGES[selected_language_name]
        return {"lua": "Patch_0.dx11", "images": f"Patch_{lang_code}.dx11", "data": f"Patch_{lang_code}.dx11", "text": f"Patch_text0{lang_code}.dx11", "message": f"Patch_text0{lang_code}.dx11"}

    def pack_mods(self, install=False):
        selected_mods = [name for name, var in self.mod_vars.items() if var.get()]
        if not selected_mods:
            messagebox.showwarning("No Mods Selected", "Please select at least one mod to pack.")
            return

        action_string = "Packing and Installing" if install else "Packing"
        self.log(f"Starting to {action_string.lower()} mods: {', '.join(selected_mods)}")

        if os.path.exists(PACKING_TEMP_DIR): shutil.rmtree(PACKING_TEMP_DIR)
        os.makedirs(PACKING_TEMP_DIR)

        patch_map = self.get_dynamic_patch_map()
        self.log(f"Using language '{self.language_var.get()}' (Code: {LANGUAGES[self.language_var.get()]})")
        modified_patches = {}

        for mod_name in selected_mods:
            mod_path = os.path.join(MODS_DIR, mod_name)
            self.log(f"Processing mod: {mod_name}")
            
            # Lógica para pastas padrão (lua, images, etc.)
            for subfolder, patch_name in patch_map.items():
                mod_subfolder_path = os.path.join(mod_path, subfolder)
                if not self.is_dir_empty(mod_subfolder_path):
                    self.log(f"-> Found content in '{subfolder}'. Preparing '{patch_name}'.")
                    temp_patch_path = os.path.join(PACKING_TEMP_DIR, patch_name)
                    if not os.path.exists(temp_patch_path):
                        base_patch_path = os.path.join(EXTRACTED_PATCHES_DIR, patch_name)
                        if not os.path.exists(base_patch_path):
                            messagebox.showerror("Missing Base Patch", f"The required base patch '{patch_name}' was not found in '{EXTRACTED_PATCHES_DIR}'.\nPlease extract the correct language patches from the game first.")
                            self.log(f"ERROR: Base patch missing: {base_patch_path}")
                            shutil.rmtree(PACKING_TEMP_DIR)
                            return
                        shutil.copytree(base_patch_path, temp_patch_path)
                    
                    dest_subfolder_path = os.path.join(temp_patch_path, subfolder)
                    shutil.copytree(mod_subfolder_path, dest_subfolder_path, dirs_exist_ok=True)
                    self.log(f"   - Copied folder '{subfolder}' into temp patch.")
                    modified_patches[patch_name] = temp_patch_path
            
            # Lógica especial para a pasta 'root'
            mod_root_path = os.path.join(mod_path, 'root')
            if not self.is_dir_empty(mod_root_path):
                root_patch_name = patch_map['images'] 
                self.log(f"-> Found content in 'root'. Preparing '{root_patch_name}'.")

                temp_patch_path = os.path.join(PACKING_TEMP_DIR, root_patch_name)
                if not os.path.exists(temp_patch_path):
                    base_patch_path = os.path.join(EXTRACTED_PATCHES_DIR, root_patch_name)
                    if not os.path.exists(base_patch_path):
                        messagebox.showerror("Missing Base Patch", f"The required base patch '{root_patch_name}' for the 'root' folder was not found in '{EXTRACTED_PATCHES_DIR}'.")
                        self.log(f"ERROR: Base patch missing: {base_patch_path}")
                        shutil.rmtree(PACKING_TEMP_DIR)
                        return
                    shutil.copytree(base_patch_path, temp_patch_path)

                shutil.copytree(mod_root_path, temp_patch_path, dirs_exist_ok=True)
                self.log(f"   - Copied 'root' contents into base of temp patch.")
                modified_patches[root_patch_name] = temp_patch_path

        if not modified_patches:
            messagebox.showinfo("Nothing to Pack", "The selected mods have no content in their subfolders.")
            self.log("Packing cancelled: No mod content found.")
            shutil.rmtree(PACKING_TEMP_DIR)
            return
        
        self.log("All mods processed. Now packing into .mvgl files...")
        generated_mvgl_files = []
        for patch_name, path in modified_patches.items():
            output_mvgl_name = f"{os.path.basename(path)}.MVGL"
            temp_mvgl_path = os.path.join(PACKING_TEMP_DIR, output_mvgl_name)
            command = [TOOLS_EXE_PATH, "--pack", path, temp_mvgl_path]
            if self.run_command(command):
                generated_mvgl_files.append(temp_mvgl_path)

        if not generated_mvgl_files:
            messagebox.showerror("Packing Failed", "No MVGL files were created. Check the log for errors.")
            shutil.rmtree(PACKING_TEMP_DIR)
            return

        try:
            if install:
                self.log("Installing packed files...")
                gamedata_path = os.path.join(self.game_path.get(), "gamedata")
                for mvgl_file in generated_mvgl_files:
                    dest_path = os.path.join(gamedata_path, os.path.basename(mvgl_file))
                    shutil.move(mvgl_file, dest_path)
                    self.log(f"Installed '{os.path.basename(mvgl_file)}' to game folder.")
                messagebox.showinfo("Success", "Mods were packed and installed successfully!")
            else:
                self.log(f"Moving packed files to '{PACKED_DIR}' directory...")
                os.makedirs(PACKED_DIR, exist_ok=True)
                for mvgl_file in generated_mvgl_files:
                    dest_path = os.path.join(PACKED_DIR, os.path.basename(mvgl_file))
                    shutil.move(mvgl_file, dest_path)
                    self.log(f"Moved '{os.path.basename(mvgl_file)}' to '{PACKED_DIR}' directory.")
                messagebox.showinfo("Success", f"Mods packed successfully! The .MVGL files are in the '{PACKED_DIR}' folder.")
        
        except Exception as e:
            action = "install" if install else "move"
            messagebox.showerror(f"{action.capitalize()} Failed", f"Could not {action} MVGL files:\n{e}")
            self.log(f"ERROR during file {action}: {e}")

        shutil.rmtree(PACKING_TEMP_DIR)


if __name__ == "__main__":
    if not os.path.exists(TOOLS_EXE_PATH):
        messagebox.showerror("Tool Not Found", f"The helper tool was not found at the expected location:\n{TOOLS_EXE_PATH}\n\nPlease make sure THL-Tools.exe is included when building the executable.")
    else:
        app = ModManagerApp()
        app.mainloop()