"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Persisted DB-backed activities
from src import db as _db


@app.on_event("startup")
def _startup_db():
    # Initialize DB and seed a few defaults when empty.
    _db.init_db()
    _db.seed_default_activities()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return _db.list_activities()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity (persisted)."""
    success = _db.signup(activity_name, email)
    if not success:
        # Try to determine reason
        with _db.Session(_db.engine) as session:
            a = _db._get_activity_by_name(session, activity_name)
            if not a:
                raise HTTPException(status_code=404, detail="Activity not found")
            regs = session.exec(_db.select(_db.Registration).where(_db.Registration.activity_id == a.id)).all()
            if email in [r.email for r in regs]:
                raise HTTPException(status_code=400, detail="Student is already signed up")
            if a.max_participants and len(regs) >= a.max_participants:
                raise HTTPException(status_code=400, detail="Activity is full")
        raise HTTPException(status_code=400, detail="Could not sign up")
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity (persisted)."""
    success = _db.unregister(activity_name, email)
    if not success:
        with _db.Session(_db.engine) as session:
            a = _db._get_activity_by_name(session, activity_name)
            if not a:
                raise HTTPException(status_code=404, detail="Activity not found")
            statement = _db.select(_db.Registration).where(_db.Registration.activity_id == a.id, _db.Registration.email == email)
            r = session.exec(statement).first()
            if not r:
                raise HTTPException(status_code=400, detail="Student is not signed up for this activity")
        raise HTTPException(status_code=400, detail="Could not unregister user")
    return {"message": f"Unregistered {email} from {activity_name}"}
