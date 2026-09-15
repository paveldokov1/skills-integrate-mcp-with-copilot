"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import sqlite3
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

DATABASE_PATH = Path(os.getenv("ACTIVITIES_DB_PATH", current_dir / "activities.db"))

INITIAL_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                UNIQUE(activity_id, student_id),
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            """
        )

        for name, details in INITIAL_ACTIVITIES.items():
            connection.execute(
                """
                INSERT INTO activities (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    schedule = excluded.schedule,
                    max_participants = excluded.max_participants
                """,
                (name, details["description"], details["schedule"], details["max_participants"]),
            )

            activity_id = connection.execute(
                "SELECT id FROM activities WHERE name = ?", (name,)
            ).fetchone()["id"]
            for email in details["participants"]:
                connection.execute(
                    "INSERT INTO students (email) VALUES (?) ON CONFLICT(email) DO NOTHING",
                    (email,),
                )
                student_id = connection.execute(
                    "SELECT id FROM students WHERE email = ?", (email,)
                ).fetchone()["id"]
                connection.execute(
                    """
                    INSERT INTO enrollments (activity_id, student_id)
                    VALUES (?, ?)
                    ON CONFLICT(activity_id, student_id) DO NOTHING
                    """,
                    (activity_id, student_id),
                )


def load_activities():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT activities.name, activities.description, activities.schedule,
                   activities.max_participants, students.email
            FROM activities
            LEFT JOIN enrollments ON enrollments.activity_id = activities.id
            LEFT JOIN students ON students.id = enrollments.student_id
            ORDER BY activities.id, enrollments.id
            """
        ).fetchall()

    result = {}
    for row in rows:
        activity = result.setdefault(
            row["name"],
            {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": [],
            },
        )
        if row["email"] is not None:
            activity["participants"].append(row["email"])
    return result


initialize_database()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return load_activities()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with get_connection() as connection:
        activity = connection.execute(
            "SELECT id FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        connection.execute(
            "INSERT INTO students (email) VALUES (?) ON CONFLICT(email) DO NOTHING",
            (email,),
        )
        student = connection.execute(
            "SELECT id FROM students WHERE email = ?", (email,)
        ).fetchone()
        try:
            connection.execute(
                "INSERT INTO enrollments (activity_id, student_id) VALUES (?, ?)",
                (activity["id"], student["id"]),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Student is already signed up")
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with get_connection() as connection:
        enrollment = connection.execute(
            """
            SELECT enrollments.id
            FROM enrollments
            JOIN activities ON activities.id = enrollments.activity_id
            JOIN students ON students.id = enrollments.student_id
            WHERE activities.name = ? AND students.email = ?
            """,
            (activity_name, email),
        ).fetchone()
        activity_exists = connection.execute(
            "SELECT 1 FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity_exists is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        if enrollment is None:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )
        connection.execute("DELETE FROM enrollments WHERE id = ?", (enrollment["id"],))
    return {"message": f"Unregistered {email} from {activity_name}"}
