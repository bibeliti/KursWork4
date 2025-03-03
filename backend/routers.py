from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import AuditoriumState
from schemas import Auditorium, AuditoriumStateRead
from database import get_session_local
from utils import run_ansible_playbook, auto_unlock_network
from typing import List
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/auditoriums/lock")
async def lock_auditorium(auditorium: Auditorium, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("network_off.yaml", auditorium.number)
    unlock_time = datetime.utcnow() + timedelta(minutes=auditorium.duration)

    async with session.begin():
        result = await session.execute(
            select(AuditoriumState)
            .where(AuditoriumState.auditorium_number == auditorium.number)
            .execution_options(populate_existing=True)
        )
        existing_state = result.scalar_one_or_none()

        if existing_state:
            existing_state.is_network_on = False
            existing_state.unlock_time = unlock_time
        else:
            new_state = AuditoriumState(
                auditorium_number=auditorium.number,
                is_network_on=False,
                unlock_time=unlock_time,
            )
            session.add(new_state)

        await session.commit()

    background_tasks.add_task(auto_unlock_network, auditorium)
    return {"message": f"Аудитория номер {auditorium.number} заблокирована до {unlock_time}"}

@router.post("/auditoriums/unlock")
async def unlock_auditorium(auditorium: Auditorium, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("network_on.yaml", auditorium.number)

    async with session.begin():
        await session.execute(
            AuditoriumState.__table__.update()
            .where(AuditoriumState.auditorium_number == auditorium.number)
            .values(is_network_on=True, unlock_time=None)
        )
        await session.commit()

    return {"message": f"Аудитория номер {auditorium.number} успешно разблокирована"}

@router.post("/auditoriums/configure")
async def configure_auditorium(auditorium: Auditorium, class_number: int, state: str, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("firewall.yml", auditorium.number, class_number, state)
    return {"message": f"Аудитория номер {auditorium.number} настроена с классом {class_number} и состоянием {state}"}

@router.get("/auditoriums/status", response_model=List[AuditoriumStateRead])
async def get_auditoriums_status(session: AsyncSession = Depends(get_session_local)):
    result = await session.execute(select(AuditoriumState))
    auditoriums = result.scalars().all()
    return auditoriums
