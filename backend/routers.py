from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import AuditoriumState
from schemas import Auditorium, AuditoriumStateRead
from database import get_session_local
from utils import run_ansible_playbook, auto_unlock_network
from typing import List
from datetime import datetime, timedelta
import logging

router = APIRouter()

@router.post("/auditoriums/lock")
async def lock_auditorium(auditorium: Auditorium, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("firewall.yml", auditorium_number=auditorium.number, class_number=auditorium.number, state="disabled")

    unlock_time = datetime.utcnow() + timedelta(minutes=auditorium.duration)
    unlock_time_str = unlock_time.strftime("%H:%M:%S") 

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
    return {"message": f"Аудитория номер {auditorium.number} заблокирована до {unlock_time_str}"}

@router.post("/auditoriums/unlock")
async def unlock_auditorium(auditorium: Auditorium, session: AsyncSession = Depends(get_session_local)):
    await run_ansible_playbook("firewall.yml", auditorium_number=auditorium.number, class_number=auditorium.number, state="enabled")

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
    await run_ansible_playbook("firewall.yml", auditorium_number=auditorium.number, class_number=class_number, state=state)
    return {"message": f"Аудитория номер {auditorium.number} настроена с классом {class_number} и состоянием {state}"}

@router.get("/auditoriums/status", response_model=List[AuditoriumStateRead])
async def get_auditoriums_status(session: AsyncSession = Depends(get_session_local)):
    result = await session.execute(select(AuditoriumState))
    auditoriums = result.scalars().all()
    return auditoriums

@router.post("/auditoriums/check_and_restore")
async def check_and_restore_network(session: AsyncSession = Depends(get_session_local)):
    logging.info("Запуск проверки состояния аудиторий через Ansible...")

    output = await run_ansible_playbook("firewall.yml", auditorium_number=None, class_number=None, state=None)

    blocked_auditoriums = []
    for line in output.split("\n"):
        if line.strip().isdigit(): 
            blocked_auditoriums.append(int(line.strip()))

    if not blocked_auditoriums:
        return {"message": "Все аудитории уже с сетью."}

    logging.info(f"Найдено {len(blocked_auditoriums)} заблокированных аудиторий: {blocked_auditoriums}")

    restored_auditoriums = []
    for class_number in blocked_auditoriums:
        await run_ansible_playbook("firewall.yml", auditorium_number=class_number, class_number=class_number, state="disabled")
        restored_auditoriums.append(class_number)

        async with session.begin():
            await session.execute(
                AuditoriumState.__table__.update()
                .where(AuditoriumState.auditorium_number == class_number)
                .values(is_network_on=True, unlock_time=None)
            )
            await session.commit()

    return {
        "message": "Проверка завершена.",
        "restored_auditoriums": restored_auditoriums
    }
