import subprocess
import asyncio
import os
import signal
from datetime import datetime, timedelta
from fastapi import HTTPException
from models import AuditoriumState
from database import SessionLocal
from sqlalchemy.future import select

async def run_ansible_playbook(playbook_name, auditorium_number, class_number=None, state=None):
    playbook_path = f"./playbooks/{playbook_name}"
    extra_vars = f"auditorium_number={auditorium_number}"
    if class_number is not None:
        extra_vars += f" class={class_number}"
    if state is not None:
        extra_vars += f" state={state}"

    if os.getenv("MODE", "development") == "production":
        result = subprocess.run(
            ["ansible-playbook", playbook_path, "-e", extra_vars],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Ansible playbook failed: {result.stderr}")
        return result.stdout
    else:
        return f"Simulated running playbook {playbook_name} for auditorium {auditorium_number}"

async def shutdown():
    print('Завершение работы сервера...')
    await asyncio.sleep(0.1)
    asyncio.get_event_loop().stop()

def signal_handler(sig, frame):
    asyncio.create_task(shutdown())

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def auto_unlock_network(auditorium):
    async with SessionLocal() as session:
        try:
            result = await session.execute(
                select(AuditoriumState)
                .where(AuditoriumState.auditorium_number == auditorium.number)
                .execution_options(populate_existing=True)
            )
            auditorium_state = result.scalar_one_or_none()
            if not auditorium_state:
                raise ValueError(f"Аудитория {auditorium.number} не найдена.")

            current_time = datetime.utcnow()
            if auditorium_state.unlock_time:
                delay = (auditorium_state.unlock_time - current_time).total_seconds()
                if delay > 0:
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        print(f"Задача разблокировки аудитории {auditorium.number} была отменена.")
                        return

            await run_ansible_playbook("network_on.yaml", auditorium.number)
            auditorium_state.is_network_on = True
            auditorium_state.unlock_time = None
            await session.commit()
        except Exception as e:
            print(f"Ошибка разблокировки аудитории {auditorium.number}: {e}")

async def initialize_auditoriums(conn):
    auditoriums = [11, 14, 15, 17, 19, 20, 23, 24, 103, 113, 262]
    async with SessionLocal() as session:
        for number in auditoriums:
            result = await session.execute(
                select(AuditoriumState)
                .where(AuditoriumState.auditorium_number == number)
            )
            auditorium_state = result.scalar_one_or_none()
            if not auditorium_state:
                auditorium_state = AuditoriumState(
                    auditorium_number=number,
                    is_network_on=True,
                    unlock_time=None
                )
                session.add(auditorium_state)
        await session.commit()
