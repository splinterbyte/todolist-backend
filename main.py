from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from fastapi.middleware.cors import CORSMiddleware

class BorderBase(SQLModel):
    pass

class Border(BorderBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tasks: list["Task"] = Relationship(back_populates="owner")

class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str | None = None
    owner_id: int = Field(default=None, foreign_key="border.id")
    owner: Border = Relationship(back_populates="tasks")

class BorderPublic(BorderBase):
    id: int
    tasks: list[Task] = []


class BorderCreate(BorderBase):
    tasks: list[Task] = []

class TaskCreate(SQLModel):
    pass

class TaskUpdate(SQLModel):
    text: str | None = None 


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/borders/", response_model=BorderPublic)
def create_border(border: BorderCreate, session: SessionDep):
    db_border = Border(tasks=[])
    session.add(db_border)
    session.commit()
    session.refresh(db_border)
    return db_border

@app.post("/borders/{border_id}/tasks/", response_model=list[Task])

def add_task_to_border(border_id: int, task: TaskCreate, session: SessionDep):
    db_border = session.get(Border, border_id)
    if not db_border:
        raise HTTPException(status_code=404, detail="Border not found")

    db_task = Task(owner_id=db_border.id)
    session.add(db_task)
    session.commit()
    session.refresh(db_border)
    return db_border.tasks

@app.get("/borders/", response_model=list[BorderPublic])
def read_borders(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    borders = session.exec(select(Border).offset(offset).limit(limit)).all()
    return borders


@app.get("/borders/{border_id}", response_model=BorderPublic)
def read_border(border_id: int, session: SessionDep):
    border = session.get(Border, border_id)
    if not border:
        raise HTTPException(status_code=404, detail="Border not found")
    return border

@app.patch("/borders/{border_id}/tasks/{task_id}", response_model=Task)
def update_task(border_id: int, task_id: int, task_update: TaskUpdate, session: SessionDep):
    db_border = session.get(Border, border_id)
    if not db_border:
        raise HTTPException(status_code=404, detail="Border not found")

    task = session.get(Task, task_id)
    if not task or task.owner_id != db_border.id:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = task_update.model_dump(exclude_unset=True)
    task.sqlmodel_update(task_data)
    
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@app.delete("/borders/{border_id}")
def delete_border(border_id: int, session: SessionDep):
    border = session.get(Border, border_id)
    if not border:
        raise HTTPException(status_code=404, detail="Border not found")
    
    for task in border.tasks:
        session.delete(task)
    
    session.delete(border)
    session.commit()
    return {"ok": True}

@app.delete("/borders/{border_id}/tasks/{task_id}")
def delete_task(border_id: int, task_id: int, session: SessionDep):

    db_border = session.get(Border, border_id)
    if not db_border:
        raise HTTPException(status_code=404, detail="Border not found")
    task = session.get(Task, task_id)
    if not task or task.owner_id != db_border.id:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(task)
    session.commit()
    return {"ok": True}