from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

class Auditorium(BaseModel):
    number: int

MODE = os.getenv("MODE", "development")

def run_ansible_playbook(playbook_name, auditorium_number):
    if MODE == "production":
        result = subprocess.run(
            ["ansible-playbook", playbook_name, "-e", f"auditorium_number={auditorium_number}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Ansible playbook failed: {result.stderr}")
        return result.stdout
    else:
        return f"Simulated running playbook {playbook_name} for auditorium {auditorium_number}"

@app.post("/turn_off_network/")
def turn_off_network(auditorium: Auditorium):
    try:
        output = run_ansible_playbook("turn_off_network.yml", auditorium.number)
        return {"message": "Network turned off", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/turn_on_network/")
def turn_on_network(auditorium: Auditorium):
    try:
        output = run_ansible_playbook("turn_on_network.yml", auditorium.number)
        return {"message": "Network turned on", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_network/")
def check_network(auditorium: Auditorium):
    try:
        output = run_ansible_playbook("check_network.yml", auditorium.number)
        return {"message": "Network status checked", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
