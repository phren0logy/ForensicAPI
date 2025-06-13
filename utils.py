from dotenv import load_dotenv

env_loaded = False

def ensure_env_loaded():
    global env_loaded
    if not env_loaded:
        load_dotenv()
        env_loaded = True
