# Palm Scanner System

This project is a **Palm Access System** built using Python, OpenCV, and MediaPipe.  
It allows users and tourists to register their palms and later verify them for authentication purposes.

## 🚀 Features
- Register and verify **Users**
- Register and verify **Tourists**
- View database of registered palms
- Delete user entries
- Uses **SQLite** for database management
- Palm recognition powered by **MediaPipe** and **OpenCV**

## 🛠️ Requirements
Install the dependencies before running the project:

```bash
pip install opencv-python mediapipe sqlite3 numpy
```

## ▶️ How to Run
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/palm-scanner.git
   cd palm-scanner
   ```
2. Run the palm scanner system:
   ```bash
   python palm_scanner.py
   ```

## 📂 Project Structure
```
palm-scanner/
│-- palm_scanner.py   # Main script for palm registration & verification
│-- palm_scanner.db   # SQLite database (auto-created after running)
│-- README.md         # Project documentation
```

## 📸 Demo (Example Menu)
```
--- Palm Access System ---
1. Register User
2. Verify User
3. Register Tourist
4. Verify Tourist
5. View Database
6. Delete User
7. Exit
```

## 🔮 Future Improvements
- Better palm recognition accuracy
- Integration with payment/entry systems
- GUI-based version

---

