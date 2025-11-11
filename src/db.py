from typing import Optional, Dict, Any, List
from pathlib import Path

from sqlmodel import SQLModel, Field, create_engine, Session, select

# Simple SQLite DB for development
DB_FILE = Path(__file__).parent.parent / "activities.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create engine (allow multithread for FastAPI dev server)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    schedule: Optional[str] = None
    max_participants: int = 0


class Registration(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    activity_id: int = Field(foreign_key="activity.id")
    email: str


def init_db() -> None:
    """Create database file and tables if they don't exist."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def _get_activity_by_name(session: Session, name: str) -> Optional[Activity]:
    statement = select(Activity).where(Activity.name == name)
    return session.exec(statement).first()


def list_activities() -> Dict[str, Any]:
    """Return activities in the same shape the previous in-memory API returned."""
    with Session(engine) as session:
        activities = session.exec(select(Activity)).all()
        result: Dict[str, Any] = {}
        for a in activities:
            regs = session.exec(select(Registration).where(Registration.activity_id == a.id)).all()
            result[a.name] = {
                "description": a.description or "",
                "schedule": a.schedule or "",
                "max_participants": a.max_participants,
                "participants": [r.email for r in regs],
            }
        return result


def ensure_activity(name: str, description: str = "", schedule: str = "", max_participants: int = 0) -> Activity:
    with Session(engine) as session:
        a = _get_activity_by_name(session, name)
        if a:
            return a
        a = Activity(name=name, description=description, schedule=schedule, max_participants=max_participants)
        session.add(a)
        session.commit()
        session.refresh(a)
        return a


def signup(activity_name: str, email: str) -> bool:
    with Session(engine) as session:
        a = _get_activity_by_name(session, activity_name)
        if not a:
            return False
        regs = session.exec(select(Registration).where(Registration.activity_id == a.id)).all()
        if email in [r.email for r in regs]:
            # already registered
            return False
        if a.max_participants and len(regs) >= a.max_participants:
            # full
            return False
        r = Registration(activity_id=a.id, email=email)
        session.add(r)
        session.commit()
        return True


def unregister(activity_name: str, email: str) -> bool:
    with Session(engine) as session:
        a = _get_activity_by_name(session, activity_name)
        if not a:
            return False
        statement = select(Registration).where(Registration.activity_id == a.id, Registration.email == email)
        r = session.exec(statement).first()
        if not r:
            return False
        session.delete(r)
        session.commit()
        return True


def seed_default_activities() -> None:
    """Seed DB with a small default set when empty."""
    defaults = [
        ("Chess Club", "Learn strategies and compete in chess tournaments", "Fridays, 3:30 PM - 5:00 PM", 12),
        ("Programming Class", "Learn programming fundamentals and build software projects", "Tuesdays and Thursdays, 3:30 PM - 4:30 PM", 20),
        ("Gym Class", "Physical education and sports activities", "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM", 30),
    ]
    with Session(engine) as session:
        count = session.exec(select(Activity)).all()
        if count:
            return
    for name, desc, sched, maxp in defaults:
        ensure_activity(name, description=desc, schedule=sched, max_participants=maxp)
