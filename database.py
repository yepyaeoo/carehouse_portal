from app import app
from models import db, User, PatientProfile
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            admin = User(
                username      = "admin",
                password_hash = generate_password_hash("1234"),
                role          = "admin"
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin created.")
        else:
            print("Admin already exists. Skipping.")

        dummy_patients = [
            {"username": "user1", "name": "Tanaka Hiroshi",  "age": 72, "weight": 68.5, "height": 168, "bp": "135/85"},
            {"username": "user2", "name": "Yamamoto Keiko",  "age": 68, "weight": 55.2, "height": 155, "bp": "128/80"},
            {"username": "user3", "name": "Sato Fumio",      "age": 75, "weight": 71.0, "height": 170, "bp": "142/90"},
            {"username": "user4", "name": "Nakamura Yuki",   "age": 65, "weight": 60.3, "height": 160, "bp": "118/75"},
            {"username": "user5", "name": "Kobayashi Akira", "age": 80, "weight": 65.8, "height": 163, "bp": "150/95"},
        ]

        for p in dummy_patients:
            if not User.query.filter_by(username=p["username"]).first():
                user = User(
                    username      = p["username"],
                    password_hash = generate_password_hash("abcd"),
                    role          = "patient"
                )
                db.session.add(user)
                db.session.flush()

                profile = PatientProfile(
                    user_id        = user.id,
                    name           = p["name"],
                    age            = p["age"],
                    weight_kg      = p["weight"],
                    height_cm      = p["height"],
                    blood_pressure = p["bp"]
                )
                db.session.add(profile)
                print(f"Created patient: {p['username']} — {p['name']}")
            else:
                print(f"Skipping {p['username']}, already exists.")

        db.session.commit()
        print("\nDatabase ready.")
        print("Admin    → username: admin       | password: 1234")
        print("Patients → username: user1–user5 | password: abcd")

if __name__ == "__main__":
    init_db()