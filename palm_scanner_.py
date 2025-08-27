import cv2
import sqlite3
import pickle
import numpy as np
from datetime import datetime

DB_NAME = "palmpay.db"

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


def capture_palm(user_type, num_frames=5):
    name = input(f"Enter {user_type} name: ").strip()
    cap = cv2.VideoCapture(0)
    orb = cv2.ORB_create()

    print(f"Position your palm. Capturing {num_frames} frames automatically...")

    descriptors_list = []

    while len(descriptors_list) < num_frames:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp, des = orb.detectAndCompute(gray, None)

        # Capture only if enough keypoints detected
        if des is not None and len(kp) > 30:
            descriptors_list.append(des)
            print(f"Captured frame {len(descriptors_list)}/{num_frames}")

        cv2.putText(frame, f"Show your palm clearly... ({len(descriptors_list)}/{num_frames})",
                    (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow(f"Register Palm - {user_type}", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Registration cancelled.")
            cap.release()
            cv2.destroyAllWindows()
            return

    palm_blob = pickle.dumps(descriptors_list)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO users 
                      (name, user_type, wallet_balance, palm_template, registration_date)
                      VALUES (?, ?, ?, ?, ?)''',
                   (name, user_type, 500.0, palm_blob, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    cap.release()
    cv2.destroyAllWindows()
    print(f"{user_type} '{name}' registered successfully with {num_frames} templates!")


def verify_and_pay(user_type):
    amount = float(input("Enter amount to charge: "))
    cap = cv2.VideoCapture(0)
    orb = cv2.ORB_create()
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, palm_template, wallet_balance FROM users WHERE user_type=?", (user_type,))
    users = cursor.fetchall()
    conn.close()

    if not users:
        print(f"No {user_type.lower()}s registered.")
        return

    print("Position your palm for automatic verification...")
    identified = None

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp2, des2 = orb.detectAndCompute(gray, None)
        if des2 is None or len(kp2) < 20:
            cv2.putText(frame, "Show your palm clearly...", (30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow(f"Verify Palm - {user_type}", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Verification cancelled.")
                cap.release()
                cv2.destroyAllWindows()
                return
            continue

        # Multi-frame matching
        best_score = 0
        best_user = None

        for user_id, name, palm_blob, balance in users:
            descriptors_list = pickle.loads(palm_blob)
            total_good_matches = 0
            for des1 in descriptors_list:
                matches = bf.match(des1, des2)
                good_matches = [m for m in matches if m.distance < 60]
                total_good_matches += len(good_matches)
            if total_good_matches > best_score:
                best_score = total_good_matches
                best_user = (user_id, name, balance)

        if best_score > 100:
            identified = best_user
            break

        cv2.putText(frame, "Verifying...", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow(f"Verify Palm - {user_type}", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Verification cancelled.")
            cap.release()
            cv2.destroyAllWindows()
            return

    cap.release()
    cv2.destroyAllWindows()

    user_id, name, balance = identified
    if balance >= amount:
        new_balance = balance - amount
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet_balance=? WHERE user_id=?", (new_balance, user_id))
        cursor.execute("INSERT INTO transactions (user_id, amount, timestamp) VALUES (?, ?, ?)",
                       (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        print(f"Payment successful! New balance for {name}: ₹{new_balance}")
    else:
        print(f"Payment failed for {name}: Insufficient funds.")


def view_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, user_type, wallet_balance, registration_date FROM users")
    users = cursor.fetchall()
    conn.close()

    print("\n--- All Users ---")
    for u in users:
        print(f"ID: {u[0]}, Name: {u[1]}, Type: {u[2]}, Balance: ₹{u[3]}, Registered: {u[4]}")


def delete_user():
    user_id = input("Enter User ID to delete: ").strip()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM transactions WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    print(f"User {user_id} and their transactions deleted successfully!")

def main():
    init_db()
    while True:
        print("\n--- PalmPay Biometric System ---")
        print("1. Register User (Permanent)")
        print("2. Make Payment (Permanent User)")
        print("3. Register Tourist")
        print("4. Make Payment (Tourist)")
        print("5. View All Users")
        print("6. Delete User")
        print("7. Exit")
        choice = input("Enter choice: ").strip()

        if choice == "1":
            capture_palm("Permanent")
        elif choice == "2":
            verify_and_pay("Permanent")
        elif choice == "3":
            capture_palm("Tourist")
        elif choice == "4":
            verify_and_pay("Tourist")
        elif choice == "5":
            view_db()
        elif choice == "6":
            delete_user()
        elif choice == "7":
            print("Exiting PalmPay. Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
