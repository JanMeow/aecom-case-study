import os 
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parents[1]/ ".env"
load_dotenv(dotenv_path)



anthropic_api_key= os.environ.get("ANTHROPIC_API_KEY")

