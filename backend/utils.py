import subprocess
import asyncio
import os
import signal
import logging
from datetime import datetime
from fastapi import HTTPException
from models import AuditoriumState
from database import SessionLocal
from sqlalchemy.future import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run_ansible_playbook(playbook_name, *, auditorium_number, class_number=None, state=None):
    playbook_path = f"./playbooks/{playbook_name}"
    
    if not os.path.exists(playbook_path):
        logging.error(f"Playbook {playbook_name} не найден по пути: {playbook_path}")
        raise HTTPException(status_code=404, detail=f"Playbook {playbook_name} not found")

    extra_vars = [f"auditorium_number={auditorium_number}"]
    if class_number is not None:
        extra_vars.append(f"class={class_number}")
    if state is not None:
        extra_vars.append(f"state={state}")
    extra_vars_str = " ".join(extra_vars)

    mode = os.getenv("MODE", "production")
    logging.info(f"Запуск playbook: {playbook_name}, переменные: {extra_vars_str}, режим: {mode}")

    if mode == "production":
        logging.info("Используется реальный Ansible (production)")
        
        process = await asyncio.create_subprocess_exec(
            "ansible-playbook", playbook_path, "-e", extra_vars_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_message = stderr.decode()
            logging.error(f"Ошибка выполнения playbook {playbook_name}: {error_message}")
            raise HTTPException(
                status_code=500,
                detail=f"Ansible playbook failed: {error_message}"
            )
        
        logging.info(f"Playbook {playbook_name} выполнен успешно: {stdout.decode()}")
        return stdout.decode()
    else:
        logging.info("Режим разработки: имитация выполнения playbook'а")
        return {
            "status": "simulated",
            "playbook": playbook_name,
            "variables": {
                "auditorium_number": auditorium_number,
                "class": class_number,
                "state": state
            }
        }

async def shutdown():
    logging.info("Завершение работы сервера...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logging.error(f"Ошибка при завершении задач")

    logging.info("Все фоновые задачи завершены.")


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
