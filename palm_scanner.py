import cv2
import sqlite3
import pickle
import numpy as np
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import threading

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Pillow library not found. Please install it using: pip install Pillow")
    Image = None
    ImageTk = None

DB_NAME = "palmpay.db"

STYLE = {
    "background": "#1e1e2f",
    "foreground": "#f8f8f2",
    "button_bg": "#44475a",
    "button_active_bg": "#6272a4",
    "button_fg": "#f8f8f2",
    "accent_cyan": "#8be9fd",
    "accent_green": "#50fa7b",
    "accent_red": "#ff5555",
    "title_font": ("Arial", 32, "bold"),
    "header_font": ("Arial", 16, "bold"),
    "label_font": ("Arial", 14),
    "button_font": ("Arial", 16, "bold"),
}


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        user_type TEXT NOT NULL,
                        wallet_balance REAL NOT NULL,
                        palm_template BLOB NOT NULL,
                        registration_date TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        amount REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    conn.commit()
    conn.close()


def capture_palm(user_type, name, status_callback, close_callback):
    cap = cv2.VideoCapture(0)
    orb = cv2.ORB_create(nfeatures=2000)
    num_frames = 5
    descriptors_list = []
    last_frame = None

    status_callback("Position your palm. Capturing...")

    while len(descriptors_list) < num_frames:
        ret, frame = cap.read()
        if not ret: continue

        last_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp, des = orb.detectAndCompute(gray, None)

        if des is not None and len(kp) > 50:
            descriptors_list.append(des)
            status_callback(f"Captured frame {len(descriptors_list)}/{num_frames}")

        cv2.putText(frame, f"Show your palm... ({len(descriptors_list)}/{num_frames})",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.imshow(f"Register Palm - {user_type}", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            status_callback("Registration cancelled by user.")
            break

    if len(descriptors_list) == num_frames:
        palm_blob = pickle.dumps(descriptors_list)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO users 
                            (name, user_type, wallet_balance, palm_template, registration_date)
                            VALUES (?, ?, ?, ?, ?)''',
                       (name, user_type, 500.0, palm_blob, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        cv2.putText(last_frame, "Registration Complete!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        cv2.imshow(f"Register Palm - {user_type}", last_frame)
        cv2.waitKey(2000)

        status_callback(f"{user_type} '{name}' registered successfully!", STYLE["accent_green"])

    cap.release()
    cv2.destroyAllWindows()
    if close_callback:
        close_callback()


def verify_and_pay(amount, status_callback, close_callback):
    cap = cv2.VideoCapture(0)
    orb = cv2.ORB_create(nfeatures=2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, user_type, palm_template, wallet_balance FROM users")
    users = cursor.fetchall()
    conn.close()

    if not users:
        status_callback("No users are registered in the system.", STYLE["accent_red"])
        cap.release()
        if close_callback: close_callback()
        return

    status_callback("Position palm for verification...")
    identified = None
    verification_frame = None

    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp2, des2 = orb.detectAndCompute(gray, None)

        if des2 is None or len(kp2) < 50:
            cv2.putText(frame, "Present palm clearly...", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow("Verify Palm and Pay", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                status_callback("Verification cancelled.", STYLE["accent_red"])
                break
            continue

        best_score = 0
        best_user = None
        for user_id, name, user_type, palm_blob, balance in users:
            descriptors_list = pickle.loads(palm_blob)
            total_good_matches = 0
            for des1 in descriptors_list:
                matches = bf.match(des1, des2)
                good_matches = [m for m in matches if m.distance < 50]
                total_good_matches += len(good_matches)

            avg_score = total_good_matches / len(descriptors_list) if descriptors_list else 0

            if avg_score > best_score:
                best_score = avg_score
                best_user = (user_id, name, user_type, balance)

        if best_score > 35:
            identified = best_user
            verification_frame = frame.copy()
            break

        cv2.putText(frame, "Verifying... Hold steady.", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow("Verify Palm and Pay", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            status_callback("Verification cancelled.", STYLE["accent_red"])
            break

    if identified:
        user_id, name, user_type, balance = identified
        cv2.putText(verification_frame, f"Verified: {name}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        cv2.imshow("Verify Palm and Pay", verification_frame)
        cv2.waitKey(2000)

    cap.release()
    cv2.destroyAllWindows()

    if identified:
        user_id, name, user_type, balance = identified
        if balance >= amount:
            new_balance = balance - amount
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET wallet_balance=? WHERE user_id=?", (new_balance, user_id))
            cursor.execute("INSERT INTO transactions (user_id, amount, timestamp) VALUES (?, ?, ?)",
                           (user_id, -amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            status_callback(f"Payment success! {name} ({user_type}), new balance: ₹{new_balance:.2f}",
                            STYLE["accent_green"])
        else:
            status_callback(f"Payment failed for {name}: Insufficient funds.", STYLE["accent_red"])
    else:
        status_callback("Verification failed. User not recognized.", STYLE["accent_red"])

    if close_callback:
        close_callback()


def delete_user_by_id(user_id, status_callback):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id=?", (user_id,))
        user_record = cursor.fetchone()

        if not user_record:
            status_callback(f"User ID {user_id} not found.", STYLE["accent_red"])
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete user '{user_record[0]}' (ID: {user_id})?\nThis action cannot be undone."
        )

        if confirm:
            cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            cursor.execute("DELETE FROM transactions WHERE user_id=?", (user_id,))
            conn.commit()
            status_callback(f"Successfully deleted user ID {user_id}.", STYLE["accent_green"])
        else:
            status_callback("Delete operation cancelled.", STYLE["accent_cyan"])
    except Exception as e:
        status_callback(f"An error occurred: {e}", STYLE["accent_red"])
    finally:
        conn.close()


def threaded(func, *args):
    thread = threading.Thread(target=lambda: func(*args), daemon=True)
    thread.start()


def create_fullscreen_window(title):
    win = tk.Toplevel(bg=STYLE["background"])
    win.title(title)
    win.attributes('-fullscreen', True)

    center_frame = tk.Frame(win, bg=STYLE["background"])
    center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    tk.Button(win, text="Back to Main Menu",
              font=("Arial", 12),
              bg=STYLE["button_bg"], fg=STYLE["button_fg"],
              activebackground=STYLE["button_active_bg"],
              bd=0, cursor="hand2",
              command=win.destroy).place(relx=0.02, rely=0.03, anchor=tk.NW)

    return win, center_frame


def open_register_window(user_type):
    win, center_frame = create_fullscreen_window(f"Register New {user_type}")

    tk.Label(center_frame, text=f"Enter {user_type} Name:",
             font=STYLE["header_font"], bg=STYLE["background"], fg=STYLE["foreground"]
             ).pack(pady=20)

    entry_name = tk.Entry(center_frame, width=25, font=STYLE["label_font"])
    entry_name.pack(pady=10)

    status_label = tk.Label(center_frame, text="", font=STYLE["label_font"],
                            bg=STYLE["background"], fg=STYLE["accent_cyan"])
    status_label.pack(pady=20)

    def status_update(msg, color=STYLE["accent_cyan"]):
        status_label.config(text=msg, fg=color)

    def call_capture():
        name = entry_name.get().strip()
        if not name:
            status_update("Name cannot be empty.", STYLE["accent_red"])
            return
        btn_start.config(state="disabled", text="Registering...")
        threaded(capture_palm, user_type, name, status_update, win.destroy)

    btn_start = tk.Button(center_frame, text="Start Registration",
                          font=STYLE["button_font"], bg=STYLE["button_bg"], fg=STYLE["button_fg"],
                          activebackground=STYLE["button_active_bg"], activeforeground=STYLE["button_fg"],
                          bd=0, width=20, height=2, command=call_capture, cursor="hand2")
    btn_start.pack(pady=20)


def choose_user_type_for_registration():
    win, center_frame = create_fullscreen_window("Choose User Type")

    tk.Label(center_frame, text="Select Registration Type",
             font=STYLE["header_font"], bg=STYLE["background"], fg=STYLE["foreground"]
             ).pack(pady=30)

    btn_style = {
        "font": STYLE["button_font"], "bg": STYLE["button_bg"], "fg": STYLE["button_fg"],
        "activebackground": STYLE["button_active_bg"], "bd": 0,
        "width": 20, "height": 3, "cursor": "hand2"
    }

    tk.Button(center_frame, text="Permanent User", **btn_style,
              command=lambda: [win.destroy(), open_register_window("Permanent")]
              ).pack(pady=15)

    tk.Button(center_frame, text="Tourist", **btn_style,
              command=lambda: [win.destroy(), open_register_window("Tourist")]
              ).pack(pady=15)


def open_payment_window():
    win, center_frame = create_fullscreen_window("Make Payment")

    tk.Label(center_frame, text="Enter Amount to Pay (₹):",
             font=STYLE["header_font"], bg=STYLE["background"], fg=STYLE["foreground"]
             ).pack(pady=20)

    entry_amount = tk.Entry(center_frame, width=22, font=STYLE["label_font"])
    entry_amount.pack(pady=10)

    status_label = tk.Label(center_frame, text="", font=STYLE["label_font"],
                            bg=STYLE["background"], fg=STYLE["accent_cyan"])
    status_label.pack(pady=20)

    def status_update(msg, color=STYLE["accent_cyan"]):
        status_label.config(text=msg, fg=color)

    def call_payment():
        try:
            amount = float(entry_amount.get().strip())
            if amount <= 0:
                status_update("Amount must be positive.", STYLE["accent_red"])
                return
        except ValueError:
            status_update("Please enter a valid amount.", STYLE["accent_red"])
            return

        btn_pay.config(state="disabled", text="Processing...")
        threaded(verify_and_pay, amount, status_update, win.destroy)

    btn_pay = tk.Button(center_frame, text="Verify Palm and Pay",
                        font=STYLE["button_font"], bg=STYLE["button_bg"], fg=STYLE["button_fg"],
                        activebackground=STYLE["button_active_bg"], activeforeground=STYLE["button_fg"],
                        bd=0, width=22, height=2, command=call_payment, cursor="hand2")
    btn_pay.pack(pady=20)


def open_view_users_window():
    win, _ = create_fullscreen_window("All Registered Users")

    view_frame = tk.Frame(win, bg=STYLE["background"])
    view_frame.pack(fill='both', expand=True, padx=50, pady=80)

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background=STYLE["background"], foreground=STYLE["foreground"],
                    rowheight=35, fieldbackground=STYLE["background"], bordercolor="#36415a",
                    font=('Arial', 14))
    style.configure("Treeview.Heading", background=STYLE["button_bg"], foreground=STYLE["foreground"],
                    font=('Arial', 16, 'bold'))
    style.map("Treeview", background=[('selected', STYLE["button_active_bg"])])

    cols = ("User ID", "Name", "Type", "Balance ₹", "Registered On")
    tree = ttk.Treeview(view_frame, columns=cols, show='headings', style="Treeview")

    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, anchor=tk.CENTER, width=150)

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, user_type, wallet_balance, registration_date FROM users ORDER BY user_id DESC")
        users = cursor.fetchall()
        for u in users:
            formatted_user = (u[0], u[1], u[2], f"{u[3]:.2f}", u[4])
            tree.insert("", "end", values=formatted_user)
    except Exception as e:
        messagebox.showerror("Database Error", f"Could not fetch user data: {e}")
    finally:
        if conn: conn.close()

    scrollbar = ttk.Scrollbar(view_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')


def open_delete_user_window():
    win, center_frame = create_fullscreen_window("Delete User")

    tk.Label(center_frame, text="Enter User ID to Delete:",
             font=STYLE["header_font"], bg=STYLE["background"], fg=STYLE["foreground"]
             ).pack(pady=20)

    entry_id = tk.Entry(center_frame, width=22, font=STYLE["label_font"])
    entry_id.pack(pady=10)

    status_label = tk.Label(center_frame, text="", font=STYLE["label_font"],
                            bg=STYLE["background"], fg=STYLE["accent_cyan"])
    status_label.pack(pady=20)

    def status_update(msg, color=STYLE["accent_cyan"]):
        status_label.config(text=msg, fg=color)

    def call_delete():
        user_id = entry_id.get().strip()
        if not user_id.isdigit():
            status_update("Please enter a valid numeric User ID.", STYLE["accent_red"])
            return

        delete_user_by_id(int(user_id), status_update)
        entry_id.delete(0, tk.END)

    btn = tk.Button(center_frame, text="Delete User", font=STYLE["button_font"],
                    bg="#c13f48", fg=STYLE["button_fg"], activebackground="#e06c75",
                    bd=0, width=20, height=2, command=call_delete, cursor="hand2")
    btn.pack(pady=20)


def main_gui():
    init_db()
    root = tk.Tk()
    root.title("PalmPay Biometric System")
    root.attributes('-fullscreen', True)
    root.configure(bg=STYLE["background"])

    logo_image = None
    if Image and ImageTk:
        try:
            original_logo = Image.open(r"C:\Users\ASUS\Downloads\logo1-removebg-preview.png")
            h = 250
            w = int(h * (original_logo.width / original_logo.height))
            resized_logo = original_logo.resize((w, h), Image.Resampling.LANCZOS)
            logo_image = ImageTk.PhotoImage(resized_logo)

            logo_label = tk.Label(root, image=logo_image, bg=STYLE["background"])
            logo_label.pack(pady=(40, 0))
            logo_label.image = logo_image

        except FileNotFoundError:
            tk.Label(root, text="[PalmPay Logo Not Found]", font=("Arial", 16),
                     bg=STYLE["background"], fg=STYLE["foreground"]).pack(pady=(40, 10))
        except Exception as e:
            print(f"Error loading logo: {e}")

    tk.Label(root, text="PalmPay Biometric System",
             font=STYLE["title_font"], bg=STYLE["background"], fg=STYLE["foreground"]).pack(pady=(15, 30))

    button_frame = tk.Frame(root, bg=STYLE["background"])
    button_frame.pack()

    btn_style = {
        "font": STYLE["button_font"],
        "bg": STYLE["button_bg"],
        "fg": STYLE["button_fg"],
        "activebackground": STYLE["button_active_bg"],
        "activeforeground": STYLE["button_fg"],
        "bd": 0, "relief": "flat", "height": 3, "width": 25, "cursor": "hand2"
    }

    tk.Button(button_frame, text="Register User", command=choose_user_type_for_registration, **btn_style).grid(row=0,
                                                                                                               column=0,
                                                                                                               padx=15,
                                                                                                               pady=15)
    tk.Button(button_frame, text="Make Payment", command=open_payment_window, **btn_style).grid(row=0, column=1,
                                                                                                padx=15, pady=15)
    tk.Button(button_frame, text="View All Users", command=open_view_users_window, **btn_style).grid(row=1, column=0,
                                                                                                     padx=15, pady=15)
    tk.Button(button_frame, text="Delete User", command=open_delete_user_window, **btn_style).grid(row=1, column=1,
                                                                                                   padx=15, pady=15)

    exit_btn_style = btn_style.copy()
    exit_btn_style["bg"] = "#c13f48"
    exit_btn_style["activebackground"] = "#e06c75"

    tk.Button(button_frame, text="Exit Application", command=root.quit, **exit_btn_style).grid(row=2, column=0,
                                                                                               columnspan=2, padx=15,
                                                                                               pady=40)

    root.mainloop()


if __name__ == "__main__":
    main_gui()